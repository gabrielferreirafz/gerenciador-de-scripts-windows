"""Confere a origem entregue pelo receptor antes de abrir a interface."""

from application.foco import FocoCapturado


def mesma_origem(original: FocoCapturado, atual: FocoCapturado) -> bool:
    if original.campo_estavel is False or atual.campo_estavel is False:
        return False
    if not (original.janela and original.processo and original.janela_estavel and atual.janela_estavel):
        return False
    if (original.janela, original.processo, original.controle) != (
            atual.janela, atual.processo, atual.controle):
        return False
    # Metadados ajudam a recusar outro campo que compartilhe o HWND do
    # navegador. Não representam identidade universal de um campo HTML.
    if original.id_uia is not None and original.id_uia != atual.id_uia:
        return False
    if original.id_uia is not None and (original.tem_foco_uia is not True or atual.tem_foco_uia is not True):
        return False
    # A identidade estável permite seguir o mesmo campo quando ele se move.
    nomes = ("tipo_uia", "classe_uia", "processo_uia")
    if original.id_uia is None:
        nomes += ("area_uia",)
    for nome in nomes:
        esperado = getattr(original, nome)
        if esperado is not None and esperado != "" and esperado != getattr(atual, nome):
            return False
    return True
