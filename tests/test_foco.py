"""Captura de metadados de foco sem inspeção ou inserção de conteúdo."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from application.foco import FocoCapturado
from infraestructure.foco import capturar_foco
import main


class TestFoco(unittest.TestCase):
    def preparar(self):
        api = Mock()
        api.janela_atual.return_value = 10
        api.processo.return_value = 20
        api.titulo_janela.return_value = "Página de teste - Google Chrome"
        api.classe_janela.side_effect = lambda hwnd: "Chrome_WidgetWin_1" if hwnd == 10 else "Chrome_RenderWidgetHostHWND"
        api.foco.return_value = 30
        automacao = Mock()
        elemento = MagicMock()
        elemento.__enter__.return_value = elemento
        automacao.focado.return_value = elemento
        automacao.focado_estavel.return_value = elemento
        automacao.identificador_elemento.return_value = (42, 20, 30)
        automacao.mesmo_elemento.return_value = True
        automacao.propriedade.side_effect = lambda _elemento, prop: {30003: 50004, 30008: True, 30002: 20}[prop]
        automacao.classe_elemento.return_value = "campo-de-teste"
        automacao.area_elemento.return_value = (100.0, 150.0, 300.0, 80.0)
        return api, automacao, elemento

    def test_captura_janela_controle_e_metadados_uia_sem_padroes_de_texto(self):
        api, automacao, elemento = self.preparar()
        foco = capturar_foco(api, lambda: automacao)
        self.assertEqual((foco.janela, foco.controle, foco.processo), (10, 30, 20))
        self.assertEqual(foco.tipo_uia, 50004)
        self.assertTrue(foco.tem_foco_uia)
        self.assertTrue(foco.janela_estavel)
        self.assertTrue(foco.campo_estavel)
        self.assertEqual(foco.area_uia, (100, 150, 300, 80))
        elemento.objeto.assert_not_called()
        automacao.capturar_campo.assert_not_called()
        automacao.texto.assert_not_called()
        automacao.texto_valor.assert_not_called()
        api.copiar.assert_not_called()
        api.colar.assert_not_called()
        api.restaurar.assert_not_called()
        automacao.fechar.assert_called_once()
        api.fechar.assert_called_once()

    def test_sem_uia_preserva_dados_win32(self):
        api, _, _ = self.preparar()
        foco = capturar_foco(api, Mock(side_effect=OSError("UIA indisponível")))
        self.assertEqual(foco.controle, 30)
        self.assertTrue(foco.janela_estavel)
        self.assertIsNone(foco.tipo_uia)
        self.assertEqual(foco.erro_uia, "UIA indisponível")

    def test_troca_de_campo_na_mesma_janela_descarta_identidade(self):
        api, automacao, _ = self.preparar()
        automacao.mesmo_elemento.return_value = False
        foco = capturar_foco(api, lambda: automacao)
        self.assertTrue(foco.janela_estavel)
        self.assertFalse(foco.campo_estavel)
        self.assertIsNone(foco.id_uia)
        self.assertIn("campo mudou", foco.erro_uia)

    def test_painel_sem_foco_mostra_diagnostico_da_busca_sem_ler_texto(self):
        api, automacao, _ = self.preparar()
        automacao.propriedade.side_effect = lambda _elemento, prop: {30003: 50033, 30008: False, 30002: 20}[prop]
        automacao.motivo_busca_foco = "Nenhum descendente com foco explícito."
        foco = capturar_foco(api, lambda: automacao)
        self.assertFalse(foco.tem_foco_uia)
        self.assertEqual(foco.erro_uia, automacao.motivo_busca_foco)
        automacao.texto.assert_not_called()

    def test_sem_controle_win32_ainda_consulta_elemento_uia(self):
        api, automacao, _ = self.preparar()
        api.foco.return_value = None
        foco = capturar_foco(api, lambda: automacao)
        self.assertIsNone(foco.controle)
        self.assertTrue(foco.tem_foco_uia)
        self.assertIn("não informou", foco.erro_win32)

    def test_mudanca_de_janela_descarta_elemento_uia(self):
        api, automacao, _ = self.preparar()
        api.janela_atual.side_effect = [10, 10, 99]
        foco = capturar_foco(api, lambda: automacao)
        self.assertFalse(foco.janela_estavel)
        self.assertIsNone(foco.tipo_uia)
        self.assertIsNone(foco.area_uia)
        self.assertIn("mudou", foco.erro_uia)

    def test_sem_janela_nao_consulta_acessibilidade(self):
        api, _, _ = self.preparar()
        api.janela_atual.return_value = None
        factory = Mock()
        foco = capturar_foco(api, factory)
        self.assertIsNone(foco.janela)
        factory.assert_not_called()
        api.fechar.assert_called_once()


    def test_interface_valida_origem_e_captura_antes_do_banco(self):
        eventos = []
        foco = FocoCapturado(janela=10, processo=20, janela_estavel=True)
        parada = Mock()
        parada.sinalizado.return_value = False
        insercao = Mock(janela=10, processo=20)
        with patch("infraestructure.foco.capturar_foco", side_effect=lambda: eventos.append("foco") or foco), \
                patch("infraestructure.windows.InsercaoWindows.capturar", side_effect=lambda **_: eventos.append("insercao") or insercao), \
                patch("infraestructure.database.BancoDados", side_effect=lambda: eventos.append("banco") or Mock()), \
                patch("infraestructure.repository.RepositorioPastasSQLite"), \
                patch("infraestructure.repository.RepositorioScriptsSQLite"), \
                patch("presentation.interface.abrir_interface") as abrir:
            main.executar_interface(foco, parada)
        self.assertEqual(eventos, ["foco", "insercao", "banco"])
        self.assertEqual(abrir.call_args.kwargs, {"parada": parada})
        insercao.fechar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
