from dataclasses import dataclass


@dataclass
class Pasta:
    """Agrupamento de scripts, incluindo pastas protegidas do sistema."""

    id: int
    nome: str
    sistema: bool
