from dataclasses import dataclass, replace

from domain.erros import PastaProtegida


@dataclass(frozen=True)
class Pasta:
    """Agrupamento de scripts, incluindo pastas protegidas do sistema."""

    id: int
    nome: str
    sistema: bool

    def verificar_exclusao(self) -> None:
        if self.sistema:
            raise PastaProtegida("A pasta do sistema não pode ser excluída.")

    def renomear(self, nome: str) -> "Pasta":
        if self.sistema:
            raise PastaProtegida("A pasta do sistema não pode ser renomeada.")
        return replace(self, nome=nome)
