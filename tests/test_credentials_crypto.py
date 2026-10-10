import os
import unittest

# 固定测试密钥，隔离真实 data/.credentials.key
_TEST_KEY = 'MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY='  # b'0123456789abcdef0123456789abcdef'
os.environ['TMALL_CREDENTIALS_KEY'] = _TEST_KEY

from services.credentials_crypto import decrypt_password, encrypt_password  # noqa: E402


class CredentialsCryptoTests(unittest.TestCase):
    def tearDown(self):
        os.environ['TMALL_CREDENTIALS_KEY'] = _TEST_KEY

    def test_roundtrip(self):
        for plain in ('secret-123', '密码含中文', 'a' * 200, ' x y z '):
            stored = encrypt_password(plain)
            self.assertTrue(stored.startswith('fernet:'))
            self.assertNotIn(plain, stored)
            self.assertEqual(decrypt_password(stored), plain)

    def test_empty_password_stays_empty(self):
        self.assertEqual(encrypt_password(''), '')
        self.assertEqual(encrypt_password(None), '')
        self.assertEqual(decrypt_password(''), '')

    def test_legacy_plaintext_passes_through(self):
        self.assertEqual(decrypt_password('legacy-plain-password'), 'legacy-plain-password')

    def test_wrong_key_raises(self):
        stored = encrypt_password('sensitive')
        os.environ['TMALL_CREDENTIALS_KEY'] = 'MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY='.replace('Y', 'Z')
        with self.assertRaises(ValueError):
            decrypt_password(stored)

    def test_garbage_fernet_token_raises(self):
        with self.assertRaises(ValueError):
            decrypt_password('fernet:not-a-valid-token')


if __name__ == '__main__':
    unittest.main()
