"""Frontend-only Compass entry and narrowly allowlisted local catalog/photos."""
import os
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient
from test_demo import app

class CompassEntryTests(unittest.TestCase):
    def test_new_entry_defaults_to_compass_and_serves_only_local_catalog_assets(self):
        with TestClient(app) as client, patch.dict(os.environ, {"TRAVELOS_PROTOTYPE": "1"}):
            page = client.get('/prototype').text
            self.assertIn('data-appearance="compass"', page)
            self.assertIn('/assets/compass.css', page)
            for name in ['compass.css', 'compass-fixtures.mjs', 'compass-model.mjs', 'compass-views.mjs', 'compass-flow.mjs']:
                self.assertEqual(client.get('/assets/' + name).status_code, 200, name)
            catalog = client.get('/assets/compass-demo.json')
            self.assertIn('application/json', catalog.headers['content-type'])
            for photo in catalog.json()['photos']:
                response = client.get('/assets/photos/compass/' + photo['file'])
                self.assertEqual(response.status_code, 200)
                self.assertIn('image/jpeg', response.headers['content-type'])
            self.assertEqual(client.get('/assets/photos/compass/private.json').status_code, 404)
            self.assertEqual(client.get('/assets/photos/compass/manifest.json').status_code, 404)
            self.assertEqual(client.get('/assets/data.py').status_code, 404)
        with TestClient(app) as client, patch.dict(os.environ, {"TRAVELOS_PROTOTYPE": "0"}):
            self.assertEqual(client.get('/assets/compass-demo.json').status_code, 404)
            self.assertEqual(client.get('/assets/photos/compass/la-jolla-beach.jpg').status_code, 404)
