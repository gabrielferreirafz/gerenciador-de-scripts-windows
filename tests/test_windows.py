"""Orquestração da inserção sem enviar teclas a aplicações pessoais."""

import unittest
from unittest.mock import Mock, patch

from infraestructure.windows import InsercaoWindows, normalizar, confirmar_substituicao, confirmar_texto


class TestInsercaoWindows(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.api.janela_valida.return_value = True
        self.api.janela_atual.return_value = 10
        self.api.restaurar.return_value = True
        self.api.modificadores_livres.return_value = True
        self.campo = Mock()
        self.campo.original = "antes alvo depois"
        self.campo.prefixo = "antes "
        self.campo.sufixo = " depois"
        self.campo.ler.return_value = self.campo.original
        self.campo.editavel.return_value = True
        self.campo.esta_focado.return_value = True
        self.insercao = InsercaoWindows(self.api)
        self.insercao.janela = 10
        self.insercao.processo = 20
        self.insercao.campo = self.campo

    def colagem_confirmada(self, texto):
        def colar():
            self.campo.ler.return_value = self.campo.prefixo + texto + self.campo.sufixo
            return True
        self.api.colar.side_effect = colar

    def test_substitui_selecao_e_confirma_texto_exato(self):
        self.colagem_confirmada("Olá!\r\nComo ajudar? 👋")
        self.assertTrue(self.insercao.inserir("Olá!\nComo ajudar? 👋"))
        self.campo.restaurar.assert_called_once()
        self.api.copiar.assert_called_once_with("Olá!\nComo ajudar? 👋")
        self.api.colar.assert_called_once()

    def test_sem_campo_nao_copia_nem_cola(self):
        self.insercao.campo = None
        self.assertFalse(self.insercao.destino_valido())
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.copiar.assert_not_called()
        self.api.colar.assert_not_called()

    def test_janela_fechada_ou_reutilizada_recusada(self):
        self.api.janela_valida.return_value = False
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_somente_leitura_recusado(self):
        self.campo.editavel.return_value = False
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_destino_alterado_desde_abertura_recusado(self):
        self.campo.ler.return_value = "Texto alterado pelo usuário"
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_falha_de_foco_nao_copia_nem_cola(self):
        self.api.restaurar.return_value = False
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.copiar.assert_not_called()
        self.assertIn("reativar a janela", self.insercao.diagnostico_falha())

    def test_foco_em_outro_controle_nao_cola(self):
        self.campo.esta_focado.return_value = False
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_tecla_modificadora_pressionada_nao_cola(self):
        self.api.modificadores_livres.return_value = False
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_clipboard_ocupado_nao_cola(self):
        self.api.copiar.side_effect = OSError("Ocupado")
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_texto_alterado_durante_preparacao_nao_cola(self):
        def copiar(_):
            self.campo.ler.return_value = "Texto alterado durante a preparação"
        self.api.copiar.side_effect = copiar
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_cursor_alterado_durante_preparacao_nao_cola(self):
        self.campo.esta_focado.side_effect = [True, False]
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_not_called()

    def test_envio_parcial_nao_confirma_nem_repete(self):
        self.api.colar.return_value = False
        self.assertFalse(self.insercao.inserir("Texto"))
        self.assertFalse(self.insercao.inserir("Texto"))
        self.api.colar.assert_called_once()

    def test_enviar_teclas_sem_mudar_texto_nao_comprova_sucesso(self):
        self.api.colar.return_value = True
        with patch("infraestructure.windows.time.monotonic", side_effect=[0, 2]):
            self.assertFalse(self.insercao.inserir("Texto"))
        self.assertIn("colagem foi solicitada", self.insercao.diagnostico_falha())
        self.assertIn("acessibilidade", self.insercao.diagnostico_falha())
        self.assertFalse(self.insercao.destino_valido())
        self.api.colar.assert_called_once()

    def test_texto_vazio_nul_e_sem_alteracao_nao_sao_enviados(self):
        for conteudo in ("", "a\0b", "alvo"):
            self.assertFalse(self.insercao.inserir(conteudo))
        self.api.colar.assert_not_called()

    def test_indisponibilidade_da_acessibilidade_mantem_fechado_para_insercao(self):
        self.campo.ler.side_effect = OSError("Provider desconectado")
        self.assertFalse(self.insercao.destino_valido())
        self.api.colar.assert_not_called()

    def test_encerramento_libera_recursos(self):
        self.insercao.automacao = Mock()
        automacao = self.insercao.automacao
        self.insercao.fechar()
        self.campo.fechar.assert_called_once()
        automacao.fechar.assert_called_once()
        self.api.fechar.assert_called_once()
        self.assertIsNone(self.insercao.campo)

    def test_normaliza_somente_quebras_sem_remover_espacos(self):
        self.assertEqual(normalizar("  a\r\nb\rc\n  "), "  a\nb\nc\n  ")

    def test_confirmacao_web_aceita_apenas_variacao_direcional_de_espaco(self):
        self.assertTrue(confirmar_texto("antes texto depois", "antes\u00a0texto\u00a0depois", True))
        self.assertFalse(confirmar_texto("antes texto depois", "antes\u00a0texto\u00a0depois"))
        for esperado, atual in (("a b", "a  b"), ("a b", "ab"),
                                 ("a\u00a0b", "a b"), ("a b", "a\u200bb"),
                                 ("a\nb", "a b"), ("a b", "a x")):
            with self.subTest(esperado=esperado, atual=atual):
                self.assertFalse(confirmar_texto(esperado, atual, True))

    def test_captura_aguarda_provider_do_navegador_ficar_pronto(self):
        automacao = Mock()
        automacao.capturar_campo.side_effect = [OSError("Provider iniciando"), self.campo]
        self.api.processo.return_value = 20
        self.api.capturar_campo_nativo.return_value = None
        with patch("infraestructure.windows.APIWindows", return_value=self.api), \
                patch("infraestructure.windows.Automacao", return_value=automacao), \
                patch("infraestructure.windows.time.sleep"):
            destino = InsercaoWindows.capturar()
        self.assertIs(destino.campo, self.campo)
        self.assertIsNone(destino.erro_captura)
        self.assertEqual(automacao.capturar_campo.call_count, 2)

    def test_espera_de_captura_nao_muda_janela_original(self):
        automacao = Mock()
        automacao.capturar_campo.side_effect = OSError("Provider iniciando")
        self.api.processo.return_value = 20
        self.api.capturar_campo_nativo.return_value = None
        self.api.janela_atual.side_effect = [10, 10, 99]
        with patch("infraestructure.windows.APIWindows", return_value=self.api), \
                patch("infraestructure.windows.Automacao", return_value=automacao), \
                patch("infraestructure.windows.time.sleep"):
            destino = InsercaoWindows.capturar()
        self.assertIsNone(destino.campo)
        self.assertEqual(automacao.capturar_campo.call_count, 1)
        self.assertIn("perdeu o foco", destino.erro_captura)

    def test_captura_tem_limite_quando_provider_nao_fica_pronto(self):
        automacao = Mock()
        automacao.capturar_campo.side_effect = OSError("Sem campo")
        self.api.processo.return_value = 20
        self.api.capturar_campo_nativo.return_value = None
        with patch("infraestructure.windows.APIWindows", return_value=self.api), \
                patch("infraestructure.windows.Automacao", return_value=automacao), \
                patch("infraestructure.windows.time.sleep"):
            destino = InsercaoWindows.capturar()
        self.assertIsNone(destino.campo)
        self.assertEqual(automacao.capturar_campo.call_count, 4)

    def test_falha_nativa_tenta_acessibilidade_do_mesmo_destino(self):
        automacao = Mock()
        automacao.capturar_campo.return_value = self.campo
        self.api.processo.return_value = 20
        self.api.capturar_campo_nativo.side_effect = OSError("Mensagens clássicas não suportadas")
        with patch("infraestructure.windows.APIWindows", return_value=self.api), \
                patch("infraestructure.windows.Automacao", return_value=automacao):
            destino = InsercaoWindows.capturar()
        self.assertIs(destino.campo, self.campo)
        self.assertIsNone(destino.erro_captura)

    def test_diagnostico_de_recusa_nao_expoe_conteudo(self):
        self.campo.ler.return_value = "Um texto privado alterado no destino"
        self.assertFalse(self.insercao.destino_valido())
        diagnostico = self.insercao.diagnostico_falha()
        self.assertIn("mudou", diagnostico)
        self.assertNotIn("privado", diagnostico)
        self.assertNotIn(self.campo.original, diagnostico)

    def test_diagnostico_mostra_motivo_da_captura(self):
        self.insercao.campo = None
        self.insercao.erro_captura = "Provedor não disponibilizou TextPattern"
        self.assertFalse(self.insercao.destino_valido())
        self.assertEqual(self.insercao.diagnostico_falha(), self.insercao.erro_captura)

    def test_valuepattern_confirma_sem_offsets_de_selecao(self):
        self.campo.prefixo = None
        self.campo.sufixo = None

        def colar():
            self.campo.ler.return_value = "antes Olá! depois"
            return True

        self.api.colar.side_effect = colar
        self.assertTrue(self.insercao.inserir("Olá!"))

    def test_valuepattern_nao_confirma_texto_apenas_por_conter_script(self):
        casos = (
            ("abc", "X", "abXc", True),
            ("abc", "X", "aXc", True),
            ("abc", "X", "X", True),
            ("", "Olá!", "Olá!", True),
            ("abc", "X", "Xabc", True),
            ("abc", "X", "abcX", True),
            ("  ab\r\nc  ", "Olá!\n", "  aOlá!\nc  ", True),
            ("aaaa", "aa", "aaaaaa", True),
            ("abc", "X", "texto errado X", False),
            ("abc", "X", "abXconteúdo extra", False),
            ("abc", "X", "abc", False),
            ("abc", "abc", "abc", False),
            ("abc", "", "ab", False),
            ("", "Olá!", "Olá! extra", False),
        )
        for original, inserido, atual, esperado in casos:
            with self.subTest(original=original, inserido=inserido, atual=atual):
                self.assertEqual(confirmar_substituicao(original, inserido, atual), esperado)


if __name__ == "__main__":
    unittest.main()
