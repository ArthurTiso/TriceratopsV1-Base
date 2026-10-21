import unittest

from sender.modulo3_payload import (
    base_sequencia,
    build_capture_payload,
    url_captura,
    url_ensaio_ativo,
)

RUN_ID = "0b6f8a3e-7c1e-4a55-9d3a-2f6c1c9e8b10"


class Module3PayloadTest(unittest.TestCase):
    def test_converts_kg_and_seconds_to_the_module_3_contract(self):
        payload = build_capture_payload(RUN_ID, "M2-01", 7, 12.0, 7.3)

        self.assertEqual(
            payload,
            {
                "test_run_id": RUN_ID,
                "device_code": "M2-01",
                "sequence": 7,
                "elapsed_ms": 12000,
                "load_grams": 7300,
                "event": "sample",
            },
        )

    def test_keeps_millisecond_resolution_of_the_elapsed_time(self):
        payload = build_capture_payload(RUN_ID, "M2-01", 1, 2.5004, 12.3)

        self.assertEqual(payload["elapsed_ms"], 2500)
        self.assertEqual(payload["load_grams"], 12300)

    def test_never_sends_negative_values(self):
        payload = build_capture_payload(RUN_ID, "M2-01", 1, -0.1, -0.2)

        self.assertEqual((payload["elapsed_ms"], payload["load_grams"]), (0, 0))

    def test_rejects_unknown_events_and_missing_run(self):
        with self.assertRaises(ValueError):
            build_capture_payload(RUN_ID, "M2-01", 1, 0, 0, event="broken")
        with self.assertRaises(ValueError):
            build_capture_payload("", "M2-01", 1, 0, 0)

    def test_urls_accept_the_site_root_or_any_api_url(self):
        for url in (
            "https://pontedepalito.ifspcaraguatatuba.edu.br",
            "https://pontedepalito.ifspcaraguatatuba.edu.br/",
            "https://pontedepalito.ifspcaraguatatuba.edu.br/api/v1/sensors/devices/M2-01/active-run",
            "https://pontedepalito.ifspcaraguatatuba.edu.br/api/v1/sensors/capture",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    url_captura(url),
                    "https://pontedepalito.ifspcaraguatatuba.edu.br/api/v1/sensors/capture",
                )
                self.assertEqual(
                    url_ensaio_ativo(url, "M2-01"),
                    "https://pontedepalito.ifspcaraguatatuba.edu.br/api/v1/sensors/devices/M2-01/active-run",
                )

    def test_sequence_base_grows_faster_than_readings(self):
        # Retomar o mesmo ensaio 1 s depois não pode reutilizar sequências
        self.assertGreaterEqual(base_sequencia(1_800_000_001) - base_sequencia(1_800_000_000), 10)
        self.assertGreater(base_sequencia(), 0)


if __name__ == "__main__":
    unittest.main()
