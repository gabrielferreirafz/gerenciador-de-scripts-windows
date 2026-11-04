"""Janelas modais escuras para cadastro, leitura e confirmação."""

import tkinter as tk
from tkinter import ttk

from domain.pasta import Pasta
from domain.script import Script
from presentation.tema import (FUNDO, CAMPO, BORDA, TEXTO, SECUNDARIO,
                                FONTE, barra_escura, rotulos_pastas, texto)


class Dialogo(tk.Toplevel):
    def __init__(self, pai: tk.Misc, titulo: str):
        super().__init__(pai, bg=FUNDO)
        self.withdraw()
        self.title(titulo)
        self.transient(pai.winfo_toplevel())
        self.resizable(False, False)
        self.corpo = tk.Frame(self, bg=FUNDO, padx=20, pady=18)
        self.corpo.pack(fill="both", expand=True)
        texto(self.corpo, titulo, tamanho=15, negrito=True).pack(anchor="w", pady=(0, 14))
        self.bind("<Escape>", lambda _: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._grab_anterior = self.grab_current()
        self.bind("<Destroy>", self._restaurar_grab)

    def _restaurar_grab(self, evento):
        anterior = self._grab_anterior
        if evento.widget is self and anterior is not None and anterior.winfo_exists():
            anterior.grab_set()

    def mostrar(self):
        self.update_idletasks()
        pai = self.master.winfo_toplevel()
        largura = max(380, self.winfo_reqwidth())
        altura = self.winfo_reqheight()
        x = max(0, min(pai.winfo_rootx() + (pai.winfo_width()-largura)//2,
                       self.winfo_screenwidth()-largura))
        y = max(0, min(pai.winfo_rooty() + (pai.winfo_height()-altura)//2,
                       self.winfo_screenheight()-altura-48))
        self.geometry(f"{largura}x{altura}+{x}+{y}")
        self.deiconify()
        barra_escura(self)
        if not self.winfo_viewable():
            self.wait_visibility()
        self.grab_set()
        self.focus_set()

    def botoes(self) -> tk.Frame:
        linha = tk.Frame(self.corpo, bg=FUNDO)
        linha.pack(fill="x", pady=(18, 0))
        return linha


def informar(pai: tk.Misc, titulo: str, mensagem: str):
    janela = Dialogo(pai, titulo)
    texto(janela.corpo, mensagem, wraplength=340, cor=SECUNDARIO).pack(fill="x")
    ttk.Button(janela.botoes(), text="Entendi", command=janela.destroy,
               style="Destaque.TButton").pack(side="right")
    janela.mostrar()
    janela.wait_window()


def confirmar(pai: tk.Misc, titulo: str, mensagem: str) -> bool:
    janela = Dialogo(pai, titulo)
    resultado = False

    def aceitar():
        nonlocal resultado
        resultado = True
        janela.destroy()

    texto(janela.corpo, mensagem, wraplength=340, cor=SECUNDARIO).pack(fill="x")
    linha = janela.botoes()
    ttk.Button(linha, text="Excluir", style="Perigo.TButton", command=aceitar).pack(side="right")
    cancelar = ttk.Button(linha, text="Cancelar", command=janela.destroy)
    cancelar.pack(side="right", padx=(0, 8))
    janela.mostrar()
    cancelar.focus_set()
    janela.wait_window()
    return resultado


class EditorPasta(Dialogo):
    def __init__(self, pai, ao_salvar, pasta: Pasta | None = None, *, subpasta=False):
        tipo = "subpasta" if subpasta else "pasta"
        super().__init__(pai, f"Renomear {tipo}" if pasta else f"Nova {tipo}")
        texto(self.corpo, "Nome da pasta", cor=SECUNDARIO).pack(anchor="w", pady=(0, 6))
        self.nome = ttk.Entry(self.corpo, width=36)
        self.nome.pack(fill="x")
        self.nome.insert(0, pasta.nome if pasta else "")

        def salvar():
            if ao_salvar(self.nome.get()):
                self.destroy()

        linha = self.botoes()
        ttk.Button(linha, text="Salvar" if pasta else f"Criar {tipo}", command=salvar,
                   style="Destaque.TButton").pack(side="right")
        ttk.Button(linha, text="Cancelar", command=self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda _: salvar())
        self.mostrar()
        self.nome.focus_set()
        self.nome.selection_range(0, "end")


class EditorScript(Dialogo):
    def __init__(self, pai, pastas: list[Pasta], pasta_id: int, ao_salvar,
                 script: Script | None = None):
        super().__init__(pai, "Editar script" if script else "Novo script")
        texto(self.corpo, "Título", cor=SECUNDARIO).pack(anchor="w", pady=(0, 6))
        self.titulo = ttk.Entry(self.corpo, width=39)
        self.titulo.pack(fill="x")
        self.titulo.insert(0, script.titulo if script else "")
        texto(self.corpo, "Pasta", cor=SECUNDARIO).pack(anchor="w", pady=(14, 6))
        self.pasta = ttk.Combobox(self.corpo, state="readonly", values=rotulos_pastas(pastas))
        self.pasta.pack(fill="x")
        self.pasta.current(next(i for i, p in enumerate(pastas) if p.id == pasta_id))
        if script:
            self.pasta.configure(state="disabled")
        texto(self.corpo, "Conteúdo", cor=SECUNDARIO).pack(anchor="w", pady=(14, 6))
        self.conteudo = campo_texto(self.corpo, altura=9)
        self.conteudo.insert("1.0", script.conteudo if script else "")
        texto(self.corpo, "Ctrl+Enter para salvar", tamanho=9, cor=SECUNDARIO).pack(
            anchor="w", pady=(8, 0))

        def salvar():
            if ao_salvar(self.titulo.get(), self.conteudo.get("1.0", "end-1c"),
                         pastas[self.pasta.current()].id):
                self.destroy()

        linha = self.botoes()
        ttk.Button(linha, text="Salvar script", command=salvar,
                   style="Destaque.TButton").pack(side="right")
        ttk.Button(linha, text="Cancelar", command=self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Control-Return>", lambda _: salvar())
        self.mostrar()
        self.titulo.focus_set()


def campo_texto(pai, altura=12) -> tk.Text:
    moldura = tk.Frame(pai, bg=BORDA, padx=1, pady=1)
    moldura.pack(fill="both", expand=True)
    campo = tk.Text(moldura, height=altura, width=39, wrap="word", bg=CAMPO,
                    fg=TEXTO, insertbackground=TEXTO, selectbackground="#365570",
                    relief="flat", font=(FONTE, 10), padx=10, pady=10,
                    undo=True, highlightthickness=0)
    barra = ttk.Scrollbar(moldura, command=campo.yview)
    campo.configure(yscrollcommand=barra.set)
    barra.pack(side="right", fill="y")
    campo.pack(side="left", fill="both", expand=True)
    return campo
