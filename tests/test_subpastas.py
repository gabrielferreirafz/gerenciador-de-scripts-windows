"""Hierarquia, migração dos dados anteriores e navegação com widgets reais."""

from dataclasses import replace
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from application.erros import ConfirmacaoNecessaria, EntidadeNaoEncontrada
from application.pasta import CasosDeUsoPastas
from application.scripts import CasosDeUsoScripts
from domain.erros import ErroDominio, PastaProtegida
from domain.pasta import Pasta
from infraestructure.database import BancoDados, ESQUEMA
from infraestructure.repository import RepositorioPastasSQLite, RepositorioScriptsSQLite
from presentation.dialogos import Dialogo, EditorPasta, EditorScript
from presentation.interface import Interface
from presentation.tema import rotulos_pastas
from test_interface import clicar, descendentes


class TestSubpastas(unittest.TestCase):
    def setUp(self):
        temporario = TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.banco = BancoDados(Path(temporario.name) / "teste.sqlite3")
        self.banco.inicializar()
        self.repo = RepositorioPastasSQLite(self.banco)
        self.pastas = CasosDeUsoPastas(self.repo)
        self.scripts = CasosDeUsoScripts(RepositorioScriptsSQLite(self.banco), self.repo)

    def test_scripts_independentes_em_cada_nivel_e_pasta_vazia(self):
        pai = self.pastas.criar("Atendimento")
        filha = self.pastas.criar("Financeiro", pai.id)
        neta = self.pastas.criar("Estorno", filha.id)
        raiz = self.scripts.criar("Raiz", "A", pai.id)
        interno = self.scripts.criar("Interno", "B", filha.id)
        self.assertEqual(self.scripts.listar(pai.id), [raiz])
        self.assertEqual(self.scripts.listar(filha.id), [interno])
        self.assertEqual(self.scripts.listar(neta.id), [])
        self.assertEqual(self.pastas.listar_filhas(pai.id), [filha])
        self.assertEqual(self.pastas.listar_filhas(filha.id), [neta])
        self.assertNotIn(filha, self.pastas.listar_filhas())

    def test_renomear_preserva_pai_e_persistencia(self):
        pai = self.pastas.criar("Atendimento")
        filha = self.pastas.criar("Antigo", pai.id)
        atualizada = self.pastas.renomear(filha.id, "Novo")
        self.banco.inicializar()
        self.assertEqual(self.repo.obter(filha.id), atualizada)
        self.assertEqual(atualizada.pai_id, pai.id)
        with self.assertRaises(ErroDominio):
            self.repo.atualizar(replace(atualizada, pai_id=None))

    def test_pai_precisa_existir(self):
        with self.assertRaises(EntidadeNaoEncontrada):
            self.pastas.criar("Órfã", 999)
        with self.assertRaises(EntidadeNaoEncontrada):
            self.repo.criar("Órfã", 999)
        with self.assertRaises(ErroDominio):
            self.pastas.criar("Inválida", True)
        with self.assertRaises(ErroDominio):
            Pasta(4, "Inválida", False, 4)
        with self.assertRaises(PastaProtegida):
            Pasta(4, "Geral", True, 3)

    def test_exclusao_recursiva_exige_confirmacao_e_preserva_outros_ramos(self):
        pai = self.pastas.criar("Atendimento")
        filha = self.pastas.criar("Financeiro", pai.id)
        neta = self.pastas.criar("Estorno", filha.id)
        outro = self.pastas.criar("Outro")
        preservado = self.scripts.criar("Preservado", "Texto", outro.id)
        for pasta in (pai, filha, neta):
            self.scripts.criar("Excluir", "Texto", pasta.id)
        with self.assertRaises(ConfirmacaoNecessaria):
            self.pastas.excluir(pai.id)
        self.assertEqual(len(self.scripts.listar()), 4)
        self.assertIn("subpastas", self.pastas.solicitar_exclusao(pai.id))
        self.pastas.excluir(pai.id, confirmado=True)
        for pasta in (pai, filha, neta):
            self.assertIsNone(self.repo.obter(pasta.id))
        self.assertEqual(self.scripts.listar(), [preservado])
        self.assertEqual(self.repo.obter(outro.id), outro)

    def test_excluir_subpasta_preserva_pai_irma_e_geral_protegida(self):
        pai = self.pastas.garantir_geral()
        filha = self.pastas.criar("Filha", pai.id)
        irma = self.pastas.criar("Irmã", pai.id)
        preservado = self.scripts.criar("Texto do pai", "Texto", pai.id)
        self.pastas.excluir(filha.id, confirmado=True)
        self.assertEqual(self.pastas.listar_filhas(pai.id), [irma])
        self.assertEqual(self.scripts.listar(pai.id), [preservado])
        with self.assertRaises(PastaProtegida):
            self.pastas.excluir(pai.id, confirmado=True)

    def test_sql_impede_ciclo_e_pai_inexistente(self):
        pai = self.pastas.criar("Pai")
        filha = self.pastas.criar("Filha", pai.id)
        neta = self.pastas.criar("Neta", filha.id)
        for destino in (pai.id, neta.id, 999):
            with self.subTest(destino=destino), self.assertRaises(sqlite3.IntegrityError):
                with self.banco.transacao() as conexao:
                    conexao.execute("UPDATE pastas SET pai_id = ? WHERE id = ?", (destino, pai.id))
        self.assertIsNone(self.repo.obter(pai.id).pai_id)

    def test_falha_na_cascata_desfaz_exclusao_inteira(self):
        pai = self.pastas.criar("Pai")
        filha = self.pastas.criar("Filha", pai.id)
        script = self.scripts.criar("Protegido no teste", "Texto", filha.id)
        with self.banco.transacao() as conexao:
            conexao.execute("""CREATE TRIGGER simular_falha BEFORE DELETE ON scripts
                BEGIN SELECT RAISE(ABORT, 'falha simulada'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.pastas.excluir(pai.id, confirmado=True)
        self.assertEqual(self.repo.obter(pai.id), pai)
        self.assertEqual(self.repo.obter(filha.id), filha)
        self.assertEqual(self.scripts.obter(script.id), script)

    def test_migracao_de_banco_antigo_preserva_ids_texto_e_relacoes(self):
        antigo = BancoDados(self.banco.caminho.with_name("antigo.sqlite3"))
        with antigo.transacao() as conexao:
            for comando in ESQUEMA:
                conexao.execute(comando)
            conexao.execute("INSERT INTO pastas(id,nome,sistema) VALUES(42,'Atendimento',0)")
            conexao.execute("INSERT INTO scripts VALUES(85,'Título','Texto 👋',42)")
        for _ in range(3):
            antigo.inicializar()
        pastas = RepositorioPastasSQLite(antigo)
        self.assertIsNone(pastas.obter(42).pai_id)
        script = RepositorioScriptsSQLite(antigo).obter(85)
        self.assertEqual((script.pasta_id, script.conteudo), (42, "Texto 👋"))
        filha = pastas.criar("Nova subpasta", 42)
        self.assertEqual(pastas.obter(filha.id).pai_id, 42)
        with antigo.conectar() as conexao:
            self.assertEqual(list(conexao.execute("PRAGMA foreign_key_check")), [])

    def test_selecao_mostra_caminhos_e_distingue_nomes_repetidos(self):
        pai = self.pastas.criar("Atendimento")
        filha = self.pastas.criar("Suporte", pai.id)
        outra = self.pastas.criar("Suporte", pai.id)
        pastas = self.pastas.listar()
        rotulos = dict(zip((p.id for p in pastas), rotulos_pastas(pastas)))
        self.assertEqual(rotulos[filha.id], "Atendimento / Suporte (1)")
        self.assertEqual(rotulos[outra.id], "Atendimento / Suporte (2)")


class TestInterfaceSubpastas(unittest.TestCase):
    def setUp(self):
        temporario = TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        banco = BancoDados(Path(temporario.name) / "interface.sqlite3")
        banco.inicializar()
        self.repo = RepositorioPastasSQLite(banco)
        self.pastas = CasosDeUsoPastas(self.repo)
        self.scripts = CasosDeUsoScripts(RepositorioScriptsSQLite(banco), self.repo)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.erros = []
        self.root.report_callback_exception = lambda *erro: self.erros.append(erro)
        self.addCleanup(lambda: self.assertEqual(self.erros, []))
        mostrar = patch.object(Dialogo, "mostrar", lambda _: None)
        mostrar.start()
        self.addCleanup(mostrar.stop)
        self.ui = Interface(self.root, self.pastas, self.scripts)
        self.pai = self.pastas.criar("Atendimento")
        self.filha = self.pastas.criar("Financeiro", self.pai.id)
        self.ui.atualizar()

    def labels(self):
        return [w.cget("text") for w in descendentes(self.ui.lista.corpo) if isinstance(w, tk.Label)]

    def editor(self, tipo):
        return next(w for w in self.root.winfo_children() if isinstance(w, tipo))

    def test_raiz_oculta_subpastas_e_navegacao_volta_um_nivel(self):
        self.assertNotIn("Financeiro", self.labels())
        self.assertFalse(self.ui.botao_subpasta.winfo_manager())
        self.ui.abrir_pasta(self.pai.id)
        self.assertIn("Financeiro", self.labels())
        self.assertNotIn("Esta pasta está vazia.", self.labels())
        self.root.deiconify()
        self.root.update()
        cartao = self.ui.lista.corpo.winfo_children()[0]
        cartao.event_generate("<Button-1>", x=2, y=2)
        self.assertEqual(self.ui.pasta_id, self.filha.id)
        self.assertEqual(self.ui.pasta_atual.cget("text"), "Atendimento / Financeiro")
        self.ui.voltar()
        self.assertEqual(self.ui.pasta_id, self.pai.id)
        self.ui.voltar()
        self.assertIsNone(self.ui.pasta_id)

    def test_criar_renomear_e_excluir_subpasta_pelos_controles(self):
        self.ui.abrir_pasta(self.pai.id)
        self.ui.botao_subpasta.invoke()
        editor = self.editor(EditorPasta)
        editor.nome.insert(0, "Nova")
        clicar(editor, "Criar subpasta")
        nova = next(p for p in self.pastas.listar_filhas(self.pai.id) if p.nome == "Nova")
        self.ui.editar_pasta(nova.id)
        editor = self.editor(EditorPasta)
        editor.nome.delete(0, "end")
        editor.nome.insert(0, "Renomeada")
        clicar(editor, "Salvar")
        self.assertEqual(self.pastas.obter(nova.id).pai_id, self.pai.id)
        self.assertIn("Renomeada", self.labels())
        self.ui.abrir_pasta(nova.id)
        with patch("presentation.interface.confirmar", return_value=True):
            self.ui.excluir_pasta(nova.id)
        self.assertEqual(self.ui.pasta_id, self.pai.id)
        self.assertIsNone(self.repo.obter(nova.id))

    def test_cadastro_script_na_subpasta_e_selecao_de_outro_destino(self):
        self.ui.abrir_pasta(self.filha.id)
        self.ui.botao_novo.invoke()
        editor = self.editor(EditorScript)
        self.assertIn("Atendimento / Financeiro", editor.pasta.get())
        editor.titulo.insert(0, "Na filha")
        editor.conteudo.insert("1.0", "Texto")
        clicar(editor, "Salvar script")
        self.assertEqual(len(self.scripts.listar(self.filha.id)), 1)
        self.ui.editar_script()
        editor = self.editor(EditorScript)
        destinos = self.pastas.listar()
        editor.pasta.current(next(i for i, p in enumerate(destinos) if p.id == self.pai.id))
        editor.titulo.insert(0, "No pai")
        clicar(editor, "Salvar script")
        self.assertEqual(self.ui.pasta_id, self.pai.id)
        self.assertEqual(len(self.scripts.listar(self.pai.id)), 1)

    def test_scripts_e_subpastas_compartilham_lista_sem_misturar_descendentes(self):
        self.scripts.criar("Do pai", "Texto", self.pai.id)
        self.scripts.criar("Da filha", "Texto", self.filha.id)
        self.ui.abrir_pasta(self.pai.id)
        self.assertIn("Financeiro", self.labels())
        self.assertIn("Do pai", self.labels())
        self.assertNotIn("Da filha", self.labels())
        self.ui.abrir_pasta(self.filha.id)
        self.assertIn("Da filha", self.labels())
        self.assertNotIn("Do pai", self.labels())

    def test_script_da_subpasta_aciona_insercao_existente(self):
        script = self.scripts.criar("Na filha", "Texto", self.filha.id)
        self.ui.insercao = Mock()
        self.ui.abrir_pasta(self.filha.id)
        self.root.deiconify()
        self.root.update()
        with patch.object(self.ui, "usar_script") as usar:
            self.ui.lista.corpo.winfo_children()[0].event_generate("<Button-1>", x=2, y=2)
        usar.assert_called_once_with(script.id)
