import unittest

from protocol.decoder import ProtocolDecoder, calcular_checksum
from protocol.encoder import carga_para_campo, montar_quadro


class ArduinoFrameTest(unittest.TestCase):
    """Quadros no formato exato do montarQuadro() do Arduino transmissor."""

    def setUp(self):
        self.decoder = ProtocolDecoder()

    def test_decodes_a_real_arduino_frame_in_kg(self):
        # 12,34 kg no Arduino -> campo 0123 -> 12,3 kg no Módulo 2
        dados = self.decoder.decodificar("***000012301230000006107###")

        self.assertEqual(
            dados,
            {"bateria": 0, "peso_max": 12.3, "peso_atual": 12.3, "angulo": 0, "tempo": 6, "flag": 1},
        )

    def test_decodes_a_collapse_frame(self):
        dados = self.decoder.decodificar("***000012300150000008109###")

        self.assertEqual(dados["peso_max"], 12.3)
        self.assertEqual(dados["peso_atual"], 1.5)
        self.assertEqual(dados["tempo"], 8)

    def test_encoder_reproduces_the_arduino_frame(self):
        self.assertEqual(montar_quadro(12.34, 12.34, 6, 1), "***000012301230000006107###")
        self.assertEqual(len(montar_quadro(0, 0, 0, 0)), 27)

    def test_encoder_and_decoder_round_trip(self):
        quadro = montar_quadro(45.67, 30.04, 125, 0)
        dados = self.decoder.decodificar(quadro)

        self.assertEqual(dados["peso_max"], 45.7)
        self.assertEqual(dados["peso_atual"], 30.0)
        self.assertEqual(dados["tempo"], 125)
        self.assertEqual(dados["flag"], 0)

    def test_load_field_matches_peso_para_campo(self):
        self.assertEqual(carga_para_campo(-1.0), 0)
        self.assertEqual(carga_para_campo(7.25), 73)
        self.assertEqual(carga_para_campo(5000.0), 9999)

    def test_checksum_uses_the_last_three_digits(self):
        self.assertEqual(calcular_checksum("0000123012300000061"), "07")

    def test_rejects_invalid_frames(self):
        invalidos = [
            "000012301230000006107###",       # sem início
            "***00001230123000000610###",     # tamanho errado
            "***000012301230000006108###",    # checksum errado
            "***0000123012300000061A7###",    # caractere não numérico
        ]
        for quadro in invalidos:
            with self.subTest(quadro=quadro):
                with self.assertRaises(ValueError):
                    self.decoder.decodificar(quadro)


if __name__ == "__main__":
    unittest.main()
