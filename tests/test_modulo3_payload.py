import unittest

from sender.modulo3_payload import build_capture_payload


class Module3PayloadTest(unittest.TestCase):
    def test_converts_kg_and_seconds_to_the_module_3_contract(self):
        payload = build_capture_payload(
            "PONTE001",
            {"peso_atual": 7.25, "tempo": 12},
        )

        self.assertEqual(
            payload,
            {
                "team_code": "PONTE001",
                "elapsed_ms": 12000,
                "load_grams": 7250,
                "event": "sample",
            },
        )

    def test_marks_a_rupture_as_completed(self):
        payload = build_capture_payload(
            "PONTE001",
            {"peso_atual": 8, "tempo": 15},
            event="completed",
        )

        self.assertEqual(payload["event"], "completed")

    def test_requires_a_team_code(self):
        with self.assertRaises(ValueError):
            build_capture_payload("", {"peso_atual": 1, "tempo": 0})
