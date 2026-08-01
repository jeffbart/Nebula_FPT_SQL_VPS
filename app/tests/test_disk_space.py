from collections import namedtuple
import unittest
from unittest.mock import AsyncMock

from ftp.disk_space import wait_for_disk_space


Usage = namedtuple("Usage", "total used free")


class DiskSpaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_resumes_when_space_is_released(self) -> None:
        free_values = iter((5, 20))
        sleep = AsyncMock()
        clock_values = iter((10.0, 15.0))

        await wait_for_disk_space(
            "staging", 2, 10, 5, 30, "filme.mkv",
            disk_usage=lambda _: Usage(100, 0, next(free_values)),
            sleep=sleep,
            clock=lambda: next(clock_values),
        )

        sleep.assert_awaited_once_with(5)

    async def test_aborts_after_pause_timeout(self) -> None:
        sleep = AsyncMock()
        clock_values = iter((10.0, 41.0))

        with self.assertRaisesRegex(OSError, "tempo máximo"):
            await wait_for_disk_space(
                "staging", 2, 10, 5, 30, "filme.mkv",
                disk_usage=lambda _: Usage(100, 95, 5),
                sleep=sleep,
                clock=lambda: next(clock_values),
            )

        sleep.assert_awaited_once_with(5)

    async def test_does_not_pause_when_reserve_is_available(self) -> None:
        sleep = AsyncMock()

        await wait_for_disk_space(
            "staging", 2, 10, 5, 30, "filme.mkv",
            disk_usage=lambda _: Usage(100, 80, 20),
            sleep=sleep,
        )

        sleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
