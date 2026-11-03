from dataclasses import dataclass


@dataclass
class Script:
    """Mensagem textual reutilizável vinculada a uma única pasta."""

    id: int
    titulo: str
    conteudo: str
    pasta_id: int
