"""A false completion result must fail these tests, even if the path exists."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest

from download_helpers import ensure_empty, wait_for_download

BODY = b"complete fixture\n"
DIGEST = hashlib.sha256(BODY).hexdigest()


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "result.bin"

    def wait(self):
        return wait_for_download(self.target, len(BODY), DIGEST,
                                 timeout=0.15, poll=0.01)

    def test_reject_stale_directory(self):
        self.target.write_bytes(BODY)
        with self.assertRaises(FileExistsError):
            ensure_empty(self.root)

    def test_missing_file_times_out(self):
        with self.assertRaises(TimeoutError):
            self.wait()

    def test_truncated_file_is_not_success(self):
        self.target.write_bytes(BODY[:3])
        with self.assertRaises(TimeoutError):
            self.wait()

    def test_wrong_content_is_not_success(self):
        self.target.write_bytes(b"x" * len(BODY))
        with self.assertRaises(ValueError):
            self.wait()

    def test_partial_artifact_blocks_success(self):
        for suffix in (".part", ".crdownload"):
            with self.subTest(suffix=suffix):
                self.target.write_bytes(BODY)
                partial = self.root / ("result.bin" + suffix)
                partial.touch()
                with self.assertRaises(TimeoutError):
                    self.wait()
                partial.unlink()

    def test_delayed_rename_succeeds(self):
        partial = self.root / "result.bin.part"
        def writer():
            partial.write_bytes(BODY[:3])
            time.sleep(0.04)
            partial.write_bytes(BODY)
            partial.rename(self.target)
        thread = Thread(target=writer)
        thread.start()
        try:
            self.assertEqual(self.wait().read_bytes(), BODY)
        finally:
            thread.join()

    def test_create_absolute_directory(self):
        result = ensure_empty(self.root / "nested")
        self.assertTrue(result.is_absolute() and result.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
