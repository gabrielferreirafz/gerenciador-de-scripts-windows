"""Conexões, esquema inicial e transações SQLite."""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator


ESQUEMA = (
    """CREATE TABLE IF NOT EXISTS pastas (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL,
        sistema INTEGER NOT NULL CHECK (sistema IN (0, 1)),
        CHECK (sistema = 0 OR nome = 'Geral')
    )""",
    """CREATE UNIQUE INDEX IF NOT EXISTS unica_pasta_sistema
        ON pastas(sistema) WHERE sistema = 1""",
    """CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY,
        titulo TEXT NOT NULL,
        conteudo TEXT NOT NULL,
        pasta_id INTEGER NOT NULL REFERENCES pastas(id) ON DELETE CASCADE
    )""",
    """CREATE INDEX IF NOT EXISTS scripts_por_pasta ON scripts(pasta_id)""",
    """CREATE TRIGGER IF NOT EXISTS proteger_exclusao_geral
        BEFORE DELETE ON pastas WHEN OLD.sistema = 1
        BEGIN SELECT RAISE(ABORT, 'A pasta Geral nao pode ser excluida.'); END""",
    """CREATE TRIGGER IF NOT EXISTS proteger_alteracao_geral
        BEFORE UPDATE ON pastas WHEN OLD.sistema = 1
        BEGIN SELECT RAISE(ABORT, 'A pasta Geral nao pode ser alterada.'); END""",
)


def caminho_padrao() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("A pasta LOCALAPPDATA do Windows não foi encontrada.")
    return Path(local_app_data) / "GerenciadorScripts" / "gerenciador.sqlite3"


def garantir_geral(conexao: sqlite3.Connection) -> sqlite3.Row:
    """Deve ser chamada dentro de uma transação de escrita."""
    conexao.execute(
        """INSERT INTO pastas (nome, sistema)
           SELECT 'Geral', 1 WHERE NOT EXISTS
           (SELECT 1 FROM pastas WHERE sistema = 1)"""
    )
    return conexao.execute("SELECT * FROM pastas WHERE sistema = 1").fetchone()


class BancoDados:
    def __init__(self, caminho: str | Path | None = None) -> None:
        self.caminho = Path(caminho) if caminho is not None else caminho_padrao()

    @contextmanager
    def conectar(self) -> Iterator[sqlite3.Connection]:
        """Abre uma conexão por operação e sempre libera o arquivo ao sair."""
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(
            self.caminho, timeout=5, isolation_level=None,
            autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL,
        )
        try:
            conexao.row_factory = sqlite3.Row
            conexao.execute("PRAGMA foreign_keys = ON")
            conexao.execute("PRAGMA synchronous = FULL")
            yield conexao
        finally:
            conexao.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        """Confirma tudo ao concluir ou desfaz tudo em caso de exceção."""
        with self.conectar() as conexao:
            conexao.execute("BEGIN IMMEDIATE")
            try:
                yield conexao
                conexao.commit()
            except BaseException:
                conexao.rollback()
                raise

    def inicializar(self) -> None:
        """Cria o esquema e Geral atomicamente; pode ser repetida sem apagar dados."""
        with self.transacao() as conexao:
            for comando in ESQUEMA:
                conexao.execute(comando)
            garantir_geral(conexao)
