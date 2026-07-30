class ProtocolDecoder:

    def decodificar(self, pacote: str) -> dict:
        # 1. Validar delimitadores
        if not pacote.startswith("***") or not pacote.endswith("###"):
            raise ValueError("Pacote inválido: delimitadores incorretos")

        # 2. Remover delimitadores
        conteudo = pacote[3:-3]

        # 3. Validar tamanho esperado
        if len(conteudo) != 3 + 4 + 4 + 3 + 4 + 1 + 2:
            raise ValueError("Pacote inválido: tamanho incorreto")

        # 4. Separar partes
        bateria = conteudo[0:3]
        peso_max = conteudo[3:7]
        peso_atual = conteudo[7:11]
        angulo = conteudo[11:14]
        tempo = conteudo[14:18]
        flag = conteudo[18:19]
        checksum_recebido = conteudo[19:21]

        # 5. Validar checksum
        dados_sem_checksum = conteudo[:19]
        checksum_calculado = self._calcular_checksum(dados_sem_checksum)

        if checksum_calculado != checksum_recebido:
            raise ValueError(
                f"Checksum inválido: esperado {checksum_calculado}, recebido {checksum_recebido}"
            )

        # 6. Converter para tipos corretos
        return {
            "bateria": int(bateria),
            "peso_max": int(peso_max),
            "peso_atual": int(peso_atual),
            "angulo": int(angulo),
            "tempo": int(tempo),
            "flag": int(flag)
        }

    def _calcular_checksum(self, dados: str) -> str:
        """
        Soma dos últimos 3 dígitos % 100
        """
        soma = sum(int(d) for d in dados[-3:])
        return f"{soma % 100:02d}"