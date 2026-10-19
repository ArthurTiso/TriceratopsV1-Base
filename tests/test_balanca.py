import unittest

from protocol.balanca import (
    ErroSensor,
    Medida,
    TaraConcluida,
    TaraIniciada,
    TaraProgresso,
    formatar_medida,
    interpretar_linha,
)


class InterpretarLinhaTest(unittest.TestCase):
    """Linhas no formato exato impresso pelo firmware do Módulo 1."""

    def test_measurement_line(self):
        evento = interpretar_linha("AMOSTRA_KG=12.3 | MEDIA_KG=12.1 | PICO_ABS_KG=12.4 | BRUTO=-325112\r\n")

        self.assertEqual(evento, Medida(12.3, 12.1, 12.4, -325112))
        self.assertEqual(evento.carga_kg, 12.1)

    def test_negative_average_becomes_a_positive_load(self):
        evento = interpretar_linha("AMOSTRA_KG=-0.1 | MEDIA_KG=-0.0 | PICO_ABS_KG=0.2 | BRUTO=8423200")

        self.assertEqual(evento.media_kg, -0.0)
        self.assertEqual(evento.carga_kg, 0.0)

    def test_tare_lines(self):
        self.assertEqual(
            interpretar_linha("Tarando: deixe a balanca sem carga (20 amostras)."), TaraIniciada()
        )
        self.assertEqual(interpretar_linha("TARA=7/20 | BRUTO=8423311"), TaraProgresso(7, 20))
        self.assertEqual(interpretar_linha("TARA=0/20"), TaraProgresso(0, 20))
        self.assertEqual(interpretar_linha("Tara concluida. Offset=8423190"), TaraConcluida(8423190))

    def test_sensor_error(self):
        linha = "ERRO: HX711 sem dados ha pelo menos 2 s. Confira DT, SCK, alimentacao e GND."

        self.assertEqual(interpretar_linha(linha), ErroSensor(linha))

    def test_boot_header_is_ignored(self):
        cabecalho = [
            "SPINO - balanca no PC via USB",
            "HX711: DT=46 | SCK=47 | Monitor Serial=115200 baud",
            "Escala de calibracao: -26422.05",
            "MEDIA_KG: media movel das ultimas 10 amostras, mantendo o sinal.",
            "PICO_ABS_KG: maior magnitude da media desde a tara.",
            "Comando: t + Enviar, sem carga, para tarar e zerar o pico.",
            "",
            "lixo \x00\xff",
        ]
        for linha in cabecalho:
            with self.subTest(linha=linha):
                self.assertIsNone(interpretar_linha(linha))

    def test_formatter_matches_the_parser(self):
        linha = formatar_medida(7.25, -3.04, 9.96, 8423190.7)

        self.assertEqual(linha, "AMOSTRA_KG=7.2 | MEDIA_KG=-3.0 | PICO_ABS_KG=10.0 | BRUTO=8423190")
        self.assertEqual(interpretar_linha(linha), Medida(7.2, -3.0, 10.0, 8423190))


if __name__ == "__main__":
    unittest.main()
