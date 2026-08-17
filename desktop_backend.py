import argparse
import ctypes
import json
import logging
import os
import threading
import time

from desktop_runtime import (
    DesktopPaths,
    desktop_data_paths,
    desktop_environment,
    ensure_desktop_directories,
)


def _desktop_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError('端口必须是整数') from error
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError('端口必须在 1024 到 65535 之间')
    return port


def _positive_pid(value):
    try:
        pid = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError('父进程 PID 必须是整数') from error
    if pid <= 0:
        raise argparse.ArgumentTypeError('父进程 PID 必须大于 0')
    return pid


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='天猫数据仪表盘桌面后端')
    parser.set_defaults(host='127.0.0.1')
    parser.add_argument('--port', type=_desktop_port, required=True)
    parser.add_argument('--parent-pid', type=_positive_pid, required=True)
    return parser.parse_args(argv)


def build_app_config(paths: DesktopPaths):
    environment = desktop_environment(paths)
    scan_roots = [root for root in environment['IMPORT_SCAN_ALLOWED_ROOTS'].split(os.pathsep) if root]
    return {
        'TESTING': False,
        'DATABASE_PATH': paths.database,
        'SQLALCHEMY_DATABASE_URI': environment['DATABASE_URL'],
        'UPLOAD_FOLDER': paths.uploads,
        'IMPORT_SCAN_ALLOWED_ROOTS': scan_roots,
        'TMALL_DESKTOP_MODE': environment['TMALL_DESKTOP_MODE'],
    }


class _PerRecordFileHandler(logging.Handler):
    """Write desktop logs without retaining a Windows file handle between records."""

    def __init__(self, path):
        super().__init__()
        self.path = path

    def emit(self, record):
        try:
            line = self.format(record)
            with open(self.path, 'a', encoding='utf-8') as stream:
                stream.write(line + os.linesep)
        except Exception:
            self.handleError(record)


def configure_desktop_logging(paths: DesktopPaths):
    log_path = os.path.join(paths.logs, 'backend.log')
    handler = _PerRecordFileHandler(log_path)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s',
    ))
    handler._tmall_desktop_handler = True
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    logging.captureWarnings(True)
    return logging.getLogger('tmall.desktop')


def close_desktop_logging():
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if not getattr(handler, '_tmall_desktop_handler', False):
            continue
        root_logger.removeHandler(handler)
        handler.close()


def _process_exists(pid):
    if os.name == 'nt':
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def monitor_parent(parent_pid, close_server, interval=1.0):
    def watch():
        while _process_exists(parent_pid):
            time.sleep(interval)
        close_server()

    thread = threading.Thread(target=watch, name='desktop-parent-monitor', daemon=True)
    thread.start()
    return thread


def main(argv=None):
    args = parse_args(argv)
    paths = desktop_data_paths()
    ensure_desktop_directories(paths)
    logger = configure_desktop_logging(paths)
    os.environ.update(desktop_environment(paths))

    from app import create_app
    from waitress import create_server

    application = create_app(build_app_config(paths))
    server = create_server(application, host=args.host, port=args.port)
    monitor_parent(args.parent_pid, server.close)
    logger.info('桌面后端已启动 url=http://%s:%s database=%s', args.host, args.port, paths.database)
    print(json.dumps({
        'event': 'starting',
        'url': f'http://{args.host}:{args.port}',
        'database': paths.database,
    }, ensure_ascii=False), flush=True)
    try:
        server.run()
    except KeyboardInterrupt:
        server.close()
    finally:
        close_desktop_logging()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
