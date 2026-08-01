import unittest
import ast
from pathlib import Path

from ftp.queue_status import build_failure_report, build_queue_message


class QueueStatusTests(unittest.TestCase):
    def test_queue_handler_is_not_registered_with_sync_lambda(self) -> None:
        main_path = Path(__file__).parents[1] / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))
        message_handlers = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "MessageHandler"
        ]

        self.assertEqual(len(message_handlers), 2)
        for handler in message_handlers:
            self.assertNotIsInstance(handler.args[0], ast.Lambda)

    def test_empty_queue(self) -> None:
        self.assertEqual(
            build_queue_message([]),
            "✅ A fila de uploads está vazia.",
        )

    def test_groups_files_and_formats_progress(self) -> None:
        mb = 1024**2
        items = [
            {
                "name": "filme.mkv",
                "status": "uploading",
                "uploaded_bytes": 300 * mb,
                "size_bytes": 1024 * mb,
            },
            {
                "name": "backup.zip",
                "status": "staging",
                "uploaded_bytes": 0,
                "size_bytes": 500 * mb,
            },
            {
                "name": "falhou.mp4",
                "status": "failed",
                "uploaded_bytes": 64 * mb,
                "size_bytes": 200 * mb,
            },
        ]

        message = build_queue_message(items)

        self.assertIn("📤 Em processamento (1)", message)
        self.assertIn("filme.mkv — 300 MB de 1 GB", message)
        self.assertIn("⏳ Aguardando (1)", message)
        self.assertIn("backup.zip — 0 bytes de 500 MB", message)
        self.assertIn("⚠️ Com falha (1)", message)

    def test_builds_failure_report(self) -> None:
        report = build_failure_report(
            [
                {
                    "node_id": 42,
                    "parent_path": "/filmes",
                    "name": "falhou.mkv",
                    "size_bytes": 100,
                    "uploaded_bytes": 64,
                    "attempts": 3,
                    "modified_at": "2026-08-01 16:00:00",
                    "last_error": "erro\ncom quebra",
                }
            ]
        )

        self.assertIn("Total: 1", report)
        self.assertIn("42\t/filmes/falhou.mkv\t100\t64\t3", report)
        self.assertIn("erro com quebra", report)


if __name__ == "__main__":
    unittest.main()
