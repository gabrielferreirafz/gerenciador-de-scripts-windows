"""Portas implementadas futuramente pelos adaptadores SQLite e Windows."""

from typing import Protocol

from domain.pasta import Pasta
from domain.script import Script


class RepositorioPastas(Protocol):
    def garantir_geral(self) -> Pasta:
        """Retorna a única Geral protegida, criando-a atomicamente se necessário.

        Não identifica Geral apenas pelo nome nem pressupõe um ID fixo.
        """
        ...

    def criar(self, nome: str) -> Pasta:
        """Persiste uma pasta do usuário (sistema=False) e retorna seu ID."""
        ...

    def obter(self, pasta_id: int) -> Pasta | None: ...

    def listar(self) -> list[Pasta]: ...

    def atualizar(self, pasta: Pasta) -> None: ...

    def excluir_com_scripts(self, pasta_id: int) -> None:
        """Exclui pasta e scripts atomicamente, revertendo tudo em caso de falha.

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

    def inserir(self, conteudo: str) -> bool:
        """Revalida o destino, restaura o foco e tenta inserir o texto.

        Retorna True somente quando a inserção for reconhecida como bem-sucedida.
        Enviar eventos de teclado, por si só, não comprova sucesso. Retorna False
        em falha ou resultado incerto, inclusive se o destino deixar de ser válido.
        """
        ...
