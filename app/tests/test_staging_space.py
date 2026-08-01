import os
from pathlib import Path
import tempfile
import unittest

from ftp.staging_space import release_uploaded_range


class StagingSpaceTests(unittest.TestCase):
    def test_rejects_invalid_range(self) -> None:
        self.assertFalse(release_uploaded_range(Path("missing"), -1, 10))
        self.assertFalse(release_uploaded_range(Path("missing"), 0, 0))

    @unittest.skipUnless(os.name == "nt", "Recurso específico do Windows")
    def test_zeroes_released_range_without_changing_size(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "staging.bin"
            prefix = b"A" * (1024 * 1024)
            suffix = b"B" * 4096
            path.write_bytes(prefix + suffix)

            with path.open("rb") as stream:
                if not release_uploaded_range(path, 0, len(prefix)):
                    self.skipTest("Volume temporário não oferece arquivo esparso")

                self.assertEqual(path.stat().st_size, len(prefix) + len(suffix))
                self.assertEqual(stream.read(len(prefix)), b"\0" * len(prefix))
                self.assertEqual(stream.read(), suffix)


if __name__ == "__main__":
    unittest.main()
