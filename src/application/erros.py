"""Erros dos casos de uso que a interface poderá apresentar ao usuário."""


class EntidadeNaoEncontrada(LookupError):
    """A pasta ou o script solicitado não existe."""


class ConfirmacaoNecessaria(ValueError):
    """A exclusão depende de confirmação explícita do usuário."""
