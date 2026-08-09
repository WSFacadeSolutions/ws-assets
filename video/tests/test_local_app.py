import copy
import sys
import unittest
from pathlib import Path


VIDEO_DIR = Path(__file__).resolve().parents[1]
if str(VIDEO_DIR) not in sys.path:
    sys.path.insert(0, str(VIDEO_DIR))

import local_app


class LocalMiniPremiereTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        local_app.app.config.update(TESTING=True)
        cls.client = local_app.app.test_client()

    def test_health_and_editor_are_local(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["service"], "ws-film-mini-premiere")
        with self.client.get("/film-editor?project=ecosystem") as editor:
            self.assertEqual(editor.status_code, 200)

    def test_timeline_round_trip_is_byte_stable(self):
        path = VIDEO_DIR / "timeline.json"
        before = path.read_bytes()
        payload = self.client.get("/api/film-timeline?project=ecosystem").get_json()
        saved = self.client.post("/api/film-timeline", json={
            "project": "ecosystem", "timeline": payload["timeline"],
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json(), {"ok": True, "changed": False})
        self.assertEqual(path.read_bytes(), before)

    def test_timeline_validation_refuses_a_gap(self):
        payload = self.client.get("/api/film-timeline?project=ecosystem").get_json()
        timeline = copy.deepcopy(payload["timeline"])
        timeline["film"]["scenes"][1]["start"] += 1
        response = self.client.post("/api/film-timeline", json={
            "project": "ecosystem", "timeline": timeline,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("contíguas", response.get_json()["error"])

    def test_composition_supports_byte_ranges(self):
        with self.client.get("/film-comp/ecosystem/film.html",
                             headers={"Range": "bytes=0-99"}) as response:
            self.assertEqual(response.status_code, 206)
            self.assertEqual(len(response.data), 100)
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")

    def test_unknown_project_is_rejected(self):
        response = self.client.get("/api/film-timeline?project=not-a-project")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
