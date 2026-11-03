"""Casos de uso de pastas; operações de gerenciamento não encerram a aplicação."""

from application.contratos import RepositorioPastas
from application.erros import ConfirmacaoNecessaria, EntidadeNaoEncontrada
from domain.pasta import Pasta


class CasosDeUsoPastas:
    def __init__(self, repositorio: RepositorioPastas) -> None:
        self._repositorio = repositorio

    def garantir_geral(self) -> Pasta:
        """Inicialização idempotente da pasta padrão, sem ID fixo."""
        return self._repositorio.garantir_geral()

    def criar(self, nome: str) -> Pasta:
        return self._repositorio.criar(nome)

    def obter(self, pasta_id: int) -> Pasta:
        pasta = self._repositorio.obter(pasta_id)
        if pasta is None:
            raise EntidadeNaoEncontrada(f"Pasta {pasta_id} não encontrada.")
        return pasta

    def listar(self) -> list[Pasta]:
        self.garantir_geral()
        return self._repositorio.listar()

    def renomear(self, pasta_id: int, nome: str) -> Pasta:
        pasta = self.obter(pasta_id).renomear(nome)
        self._repositorio.atualizar(pasta)
        return pasta

    def solicitar_exclusao(self, pasta_id: int) -> str:
        """Fornece o aviso que a interface deve exibir antes da confirmação."""
        pasta = self.obter(pasta_id)
        pasta.verificar_exclusao()
        return (
            f'Excluir a pasta "{pasta.nome}"? '
            "Todos os scripts associados também serão excluídos."
        )

    def excluir(self, pasta_id: int, *, confirmado: bool = False) -> None:
        pasta = self.obter(pasta_id)
        pasta.verificar_exclusao()
        if confirmado is not True:
            raise ConfirmacaoNecessaria(self.solicitar_exclusao(pasta_id))
        self._repositorio.excluir_com_scripts(pasta_id)
