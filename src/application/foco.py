"""Dados da captura de foco, sem leitura ou inserção do texto do destino."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FocoCapturado:
    janela: int | None = None
    titulo_janela: str = ""
    classe_janela: str = ""
    processo: int | None = None
    controle: int | None = None
    classe_controle: str = ""
    tipo_uia: int | None = None
    classe_uia: str = ""
    processo_uia: int | None = None
    tem_foco_uia: bool | None = None
    area_uia: tuple[float, float, float, float] | None = None
    id_uia: tuple[int, ...] | None = None
    campo_estavel: bool | None = None
    janela_estavel: bool = False
    erro_win32: str = ""
    erro_uia: str = ""
