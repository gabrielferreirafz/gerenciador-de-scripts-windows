"""Compatibilidade de papéis UIA e proteção antes de ler qualquer texto."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from infraestructure.uia import Automacao, CampoTexto, CampoValor, ErroAutomacao


def recurso():
    objeto = MagicMock()
    objeto.__enter__.return_value = objeto
    return objeto


class TestCapturaUIA(unittest.TestCase):
    def preparar(self, propriedades=None, somente_leitura=False):
        api = Automacao.__new__(Automacao)
        elemento, padrao, documento = recurso(), recurso(), recurso()
        selecoes, selecao = recurso(), recurso()
        elemento.objeto.return_value = padrao
        padrao.objeto.side_effect = lambda indice: {7: documento, 5: selecoes}[indice]
        selecoes.objeto.return_value = selecao

        def quantidade(_indice, _tipos, argumentos):
            argumentos[0]._obj.value = 1

        selecoes.chamar.side_effect = quantidade
        documento.objeto.side_effect = [recurso(), recurso()]
        valores = {30003: 50025, 30008: True, 30009: True, 30010: True, 30019: False}
        valores.update(propriedades or {})
        api.focado = Mock(return_value=elemento)
        api.focado_estavel = Mock(return_value=elemento)
        api.classe_elemento = Mock(return_value="")
        api.propriedade = Mock(side_effect=lambda _elemento, identificador: valores[identificador])
        api.atributo = Mock(return_value=somente_leitura)
        api.texto = Mock(side_effect=["antes alvo depois", "antes ", " depois"])
        return api, elemento

    def test_papel_visual_nao_substitui_capacidade_de_edicao(self):
        for papel in (50004, 50030, 50026, 50025, 50033):
            with self.subTest(papel=papel):
                api, _ = self.preparar({30003: papel})
                campo = api.capturar_campo()
                self.assertEqual(campo.prefixo, "antes ")
                self.assertEqual(campo.sufixo, " depois")
                campo.fechar()

    def test_protecao_e_foco_sao_verificados_antes_de_ler_texto(self):
        for identificador, valor in ((30008, False), (30009, False), (30010, False), (30019, True)):
            with self.subTest(identificador=identificador):
                api, elemento = self.preparar({identificador: valor})
                with self.assertRaises(ErroAutomacao):
                    api.capturar_campo()
                api.texto.assert_not_called()
                elemento.objeto.assert_not_called()

    def test_somente_leitura_e_recusado_mesmo_em_campo_customizado(self):
        api, _ = self.preparar(somente_leitura=True)
        with self.assertRaises(ErroAutomacao):
            api.capturar_campo()
        api.texto.assert_not_called()

    def preparar_valuepattern(self, somente_leitura=False):
        api, elemento = self.preparar()
        valor = recurso()

        def obter(_indice, _tipos, argumentos):
            if argumentos[0] == 10014:
                raise ErroAutomacao("Interface indisponível (método 14).")
            return valor

        def leitura(_indice, _tipos, argumentos):
            argumentos[0]._obj.value = int(somente_leitura)

        elemento.objeto.side_effect = obter
        valor.chamar.side_effect = leitura
        api.texto_valor = Mock(return_value="antes alvo depois")
        return api, valor

    def test_sem_textpattern_captura_valuepattern(self):
        api, _ = self.preparar_valuepattern()
        campo = api.capturar_campo()
        self.assertIsInstance(campo, CampoValor)
        self.assertEqual(campo.original, "antes alvo depois")
        self.assertIsNone(campo.prefixo)
        api.texto.assert_not_called()
        campo.fechar()

    def test_valuepattern_somente_leitura_nao_tem_valor_lido(self):
        api, _ = self.preparar_valuepattern(somente_leitura=True)
        with self.assertRaises(ErroAutomacao):
            api.capturar_campo()
        api.texto_valor.assert_not_called()

    def test_valuepattern_nao_forca_foco_nem_substitui_campo_inteiro(self):
        api, valor = self.preparar_valuepattern()
        campo = api.capturar_campo()
        api.mesmo_elemento = Mock(return_value=True)
        campo.restaurar()
        # A única chamada ao padrão foi a consulta de somente leitura (índice 5).
        self.assertEqual([chamada.args[0] for chamada in valor.chamar.call_args_list], [5])
        campo.elemento.chamar.assert_not_called()
        campo.fechar()

    def test_omnibox_vazia_usa_valor_sem_ler_placeholder_do_textpattern(self):
        api, elemento = self.preparar()
        api.classe_elemento.return_value = "OmniboxViewViews"
        api.texto_valor = Mock(return_value="")
        campo = api.capturar_campo()
        try:
            self.assertIsInstance(campo, CampoValor)
            self.assertEqual(campo.original, "")
            api.texto.assert_not_called()
            self.assertEqual(elemento.objeto.call_args.args[2][0], 10002)
        finally:
            campo.fechar()

    def test_omnibox_com_conteudo_mantem_textpattern_e_selecao(self):
        api, _ = self.preparar()
        api.classe_elemento.return_value = "OmniboxViewViews"
        api.texto_valor = Mock(return_value="antes alvo depois")
        campo = api.capturar_campo()
        try:
            self.assertEqual(campo.prefixo, "antes ")
            self.assertEqual(campo.sufixo, " depois")
        finally:
            campo.fechar()


class TestEstabilizacao(unittest.TestCase):
    def preparar(self, tags, foco=True):
        api = Automacao.__new__(Automacao)
        objetos = [Mock(tag=tag) for tag in tags]
        api.focado = Mock(side_effect=objetos)
        api.mesmo_elemento = Mock(side_effect=lambda a, b: a.tag == b.tag)
        api.propriedade = Mock(return_value=foco)
        return api, objetos

    def test_descarta_campo_anterior_e_aguarda_duas_leituras_do_novo(self):
        api, objetos = self.preparar(["anterior", "novo", "novo"])
        with patch("infraestructure.uia.time.sleep") as aguardar:
            escolhido = api.focado_estavel()
        self.assertIs(escolhido, objetos[2])
        self.assertEqual(aguardar.call_count, 2)
        objetos[0].fechar.assert_called_once()
        objetos[1].fechar.assert_called_once()
        objetos[2].fechar.assert_not_called()

    def test_trocas_continuas_nao_retornam_alvo_arbitrario(self):
        api, objetos = self.preparar(["a", "b", "c", "d", "e"])
        with patch("infraestructure.uia.time.sleep"), self.assertRaisesRegex(ErroAutomacao, "estabilizou"):
            api.focado_estavel()
        for objeto in objetos:
            objeto.fechar.assert_called_once()

    def test_painel_sem_foco_nao_e_aprovado_por_ser_estavel(self):
        api, objetos = self.preparar(["painel"] * 5, foco=False)
        with patch("infraestructure.uia.time.sleep"), self.assertRaises(ErroAutomacao):
            api.focado_estavel()
        for objeto in objetos:
            objeto.fechar.assert_called_once()


class TestFocoEmContainer(unittest.TestCase):
    def preparar(self, quantidade=1, foco_atual=True):
        api = Automacao.__new__(Automacao)
        api.automacao = Mock()
        api.controle_foco = 123
        principal, raiz, condicao, elementos, candidato = [recurso() for _ in range(5)]
        api.automacao.objeto.side_effect = [principal, raiz, condicao]
        raiz.objeto.return_value = elementos
        def total(_indice, _tipos, argumentos):
            argumentos[0]._obj.value = quantidade
        elementos.chamar.side_effect = total
        elementos.objeto.return_value = candidato
        api.propriedade = Mock(side_effect=lambda elemento, _prop: foco_atual if elemento is candidato else False)
        return api, principal, raiz, candidato

    def test_painel_sem_foco_resolve_unico_descendente_focado_no_hwnd(self):
        api, principal, raiz, candidato = self.preparar()
        resultado = api.focado()
        self.assertIs(resultado, candidato)
        principal.fechar.assert_called_once()
        self.assertEqual(api.automacao.objeto.call_args_list[1].args[2], (123,))
        self.assertEqual(raiz.objeto.call_args.args[2][0], 4)  # Só descendentes.

    def test_zero_ou_varios_focados_nao_escolhe_campo(self):
        for quantidade in (0, 2):
            with self.subTest(quantidade=quantidade):
                api, principal, _, candidato = self.preparar(quantidade)
                self.assertIs(api.focado(), principal)
                principal.fechar.assert_not_called()
                self.assertIn("descendente", api.motivo_busca_foco)
                candidato.chamar.assert_not_called()

    def test_descendente_que_perdeu_foco_e_liberado(self):
        api, principal, _, candidato = self.preparar(foco_atual=False)
        self.assertIs(api.focado(), principal)
        candidato.fechar.assert_called_once()
        self.assertIn("deixou de informar", api.motivo_busca_foco)

    def test_foco_global_valido_nao_executa_busca_em_arvore(self):
        api, principal, _, _ = self.preparar()
        api.propriedade.return_value = True
        api.propriedade.side_effect = None
        self.assertIs(api.focado(), principal)
        self.assertEqual(api.automacao.objeto.call_count, 1)
        principal.fechar.assert_not_called()


class TestSelecaoEditorDinamico(unittest.TestCase):
    def preparar(self, textos=None, comparar_erro=False):
        api = Mock()
        elemento, padrao, selecao, selecoes, atual, documento = [recurso() for _ in range(6)]
        api.focado.return_value = recurso()
        api.mesmo_elemento.return_value = True
        padrao.objeto.side_effect = lambda indice: {5: selecoes, 7: documento}[indice]
        def quantidade(_indice, _tipos, argumentos):
            argumentos[0]._obj.value = 1
        selecoes.chamar.side_effect = quantidade
        selecoes.objeto.return_value = atual
        documento.objeto.side_effect = lambda _indice: recurso()
        if comparar_erro:
            selecao.chamar.side_effect = ErroAutomacao("Intervalo expirado")
        api.texto.side_effect = textos or ["antes alvo depois", "antes ", " depois"]
        campo = CampoTexto(api, elemento, padrao, selecao,
                           "antes alvo depois", "antes ", " depois", Mock())
        return campo, api, selecao

    def test_intervalo_diferente_com_mesmo_texto_e_posicao_e_aceito(self):
        campo, _, _ = self.preparar()
        self.assertTrue(campo.esta_focado())

    def test_intervalo_expirado_com_posicao_preservada_e_aceito(self):
        campo, _, selecao = self.preparar(comparar_erro=True)
        self.assertTrue(campo.esta_focado())
        selecao.chamar.assert_not_called()

    def test_cursor_realmente_movido_e_recusado(self):
        campo, _, _ = self.preparar(["antes alvo depois", "antes a", " depois"])
        self.assertFalse(campo.esta_focado())
        self.assertIn("posição textual", campo.motivo_foco)

    def test_conteudo_alterado_e_recusado(self):
        campo, _, _ = self.preparar(["conteúdo alterado"])
        self.assertFalse(campo.esta_focado())
        self.assertIn("conteúdo", campo.motivo_foco)

    def test_outro_editor_e_recusado_sem_comparar_selecao(self):
        campo, api, selecao = self.preparar()
        api.mesmo_elemento.return_value = False
        self.assertFalse(campo.esta_focado())
        selecao.chamar.assert_not_called()
        api.texto.assert_not_called()

    def test_nao_reaplica_intervalo_antigo_se_cursor_ja_esta_correto(self):
        campo, _, selecao = self.preparar(comparar_erro=True)
        campo.restaurar()
        campo.elemento.chamar.assert_called_once_with(3)
        selecao.chamar.assert_not_called()

    def test_nao_seleciona_intervalo_antigo_que_mudou_de_posicao(self):
        campo, _, selecao = self.preparar([
            "antes alvo depois", "antes a", "antes alvo depois", "antes a"])
        with self.assertRaisesRegex(ErroAutomacao, "intervalo original"):
            campo.restaurar()
        selecao.chamar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
