"""Explicit collector browser selection and listener ownership; never launches UI."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


class BrowserConfigurationError(ValueError):
    pass


def resolve_browser(root, *, environ=None):
    env = os.environ if environ is None else environ
    record = Path(root) / 'data/collector-browser.json'
    config = {}
    if record.exists():
        try:
            config = json.loads(record.read_text(encoding='utf-8-sig'))
            if not isinstance(config, dict) or type(config.get('schema_version')) is not int or config['schema_version'] != 1:
                raise ValueError('schema_version must be 1')
            if not {'executable', 'user_data_dir', 'host', 'port', 'reuse_only'} <= config.keys():
                raise ValueError('missing browser fields')
        except (OSError, ValueError, TypeError) as exc:
            raise BrowserConfigurationError('BROWSER_CONFIG_INVALID') from exc
    elif not (env.get('TMALL_CHROME_PATH') and env.get('TMALL_CHROME_PROFILE')):
        raise BrowserConfigurationError('BROWSER_CONFIG_REQUIRED: explicitly select a browser and profile')
    defaults = {'schema_version': 1, 'host': '127.0.0.1', 'port': 9223, 'reuse_only': True}
    defaults.update(config)
    config = defaults
    for key, name in [('executable', 'TMALL_CHROME_PATH'), ('user_data_dir', 'TMALL_CHROME_PROFILE'),
                      ('host', 'TMALL_CDP_HOST'), ('port', 'TMALL_CDP_PORT')]:
        if name in env:
            config[key] = env[name]
    if 'TMALL_CHROME_REUSE_ONLY' in env:
        value = env['TMALL_CHROME_REUSE_ONLY']
        if value not in ('0', '1'):
            raise BrowserConfigurationError('BROWSER_CONFIG_INVALID: reuse override must be 0 or 1')
        config['reuse_only'] = value == '1'
    try:
        if type(config['port']) is bool or not str(config['port']).isdigit():
            raise ValueError('port')
        config['port'] = int(config['port'])
        if not 1 <= config['port'] <= 65535 or config['host'] != '127.0.0.1' or type(config['reuse_only']) is not bool:
            raise ValueError('endpoint')
        for name, directory in [('executable', False), ('user_data_dir', True)]:
            value = config.get(name)
            if not isinstance(value, str) or not Path(value).is_absolute():
                raise ValueError('path')
            if not (Path(value).is_dir() if directory else Path(value).is_file()):
                raise ValueError('path missing')
    except (ValueError, TypeError, OSError) as exc:
        raise BrowserConfigurationError('BROWSER_CONFIG_INVALID: invalid path or endpoint') from exc
    return {name: config[name] for name in ('schema_version', 'executable', 'user_data_dir', 'host', 'port', 'reuse_only')}


def _listener_processes(config):
    if os.name != 'nt':
        raise RuntimeError('BROWSER_IDENTITY_UNSUPPORTED')
    # Only the validated numeric port enters this script. Never echo command lines.
    script = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
              "$ErrorActionPreference='Stop'; $rows=@(); "
              f"$listeners=@(Get-NetTCPConnection -State Listen -LocalPort {config['port']} -ErrorAction SilentlyContinue); "
              "foreach($listener in $listeners) { "
              "$p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $listener.OwningProcess); "
              "$rows += @{address=$listener.LocalAddress;pid=$listener.OwningProcess;"
              "executable=$p.ExecutablePath;command_line=$p.CommandLine} }; "
              "ConvertTo-Json -InputObject @($rows) -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('BROWSER_IDENTITY_QUERY_FAILED')
    return json.loads(result.stdout)


def verify_browser_identity(config, *, process_probe=None):
    """Match listener address AND owner executable/profile, not merely CDP text."""
    try:
        rows = (process_probe or _listener_processes)(config)
        if not isinstance(rows, list):
            raise ValueError('invalid listener inventory')
        if not rows:
            return {'ok': False, 'status': 'blocked', 'code': 'BROWSER_NOT_RUNNING'}
        matches = [row for row in rows if row.get('address') == config['host']]
        if len(matches) != 1:
            return {'ok': False, 'status': 'blocked', 'code': 'BROWSER_LISTENER_MISMATCH'}
        owner = matches[0]
        command = owner.get('command_line') or ''
        profile = re.search(r'(?:^|\s)--user-data-dir(?:=|\s+)(?:"([^"]+)"|([^\s]+))', command)
        actual_profile = (profile.group(1) or profile.group(2)) if profile else ''
        norm = lambda value: os.path.normcase(os.path.abspath(value))
        if not owner.get('executable') or norm(owner['executable']) != norm(config['executable']):
            return {'ok': False, 'status': 'blocked', 'code': 'BROWSER_EXECUTABLE_MISMATCH'}
        if not actual_profile or norm(actual_profile) != norm(config['user_data_dir']):
            return {'ok': False, 'status': 'blocked', 'code': 'BROWSER_PROFILE_MISMATCH'}
        return {'ok': True, 'status': 'ready', 'code': 'BROWSER_IDENTITY_VERIFIED', 'pid': owner['pid']}
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired):
        return {'ok': False, 'status': 'unknown', 'code': 'BROWSER_IDENTITY_UNKNOWN'}


def require_browser_identity(config):
    result = verify_browser_identity(config)
    if not result['ok']:
        raise BrowserConfigurationError(result['code'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--action', choices=['config', 'identity'], default='config')
    args = parser.parse_args(argv)
    try:
        config = resolve_browser(args.root)
        result = {'ok': True, 'config': config} if args.action == 'config' else verify_browser_identity(config)
    except BrowserConfigurationError as exc:
        result = {'ok': False, 'status': 'blocked', 'code': str(exc)}
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['ok'] else 21


if __name__ == '__main__':
    raise SystemExit(main())
