import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import server


class ServerUpdates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        environment = patch.dict(os.environ, {key: "" for key in ("KIRIM_DATA_DIR", "KIRIM_ITEMS_DB", "KIRIM_DECKS_DB")})
        environment.start()
        self.addCleanup(environment.stop)
        (self.root / ".env.example").write_text("DISCORD_TOKEN=\nKIRIM_DATA_DIR=data\n")
        self.git("init")
        self.git("config", "user.name", "Kirim Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / ".gitignore").write_text(".env\ndata/\n")
        (self.root / "VERSION").write_text("old\n")
        self.git("add", ".")
        self.git("commit", "-m", "old")
        self.old = self.git("rev-parse", "HEAD")
        (self.root / "VERSION").write_text("new\n")
        self.git("add", "VERSION")
        self.git("commit", "-m", "new")
        self.new = self.git("rev-parse", "HEAD")
        self.git("reset", "--keep", self.old)
        server.ensure_env(self.root)
        (self.root / ".env").write_text("DISCORD_TOKEN=local-test-value\nKIRIM_DATA_DIR=data\n")
        data = server.settings(self.root)["data"]
        with sqlite3.connect(data / "items.db") as db:
            db.execute("CREATE TABLE sample (value TEXT)")
            db.execute("INSERT INTO sample VALUES ('original')")
        self.python = self.root / "data" / "venvs" / self.new / "bin" / "python"
        self.python.parent.mkdir(parents=True)
        self.python.touch()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, text=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()

    def test_env_is_created_once_and_never_overwritten(self):
        server.ensure_env(self.root)
        self.assertIn("local-test-value", (self.root / ".env").read_text())

    def test_backup_contains_consistent_database_and_env(self):
        emoji_map = self.root / "data/emojis.json"
        emoji_map.write_text('{"application_id":"123","emojis":{}}')
        archive = server.backup(self.root)
        with ZipFile(archive) as zipfile:
            self.assertIn("local-test-value", zipfile.read("config/.env").decode())
            self.assertEqual(zipfile.read("data/emojis.json"), emoji_map.read_bytes())
            target = self.root / "restored.db"
            target.write_bytes(zipfile.read("data/items.db"))
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "original")
        if os.name != "nt":
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)

    def test_rejects_lfs_pointer(self):
        source = self.root / "pointer.db"
        source.write_text("version https://git-lfs.github.com/spec/v1\n")
        with self.assertRaisesRegex(RuntimeError, "Git-LFS"):
            server.import_database(source, self.root)

    def test_refuses_local_program_changes(self):
        (self.root / "VERSION").write_text("user edit")
        with self.assertRaisesRegex(RuntimeError, "Lokale Änderungen"):
            server.apply_update(self.new, self.root)

    def test_successful_update_keeps_env_and_data(self):
        original = (self.root / ".env").read_bytes()
        with patch.object(server, "install_dependencies", return_value=self.python), \
             patch.object(server, "check_bot"), patch.object(server, "service_active", return_value=False):
            server.apply_update(self.new, self.root)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.new)
        self.assertEqual((self.root / ".env").read_bytes(), original)
        self.assertEqual(server.active_python(self.root), self.python)
        with sqlite3.connect(self.root / "data/items.db") as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "original")

    def test_failed_preflight_leaves_previous_installation(self):
        with patch.object(server, "install_dependencies", return_value=self.python), \
             patch.object(server, "check_bot", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                server.apply_update(self.new, self.root)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.old)
        self.assertFalse((self.root / "data/runtime.json").exists())

    def test_service_failure_rolls_back_code_and_runtime(self):
        state = self.root / "data/runtime.json"
        state.write_text('{"python":"old-python"}')
        previous = state.read_bytes()
        original_run = server.run
        starts = []
        def runner(*args, **kwargs):
            if args[0] in {"systemctl", "sudo"}:
                if args[-2] == "start":
                    starts.append(True)
                    if len(starts) == 1:
                        raise subprocess.CalledProcessError(1, ["systemctl", "start"])
                return ""
            return original_run(*args, **kwargs)
        with patch.object(server, "install_dependencies", return_value=self.python), \
             patch.object(server, "check_bot"), patch.object(server, "service_active", return_value=True), \
             patch.object(server, "run", side_effect=runner):
            with self.assertRaises(subprocess.CalledProcessError):
                server.apply_update(self.new, self.root)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.old)
        self.assertEqual(state.read_bytes(), previous)
        self.assertEqual(len(starts), 2)

    def test_runtime_preserves_virtualenv_symlink_path(self):
        if os.name == "nt":
            self.skipTest("Symlink-Prüfung für Unix")
        self.python.unlink()
        self.python.symlink_to("/usr/bin/python3")
        config = server.settings(self.root)
        server.write_runtime(config, self.python)
        self.assertEqual(json.loads((config["data"] / "runtime.json").read_text())["python"], str(self.python))

    def test_maintenance_lock_rejects_second_operation(self):
        with server.maintenance_lock(self.root):
            with self.assertRaisesRegex(RuntimeError, "Wartung"):
                with server.maintenance_lock(self.root):
                    pass
        self.assertFalse((self.root / "data/.maintenance.lock").exists())


if __name__ == "__main__":
    unittest.main()
