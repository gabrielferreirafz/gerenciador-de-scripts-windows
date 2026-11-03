"""Adaptadores SQLite dos contratos de persistência da aplicação."""

import sqlite3

from application.erros import EntidadeNaoEncontrada
from domain.erros import ErroDominio
from domain.pasta import Pasta
from domain.script import Script
from infraestructure.database import BancoDados, garantir_geral


def _pasta(linha: sqlite3.Row) -> Pasta:
    return Pasta(linha["id"], linha["nome"], bool(linha["sistema"]))


def _script(linha: sqlite3.Row) -> Script:
    return Script(linha["id"], linha["titulo"], linha["conteudo"], linha["pasta_id"])


def _obter_pasta(conexao: sqlite3.Connection, pasta_id: int) -> Pasta:
    linha = conexao.execute("SELECT * FROM pastas WHERE id = ?", (pasta_id,)).fetchone()
    if linha is None:
        raise EntidadeNaoEncontrada(f"Pasta {pasta_id} não encontrada.")
    return _pasta(linha)


class RepositorioPastasSQLite:
    def __init__(self, banco: BancoDados) -> None:
        self._banco = banco

    def garantir_geral(self) -> Pasta:
        with self._banco.transacao() as conexao:
            return _pasta(garantir_geral(conexao))

    def criar(self, nome: str) -> Pasta:
        with self._banco.transacao() as conexao:
            cursor = conexao.execute(
                "INSERT INTO pastas (nome, sistema) VALUES (?, 0)", (nome,)
            )
            return _obter_pasta(conexao, cursor.lastrowid)

    def obter(self, pasta_id: int) -> Pasta | None:
        with self._banco.conectar() as conexao:
            linha = conexao.execute(
                "SELECT * FROM pastas WHERE id = ?", (pasta_id,)
            ).fetchone()
            return _pasta(linha) if linha is not None else None

    def listar(self) -> list[Pasta]:
        with self._banco.conectar() as conexao:
            return [
                _pasta(linha) for linha in conexao.execute(
                    "SELECT * FROM pastas ORDER BY sistema DESC, id"
                )
            ]

    def atualizar(self, pasta: Pasta) -> None:
        with self._banco.transacao() as conexao:
            atual = _obter_pasta(conexao, pasta.id)
            atual.renomear(pasta.nome)  # Proteção também no adaptador.
            if pasta.sistema != atual.sistema:
                raise ErroDominio("Não é permitido alterar a proteção de uma pasta.")
            conexao.execute(
                "UPDATE pastas SET nome = ? WHERE id = ?", (pasta.nome, pasta.id)
            )

    def excluir_com_scripts(self, pasta_id: int) -> None:
        with self._banco.transacao() as conexao:
            _obter_pasta(conexao, pasta_id).verificar_exclusao()
            # A chave estrangeira remove os scripts na mesma transação.
            conexao.execute("DELETE FROM pastas WHERE id = ?", (pasta_id,))


class RepositorioScriptsSQLite:
    def __init__(self, banco: BancoDados) -> None:
        self._banco = banco

    def criar(self, titulo: str, conteudo: str, pasta_id: int) -> Script:
        with self._banco.transacao() as conexao:
            _obter_pasta(conexao, pasta_id)
            cursor = conexao.execute(
                "INSERT INTO scripts (titulo, conteudo, pasta_id) VALUES (?, ?, ?)",
                (titulo, conteudo, pasta_id),
            )
            return Script(cursor.lastrowid, titulo, conteudo, pasta_id)

    def obter(self, script_id: int) -> Script | None:
        with self._banco.conectar() as conexao:
            linha = conexao.execute(
                "SELECT * FROM scripts WHERE id = ?", (script_id,)
            ).fetchone()
            return _script(linha) if linha is not None else None

    def listar(self, pasta_id: int | None = None) -> list[Script]:
        with self._banco.conectar() as conexao:
            if pasta_id is None:
                linhas = conexao.execute("SELECT * FROM scripts ORDER BY id")
            else:
                linhas = conexao.execute(
                    "SELECT * FROM scripts WHERE pasta_id = ? ORDER BY id", (pasta_id,)
                )
            return [_script(linha) for linha in linhas]

    def atualizar(self, script: Script) -> None:
        with self._banco.transacao() as conexao:
            linha = conexao.execute(
                "SELECT pasta_id FROM scripts WHERE id = ?", (script.id,)
            ).fetchone()
            if linha is None:
                raise EntidadeNaoEncontrada(f"Script {script.id} não encontrado.")
            if linha["pasta_id"] != script.pasta_id:
                raise ErroDominio("A edição do script deve preservar sua pasta.")
            conexao.execute(
                "UPDATE scripts SET titulo = ?, conteudo = ? WHERE id = ?",
                (script.titulo, script.conteudo, script.id),
            )

    def excluir(self, script_id: int) -> None:
        with self._banco.transacao() as conexao:
            cursor = conexao.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
            if cursor.rowcount == 0:
                raise EntidadeNaoEncontrada(f"Script {script_id} não encontrado.")
