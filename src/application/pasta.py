"""Casos de uso de pastas; operações de gerenciamento não encerram a aplicação."""

from application.contratos import RepositorioPastas
from application.erros import ConfirmacaoNecessaria, EntidadeNaoEncontrada
from domain.erros import ErroDominio
from domain.pasta import Pasta


class CasosDeUsoPastas:
    def __init__(self, repositorio: RepositorioPastas) -> None:
        self._repositorio = repositorio

    def garantir_geral(self) -> Pasta:
        """Inicialização idempotente da pasta padrão, sem ID fixo."""
        return self._repositorio.garantir_geral()

    def criar(self, nome: str, pai_id: int | None = None) -> Pasta:
        if pai_id is not None:
            if type(pai_id) is not int:
                raise ErroDominio("A pasta pai deve ser identificada por um ID inteiro.")
            self.obter(pai_id)
        return self._repositorio.criar(nome, pai_id)

    def obter(self, pasta_id: int) -> Pasta:
        pasta = self._repositorio.obter(pasta_id)
        if pasta is None:
            raise EntidadeNaoEncontrada(f"Pasta {pasta_id} não encontrada.")
        return pasta

    def listar(self) -> list[Pasta]:
        self.garantir_geral()
        return self._repositorio.listar()

    def listar_filhas(self, pai_id: int | None = None) -> list[Pasta]:
        """Lista somente o nível solicitado; None representa a raiz."""
        if pai_id is not None:
            self.obter(pai_id)
        return [pasta for pasta in self.listar() if pasta.pai_id == pai_id]

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
            "Todos os scripts associados também serão excluídos, "
            "incluindo todas as subpastas e os scripts dentro delas."
        )

    def excluir(self, pasta_id: int, *, confirmado: bool = False) -> None:
        pasta = self.obter(pasta_id)
        pasta.verificar_exclusao()
        if confirmado is not True:
            raise ConfirmacaoNecessaria(self.solicitar_exclusao(pasta_id))
        self._repositorio.excluir_com_scripts(pasta_id)
