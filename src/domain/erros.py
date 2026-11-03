"""Erros de regras de negócio, independentes da interface e persistência."""


class ErroDominio(ValueError):
    """Uma operação viola uma regra do domínio."""


class PastaProtegida(ErroDominio):
    """Pastas do sistema não podem ser renomeadas ou excluídas."""
