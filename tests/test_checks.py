import datetime
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from checks import missing_log_channel_permissions, is_recent_audit_entry
from log_types import LOG_TYPES


class MissingLogChannelPermissionsTest(unittest.TestCase):
    def perms(self, **overrides):
        values = {"view_channel": True, "send_messages": True, "embed_links": True}
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_all_permissions_present(self):
        self.assertEqual(missing_log_channel_permissions(self.perms()), [])

    def test_missing_embed_links_is_reported(self):
        self.assertEqual(missing_log_channel_permissions(self.perms(embed_links=False)), ["Embed Links"])

    def test_everything_missing_keeps_order(self):
        perms = self.perms(view_channel=False, send_messages=False, embed_links=False)
        self.assertEqual(missing_log_channel_permissions(perms), ["View Channel", "Send Messages", "Embed Links"])


class RecentAuditEntryTest(unittest.TestCase):
    now = datetime.datetime(2026, 11, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)

    def ago(self, seconds):
        return self.now - datetime.timedelta(seconds=seconds)

    def test_fresh_entry_counts(self):
        self.assertTrue(is_recent_audit_entry(self.ago(2), self.now))

    def test_old_entry_is_ignored(self):
        # The bug: an hour old deletion by a mod was shown as "Deleted By"
        self.assertFalse(is_recent_audit_entry(self.ago(3600), self.now))

    def test_slight_clock_skew_is_tolerated(self):
        self.assertTrue(is_recent_audit_entry(self.ago(-2), self.now))


class LogTypesTest(unittest.TestCase):
    def test_every_log_type_is_a_database_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_PATH"] = os.path.join(tmp, "test.db")
            import config
            import importlib
            importlib.reload(config)
            from db_handler import DatabaseHandler
            handler = DatabaseHandler()
            handler.init_new_guild(1, "test")
            settings = handler.get_log_settings(1)
            for key in LOG_TYPES:
                self.assertIn(key, settings)

    def test_choices_fit_discord_limits(self):
        self.assertLessEqual(len(LOG_TYPES), 25)
        for label in LOG_TYPES.values():
            self.assertLessEqual(len(label), 100)


if __name__ == "__main__":
    unittest.main()
