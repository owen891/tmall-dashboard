"""One runtime selection contract for API and scheduled collection.

The operator publishes data/runtime.json only after validating that runtime.
This resolver never installs an interpreter, changes permissions or silently
falls back when an explicit deployment setting is invalid.
"""
import json
import os
from pathlib import Path
import sys


class RuntimeConfigurationError(ValueError):
    pass


def _absolute_existing(value, *, directory=False):
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigurationError('RUNTIME_PATH_INVALID: expected an absolute path')
    path = Path(value)
    if not path.is_absolute() or not (path.is_dir() if directory else path.is_file()):
        raise RuntimeConfigurationError('RUNTIME_PATH_INVALID: path must be absolute and exist')
    return path


def resolve_python(root, *, environ=None, fallback=None):
    env = os.environ if environ is None else environ
    if 'TMALL_COLLECT_PYTHON' in env:
        return str(_absolute_existing(env['TMALL_COLLECT_PYTHON']))
    record = Path(root) / 'data' / 'runtime.json'
    if record.exists():
        try:
            data = json.loads(record.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
                raise RuntimeConfigurationError('RUNTIME_SCHEMA_INVALID: expected schema_version=1')
            python = _absolute_existing(data.get('python'))
            runtime_root = _absolute_existing(data.get('runtime_root'), directory=True)
            # Lexical containment matches PowerShell GetFullPath and permits a
            # normal POSIX venv whose bin/python symlinks to its base interpreter.
            if not Path(os.path.abspath(python)).is_relative_to(Path(os.path.abspath(runtime_root))):
                raise RuntimeConfigurationError('RUNTIME_PATH_INVALID: python is outside runtime_root')
            return str(python)
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeConfigurationError(f'RUNTIME_CONFIG_INVALID: {type(exc).__name__}') from exc
    return str(_absolute_existing(fallback if fallback is not None else sys.executable))


def loopback_proxy_env(environ=None):
    """Preserve remote proxies; extend only process-local no_proxy settings."""
    env = dict(os.environ if environ is None else environ)
    hosts = []
    for key in ('NO_PROXY', 'no_proxy'):
        hosts.extend(item.strip() for item in env.get(key, '').split(',') if item.strip())
    for host in ('localhost', '127.0.0.1', '::1'):
        if host not in hosts:
            hosts.append(host)
    env['NO_PROXY'] = env['no_proxy'] = ','.join(dict.fromkeys(hosts))
    return env
