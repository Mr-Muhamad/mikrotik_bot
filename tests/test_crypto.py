import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

import utils.crypto as crypto


class TestCryptoRoundtrip(unittest.TestCase):
    def setUp(self):
        self._orig_key = crypto._key
        crypto._key = None
        self.test_key = Fernet.generate_key().decode()

    def tearDown(self):
        crypto._key = self._orig_key

    @patch.dict(os.environ, {}, clear=False)
    def test_encrypt_decrypt_roundtrip(self):
        os.environ["ENCRYPTION_KEY"] = self.test_key
        plaintext = "router-secret-123"
        token = crypto.encrypt_password(plaintext)
        self.assertNotEqual(token, plaintext)
        self.assertEqual(crypto.decrypt_password(token), plaintext)

    @patch.dict(os.environ, {}, clear=False)
    def test_empty_password_returns_empty(self):
        os.environ["ENCRYPTION_KEY"] = self.test_key
        self.assertEqual(crypto.encrypt_password(""), "")
        self.assertEqual(crypto.decrypt_password(""), "")

    @patch.dict(os.environ, {}, clear=False)
    def test_decrypt_invalid_token_returns_empty(self):
        os.environ["ENCRYPTION_KEY"] = self.test_key
        self.assertEqual(crypto.decrypt_password("not-a-valid-token"), "")


if __name__ == "__main__":
    unittest.main()
