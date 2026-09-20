"""Smoke tests for the local TravelOS journey and its no-provider contract."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from starlette.testclient import TestClient

_RUNTIME_ROOT = Path(__file__).resolve().parent / ".runtime"
_RUNTIME_ROOT.mkdir(exist_ok=True)
_TEMP_DATA = tempfile.TemporaryDirectory(dir=_RUNTIME_ROOT)
os.environ["TRAVELOS_DATA_DIR"] = _TEMP_DATA.name

from main import app  # noqa: E402  (environment must be set before bootstrap)


class TravelOSDemoTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_public_discovery_is_available_without_a_session(self):
        response = self.client.get("/discover?q=granada")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Granada after dark", response.text)
        self.assertIn("Creator-built routes", self.client.get("/discover").text)

    def test_fork_flow_creates_a_signed_in_workspace(self):
        sign_in = self.client.post(
            "/signin", data={"next": "/plans/granada-after-dark"}, follow_redirects=False
        )
        self.assertEqual(sign_in.status_code, 303)
        self.assertEqual(sign_in.headers["location"], "/plans/granada-after-dark?forked=ready")

        fork = self.client.post("/plans/granada-after-dark/fork", follow_redirects=False)
        self.assertEqual(fork.status_code, 303)
        self.assertEqual(fork.headers["location"], "/workspace")

        workspace = self.client.get("/workspace")
        self.assertEqual(workspace.status_code, 200)
        self.assertIn("Trip command center", workspace.text)
        self.assertIn("Booking board", workspace.text)
        self.assertIn("Weather window", workspace.text)
        self.assertIn("Cost ledger", workspace.text)

    def test_creator_pitch_is_local_and_persists(self):
        response = self.client.post(
            "/creators/submit",
            data={
                "creator_name": "Test Guide",
                "email": "guide@example.test",
                "destination": "Lisbon",
                "story_title": "Late tram notes",
                "youtube": "@testguide",
                "instagram": "@testguide",
                "note": "A useful, slow itinerary.",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Pitch received in the local creator queue", response.text)
        self.assertTrue((Path(_TEMP_DATA.name) / "travelos_host.db").exists())
        self.assertTrue((Path(_TEMP_DATA.name) / "travelos-weekend-club_db.db").exists())

    def test_public_pages_make_fixture_scope_clear(self):
        plan = self.client.get("/plans/granada-after-dark")
        self.assertIn("Fixture data", plan.text)
        self.assertIn("No live reservations are made in this demo", plan.text)
        self.assertNotIn("googleapis", plan.text.lower())
        self.assertNotIn("unpkg", plan.text.lower())


if __name__ == "__main__":
    unittest.main()
