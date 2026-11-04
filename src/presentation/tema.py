"""Paleta e componentes visuais da janela compacta."""

import ctypes
from collections import Counter
import sys
import tkinter as tk
from tkinter import ttk

FUNDO = "#202020"
CARTAO = "#2b2b2b"
CAMPO = "#191919"
BORDA = "#414141"
TEXTO = "#f5f5f5"
SECUNDARIO = "#b5b5b5"
DESTAQUE = "#9cceff"
FONTE = "Segoe UI"


def aplicar_tema(janela: tk.Tk) -> None:
    janela.configure(bg=FUNDO)
    janela.option_add("*Font", (FONTE, 10))
    estilo = ttk.Style(janela)
    estilo.theme_use("clam")
    estilo.configure("TButton", background=CARTAO, foreground=TEXTO,
                     borderwidth=0, padding=(12, 8), focusthickness=1,
                     focuscolor=DESTAQUE)
    estilo.map("TButton", background=[("active", "#3b3b3b"), ("pressed", BORDA)],
               foreground=[("disabled", "#777777")])
    estilo.configure("Destaque.TButton", background=DESTAQUE, foreground="#102236")
    estilo.map("Destaque.TButton", background=[("active", "#baddff")],
               foreground=[("disabled", "#777777")])
    estilo.configure("Perigo.TButton", foreground="#ffb4b4")
    estilo.configure("TEntry", fieldbackground=CAMPO, foreground=TEXTO,
                     insertcolor=TEXTO, bordercolor=BORDA, padding=8)
    estilo.map("TEntry", bordercolor=[("focus", DESTAQUE)])
    estilo.configure("TCombobox", fieldbackground=CAMPO, background=CARTAO,
                     foreground=TEXTO, arrowcolor=TEXTO, padding=7,
                     bordercolor=BORDA)
    estilo.map("TCombobox", fieldbackground=[("readonly", CAMPO)],
               foreground=[("disabled", SECUNDARIO), ("readonly", TEXTO)], selectbackground=[("readonly", CAMPO)],
               selectforeground=[("readonly", TEXTO)])
    janela.option_add("*TCombobox*Listbox.background", CARTAO)
    janela.option_add("*TCombobox*Listbox.foreground", TEXTO)
    janela.option_add("*TCombobox*Listbox.selectBackground", BORDA)
    janela.option_add("*TCombobox*Listbox.selectForeground", TEXTO)
    estilo.configure("Vertical.TScrollbar", background=BORDA, troughcolor=FUNDO,
                     borderwidth=0, arrowsize=10)
    _botoes_arredondados(janela, estilo)


def _botoes_arredondados(janela: tk.Tk, estilo: ttk.Style) -> None:
    """Mantém botões ttk nativos com uma superfície arredondada extensível."""
    imagens = []

    def superficie(cor, contorno):
        tamanho, raio = 26, 12
        imagem = tk.PhotoImage(master=janela, width=tamanho, height=tamanho)
        for y in range(tamanho):
            for x in range(tamanho):
                cx = min(max(x, raio), tamanho - 1 - raio)
                cy = min(max(y, raio), tamanho - 1 - raio)
                distancia = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if distancia <= raio:
                    borda = distancia > raio - 1 or x in (0, tamanho-1) or y in (0, tamanho-1)
                    imagem.put(contorno if borda else cor, (x, y))
        imagens.append(imagem)
        return imagem

    for nome, cor, hover, pressionado, letra in (
        ("Arredondado", CARTAO, "#3b3b3b", BORDA, TEXTO),
        ("ArredondadoDestaque", DESTAQUE, "#baddff", "#80b8ec", "#102236"),
    ):
        elemento = f"{nome}.surface"
        estilo.element_create(
            elemento, "image", superficie(cor, cor),
            ("pressed", superficie(pressionado, pressionado)),
            ("focus", superficie(cor, TEXTO)),
            ("active", superficie(hover, hover)),
            border=12, padding=0, sticky="nsew",
        )
        estilo.layout(f"{nome}.TButton", [(elemento, {
            "sticky": "nsew", "children": [("Button.padding", {
                "sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})],
            })],
        })])
        estilo.configure(f"{nome}.TButton", background=FUNDO, foreground=letra,
                         padding=(8, 4))
        estilo.map(f"{nome}.TButton", background=[("active", FUNDO), ("pressed", FUNDO)])
    # PhotoImage precisa permanecer referenciada enquanto o tema estiver em uso.
    janela._imagens_botoes = imagens


