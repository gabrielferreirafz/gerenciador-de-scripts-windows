"""Persistência da ordem e gestos reais de pressionar, mover e soltar."""

from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from application.organizacao import CasosDeUsoOrganizacao
from application.pasta import CasosDeUsoPastas
from application.scripts import CasosDeUsoScripts
from domain.erros import ErroDominio
from infraestructure.database import BancoDados, ESQUEMA
from infraestructure.repository import (RepositorioPastasSQLite, RepositorioScriptsSQLite,
                                        RepositorioOrganizacaoSQLite)
from presentation.dialogos import Dialogo
from presentation.interface import Interface


class BaseOrdenacao(unittest.TestCase):
    def setUp(self):
        temporario = TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.banco = BancoDados(Path(temporario.name) / "teste.sqlite3")
        self.banco.inicializar()
        self.repo_pastas = RepositorioPastasSQLite(self.banco)
        self.repo_scripts = RepositorioScriptsSQLite(self.banco)
        self.repo = RepositorioOrganizacaoSQLite(self.banco)
        self.pastas = CasosDeUsoPastas(self.repo_pastas)
        self.scripts = CasosDeUsoScripts(self.repo_scripts, self.repo_pastas)
        self.organizacao = CasosDeUsoOrganizacao(self.repo)

    def itens(self, pai_id):
        pastas = [(p.ordem, 0, p.id, ("pasta", p.id)) for p in self.pastas.listar_filhas(pai_id)]
        scripts = [(s.ordem, 1, s.id, ("script", s.id)) for s in self.scripts.listar(pai_id)] if pai_id is not None else []
        return [item[3] for item in sorted(pastas + scripts)]


