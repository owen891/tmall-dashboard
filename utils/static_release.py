"""Content-addressed frontend releases; publication never mutates a served tree.

Publish from a complete staging source, not a directory being deployed piecemeal.
Old releases are deliberately not pruned: open tabs can request them later.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import time
import os
from uuid import uuid4


class ReleaseUnavailable(ValueError):
    """A requested release is unavailable; do not fall back to newer assets."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ReleaseUnavailable('invalid release version')
    return value


def _safe_file(root, relative):
    parts = PurePosixPath(relative).parts
    if not parts or '\\' in relative or ':' in relative or any(p in ('..', '.') for p in parts) or relative.startswith('/'):
        raise ReleaseUnavailable('invalid resource path')
    path = Path(root)
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ReleaseUnavailable('symlink resources are not supported')
    if not path.is_file():
        raise ReleaseUnavailable('resource no longer available')
    return path


def _source_files(source):
    files = {}
    source = Path(source)
    for directory in ('assets', 'pages'):
        base = source / directory
        if not base.is_dir() or base.is_symlink():
            raise ReleaseUnavailable('frontend source requires assets and pages directories')
        for path in sorted(base.rglob('*')):
            if path.is_symlink():
                raise ReleaseUnavailable('symlink source is not supported')
            if path.is_file():
                files[path.relative_to(source).as_posix()] = path.read_bytes()
    if not files:
        raise ReleaseUnavailable('empty frontend source')
    return files


def _manifest(store, version):
    version = _version(version)
    root = Path(store) / 'releases' / version
    if root.is_symlink() or root.parent.is_symlink():
        raise ReleaseUnavailable('invalid release directory')
    try:
        manifest = json.loads(_safe_file(root, 'manifest.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('schema_version') != 1 or _digest(_canonical(manifest)) != version:
            raise ReleaseUnavailable('release manifest mismatch')
        files = manifest['files']
        if not isinstance(files, dict) or not files:
            raise ReleaseUnavailable('empty release manifest')
        return root, files
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ReleaseUnavailable('release manifest unavailable') from exc


def read_release_file(store, version, relative):
    root, files = _manifest(store, version)
    try:
        expected = files[relative]
        data = _safe_file(root, relative).read_bytes()
        if _digest(data) != expected:
            raise ReleaseUnavailable('resource content mismatch')
        return data
    except (OSError, KeyError) as exc:
        raise ReleaseUnavailable('resource unavailable; update the whole page') from exc


def validate_release(store, version):
    root, files = _manifest(store, version)
    for relative, expected in files.items():
        if _digest(_safe_file(root, relative).read_bytes()) != expected:
            raise ReleaseUnavailable('release content mismatch')
    return version


def build_release(source, store):
    """Prepare an immutable release without changing the active pointer."""
    source_files = _source_files(source)
    manifest = {'schema_version': 1, 'files': {k: _digest(v) for k, v in source_files.items()}}
    version = _digest(_canonical(manifest))
    releases = Path(store) / 'releases'
    releases.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.building-', dir=releases))
    try:
        for relative, data in source_files.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (stage / 'manifest.json').write_bytes(_canonical(manifest))
        # Detect a source edit during this build, before publishing any pointer.
        if {k: _digest(v) for k, v in _source_files(source).items()} != manifest['files']:
            raise ReleaseUnavailable('source changed during build; retry from a complete staging tree')
        destination = releases / version
        if destination.exists():
            validate_release(store, version)
        else:
            try:
                stage.rename(destination)
            except OSError:
                # A concurrent builder may have installed the identical release.
                validate_release(store, version)
        validate_release(store, version)
        return version
    finally:
        if stage.exists():
            shutil.rmtree(stage)


@contextmanager
def _publication_lock(store):
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    lock = store / '.publish.lock'
    deadline = time.monotonic() + 5
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ReleaseUnavailable('publication locked; inspect interrupted publisher before retrying')
            time.sleep(.05)
    try:
        yield
    finally:
        lock.unlink()


def _activate(store, version):
    validate_release(store, version)
    pointer = Path(store) / ('.active-' + uuid4().hex)
    try:
        with pointer.open('xb') as handle:
            handle.write(_canonical({'schema_version': 1, 'version': version}))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pointer, Path(store) / 'active.json')
    finally:
        pointer.unlink(missing_ok=True)
    return version


def activate_release(store, version):
    """Activate a retained release (also the rollback operation)."""
    with _publication_lock(store):
        return _activate(store, version)


def publish_release(source, store):
    version = build_release(source, store)
    return activate_release(store, version)


def read_current(store):
    try:
        record = json.loads((Path(store) / 'active.json').read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('schema_version') != 1:
            raise ReleaseUnavailable('invalid active manifest')
        version = _version(record['version'])
        _manifest(store, version)
        return version
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ReleaseUnavailable('active frontend release unavailable') from exc


def ensure_initial_release(source, store):
    if (Path(store) / 'active.json').exists():
        return read_current(store)
    with _publication_lock(store):
        if (Path(store) / 'active.json').exists():
            return read_current(store)
        return _activate(store, build_release(source, store))


# Installs before any external resource. A missing shell must still explain how
# to recover; never silently combine old HTML with a current script fallback.
UPDATE_GUARD = """<script data-tmall-release-guard>
window.TmallAssetUpdateRequired=function(){
 if(document.getElementById('tmall-update-required'))return;
 var n=document.createElement('div');n.id='tmall-update-required';n.setAttribute('role','alert');
 n.textContent='页面资源版本已不可用，请刷新整个页面。';
 var b=document.createElement('button');b.type='button';b.textContent='刷新页面';
 b.onclick=function(){window.location.reload();};n.appendChild(b);
 (document.body||document.documentElement).appendChild(n);
};
window.addEventListener('error',function(e){var u=e.target&&(e.target.src||e.target.href);
 if(u&&u.indexOf('/assets/releases/')!==-1)window.TmallAssetUpdateRequired();},true);
</script>"""


def render_release_page(store, version, path):
    content = read_release_file(store, version, 'pages/' + path).decode('utf-8')
    def asset(match):
        relative = match.group(3).split('?', 1)[0].split('#', 1)[0]
        return match.group(1) + match.group(2) + '/assets/releases/' + version + '/' + relative + match.group(2)
    content = re.sub(r'''(\b(?:src|href)\s*=\s*)(["'])(?:\.\./|/|\./)?assets/([^"']+)\2''', asset, content)
    marker = '<meta name="tmall-release" content="' + version + '">' + UPDATE_GUARD
    return re.sub(r'(<head\b[^>]*>)', lambda m: m.group(1) + marker, content, count=1, flags=re.I)
