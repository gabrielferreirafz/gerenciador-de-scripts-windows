"""Ordenação de pastas e scripts dentro de um mesmo nível."""

from application.contratos import RepositorioOrganizacao
from domain.erros import ErroDominio


class CasosDeUsoOrganizacao:
    def __init__(self, repositorio: RepositorioOrganizacao):
        self._repositorio = repositorio

    def reordenar(self, pasta_id: int | None, itens: list[tuple[str, int]]) -> None:
        if pasta_id is not None and type(pasta_id) is not int:
            raise ErroDominio("O nível deve ser identificado por uma pasta.")
        for tipo, identificador in itens:
            if tipo not in ("pasta", "script") or type(identificador) is not int:
                raise ErroDominio("Item de ordenação inválido.")
        if len(set(itens)) != len(itens):
            raise ErroDominio("A ordem não pode conter itens repetidos.")
        self._repositorio.reordenar(pasta_id, itens)
