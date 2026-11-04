from dataclasses import dataclass, replace

from domain.erros import ErroDominio, PastaProtegida


@dataclass(frozen=True)
class Pasta:
    """Agrupamento de scripts, incluindo pastas protegidas do sistema."""

    id: int
    nome: str
    sistema: bool
    pai_id: int | None = None

    def __post_init__(self) -> None:
        if self.pai_id is not None:
            if type(self.pai_id) is not int or self.pai_id == self.id:
                raise ErroDominio("A pasta deve ter um pai válido e diferente dela mesma.")
            if self.sistema:
                raise PastaProtegida("A pasta do sistema deve permanecer na raiz.")

    def verificar_exclusao(self) -> None:
        if self.sistema:
            raise PastaProtegida("A pasta do sistema não pode ser excluída.")

    def renomear(self, nome: str) -> "Pasta":
        if self.sistema:
            raise PastaProtegida("A pasta do sistema não pode ser renomeada.")
        return replace(self, nome=nome)
