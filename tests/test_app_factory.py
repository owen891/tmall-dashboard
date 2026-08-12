import os
import sys
import unittest

from flask import Flask

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class AppFactoryTests(unittest.TestCase):
    def test_create_app_returns_configurable_flask_app(self):
        from app import create_app

        app = create_app({'TESTING': True})

        self.assertIsInstance(app, Flask)
        self.assertTrue(app.testing)

    def test_factory_keeps_dashboard_entrypoint(self):
        from app import create_app

        response = create_app({'TESTING': True}).test_client().get('/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('天猫'.encode('utf-8'), response.data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
