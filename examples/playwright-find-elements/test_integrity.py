import hashlib
import tempfile
import unittest
from pathlib import Path
from integrity import verify_manifest


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "fixture.html").write_bytes(b"original fixture")
        self.paths = {"fixture.html"}
        self.manifest = {"schema": 1, "sha256": {"fixture.html": hashlib.sha256(b"original fixture").hexdigest()}}

    def test_valid_inventory_is_accepted(self):
        self.assertTrue(verify_manifest(self.root, self.manifest, self.paths))

    def test_changed_artifact_rejected(self):
        (self.root / "fixture.html").write_bytes(b"changed fixture")
        with self.assertRaises(ValueError): verify_manifest(self.root, self.manifest, self.paths)

    def test_missing_artifact_rejected(self):
        (self.root / "fixture.html").unlink()
        with self.assertRaises(ValueError): verify_manifest(self.root, self.manifest, self.paths)

    def test_dropped_manifest_entry_rejected(self):
        self.manifest["sha256"] = {}
        with self.assertRaises(ValueError): verify_manifest(self.root, self.manifest, self.paths)

    def test_unexpected_manifest_entry_rejected(self):
        self.manifest["sha256"]["unknown"] = "0" * 64
        with self.assertRaises(ValueError): verify_manifest(self.root, self.manifest, self.paths)

    def test_path_escape_rejected(self):
        self.manifest["sha256"] = {"../fixture.html": "0" * 64}
        with self.assertRaises(ValueError): verify_manifest(self.root, self.manifest, {"../fixture.html"})

    def test_symlink_artifact_rejected(self):
        (self.root / "fixture.html").rename(self.root / "other.html")
        (self.root / "fixture.html").symlink_to(self.root / "other.html")
        with self.assertRaises(ValueError): verify_manifest(self.root, self.manifest, self.paths)
