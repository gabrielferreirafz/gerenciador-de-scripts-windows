"""Gestos dos cartões: clique no release, arraste com limiar e rolagem local."""

import tkinter as tk
from tkinter import ttk

from presentation.tema import BORDA, DESTAQUE


class ArrastarCartoes:
    def __init__(self, lista, ao_reordenar):
        self.lista, self.ao_reordenar = lista, ao_reordenar
        self.cartoes = []
        self.ativo = None
        self.arrastando = False
        self.tarefa = None
        self.indicador = tk.Frame(lista.canvas, bg=DESTAQUE, height=2)
        janela = self.janela = lista.winfo_toplevel()
        janela.bind("<Escape>", lambda _: self.cancelar(), add="+")
        janela.bind("<Destroy>", self._destruir, add="+")

    def _destruir(self, evento):
        if evento.widget is self.janela:
            self.cancelar()

    def reiniciar(self):
        self.cancelar()
        self.cartoes.clear()

    def vincular(self, cartao, chave, comando):
        self.cartoes.append((cartao, chave))

        def pressionar(evento):
            self.cancelar()
            self.ativo = (cartao, chave, comando)
            self.inicio = (evento.x_root, evento.y_root)
            self.ponteiro = self.inicio
            return "break"

        def vincular_widget(widget):
            if isinstance(widget, ttk.Button):
                return
            widget.configure(cursor="hand2")
            widget.bind("<ButtonPress-1>", pressionar)
            widget.bind("<B1-Motion>", self._mover)
            widget.bind("<ButtonRelease-1>", self._soltar)
            for filho in widget.winfo_children():
                vincular_widget(filho)
        vincular_widget(cartao)

    def _mover(self, evento):
        if self.ativo is None:
            return
        self.ponteiro = (evento.x_root, evento.y_root)
        if not self.arrastando and max(abs(a-b) for a, b in zip(self.inicio, self.ponteiro)) >= 8:
            self.arrastando = True
            cartao = self.ativo[0]
            cartao.grab_set()
            cartao.itemconfigure(cartao.superficie, outline=DESTAQUE)
            self._rolar()
        if self.arrastando:
            self._indicar()
        return "break"

    def _dentro(self, widget, ponto):
        x, y = ponto
        return (widget.winfo_rootx() <= x < widget.winfo_rootx() + widget.winfo_width()
                and widget.winfo_rooty() <= y < widget.winfo_rooty() + widget.winfo_height())

    def _destino(self):
        outros = [(c, chave) for c, chave in self.cartoes if c is not self.ativo[0]]
        indice = next((i for i, (c, _) in enumerate(outros)
                       if self.ponteiro[1] < c.winfo_rooty() + c.winfo_height()/2), len(outros))
        return outros, indice

    def _indicar(self):
        canvas = self.lista.canvas
        if not self._dentro(canvas, self.ponteiro):
            self.indicador.place_forget()
            return
        outros, indice = self._destino()
        if not outros:
            return
        y = (outros[indice][0].winfo_rooty() if indice < len(outros) else
             outros[-1][0].winfo_rooty() + outros[-1][0].winfo_height())
        self.indicador.place(x=8, y=y-canvas.winfo_rooty(), width=max(1, canvas.winfo_width()-16))
        self.indicador.lift()

    def _rolar(self):
        self.tarefa = None
        if not self.arrastando:
            return
        canvas = self.lista.canvas
        x, y = self.ponteiro
        if canvas.winfo_rootx() <= x < canvas.winfo_rootx() + canvas.winfo_width():
            local = y - canvas.winfo_rooty()
            if -24 < local < 30:
                canvas.yview_scroll(-1, "units")
            elif canvas.winfo_height()-30 < local < canvas.winfo_height()+24:
                canvas.yview_scroll(1, "units")
            canvas.update_idletasks()
            self._indicar()
        self.tarefa = canvas.after(60, self._rolar)

    def _soltar(self, evento):
        if self.ativo is None:
            return
        self.ponteiro = (evento.x_root, evento.y_root)
        cartao, chave, comando = self.ativo
        arrastando = self.arrastando
        ordem = None
        if arrastando and self._dentro(self.lista.canvas, self.ponteiro):
            outros, indice = self._destino()
            ordem = [item for _, item in outros]
            ordem.insert(indice, chave)
            if ordem == [item for _, item in self.cartoes]:
                ordem = None
        clique = not arrastando and self._dentro(cartao, self.ponteiro)
        self.cancelar()
        if ordem is not None:
            self.ao_reordenar(ordem)
        elif clique:
            comando()
        return "break"

    def cancelar(self):
        if self.tarefa is not None:
            try:
                self.lista.canvas.after_cancel(self.tarefa)
            except tk.TclError:
                pass  # A janela pode estar destruindo os comandos Tcl.
            self.tarefa = None
        if self.ativo is not None:
            cartao = self.ativo[0]
            if cartao.winfo_exists():
                if cartao.grab_current() is cartao:
                    cartao.grab_release()
                cartao.itemconfigure(cartao.superficie, outline=BORDA)
        if self.indicador.winfo_exists():
            self.indicador.place_forget()
        self.ativo = None
        self.arrastando = False
