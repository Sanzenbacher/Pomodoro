"""Lokaler Betrieb bleibt wie vorher: kein Login, keine Verschluesselung.

Aufruf: python tests/run.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="pomodoro-test-local-")
os.environ["POMODORO_MODE"] = "local"
os.environ["POMODORO_STORAGE"] = os.path.join(TMP, "storage")

import app as app_module  # noqa: E402
from data import profiles  # noqa: E402


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class LocalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.create_app()

    def test_no_login_and_plain_sqlite(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/pomodoro").status_code, 200)
        self.assertEqual(client.get("/api/pomodoro/state").status_code, 200)
        self.assertEqual(client.post("/api/pomodoro/start", json={"kind": "work"})
                         .get_json()["ok"], True)
        self.assertEqual(client.get("/login").status_code, 404)
        profile_id = profiles.all_profiles()[0]["id"]
        path = profiles.paths(profile_id)["db"]
        rows = sqlite3.connect(path).execute("SELECT COUNT(*) FROM pomo_sessions").fetchone()
        self.assertEqual(rows[0], 1)
        client.post("/api/pomodoro/abort")

    def test_feed_without_token(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/api/pomodoro/activity").status_code, 200)


if __name__ == "__main__":
    unittest.main()
