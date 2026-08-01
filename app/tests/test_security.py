import unittest

from ftp.security import PasswordManager


class PasswordManagerTests(unittest.TestCase):
    def test_bcrypt_round_trip(self) -> None:
        password_hash = PasswordManager.hash_password_bcrypt("TesteForte123!")
        self.assertNotEqual(password_hash, "TesteForte123!")
        self.assertTrue(
            PasswordManager.verify_password_bcrypt(
                "TesteForte123!",
                password_hash,
            )
        )
        self.assertFalse(
            PasswordManager.verify_password_bcrypt(
                "SenhaErrada123!",
                password_hash,
            )
        )

    def test_password_strength(self) -> None:
        self.assertFalse(PasswordManager.validate_password_strength("fraca")[0])
        self.assertTrue(
            PasswordManager.validate_password_strength("TesteForte123!")[0]
        )


if __name__ == "__main__":
    unittest.main()
