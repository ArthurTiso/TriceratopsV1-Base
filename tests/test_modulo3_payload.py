import unittest

from sender.modulo3_payload import build_capture_payload


class Module3PayloadTest(unittest.TestCase):
    def test_converts_kg_and_seconds_to_the_module_3_contract(self):
        payload = build_capture_payload("PONTE001", 12.0, 7.3)

        self.assertEqual(
            payload,
            {
                "team_code": "PONTE001",
                "elapsed_ms": 12000,
                "load_grams": 7300,
                "event": "sample",
            },
        )

    def test_keeps_millisecond_resolution_of_the_elapsed_time(self):
        payload = build_capture_payload("PONTE001", 2.5004, 12.3)

        self.assertEqual(payload["elapsed_ms"], 2500)
        self.assertEqual(payload["load_grams"], 12300)

    def test_never_sends_negative_values(self):
        payload = build_capture_payload("PONTE001", -0.1, -0.2)

        self.assertEqual((payload["elapsed_ms"], payload["load_grams"]), (0, 0))

    def test_accepts_the_module_3_events(self):
        for evento in ("started", "sample", "completed"):
            self.assertEqual(build_capture_payload("PONTE001", 0, 0, evento)["event"], evento)

    def test_rejects_unknown_events(self):
        with self.assertRaises(ValueError):
            build_capture_payload("PONTE001", 0, 0, event="broken")

    def test_requires_a_team_code(self):
        with self.assertRaises(ValueError):
            build_capture_payload("", 0, 1)


if __name__ == "__main__":
    unittest.main()
