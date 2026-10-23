"""Owned disposable gate service; deliberately has no production defaults."""
import json
import os
from pathlib import Path
import secrets
import sys
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate_environment(env):
    root = Path(env['TMALL_GATE_ROOT']).resolve(strict=True)
    nonce = env.get('TMALL_GATE_NONCE', '')
    if len(nonce) != 48 or any(c not in '0123456789abcdef' for c in nonce):
        raise ValueError('owned gate nonce required')
    database = Path(env['TMALL_DB_PATH']).resolve()
    if not database.is_relative_to(root) or database == root:
        raise ValueError('gate database must be inside owned temporary root')
    for name in ('TMALL_UPLOAD_FOLDER', 'IMPORT_SCAN_ALLOWED_ROOTS', 'TMALL_ASSET_RELEASE_ROOT'):
        if not Path(env[name]).resolve().is_relative_to(root):
            raise ValueError(f'{name} must be inside owned temporary root')
    return root, nonce, database


def production_server(factory, port, ready_callback):
    """The real Waitress proxy/security stack, bound before creating the app."""
    from scripts.start_dev_server import bind_listener
    from waitress import create_server
    from waitress.task import ThreadedTaskDispatcher
    listener = bind_listener(port)
    dispatcher = ThreadedTaskDispatcher()
    socket_map = {}
    server = None
    application = None
    def dispatch(environ, start_response):
        return application(environ, start_response)
    try:
        server = create_server(dispatch, sockets=[listener], map=socket_map, _dispatcher=dispatcher,
                               trusted_proxy='127.0.0.1', trusted_proxy_headers={'x-forwarded-for'},
                               clear_untrusted_proxy_headers=True)
        application = factory()
        dispatcher.set_thread_count(4)
        ready_callback(application, listener.getsockname()[1])
        server.run()
    finally:
        try:
            dispatcher.shutdown()
        finally:
            try:
                try:
                    if server is not None:
                        server.close()
                finally:
                    with ExitStack() as cleanup:
                        for channel in list(socket_map.values()):
                            cleanup.callback(channel.close)
            finally:
                listener.close()


def serve(env=None, factory=None, server_factory=None):
    env = dict(os.environ if env is None else env)
    root, nonce, database = validate_environment(env)
    ready = Path(env.get('TMALL_GATE_READY', root / 'service-ready.json')).resolve()
    if not ready.is_relative_to(root) or ready == root:
        raise ValueError('readiness path must be inside owned root')
    production = env.get('TMALL_GATE_SERVER_MODE') == 'production'
    def application():
        nonlocal factory
        if factory is None:
            from app import create_app
            factory = create_app
        from scripts.gate_fixture import seed_database, SHOP_ID
        app = factory({'TESTING': not production, 'DATABASE_PATH': str(database), 'SHOP_ID': SHOP_ID,
                       'UPLOAD_FOLDER': env['TMALL_UPLOAD_FOLDER'],
                       'IMPORT_SCAN_ALLOWED_ROOTS': [env['IMPORT_SCAN_ALLOWED_ROOTS']],
                       'ASSET_RELEASE_ROOT': env['TMALL_ASSET_RELEASE_ROOT'],
                       'DASHBOARD_USERNAME': env['DASHBOARD_USERNAME'],
                       'DASHBOARD_PASSWORD': env['DASHBOARD_PASSWORD']})
        if not production:
            seed_database(database)
        return app

    def ready_callback(app, port):
        record = {'pid': os.getpid(), 'port': port, 'nonce': nonce, 'database': str(database)}
        app.add_url_rule('/__gate_owner/' + nonce, 'gate_owner', lambda: record)
        temporary = root / ('ready-' + secrets.token_hex(8))
        temporary.write_text(json.dumps(record), encoding='utf-8')
        os.replace(temporary, ready)

    if production:
        port = int(env.get('TMALL_GATE_PORT', '0'))
        if port != 0 and (port <= 1023 or port > 65535 or port in (5000, 9223)):
            raise ValueError('unsafe production gate port')
        return production_server(application, port, ready_callback)
    from werkzeug.serving import make_server
    # Bind an OS-selected port before any app/database work.
    make = server_factory or make_server
    server = make('127.0.0.1', 0, lambda environ, start: [])
    try:
        if server.server_port <= 1023 or server.server_port in (5000, 9223):
            raise RuntimeError('reserved service port selected')
        app = application()
        server.app = app
        ready_callback(app, server.server_port)
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    serve()
