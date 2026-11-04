"""Captura independente de foco: não lê valores e não envia entrada."""

from application.foco import FocoCapturado
from infraestructure.uia import Automacao
from infraestructure.windows import APIWindows


def capturar_foco(api=None, automacao_factory=None) -> FocoCapturado:
    dados = {"campo_estavel": False}
    automacao = None
    api = api if api is not None else APIWindows()
    try:
        janela = api.janela_atual()
        dados["janela"] = janela or None
        if not janela:
            dados["erro_win32"] = "O Windows não informou uma janela ativa."
            return FocoCapturado(**dados)
        dados.update(titulo_janela=api.titulo_janela(janela),
                     classe_janela=api.classe_janela(janela),
                     processo=api.processo(janela))
        try:
            controle = api.foco(janela)
            dados["controle"] = controle or None
            dados["classe_controle"] = api.classe_janela(controle) if controle else ""
            if not controle:
                dados["erro_win32"] = "A janela não informou um controle Win32 em foco."
        except OSError as erro:
            dados["erro_win32"] = str(erro)

        try:
            if api.janela_atual() != janela:
                dados["erro_uia"] = "A janela mudou antes da consulta de acessibilidade."
            else:
                automacao = (automacao_factory or Automacao)()
                automacao.controle_foco = dados.get("controle")
                with automacao.focado_estavel() as elemento:
                    for nome, identificador in (("tipo_uia", 30003), ("tem_foco_uia", 30008),
                                                ("processo_uia", 30002)):
                        dados[nome] = automacao.propriedade(elemento, identificador)
                    dados["classe_uia"] = automacao.classe_elemento(elemento)
                    dados["area_uia"] = automacao.area_elemento(elemento)
                    dados["id_uia"] = automacao.identificador_elemento(elemento)
                    with automacao.focado() as final:
                        if not automacao.mesmo_elemento(elemento, final):
                            raise OSError("O campo mudou durante a leitura dos metadados de foco.")
                    dados["campo_estavel"] = dados.get("tem_foco_uia") is True
                    motivo = getattr(automacao, "motivo_busca_foco", "")
                    if dados.get("tem_foco_uia") is False and isinstance(motivo, str) and motivo:
                        dados["erro_uia"] = motivo
        except OSError as erro:
            dados["erro_uia"] = str(erro)
            for chave in ("tipo_uia", "tem_foco_uia", "processo_uia", "classe_uia", "area_uia", "id_uia"):
                dados.pop(chave, None)
        dados["janela_estavel"] = api.janela_atual() == janela
        if not dados["janela_estavel"]:
            dados["campo_estavel"] = False
            for chave in ("tipo_uia", "tem_foco_uia", "processo_uia", "classe_uia", "area_uia", "id_uia"):
                dados.pop(chave, None)
            dados["erro_uia"] = "A janela mudou durante a captura; o elemento UIA não foi confirmado."
        return FocoCapturado(**dados)
    finally:
        if automacao is not None:
            automacao.fechar()
        api.fechar()
