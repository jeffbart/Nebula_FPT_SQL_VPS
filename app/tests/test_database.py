from pathlib import Path
import unittest

from ftp.database import Database


class MigrationTests(unittest.TestCase):
    def test_split_batches(self) -> None:
        script = "SELECT 1;\nGO\nSELECT 'go';\n go \nSELECT 3;"
        self.assertEqual(
            Database._split_batches(script),
            ["SELECT 1;", "SELECT 'go';", "SELECT 3;"],
        )

    def test_initial_migration_is_present(self) -> None:
        migration = (
            Path(__file__).parents[1]
            / "ftp"
            / "migrations"
            / "001_initial.sql"
        )
        source = migration.read_text(encoding="utf-8")
        self.assertIn("nebula.file_parts", source)
        self.assertIn("telegram_message_id", source)
        self.assertIn("nebula.operation_history", source)


if __name__ == "__main__":
    unittest.main()

