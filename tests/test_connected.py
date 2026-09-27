"""The connected frontend must remain opt-in and isolated from demo auth."""
import os
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient
from test_demo import app


class ConnectedEntryTests(unittest.TestCase):
    def test_opt_in_entry_loads_only_connected_assets(self):
        with TestClient(app) as client:
            with patch.dict(os.environ, {"TRAVELOS_PROTOTYPE": "0"}):
                self.assertEqual(client.get('/prototype').status_code, 404)
                self.assertEqual(client.get('/assets/connected-state.mjs').status_code, 404)
            with patch.dict(os.environ, {"TRAVELOS_PROTOTYPE": "1"}):
                page = client.get('/prototype')
                self.assertEqual(page.status_code, 200)
                self.assertIn('connected-shell', page.text)
                self.assertIn('/assets/connected.mjs', page.text)
                self.assertNotIn('/assets/app.js', page.text)
                for name in ['connected.mjs', 'connected-state.mjs', 'connected-public.mjs', 'connected-views.mjs', 'connected.css']:
                    self.assertEqual(client.get('/assets/' + name).status_code, 200)
                self.assertEqual(client.get('/workspace', follow_redirects=False).status_code, 303)
