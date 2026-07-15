import unittest

from utils.validators import validate_mac, validate_password, validate_positive_int, validate_username


class TestValidateUsername(unittest.TestCase):
    def test_empty_rejected(self):
        valid, msg = validate_username("")
        self.assertFalse(valid)
        self.assertIn("3", msg)

    def test_too_short_rejected(self):
        valid, _ = validate_username("ab")
        self.assertFalse(valid)

    def test_min_length_accepted(self):
        valid, msg = validate_username("abc")
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_allowed_special_chars(self):
        valid, _ = validate_username("user_01-test:node.name")
        self.assertTrue(valid)

    def test_invalid_chars_rejected(self):
        valid, _ = validate_username("user@mail")
        self.assertFalse(valid)

    def test_too_long_rejected(self):
        valid, _ = validate_username("a" * 65)
        self.assertFalse(valid)


class TestValidatePassword(unittest.TestCase):
    def test_empty_rejected(self):
        valid, _ = validate_password("")
        self.assertFalse(valid)

    def test_too_short_rejected(self):
        valid, _ = validate_password("abc")
        self.assertFalse(valid)

    def test_min_length_accepted(self):
        valid, msg = validate_password("abcd")
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_whitespace_rejected(self):
        for bad in ("\n", "\r", "\t"):
            valid, _ = validate_password(f"pass{bad}word")
            self.assertFalse(valid)

    def test_too_long_rejected(self):
        valid, _ = validate_password("x" * 65)
        self.assertFalse(valid)


class TestValidatePositiveInt(unittest.TestCase):
    def test_positive_accepted(self):
        valid, msg = validate_positive_int("42")
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_zero_rejected(self):
        valid, _ = validate_positive_int("0")
        self.assertFalse(valid)

    def test_negative_rejected(self):
        valid, _ = validate_positive_int("-5")
        self.assertFalse(valid)

    def test_non_numeric_rejected(self):
        valid, _ = validate_positive_int("abc")
        self.assertFalse(valid)

    def test_float_string_rejected(self):
        valid, _ = validate_positive_int("3.14")
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()


class TestValidateMac(unittest.TestCase):
    def test_colon_form_accepted(self):
        valid, value = validate_mac("AA:BB:CC:DD:EE:FF")
        self.assertTrue(valid)
        self.assertEqual(value, "AA:BB:CC:DD:EE:FF")

    def test_hyphen_form_normalized(self):
        valid, value = validate_mac("aa-bb-cc-dd-ee-ff")
        self.assertTrue(valid)
        self.assertEqual(value, "AA:BB:CC:DD:EE:FF")

    def test_dot_form_normalized(self):
        valid, value = validate_mac("AABBCC.DDEEFF".replace(".", ""))
        self.assertTrue(valid)

    def test_lowercase_normalized(self):
        valid, value = validate_mac("aa:bb:cc:dd:ee:ff")
        self.assertTrue(valid)
        self.assertEqual(value, "AA:BB:CC:DD:EE:FF")

    def test_empty_rejected(self):
        valid, msg = validate_mac("")
        self.assertFalse(valid)

    def test_too_short_rejected(self):
        valid, _ = validate_mac("AA:BB:CC")
        self.assertFalse(valid)

    def test_non_hex_rejected(self):
        valid, _ = validate_mac("ZZ:BB:CC:DD:EE:FF")
        self.assertFalse(valid)

    def test_11_digits_rejected(self):
        valid, _ = validate_mac("AA:BB:CC:DD:EE:F")
        self.assertFalse(valid)


