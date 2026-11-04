"""Fluxos da apresentação com widgets Tk e SQLite temporário."""

from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from application.pasta import CasosDeUsoPastas
from application.scripts import CasosDeUsoScripts
from application.inserir_script import ResultadoInsercao
from infraestructure.database import BancoDados
from infraestructure.repository import RepositorioPastasSQLite, RepositorioScriptsSQLite
from presentation.dialogos import Dialogo, EditorPasta, EditorScript
from presentation.interface import Interface


def descendentes(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from descendentes(filho)


def clicar(widget, legenda):
    botao = next(w for w in descendentes(widget)
                 if isinstance(w, ttk.Button) and w.cget("text") == legenda)
    botao.invoke()


class TestInterface(unittest.TestCase):
    def setUp(self):
        temporario = TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        banco = BancoDados(Path(temporario.name) / "teste.sqlite3")
        banco.inicializar()
        repo_pastas = RepositorioPastasSQLite(banco)
        self.pastas = CasosDeUsoPastas(repo_pastas)
        self.scripts = CasosDeUsoScripts(RepositorioScriptsSQLite(banco), repo_pastas)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.erros = []
        self.root.report_callback_exception = lambda *erro: self.erros.append(erro)
        self.addCleanup(lambda: self.assertEqual(self.erros, []))
        self.mostrar = patch.object(Dialogo, "mostrar", lambda _: None)
        self.mostrar.start()
        self.addCleanup(self.mostrar.stop)
        self.ui = Interface(self.root, self.pastas, self.scripts)

    def editor(self, tipo):
        return next(w for w in self.root.winfo_children() if isinstance(w, tipo))

    def test_inicia_somente_na_listagem_de_pastas(self):
        self.assertIsNone(self.ui.pasta_id)
        self.assertEqual(self.ui.botao_novo.cget("text"), "+ Nova pasta")
        rotulos = [w.cget("text") for w in descendentes(self.ui.lista.corpo)
                   if isinstance(w, tk.Label)]
        self.assertEqual(rotulos, ["Geral"])
        self.assertEqual(self.ui.botao_voltar.winfo_manager(), "")
        textos = [w.cget("text") for w in descendentes(self.root)
                  if isinstance(w, (tk.Label, ttk.Button))]
        self.assertNotIn("ALT + C", textos)
        self.assertNotIn("Suas respostas, sempre à mão.", textos)
        self.assertNotIn("Scripts", textos)

    def test_criar_script_pelo_formulario_preserva_texto(self):
        self.ui.editar_script()
        editor = self.editor(EditorScript)
        editor.titulo.insert(0, "Saudação")
        editor.conteudo.insert("1.0", "  Olá!\nComo posso ajudar?  ")
        clicar(editor, "Salvar script")
        salvo = self.scripts.listar()[0]
        self.assertEqual(salvo.conteudo, "  Olá!\nComo posso ajudar?  ")
        self.assertEqual(self.ui.pasta_id, salvo.pasta_id)
        self.assertTrue(self.root.winfo_exists())
        self.assertFalse(editor.winfo_exists())

    def test_editar_script_preserva_pasta(self):
        original = self.scripts.criar("Original", "Texto")
        self.ui.editar_script(original.id)
        editor = self.editor(EditorScript)
        self.assertEqual(str(editor.pasta.cget("state")), "disabled")
        editor.titulo.delete(0, "end")
        editor.titulo.insert(0, "Atualizado")
        clicar(editor, "Salvar script")
        self.assertEqual(self.scripts.obter(original.id).titulo, "Atualizado")
        self.assertEqual(self.scripts.obter(original.id).pasta_id, original.pasta_id)

    def test_criar_renomear_e_selecionar_pasta(self):
        self.ui.botao_novo.invoke()
        editor = self.editor(EditorPasta)
        editor.nome.insert(0, "Atendimento")
        clicar(editor, "Criar pasta")
        self.assertIsNone(self.ui.pasta_id)
        pasta_id = next(p.id for p in self.pastas.listar() if p.nome == "Atendimento")
        self.ui.editar_pasta(pasta_id)
        editor = self.editor(EditorPasta)
        editor.nome.delete(0, "end")
        editor.nome.insert(0, "Respostas")
        clicar(editor, "Salvar")
        self.assertEqual(self.pastas.obter(pasta_id).nome, "Respostas")
        self.ui.abrir_pasta(pasta_id)
        self.assertEqual(self.ui.pasta_id, pasta_id)
        self.assertEqual(self.ui.pasta_atual.cget("text"), "Respostas")
        self.assertEqual(self.ui.botao_novo.cget("text"), "+ Novo script")
        self.ui.botao_voltar.invoke()
        self.assertIsNone(self.ui.pasta_id)
        self.assertEqual(self.ui.botao_novo.cget("text"), "+ Nova pasta")

    def test_cancelar_editor_nao_grava(self):
        self.ui.editar_script()
        editor = self.editor(EditorScript)
        editor.titulo.insert(0, "Rascunho")
        clicar(editor, "Cancelar")
        self.assertEqual(self.scripts.listar(), [])

    def test_confirmacao_e_cascata_pela_interface(self):
        pasta = self.pastas.criar("Atendimento")
        self.scripts.criar("Título", "Texto", pasta.id)
        self.ui.pasta_id = pasta.id
        self.ui.atualizar()
        with patch("presentation.interface.confirmar", return_value=False):
            self.ui.excluir_pasta(pasta.id)
        self.assertEqual(len(self.scripts.listar()), 1)
        with patch("presentation.interface.confirmar", return_value=True) as aviso:
            self.ui.excluir_pasta(pasta.id)
        self.assertIn("Todos os scripts associados", aviso.call_args.args[2])
        self.assertEqual(self.scripts.listar(), [])
        self.assertIsNone(self.ui.pasta_id)
        self.assertTrue(self.root.winfo_exists())

    def test_excluir_script_pede_confirmacao(self):
        script = self.scripts.criar("Título", "Texto")
        with patch("presentation.interface.confirmar", return_value=False):
            self.ui.excluir_script(script.id)
        self.assertEqual(self.scripts.obter(script.id), script)
        with patch("presentation.interface.confirmar", return_value=True):
            self.ui.excluir_script(script.id)
        self.assertEqual(self.scripts.listar(), [])

    def test_menu_geral_desabilita_alteracao_e_exclusao(self):
        with patch("tkinter.Menu.tk_popup"):
            self.ui._menu_pasta(self.pastas.garantir_geral())
        menu = self.ui._menu
        self.assertEqual(menu.entrycget(0, "label"), "Abrir pasta")
        self.assertEqual(menu.entrycget(0, "state"), "normal")
        self.assertEqual(menu.entrycget(1, "state"), "disabled")
        self.assertEqual(menu.entrycget(2, "state"), "disabled")

    def test_visualizacao_nao_simula_insercao(self):
        script = self.scripts.criar("Título", "Texto")
        self.ui.visualizar(script.id)
        dialogo = self.editor(Dialogo)
        botao = next(w for w in descendentes(dialogo)
                     if isinstance(w, ttk.Button) and w.cget("text") == "Inserir texto")
        self.assertTrue(botao.instate(["disabled"]))

    def test_clique_oculta_interface_antes_de_tentar_e_fecha_apos_envio(self):
        self.ui.insercao = Mock()
        def executar(_):
            self.assertEqual(self.root.state(), "withdrawn")
            return ResultadoInsercao.ENVIADO
        self.ui.insercao.executar.side_effect = executar
        with patch.object(self.root, "destroy") as destruir:
            self.ui.usar_script(1)
        self.ui.insercao.executar.assert_called_once_with(1)
        destruir.assert_called_once()

    def test_sem_destino_ou_falha_tambem_fecha_sem_aviso(self):
        self.ui.insercao = Mock()
        for resultado in (ResultadoInsercao.SEM_DESTINO_VALIDO, ResultadoInsercao.FALHA):
            self.ui.insercao.executar.return_value = resultado
            with patch.object(self.root, "destroy") as destruir, \
                    patch("presentation.interface.informar") as aviso:
                self.ui.usar_script(1)
            destruir.assert_called_once()
            aviso.assert_not_called()

    def test_inserir_pela_visualizacao_tambem_oculta_dialogo_e_fecha(self):
        self.ui.insercao = Mock()
        dialogo = Dialogo(self.root, "Visualizar script")
        def executar(_):
            self.assertEqual(dialogo.state(), "withdrawn")
            return ResultadoInsercao.ENVIADO
        self.ui.insercao.executar.side_effect = executar
        with patch.object(self.root, "destroy") as destruir:
            self.ui.usar_script(1, dialogo)
        destruir.assert_called_once()
        self.ui.insercao.diagnostico_falha.assert_not_called()

    def test_erro_durante_insercao_tambem_fecha_sem_aviso(self):
        self.ui.insercao = Mock()
        self.ui.insercao.executar.side_effect = OSError("Falha técnica")
        with patch.object(self.root, "destroy") as destruir, \
                patch("presentation.interface.informar") as aviso:
            self.ui.usar_script(1)
        destruir.assert_called_once()
        aviso.assert_not_called()

    def test_clique_no_script_insere_quando_integracao_disponivel(self):
        script = self.scripts.criar("Título", "Texto")
        self.ui.insercao = Mock()
        self.ui.abrir_pasta(script.pasta_id)
        self.root.deiconify()
        self.root.update()
        cartao = self.ui.lista.corpo.winfo_children()[0]
        with patch.object(self.ui, "usar_script") as usar:
            cartao.event_generate("<Button-1>", x=2, y=2)
        usar.assert_called_once_with(script.id)

    def test_erro_de_persistencia_exibe_aviso(self):
        import sqlite3
        with patch.object(self.scripts, "listar", side_effect=sqlite3.OperationalError), \
                patch("presentation.interface.informar") as aviso:
            self.ui.abrir_pasta(self.pastas.garantir_geral().id)
        self.assertEqual(aviso.call_args.args[1], "Dados indisponíveis")

    def test_clique_na_caixa_fundo_e_nome_abre_pasta(self):
        geral = self.pastas.garantir_geral()
        self.root.deiconify()
        for parte in ("canvas", "corpo", "nome"):
            with self.subTest(parte=parte):
                self.ui.voltar()
                self.root.update()
                cartao = self.ui.lista.corpo.winfo_children()[0]
                alvo = cartao if parte == "canvas" else cartao.corpo
                if parte == "nome":
                    alvo = next(w for w in cartao.corpo.winfo_children() if isinstance(w, tk.Label))
                alvo.event_generate("<Button-1>", x=2, y=2)
                self.assertEqual(self.ui.pasta_id, geral.id)

    def test_menu_da_pasta_nao_navega_ao_ser_aberto(self):
        pasta = self.pastas.criar("Atendimento")
        self.ui.atualizar()
        cartao = self.ui.lista.corpo.winfo_children()[1]
        with patch("tkinter.Menu.tk_popup"):
            clicar(cartao, "···")
        self.assertIsNone(self.ui.pasta_id)
        menu = self.ui._menu
        self.assertEqual([menu.entrycget(i, "label") for i in range(3)],
                         ["Abrir pasta", "Editar pasta", "Excluir pasta"])
        menu.invoke(0)
        self.assertEqual(self.ui.pasta_id, pasta.id)

    def test_cartao_script_mostra_apenas_titulo_previa_e_tres_pontos(self):
        script = self.scripts.criar("Saudação", "Olá! Como posso ajudar?")
        self.ui.abrir_pasta(script.pasta_id)
        cartao = self.ui.lista.corpo.winfo_children()[0]
        rotulos = [w.cget("text") for w in descendentes(cartao) if isinstance(w, tk.Label)]
        botoes = [w.cget("text") for w in descendentes(cartao) if isinstance(w, ttk.Button)]
        self.assertEqual(rotulos, [script.titulo, script.conteudo])
        self.assertEqual(botoes, ["···"])
        with patch("tkinter.Menu.tk_popup"):
            clicar(cartao, "···")
        self.assertEqual([self.ui._menu.entrycget(i, "label") for i in range(3)],
                         ["Ver script", "Editar script", "Excluir script"])
        with patch.object(self.ui, "visualizar") as visualizar:
            self.ui._menu.invoke(0)
        visualizar.assert_called_once_with(script.id)

    def test_lista_apenas_scripts_da_pasta_aberta(self):
        pasta = self.pastas.criar("Atendimento")
        self.scripts.criar("Script desta pasta", "Conteúdo", pasta.id)
        self.scripts.criar("Script de Geral", "Outro conteúdo")
        self.ui.abrir_pasta(pasta.id)
        rotulos = [w.cget("text") for w in descendentes(self.ui.lista.corpo)
                   if isinstance(w, tk.Label)]
        self.assertIn("Script desta pasta", rotulos)
        self.assertNotIn("Script de Geral", rotulos)

    def test_novo_script_na_pasta_aberta(self):
        pasta = self.pastas.criar("Atendimento")
        self.ui.abrir_pasta(pasta.id)
        self.ui.botao_novo.invoke()
        editor = self.editor(EditorScript)
        editor.titulo.insert(0, "Teste")
        editor.conteudo.insert("1.0", "Texto")
        clicar(editor, "Salvar script")
        self.assertEqual(self.scripts.listar()[0].pasta_id, pasta.id)

    def test_pasta_vazia_tem_mensagem_simples(self):
        self.ui.abrir_pasta(self.pastas.garantir_geral().id)
        rotulos = [w.cget("text") for w in descendentes(self.ui.lista.corpo)
                   if isinstance(w, tk.Label)]
        self.assertEqual(rotulos, ["Esta pasta está vazia."])

    def test_cartoes_mais_estreitos_preservam_janela_e_barra(self):
        script = self.scripts.criar("Título", "Conteúdo")
        self.root.deiconify()
        self.root.update()
        tamanho = (self.root.winfo_width(), self.root.winfo_height())
        barra_x = self.ui.lista.barra.winfo_rootx()
        for pasta_id in (None, script.pasta_id):
            self.ui.pasta_id = pasta_id
            self.ui.atualizar()
            self.root.update()
            cartao = self.ui.lista.corpo.winfo_children()[0]
            self.assertEqual(cartao.winfo_x(), 8)
            self.assertEqual(cartao.winfo_width(), self.ui.lista.corpo.winfo_width() - 16)
            self.assertEqual(self.ui.lista.barra.winfo_rootx(), barra_x)
            self.assertEqual((self.root.winfo_width(), self.root.winfo_height()), tamanho)

    def test_cartoes_tem_altura_padrao_com_texto_longo_e_quebras(self):
        curto = self.scripts.criar("Curto", "Texto curto")
        conteudo = "Primeira linha\n\n" + "Conteúdo muito longo\n" * 1000
        longo = self.scripts.criar("Título enorme " * 100, conteudo)
        self.ui.abrir_pasta(curto.pasta_id)
        self.root.deiconify()
        self.root.update()
        cartoes = self.ui.lista.corpo.winfo_children()
        self.assertEqual(cartoes[0].winfo_height(), cartoes[1].winfo_height())
        previa = next(w for w in cartoes[1].corpo.winfo_children() if isinstance(w, tk.Label))
        self.assertEqual(int(previa.cget("height")), 3)
        self.assertNotIn("\n", previa.cget("text"))
        self.assertTrue(previa.cget("text").endswith("…"))
        self.assertLessEqual(len(previa.cget("text")), 151)
        self.root.geometry("360x400")
        self.root.update()
        self.assertEqual(cartoes[0].winfo_height(), cartoes[1].winfo_height())
        self.assertEqual(self.scripts.obter(longo.id).conteudo, conteudo)

    def test_ver_script_preserva_conteudo_completo_apos_previa(self):
        conteudo = "  Texto com espaços\n\n" + "Linha de conteúdo\n" * 200
        script = self.scripts.criar("Título", conteudo)
        self.ui.abrir_pasta(script.pasta_id)
        self.ui.visualizar(script.id)
        dialogo = self.editor(Dialogo)
        campo = next(w for w in descendentes(dialogo) if isinstance(w, tk.Text))
        self.assertEqual(campo.get("1.0", "end-1c"), conteudo)


if __name__ == "__main__":
    unittest.main()
