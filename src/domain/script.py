from dataclasses import dataclass, replace

from domain.erros import ErroDominio


@dataclass(frozen=True)
class Script:
    """Mensagem textual reutilizável vinculada a uma única pasta."""

    id: int
    titulo: str
    conteudo: str
    pasta_id: int
    ordem: int = 0

    def __post_init__(self) -> None:
        if type(self.pasta_id) is not int:
            raise ErroDominio("O script deve estar associado a uma única pasta por ID.")

    def editar(self, titulo: str, conteudo: str) -> "Script":
        """Atualiza o texto preservando a pasta definida no cadastro."""
        return replace(self, titulo=titulo, conteudo=conteudo)
