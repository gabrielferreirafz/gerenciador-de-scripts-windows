"""Janela inicial para validar a execução sob demanda no Windows."""

import tkinter as tk
from tkinter import ttk


def abrir_interface() -> None:
    janela = tk.Tk()
    janela.title("Gerenciador de Scripts")
    janela.geometry("360x240")
    janela.minsize(300, 180)
    janela.attributes("-topmost", True)
    janela.protocol("WM_DELETE_WINDOW", janela.destroy)

    painel = ttk.Frame(janela, padding=16)
    painel.pack(fill="both", expand=True)
    ttk.Label(painel, text="Gerenciador de Scripts").pack(anchor="w")
    ttk.Label(
        painel,
        text="Aplicação iniciada sob demanda.\nFeche a janela para encerrar.",
        wraplength=300,
    ).pack(anchor="w", pady=(12, 0))

    janela.mainloop()
