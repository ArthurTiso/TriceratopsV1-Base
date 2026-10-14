import unittest

from sender.modulo3_payload import build_capture_payload


class Module3PayloadTest(unittest.TestCase):
    def test_converts_kg_and_seconds_to_the_module_3_contract(self):
        payload = build_capture_payload(
            "PONTE001",
            {"peso_atual": 7.3, "tempo": 12},
        )

        self.assertEqual(
            payload,
            {
                "team_code": "PONTE001",
                "elapsed_ms": 12000,
                "load_grams": 7300,
                "event": "sample",
            },
        )

    def test_decoded_tenths_of_kg_become_exact_grams(self):
        # 0123 no quadro = 12,3 kg; evita 12299 por erro de ponto flutuante
        payload = build_capture_payload("PONTE001", {"peso_atual": 123 / 10, "tempo": 0})

        self.assertEqual(payload["load_grams"], 12300)

    def test_marks_a_rupture_as_completed(self):
        payload = build_capture_payload(
            "PONTE001",
            {"peso_atual": 8, "tempo": 15},
            event="completed",
        )

        self.assertEqual(payload["event"], "completed")

    def test_accepts_the_started_event(self):
        payload = build_capture_payload("PONTE001", {"peso_atual": 0, "tempo": 0}, event="started")

        self.assertEqual(payload["event"], "started")

    def test_rejects_unknown_events(self):
        with self.assertRaises(ValueError):
            build_capture_payload("PONTE001", {"peso_atual": 0, "tempo": 0}, event="broken")

    def test_requires_a_team_code(self):
        with self.assertRaises(ValueError):
            build_capture_payload("", {"peso_atual": 1, "tempo": 0})


if __name__ == "__main__":
    unittest.main()
