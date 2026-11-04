"""Exibição do painel compacto sem ícone na barra de tarefas."""

import ctypes
from ctypes import wintypes
import sys
import tkinter as tk


def mostrar_painel(janela: tk.Tk) -> None:
    """Solicita exibição sem ativação para a janela já construída e oculta.

    TOOLWINDOW retira o ícone da barra de tarefas; NOACTIVATE evita a
    ativação por clique. A captura ocorre antes de criar o painel, pois
    o Tk ainda pode ativar a janela durante seu ciclo de vida.
    Os diálogos de edição continuam sendo janelas normais.
    """
    if sys.platform != "win32":
        janela.deiconify()
        return

    janela.update_idletasks()
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    user.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user.GetWindowLongW.restype = wintypes.LONG
    user.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user.SetWindowLongW.restype = wintypes.LONG
    user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.UINT]
    user.SetWindowPos.restype = wintypes.BOOL
    hwnd = user.GetAncestor(janela.winfo_id(), 2)  # GA_ROOT: wrapper do Tk.
    estilo = user.GetWindowLongW(hwnd, -20)
    ctypes.set_last_error(0)
    anterior = user.SetWindowLongW(hwnd, -20,
                                  (estilo | 0x08000000 | 0x80) & ~0x40000)
    if not anterior and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    # Evita deiconify (ativação explícita do Tk) e ShowWindow (cujo primeiro
    # comando pode ser substituído pelo modo de exibição enviado pelo atalho).
    # SHOWWINDOW | FRAMECHANGED | NOACTIVATE | NOZORDER | NOMOVE | NOSIZE.
    if not user.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0077):
        raise ctypes.WinError(ctypes.get_last_error())
