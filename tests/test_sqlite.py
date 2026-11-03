"""Integração com arquivos SQLite reais e diretórios temporários isolados."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from application.erros import ConfirmacaoNecessaria, EntidadeNaoEncontrada
from application.pasta import CasosDeUsoPastas
from application.scripts import CasosDeUsoScripts
from domain.erros import ErroDominio, PastaProtegida
from domain.pasta import Pasta
from domain.script import Script
from infraestructure.database import BancoDados, caminho_padrao
from infraestructure.repository import RepositorioPastasSQLite, RepositorioScriptsSQLite


class TestSQLite(unittest.TestCase):
    def setUp(self):
        temporario = TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.caminho = Path(temporario.name) / "dados" / "teste.sqlite3"
        self.banco = BancoDados(self.caminho)
        self.banco.inicializar()
        self.repo_pastas = RepositorioPastasSQLite(self.banco)
        self.repo_scripts = RepositorioScriptsSQLite(self.banco)
        self.pastas = CasosDeUsoPastas(self.repo_pastas)
        self.scripts = CasosDeUsoScripts(self.repo_scripts, self.repo_pastas)

    def test_local_padrao_separado_do_projeto(self):
        with patch.dict("os.environ", {"LOCALAPPDATA": str(self.caminho.parent)}):
            self.assertEqual(
                caminho_padrao(),
                self.caminho.parent / "GerenciadorScripts" / "gerenciador.sqlite3",
            )

    def test_inicializacao_idempotente_preserva_dados(self):
        original = self.scripts.criar("Título", "Texto")
        geral = self.pastas.garantir_geral()
        for _ in range(3):
            self.banco.inicializar()
        self.assertEqual(self.pastas.listar(), [geral])
        self.assertEqual(self.scripts.obter(original.id), original)

    def test_geral_nao_depende_de_id_fixo_ou_so_do_nome(self):
        outro = BancoDados(self.caminho.parent / "outro.sqlite3")
        with outro.transacao() as conexao:
            conexao.execute(
                "CREATE TABLE pastas (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, "
                "sistema INTEGER NOT NULL CHECK(sistema IN(0,1)))"
            )
            conexao.execute("INSERT INTO pastas VALUES (42, 'Geral', 0)")
        outro.inicializar()
        repo = RepositorioPastasSQLite(outro)
        geral = repo.garantir_geral()
        self.assertNotEqual(geral.id, 1)
        self.assertNotEqual(geral.id, 42)
        self.assertTrue(geral.sistema)
        self.assertFalse(repo.obter(42).sistema)
        self.assertEqual(len(repo.listar()), 2)

    def test_inicializacoes_concorrentes_nao_duplicam_geral(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda _: BancoDados(self.caminho).inicializar(), range(8)))
        self.assertEqual(len(self.pastas.listar()), 1)

    def test_chaves_estrangeiras_em_todas_as_conexoes_e_fechamento(self):
        for _ in range(2):
            with self.banco.conectar() as conexao:
                self.assertEqual(conexao.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaises(sqlite3.ProgrammingError):
                conexao.execute("SELECT 1")

    def test_sql_rejeita_script_sem_pasta_ou_com_pasta_inexistente(self):
        for pasta_id in (None, 999):
            with self.subTest(pasta_id=pasta_id), self.assertRaises(sqlite3.IntegrityError):
                with self.banco.transacao() as conexao:
                    conexao.execute(
                        "INSERT INTO scripts(titulo, conteudo, pasta_id) VALUES (?, ?, ?)",
                        ("Título", "Texto", pasta_id),
                    )
        self.assertEqual(self.scripts.listar(), [])

    def test_booleano_e_unica_pasta_protegida(self):
        for nome, sistema in (("Outra", 2), ("Geral", 1), ("Outra", 1)):
            with self.subTest(sistema=sistema), self.assertRaises(sqlite3.IntegrityError):
                with self.banco.transacao() as conexao:
                    conexao.execute(
                        "INSERT INTO pastas(nome, sistema) VALUES (?, ?)", (nome, sistema)
                    )

    def test_geral_protegida_mesmo_por_sql_direto(self):
        geral = self.pastas.garantir_geral()
        script = self.scripts.criar("Título", "Texto")
        for sql in (
            "DELETE FROM pastas WHERE id = ?",
            "UPDATE pastas SET nome = 'Outra' WHERE id = ?",
            "UPDATE pastas SET sistema = 0 WHERE id = ?",
            "UPDATE pastas SET id = 99 WHERE id = ?",
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                with self.banco.transacao() as conexao:
                    conexao.execute(sql, (geral.id,))
        self.assertEqual(self.pastas.obter(geral.id), geral)
        self.assertEqual(self.scripts.obter(script.id), script)

    def test_repositorio_revalida_protecao_de_geral(self):
        geral = self.pastas.garantir_geral()
        with self.assertRaises(PastaProtegida):
            self.repo_pastas.atualizar(replace(geral, nome="Outra", sistema=False))
        with self.assertRaises(PastaProtegida):
            self.repo_pastas.excluir_com_scripts(geral.id)
        pasta = self.pastas.criar("Usuário")
        with self.assertRaises(ErroDominio):
            self.repo_pastas.atualizar(replace(pasta, sistema=True))

    def test_crud_pasta_e_consulta_por_pasta(self):
        pasta = self.pastas.criar("Atendimento")
        renomeada = self.pastas.renomear(pasta.id, "Respostas")
        self.assertEqual(self.pastas.obter(pasta.id), renomeada)
        self.assertFalse(renomeada.sistema)
        associado = self.scripts.criar("Título", "Texto", pasta.id)
        padrao = self.scripts.criar("Padrão", "Texto")
        self.assertEqual(self.scripts.listar(pasta.id), [associado])
        self.assertEqual(padrao.pasta_id, self.pastas.garantir_geral().id)

    def test_crud_script_e_conteudo_literal_sem_injecao_sql(self):
        titulo = "'); DROP TABLE scripts; --"
        conteudo = "  Olá! 👋\nTexto com 'aspas' e espaços.  "
        script = self.scripts.criar(titulo, conteudo)
        self.assertEqual(self.scripts.obter(script.id), script)
        editado = self.scripts.editar(script.id, "Novo título", conteudo + "\nFim")
        self.assertEqual(self.scripts.obter(script.id), editado)
        self.assertEqual(editado.pasta_id, script.pasta_id)
        self.scripts.excluir(script.id)
        self.assertEqual(self.scripts.listar(), [])

    def test_pasta_inexistente_e_edicao_sem_movimentacao(self):
        with self.assertRaises(EntidadeNaoEncontrada):
            self.repo_scripts.criar("Título", "Texto", 999)
        script = self.scripts.criar("Título", "Texto")
        outra = self.pastas.criar("Outra")
        with self.assertRaises(ErroDominio):
            self.repo_scripts.atualizar(replace(script, pasta_id=outra.id))
        self.assertEqual(self.scripts.obter(script.id), script)

    def test_nomes_e_titulos_duplicados_permitidos(self):
        self.pastas.criar("Geral")
        self.pastas.criar("Geral")
        self.scripts.criar("Título", "Texto")
        self.scripts.criar("Título", "Texto")
        self.assertEqual(len(self.pastas.listar()), 3)
        self.assertEqual(len(self.scripts.listar()), 2)

    def test_repositorios_informam_entidade_inexistente(self):
        self.assertIsNone(self.repo_pastas.obter(999))
        self.assertIsNone(self.repo_scripts.obter(999))
        for operacao in (
            lambda: self.repo_pastas.atualizar(Pasta(999, "Pasta", False)),
            lambda: self.repo_pastas.excluir_com_scripts(999),
            lambda: self.repo_scripts.atualizar(Script(999, "Título", "Texto", 1)),
            lambda: self.repo_scripts.excluir(999),
        ):
            with self.assertRaises(EntidadeNaoEncontrada):
                operacao()

    def test_cancelamento_preserva_pasta_e_scripts(self):
        pasta = self.pastas.criar("Atendimento")
        script = self.scripts.criar("Título", "Texto", pasta.id)
        with self.assertRaises(ConfirmacaoNecessaria):
            self.pastas.excluir(pasta.id)
        self.assertEqual(self.pastas.obter(pasta.id), pasta)
        self.assertEqual(self.scripts.obter(script.id), script)

    def test_cascata_real_preserva_scripts_de_outras_pastas(self):
        pasta = self.pastas.criar("Atendimento")
        self.scripts.criar("Um", "Texto", pasta.id)
        self.scripts.criar("Dois", "Texto", pasta.id)
        preservado = self.scripts.criar("Outro", "Texto")
        self.pastas.excluir(pasta.id, confirmado=True)
        self.assertIsNone(self.repo_pastas.obter(pasta.id))
        self.assertEqual(self.scripts.listar(), [preservado])

    def test_falha_apos_cascata_reverte_exclusao_inteira(self):
        pasta = self.pastas.criar("Atendimento")
        script = self.scripts.criar("Título", "Texto", pasta.id)
        with self.banco.transacao() as conexao:
            conexao.execute(
                "CREATE TRIGGER simular_falha AFTER DELETE ON pastas "
                "BEGIN SELECT RAISE(ABORT, 'Falha simulada'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.pastas.excluir(pasta.id, confirmado=True)
        self.assertEqual(self.pastas.obter(pasta.id), pasta)
        self.assertEqual(self.scripts.obter(script.id), script)

    def test_erro_apos_multiplas_escritas_reverte_todas(self):
        with self.assertRaises(RuntimeError):
            with self.banco.transacao() as conexao:
                conexao.execute("INSERT INTO pastas(nome, sistema) VALUES ('Nova', 0)")
                conexao.execute("INSERT INTO pastas(nome, sistema) VALUES ('Outra', 0)")
                raise RuntimeError("Falha antes de confirmar")
        self.assertEqual(len(self.pastas.listar()), 1)

    def test_dados_persistem_apos_nova_instancia(self):
        pasta = self.pastas.criar("Atendimento")
        script = self.scripts.criar("Título", "Texto", pasta.id)
        reaberto = BancoDados(self.caminho)
        reaberto.inicializar()
        self.assertEqual(RepositorioPastasSQLite(reaberto).obter(pasta.id), pasta)
        self.assertEqual(RepositorioScriptsSQLite(reaberto).obter(script.id), script)

    def test_encerramento_abrupto_reverte_transacao_nao_confirmada(self):
        pasta = self.pastas.criar("Atendimento")
        script = self.scripts.criar("Título", "Texto", pasta.id)
        codigo = (
            "import os, sys; from infraestructure.database import BancoDados; "
            "banco = BancoDados(sys.argv[1]); "
            "transacao = banco.transacao(); conexao = transacao.__enter__(); "
            "conexao.execute('DELETE FROM pastas WHERE id = ?', (int(sys.argv[2]),)); "
            "os._exit(0)"
        )
        subprocess.run(
            [sys.executable, "-B", "-c", codigo, str(self.caminho), str(pasta.id)],
            check=True, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(self.pastas.obter(pasta.id), pasta)
        self.assertEqual(self.scripts.obter(script.id), script)
        with self.banco.conectar() as conexao:
            self.assertEqual(conexao.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conexao.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
