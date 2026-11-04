"""Contratos implementados pelos adaptadores SQLite e Windows."""

from typing import Protocol

from domain.pasta import Pasta
from domain.script import Script


class RepositorioPastas(Protocol):
    def garantir_geral(self) -> Pasta:
        """Retorna a única Geral protegida, criando-a atomicamente se necessário.

        Não identifica Geral apenas pelo nome nem pressupõe um ID fixo.
        """
        ...

    def criar(self, nome: str, pai_id: int | None = None) -> Pasta:
        """Persiste uma pasta do usuário (sistema=False) e retorna seu ID."""
        ...

    def obter(self, pasta_id: int) -> Pasta | None: ...

    def listar(self) -> list[Pasta]: ...

    def atualizar(self, pasta: Pasta) -> None: ...

    def excluir_com_scripts(self, pasta_id: int) -> None:
        """Exclui pasta, descendentes e scripts atomicamente.

        O adaptador deve preservar integridade referencial e proteção da Geral.
        """
        ...


class RepositorioScripts(Protocol):
    def criar(self, titulo: str, conteudo: str, pasta_id: int) -> Script:
        """Persiste o script com pasta existente e retorna a entidade com ID."""
        ...

    def obter(self, script_id: int) -> Script | None: ...

    def listar(self, pasta_id: int | None = None) -> list[Script]:
        """Lista todos os scripts ou somente os da pasta informada."""
        ...

    def atualizar(self, script: Script) -> None: ...

    def excluir(self, script_id: int) -> None: ...


class InsercaoTexto(Protocol):
    """Integração vinculada ao destino capturado antes de abrir a interface.

    O adaptador guarda esse destino durante a sessão, independentemente da
    aplicação de origem. Não deve substituí-lo pelo foco atual da interface.
    """

    def destino_valido(self) -> bool: ...

    def diagnostico_falha(self) -> str:
        """Explica a recusa sem incluir texto, título ou conteúdo do destino."""
        ...

    def inserir(self, conteudo: str) -> bool:
        """Revalida o destino, restaura o foco e tenta inserir o texto.

        Retorna True quando o Windows aceita o envio das teclas de colagem.
        Não lê o campo depois da colagem nem confirma o conteúdo inserido.
        Retorna False se o destino for inválido ou o envio falhar.
        """
        ...
