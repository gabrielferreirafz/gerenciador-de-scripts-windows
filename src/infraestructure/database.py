"""Conexões, esquema inicial e transações SQLite."""

from contextlib import contextmanager
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
    """Dados ao lado do projeto, dentro da pasta que agrupa a instalação."""
    projeto = Path(__file__).resolve().parents[2]
    return projeto.parent / "dados" / "gerenciador.sqlite3"


def garantir_geral(conexao: sqlite3.Connection) -> sqlite3.Row:
    """Deve ser chamada dentro de uma transação de escrita."""
    conexao.execute(
        """INSERT INTO pastas (nome, sistema)
           SELECT 'Geral', 1 WHERE NOT EXISTS
           (SELECT 1 FROM pastas WHERE sistema = 1)"""
    )
    return conexao.execute("SELECT * FROM pastas WHERE sistema = 1").fetchone()


def _migrar_ordem(conexao: sqlite3.Connection) -> None:
    migrada = False
    for tabela in ("pastas", "scripts"):
        colunas = {linha["name"] for linha in conexao.execute(f"PRAGMA table_info({tabela})")}
        if "ordem" not in colunas:
            conexao.execute(f"ALTER TABLE {tabela} ADD COLUMN ordem INTEGER NOT NULL DEFAULT 0 CHECK(ordem >= 0)")
            migrada = True
    # Geral pode mudar de posição, mas seus dados e sua proteção são imutáveis.
    conexao.execute("DROP TRIGGER IF EXISTS proteger_alteracao_geral")
    conexao.execute("""CREATE TRIGGER proteger_alteracao_geral
        BEFORE UPDATE ON pastas WHEN OLD.sistema = 1 AND (
            NEW.id IS NOT OLD.id OR NEW.nome IS NOT OLD.nome OR
            NEW.sistema IS NOT OLD.sistema OR NEW.pai_id IS NOT OLD.pai_id)
        BEGIN SELECT RAISE(ABORT, 'A pasta Geral nao pode ser alterada.'); END""")
    if migrada:
        # Preserva a exibição anterior: pastas primeiro, depois os scripts.
        niveis = [None] + [linha[0] for linha in conexao.execute("SELECT id FROM pastas")]
        for pai_id in niveis:
            pastas = [("pastas", linha[0]) for linha in conexao.execute(
                "SELECT id FROM pastas WHERE pai_id IS ? ORDER BY sistema DESC, id", (pai_id,))]
            scripts = [("scripts", linha[0]) for linha in conexao.execute(
                "SELECT id FROM scripts WHERE pasta_id = ? ORDER BY id", (pai_id,))]
            for ordem, (tabela, identificador) in enumerate(pastas + scripts):
                conexao.execute(f"UPDATE {tabela} SET ordem = ? WHERE id = ?", (ordem, identificador))


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
            # ALTER preserva IDs, scripts e os dados das instalações anteriores.
            colunas = {linha["name"] for linha in conexao.execute("PRAGMA table_info(pastas)")}
            if "pai_id" not in colunas:
                conexao.execute("""ALTER TABLE pastas ADD COLUMN pai_id INTEGER
                    REFERENCES pastas(id) ON DELETE CASCADE
                    CHECK (pai_id IS NULL OR (sistema = 0 AND pai_id <> id))""")
            conexao.execute("CREATE INDEX IF NOT EXISTS pastas_por_pai ON pastas(pai_id)")
            conexao.execute("""CREATE TRIGGER IF NOT EXISTS impedir_ciclo_pastas
                BEFORE UPDATE OF pai_id ON pastas WHEN NEW.pai_id IS NOT NULL
                BEGIN
                    SELECT RAISE(ABORT, 'Uma pasta nao pode conter a si mesma.')
                    WHERE NEW.pai_id IN (
                        WITH RECURSIVE descendentes(id) AS (
                            SELECT OLD.id
                            UNION
                            SELECT p.id FROM pastas p JOIN descendentes d ON p.pai_id = d.id
                        ) SELECT id FROM descendentes
                    );
                END""")
            _migrar_ordem(conexao)
            garantir_geral(conexao)
