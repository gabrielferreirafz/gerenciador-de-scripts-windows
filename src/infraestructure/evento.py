"""Sinal de encerramento entre receptor e interface, sem arquivos de estado."""

import ctypes as c
from ctypes import wintypes as w
from uuid import uuid4


class EventoParada:
    def __init__(self, nome=None):
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateEventW.argtypes = [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
        self.kernel.CreateEventW.restype = w.HANDLE
        self.kernel.OpenEventW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]
        self.kernel.OpenEventW.restype = w.HANDLE
        self.kernel.SetEvent.argtypes = [w.HANDLE]
        self.kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        self.kernel.WaitForSingleObject.restype = w.DWORD
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.nome = nome or "Local\\GerenciadorScripts.Interface." + uuid4().hex
        self.handle = (self.kernel.OpenEventW(0x100000, False, nome) if nome else
                       self.kernel.CreateEventW(None, True, False, self.nome))
        if not self.handle:
            raise c.WinError(c.get_last_error())

    def sinalizado(self):
        resultado = self.kernel.WaitForSingleObject(self.handle, 0)
        if resultado == 0xffffffff:
            raise c.WinError(c.get_last_error())
        return resultado == 0

    def sinalizar(self):
        if not self.kernel.SetEvent(self.handle):
            raise c.WinError(c.get_last_error())

    def fechar(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