def barra_escura(janela: tk.Misc) -> None:
    """Solicita a barra de título escura do Windows; mantém fallback do Tk."""
    if sys.platform != "win32":
        return
    janela.update_idletasks()
    try:
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [ctypes.c_void_p]
        user32.GetParent.restype = ctypes.c_void_p
        hwnd = user32.GetParent(janela.winfo_id())
        valor = ctypes.c_int(1)
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        dwm.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        dwm(hwnd, 20, ctypes.byref(valor), ctypes.sizeof(valor))
    except (AttributeError, OSError):
        pass


def texto(pai: tk.Misc, conteudo: str, *, tamanho=10, cor=TEXTO,
          negrito=False, **opcoes) -> tk.Label:
    opcoes.setdefault("anchor", "w")
    return tk.Label(pai, text=conteudo, bg=pai.cget("bg"), fg=cor,
                    font=(FONTE, tamanho, "bold" if negrito else "normal"),
                    justify="left", **opcoes)


def rotulos_pastas(pastas) -> list[str]:
    """Distingue nomes repetidos sem expor identificadores do banco."""
    totais = Counter(p.nome or "Sem nome" for p in pastas if not p.sistema)
    ocorrencias = Counter()
    rotulos = []
    for pasta in pastas:
        nome = pasta.nome or "Sem nome"
        ocorrencias[nome] += not pasta.sistema
        sufixo = " · padrão" if pasta.sistema else (
            f" ({ocorrencias[nome]})" if totais[nome] > 1 else "")
        rotulos.append(nome + sufixo)
    por_id = {p.id: p for p in pastas}
    por_id_rotulo = {p.id: rotulo for p, rotulo in zip(pastas, rotulos)}
    caminhos = []
    for pasta in pastas:
        partes = [por_id_rotulo[pasta.id]]
        while pasta.pai_id is not None:
            pasta = por_id[pasta.pai_id]
            partes.append(por_id_rotulo[pasta.id])
        caminhos.append(" / ".join(reversed(partes)))
    return caminhos


class Cartao(tk.Canvas):
    """Superfície arredondada com conteúdo Tk e altura automática."""

    def __init__(self, pai: tk.Misc):
        super().__init__(pai, bg=FUNDO, highlightthickness=0, height=80)
        self.superficie = self.create_polygon(0, 0, 0, 0, smooth=True,
                                              fill=CARTAO, outline=BORDA)
        self.corpo = tk.Frame(self, bg=CARTAO)
        self.conteudo = self.create_window(14, 12, anchor="nw", window=self.corpo)
        self.bind("<Configure>", self._dimensionar)
        self.corpo.bind("<Configure>", self._altura)

    def _altura(self, _evento=None):
        altura = self.corpo.winfo_reqheight() + 24
        if int(self.cget("height")) != altura:
            self.configure(height=altura)

    def _dimensionar(self, evento):
        largura, altura, raio = evento.width - 1, evento.height - 1, 14
        self.coords(self.superficie, raio, 1, largura-raio, 1, largura, 1,
                    largura, raio, largura, altura-raio, largura, altura,
                    largura-raio, altura, raio, altura, 1, altura,
                    1, altura-raio, 1, raio, 1, 1)
        self.itemconfigure(self.conteudo, width=max(1, largura - 28))


class ListaRolavel(tk.Frame):
    def __init__(self, pai: tk.Misc):
        super().__init__(pai, bg=FUNDO)
        self.canvas = tk.Canvas(self, bg=FUNDO, highlightthickness=0, bd=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.barra.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.corpo = tk.Frame(self.canvas, bg=FUNDO)
        self.item = self.canvas.create_window(0, 0, window=self.corpo, anchor="nw")
        self.canvas.bind("<Configure>", self._largura)
        self.corpo.bind("<Configure>", lambda _: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

    def _largura(self, evento):
        self.canvas.itemconfigure(self.item, width=evento.width)

    def limpar(self):
        for filho in self.corpo.winfo_children():
            filho.destroy()
        self.canvas.yview_moveto(0)

    def rolar(self, evento):
        if self.corpo.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if evento.delta > 0 else 1, "units")
