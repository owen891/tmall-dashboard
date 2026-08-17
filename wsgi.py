"""Production WSGI entry point for Waitress or another WSGI server."""

from app import create_app


application = create_app()
