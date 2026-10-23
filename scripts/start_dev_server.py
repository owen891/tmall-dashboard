"""Compatibility entry point for the single loopback dashboard service.

The historical script name is retained for tasks and desktop tooling. The server
is Waitress (not Flask's development server). Bind before creating the app so a
second launch fails without initializing or migrating another database.
"""
import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import socket
import traceback

PROJECT_ROOT = str(Path(os.environ.get('TMALL_PROJECT_ROOT') or Path(__file__).resolve().parents[1]).resolve())
LOG_PATH = str(Path(os.environ.get('TMALL_LOG_DIR') or Path(PROJECT_ROOT) / 'logs') / 'dev-server.log')


def _port(value):
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError('port must be between 1 and 65535')
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Run the loopback dashboard with Waitress')
    parser.add_argument('--port', type=_port, default=5000)
    return parser.parse_args(argv)


def bind_listener(port):
    """Own a real IPv4 socket; Windows SO_REUSEADDR alone allows dual bind."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', port))
        listener.listen(128)
        return listener
    except BaseException:
        listener.close()
        raise


def serve(app_factory, port, log):
    from waitress import create_server
    from waitress.task import ThreadedTaskDispatcher
    application = None

    def dispatch(environ, start_response):
        # No event loop runs until application initialization has completed.
        if application is None:
            raise RuntimeError('application is not initialized')
        return application(environ, start_response)

    # Real bind is the singleton gate: never probe/release/rebind a port.
    listener = bind_listener(port)
    server = None
    dispatcher = ThreadedTaskDispatcher()
    socket_map = {}
    try:
        server = create_server(dispatch, sockets=[listener], map=socket_map,
                               _dispatcher=dispatcher, threads=4,
                               clear_untrusted_proxy_headers=True)
        application = app_factory()
        dispatcher.set_thread_count(4)
        print(json.dumps({
            'event': 'dashboard_ready', 'server': 'waitress',
            'pid': os.getpid(), 'host': '127.0.0.1', 'port': port,
            'python': sys.executable,
            'database_path': str(Path(application.config['DATABASE_PATH']).resolve()),
            'time': datetime.now().astimezone().isoformat(),
        }, ensure_ascii=False), file=log, flush=True)
        server.run()
    finally:
        # Also cover app initialization failures and explicit shutdowns.
        try:
            dispatcher.shutdown()
        finally:
            try:
                try:
                    if server is not None:
                        server.close()
                finally:
                    # Close partial constructor resources and accepted channels,
                    # including when run/shutdown/server.close itself fails.
                    with ExitStack() as cleanup:
                        for channel in list(socket_map.values()):
                            cleanup.callback(channel.close)
            finally:
                listener.close()
    return 0


def main(argv=None):
    args = parse_args(argv)
    os.chdir(PROJECT_ROOT)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    os.environ['TMALL_PORT'] = str(args.port)
    with open(LOG_PATH, 'a', encoding='utf-8', buffering=1) as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                from app import create_app
                return serve(create_app, args.port, log)
            except KeyboardInterrupt:
                return 0
            except Exception:
                traceback.print_exc(file=log)
                return 1


if __name__ == '__main__':
    sys.exit(main())