class TestOrdemSQLite(BaseOrdenacao):
    def test_geral_pode_ser_reordenada_sem_perder_protecao(self):
        geral = self.pastas.garantir_geral()
        outra = self.pastas.criar("Outra")
        ordem = [("pasta", outra.id), ("pasta", geral.id)]
        self.organizacao.reordenar(None, ordem)
        self.banco.inicializar()
        self.assertEqual(self.itens(None), ordem)
        with self.assertRaises(ErroDominio):
            self.pastas.renomear(geral.id, "Alterada")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.banco.transacao() as c:
                c.execute("UPDATE pastas SET nome='Alterada' WHERE id=?", (geral.id,))

    def test_intercala_scripts_e_subpastas_e_persiste_apos_reabertura(self):
        pai = self.pastas.criar("Pai")
        filha = self.pastas.criar("Filha", pai.id)
        a = self.scripts.criar("A", "Conteúdo", pai.id)
        b = self.scripts.criar("B", "Conteúdo", pai.id)
        ordem = [("script", b.id), ("pasta", filha.id), ("script", a.id)]
        self.organizacao.reordenar(pai.id, ordem)
        BancoDados(self.banco.caminho).inicializar()
        self.assertEqual(self.itens(pai.id), ordem)
        self.assertEqual(self.scripts.obter(a.id).pasta_id, pai.id)
        self.assertEqual(self.pastas.obter(filha.id).pai_id, pai.id)

    def test_novos_itens_entram_no_fim_do_nivel(self):
        pai = self.pastas.criar("Pai")
        a = self.scripts.criar("A", "Texto", pai.id)
        filha = self.pastas.criar("Filha", pai.id)
        self.assertEqual(self.itens(pai.id), [("script", a.id), ("pasta", filha.id)])
        self.organizacao.reordenar(pai.id, list(reversed(self.itens(pai.id))))
        b = self.scripts.criar("B", "Texto", pai.id)
        self.assertEqual(self.itens(pai.id)[-1], ("script", b.id))

    def test_recusa_item_de_outro_nivel_duplicado_omitido_ou_removido(self):
        pai = self.pastas.criar("Pai")
        filha = self.pastas.criar("Filha", pai.id)
        script = self.scripts.criar("Script", "Texto", pai.id)
        original = self.itens(pai.id)
        invalidas = [[], [("pasta", filha.id)], original + [original[0]],
                     [("pasta", pai.id), ("script", script.id)],
                     [("pasta", filha.id), ("script", 999)]]
        for ordem in invalidas:
            with self.subTest(ordem=ordem), self.assertRaises(ErroDominio):
                self.organizacao.reordenar(pai.id, ordem)
            self.assertEqual(self.itens(pai.id), original)

    def test_falha_no_meio_desfaz_toda_a_reordenacao(self):
        pai = self.pastas.criar("Pai")
        a = self.scripts.criar("A", "Texto", pai.id)
        b = self.scripts.criar("B", "Texto", pai.id)
        with self.banco.transacao() as c:
            c.execute(f"""CREATE TRIGGER falha_ordem BEFORE UPDATE OF ordem ON scripts
                WHEN OLD.id={a.id} BEGIN SELECT RAISE(ABORT,'falha'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.organizacao.reordenar(pai.id, [("script", b.id), ("script", a.id)])
        self.assertEqual(self.itens(pai.id), [("script", a.id), ("script", b.id)])

    def test_edicao_e_exclusao_preservam_ordem_dos_restantes(self):
        pai = self.pastas.criar("Pai")
        filha = self.pastas.criar("Filha", pai.id)
        a = self.scripts.criar("A", "Texto", pai.id)
        b = self.scripts.criar("B", "Texto", pai.id)
        ordem = [("script", b.id), ("pasta", filha.id), ("script", a.id)]
        self.organizacao.reordenar(pai.id, ordem)
        self.scripts.editar(b.id, "Renomeado", "Novo conteúdo")
        self.pastas.renomear(filha.id, "Renomeada")
        self.assertEqual(self.itens(pai.id), ordem)
        self.pastas.excluir(filha.id, confirmado=True)
        self.assertEqual(self.itens(pai.id), [ordem[0], ordem[2]])

    def test_migracao_preserva_ordem_antiga_e_scripts(self):
        antigo = BancoDados(self.banco.caminho.with_name("antigo.sqlite3"))
        with antigo.transacao() as c:
            for comando in ESQUEMA:
                c.execute(comando)
            c.execute("ALTER TABLE pastas ADD COLUMN pai_id INTEGER")
            c.execute("INSERT INTO pastas(id,nome,sistema) VALUES(1,'Geral',1),(2,'Pai',0)")
            c.execute("INSERT INTO pastas(id,nome,sistema,pai_id) VALUES(5,'Filha',0,2)")
            c.execute("INSERT INTO scripts VALUES(8,'Script','Conteúdo',2)")
        antigo.inicializar()
        with antigo.conectar() as c:
            self.assertEqual(c.execute("SELECT ordem FROM pastas WHERE id=5").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT ordem FROM scripts WHERE id=8").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT conteudo FROM scripts WHERE id=8").fetchone()[0], "Conteúdo")


class TestGestosOrdenacao(BaseOrdenacao):
    def setUp(self):
        super().setUp()
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.erros = []
        self.root.report_callback_exception = lambda *erro: self.erros.append(erro)
        self.addCleanup(lambda: self.assertEqual(self.erros, []))
        mostrar = patch.object(Dialogo, "mostrar", lambda _: None)
        mostrar.start()
        self.addCleanup(mostrar.stop)
        self.pai = self.pastas.criar("Pai")
        self.filha = self.pastas.criar("Filha", self.pai.id)
        self.a = self.scripts.criar("A", "Texto", self.pai.id)
        self.b = self.scripts.criar("B", "Texto", self.pai.id)
        self.ui = Interface(self.root, self.pastas, self.scripts, Mock(), self.organizacao)
        self.ui.abrir_pasta(self.pai.id)
        self.root.update()

    def gesto(self, indice, y, mover=True, alvo=None):
        cartao = self.ui.arraste.cartoes[indice][0]
        alvo = alvo or cartao
        x = cartao.winfo_rootx() + 20
        inicio = cartao.winfo_rooty() + 15
        alvo.event_generate("<ButtonPress-1>", x=10, y=10, rootx=x, rooty=inicio)
        if mover:
            alvo.event_generate("<B1-Motion>", rootx=x, rooty=y)
        alvo.event_generate("<ButtonRelease-1>", rootx=x, rooty=y)
        self.root.update()

    def test_arrastar_script_para_primeiro_nao_insere_e_persiste(self):
        topo = self.ui.arraste.cartoes[0][0].winfo_rooty() + 2
        self.gesto(2, topo)
        self.ui.insercao.executar.assert_not_called()
        self.assertEqual(self.itens(self.pai.id)[0], ("script", self.b.id))
        self.ui.atualizar()
        self.assertEqual(self.ui.arraste.cartoes[0][1], ("script", self.b.id))

    def test_arrastar_subpasta_para_o_fim_nao_abre_pasta(self):
        ultimo = self.ui.arraste.cartoes[-1][0]
        self.gesto(0, ultimo.winfo_rooty() + ultimo.winfo_height()-2)
        self.assertEqual(self.ui.pasta_id, self.pai.id)
        self.assertEqual(self.itens(self.pai.id)[-1], ("pasta", self.filha.id))

    def test_clique_simples_aguarda_soltar_e_insere(self):
        cartao = self.ui.arraste.cartoes[1][0]
        with patch.object(self.ui, "usar_script") as usar:
            cartao.event_generate("<ButtonPress-1>", x=10, y=10)
            usar.assert_not_called()
            cartao.event_generate("<ButtonRelease-1>", x=10, y=10)
        usar.assert_called_once_with(self.a.id)

    def test_movimento_pequeno_continua_sendo_clique(self):
        cartao = self.ui.arraste.cartoes[0][0]
        y = cartao.winfo_rooty() + 17
        self.gesto(0, y)
        self.assertEqual(self.ui.pasta_id, self.filha.id)

    def test_soltar_fora_cancela_sem_inserir_ou_mudar_ordem(self):
        original = self.itens(self.pai.id)
        self.gesto(1, self.ui.lista.canvas.winfo_rooty()-80)
        self.assertEqual(self.itens(self.pai.id), original)
        self.ui.insercao.executar.assert_not_called()

    def test_escape_cancela_arraste_sem_transformar_em_clique(self):
        cartao = self.ui.arraste.cartoes[1][0]
        cartao.event_generate("<ButtonPress-1>", x=10, y=10)
        cartao.event_generate("<B1-Motion>", x=10, y=35)
        self.assertTrue(self.ui.arraste.arrastando)
        self.assertIsNotNone(self.ui.arraste.tarefa)
        self.ui.arraste.cancelar()
        cartao.event_generate("<ButtonRelease-1>", x=10, y=35)
        self.assertIsNone(self.ui.arraste.tarefa)
        self.ui.insercao.executar.assert_not_called()

    def test_rotulo_tambem_permite_arrastar(self):
        cartao = self.ui.arraste.cartoes[0][0]
        rotulo = next(w for w in cartao.corpo.winfo_children() if isinstance(w, tk.Label))
        ultimo = self.ui.arraste.cartoes[-1][0]
        self.gesto(0, ultimo.winfo_rooty() + ultimo.winfo_height()-2, alvo=rotulo)
        self.assertEqual(self.itens(self.pai.id)[-1], ("pasta", self.filha.id))

    def test_falha_ao_salvar_restaura_ordem_real(self):
        original = self.itens(self.pai.id)
        with patch.object(self.organizacao, "reordenar", side_effect=sqlite3.OperationalError), \
                patch("presentation.interface.informar") as aviso:
            self.gesto(2, self.ui.arraste.cartoes[0][0].winfo_rooty()+2)
        self.assertEqual([chave for _, chave in self.ui.arraste.cartoes], original)
        aviso.assert_called_once()

    def test_arrasta_pasta_na_raiz_sem_abrir(self):
        self.ui.voltar()
        self.root.update()
        topo = self.ui.arraste.cartoes[0][0].winfo_rooty()+2
        self.gesto(1, topo)
        self.assertIsNone(self.ui.pasta_id)
        self.assertEqual(self.ui.arraste.cartoes[0][1], ("pasta", self.pai.id))

    def test_rolagem_nas_bordas_so_existe_durante_arraste(self):
        for i in range(15):
            self.scripts.criar(str(i), "Texto", self.pai.id)
        self.ui.atualizar()
        self.root.update()
        cartao = self.ui.arraste.cartoes[0][0]
        canvas = self.ui.lista.canvas
        x = cartao.winfo_rootx()+15
        inicio = cartao.winfo_rooty()+10
        cartao.event_generate("<ButtonPress-1>", rootx=x, rooty=inicio)
        with patch.object(canvas, "yview_scroll", wraps=canvas.yview_scroll) as rolar:
            cartao.event_generate("<B1-Motion>", rootx=x,
                                  rooty=canvas.winfo_rooty()+canvas.winfo_height()-5)
            rolar.assert_called_with(1, "units")
        self.assertGreater(canvas.yview()[0], 0)
        self.assertIsNotNone(self.ui.arraste.tarefa)
        self.ui.arraste.cancelar()
        self.assertIsNone(self.ui.arraste.tarefa)
        self.assertIsNone(self.root.grab_current())
