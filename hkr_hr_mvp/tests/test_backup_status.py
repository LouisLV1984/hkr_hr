"""Do not present archive checks as a completed disaster-recovery drill."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from routes.admin import latest_log_status


class BackupStatusTests(unittest.TestCase):
    def test_restore_logs_are_partial_and_backup_success_is_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "03.Output" / "logs"
            logs.mkdir(parents=True)
            with patch("routes.admin.application_root", return_value=root):
                self.assertEqual(latest_log_status("restore_verify_*.log", "Restore verification passed.")["state"], "missing")
                file = logs / "restore_verify_test.log"
                for content in ("Restore verification passed.",
                                "Archive listing and template extraction passed; database and attachment restore NOT tested.",
                                "Database restore and template extraction passed; attachment restore NOT tested."):
                    file.write_text(content, encoding="utf-8")
                    self.assertEqual(latest_log_status("restore_verify_*.log", "Restore verification passed.")["state"], "partial")
                file.write_text("Failed extraction", encoding="utf-8")
                self.assertEqual(latest_log_status("restore_verify_*.log", "Restore verification passed.")["state"], "attention")
                with patch.object(Path, "read_text", side_effect=PermissionError):
                    self.assertEqual(latest_log_status("restore_verify_*.log", "Restore verification passed.")["state"], "unreadable")
                (logs / "backup_short_term_test.log").write_text("Backup completed: synthetic", encoding="utf-8")
                self.assertEqual(latest_log_status("backup_short_term_*.log", "Backup completed:")["state"], "ok")
