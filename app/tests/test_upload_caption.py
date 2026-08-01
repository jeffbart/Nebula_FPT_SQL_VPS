import unittest

from ftp.upload_caption import build_upload_caption, format_size


class UploadCaptionTests(unittest.TestCase):
    def test_formats_requested_caption(self) -> None:
        gb = 1024**3
        mb = 1024**2

        caption = build_upload_caption(
            filename="backup.zip",
            part_number=4,
            chunk_size=60 * mb,
            uploaded_offset=240 * mb,
            total_size=int(2.7 * gb),
            configured_chunk_size=80 * mb,
        )

        self.assertEqual(
            caption,
            "backup.zip\n(05 de 35) (300 MB de 2,7 GB)",
        )

    def test_last_part_does_not_exceed_total_size(self) -> None:
        mb = 1024**2

        caption = build_upload_caption(
            filename="video.mp4",
            part_number=1,
            chunk_size=36 * mb,
            uploaded_offset=64 * mb,
            total_size=100 * mb,
            configured_chunk_size=64 * mb,
        )

        self.assertEqual(
            caption,
            "video.mp4\n(02 de 02) (100 MB de 100 MB)",
        )

    def test_formats_small_sizes(self) -> None:
        self.assertEqual(format_size(900), "900 bytes")
        self.assertEqual(format_size(1536), "1,5 KB")


if __name__ == "__main__":
    unittest.main()
