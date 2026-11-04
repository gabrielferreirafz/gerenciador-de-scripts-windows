"""Receptor Win32 de Ctrl+Alt+Z: espera bloqueante, instância única e ícone nativo."""

import ctypes as c
from ctypes import wintypes as w

CLASSE = "GerenciadorScripts.Receptor.v1"
MUTEX = "Local\\GerenciadorScripts.Receptor.v1"
WNDPROC = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class _ClasseJanela(c.Structure):
    _fields_ = [("estilo", w.UINT), ("procedimento", WNDPROC),
                ("extra_classe", c.c_int), ("extra_janela", c.c_int),
                ("instancia", w.HINSTANCE), ("icone", w.HANDLE),
                ("cursor", w.HANDLE), ("fundo", w.HANDLE),
                ("menu", w.LPCWSTR), ("nome", w.LPCWSTR)]


class _Icone(c.Structure):
    _fields_ = [("tamanho", w.DWORD), ("janela", w.HWND), ("id", w.UINT),
                ("flags", w.UINT), ("mensagem", w.UINT), ("icone", w.HANDLE),
                ("dica", w.WCHAR * 128), ("estado", w.DWORD), ("mascara", w.DWORD),
                ("informacao", w.WCHAR * 256), ("versao", w.UINT),
                ("titulo", w.WCHAR * 64), ("tipo", w.DWORD),
                ("guid", c.c_byte * 16), ("icone_balao", w.HANDLE)]


def _bibliotecas():
    user = c.WinDLL("user32", use_last_error=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    shell = c.WinDLL("shell32", use_last_error=True)
    funcoes = {
        "DefWindowProcW": ([w.HWND, w.UINT, w.WPARAM, w.LPARAM], c.c_ssize_t),
        "RegisterClassW": ([c.POINTER(_ClasseJanela)], w.WORD),
        "UnregisterClassW": ([w.LPCWSTR, w.HINSTANCE], w.BOOL),
        "CreateWindowExW": ([w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                              c.c_int, c.c_int, c.c_int, c.c_int,
                              w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p], w.HWND),
        "DestroyWindow": ([w.HWND], w.BOOL),
        "RegisterHotKey": ([w.HWND, c.c_int, w.UINT, w.UINT], w.BOOL),
        "UnregisterHotKey": ([w.HWND, c.c_int], w.BOOL),
        "RegisterWindowMessageW": ([w.LPCWSTR], w.UINT),
        "GetMessageW": ([c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT], w.BOOL),
        "TranslateMessage": ([c.POINTER(w.MSG)], w.BOOL),
        "DispatchMessageW": ([c.POINTER(w.MSG)], c.c_ssize_t),
        "PostQuitMessage": ([c.c_int], None),
        "PostMessageW": ([w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
        "FindWindowW": ([w.LPCWSTR, w.LPCWSTR], w.HWND),
        "LoadIconW": ([w.HINSTANCE, c.c_void_p], w.HANDLE),
        "CreatePopupMenu": ([], w.HMENU),
        "AppendMenuW": ([w.HMENU, w.UINT, c.c_size_t, w.LPCWSTR], w.BOOL),
        "TrackPopupMenu": ([w.HMENU, w.UINT, c.c_int, c.c_int, c.c_int,
                             w.HWND, c.c_void_p], w.UINT),
        "DestroyMenu": ([w.HMENU], w.BOOL),
        "GetCursorPos": ([c.POINTER(w.POINT)], w.BOOL),
        "SetForegroundWindow": ([w.HWND], w.BOOL),
    }
    for nome, (argumentos, resultado) in funcoes.items():
        funcao = getattr(user, nome)
        funcao.argtypes, funcao.restype = argumentos, resultado
    kernel.CreateMutexW.argtypes = [c.c_void_p, w.BOOL, w.LPCWSTR]
    kernel.CreateMutexW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
    kernel.GetModuleHandleW.restype = w.HMODULE
    shell.Shell_NotifyIconW.argtypes = [w.DWORD, c.POINTER(_Icone)]
    shell.Shell_NotifyIconW.restype = w.BOOL
    return user, kernel, shell


class ReceptorWindows:
    def __init__(self, ativar, ao_encerrar=lambda: None, *, nome=CLASSE,
                 mutex=MUTEX, bandeja=True):
        self.ativar, self.ao_encerrar = ativar, ao_encerrar
        self.nome, self.nome_mutex = nome, mutex
        self.bandeja = bandeja
        self.user, self.kernel, self.shell = _bibliotecas()
        self.hwnd = self.mutex = None
        self.registrado = self.classe_registrada = self.tem_icone = False
        self.taskbar_created = self.user.RegisterWindowMessageW("TaskbarCreated")
        self.callback = WNDPROC(self._procedimento)
        self.instancia = self.kernel.GetModuleHandleW(None)

    def _icone(self):
        return _Icone(tamanho=c.sizeof(_Icone), janela=self.hwnd, id=1,
                      flags=7, mensagem=0x8001,
                      icone=self.user.LoadIconW(None, c.c_void_p(32512)),
                      dica="Gerenciador de Scripts — Ctrl+Alt+Z")

    def adicionar_icone(self):
        if self.bandeja:
            self.tem_icone = bool(self.shell.Shell_NotifyIconW(0, c.byref(self._icone())))
            if not self.tem_icone:
                raise OSError("Não foi possível adicionar o ícone de encerramento.")

    def avisar(self, mensagem):
        if self.tem_icone:
            icone = self._icone()
            icone.flags = 0x10
            icone.informacao = str(mensagem)[:255]
            icone.titulo = "Gerenciador de Scripts"
            icone.tipo = 3
            self.shell.Shell_NotifyIconW(1, c.byref(icone))

    def _menu(self):
        menu = self.user.CreatePopupMenu()
        if not menu:
            return
        try:
            self.user.AppendMenuW(menu, 1, 0, "Abrir com Ctrl+Alt+Z no campo desejado")
            self.user.AppendMenuW(menu, 0x800, 0, None)
            self.user.AppendMenuW(menu, 0, 1, "Encerrar gerenciador")
            ponto = w.POINT()
            self.user.GetCursorPos(c.byref(ponto))
            self.user.SetForegroundWindow(self.hwnd)
            comando = self.user.TrackPopupMenu(menu, 0x102, ponto.x, ponto.y, 0, self.hwnd, None)
            self.user.PostMessageW(self.hwnd, 0, 0, 0)
            if comando == 1:
                self.user.PostMessageW(self.hwnd, 0x10, 0, 0)
        finally:
            self.user.DestroyMenu(menu)

    def _procedimento(self, hwnd, mensagem, parametro, outro):
        try:
            if mensagem == 0x312 and parametro == 1:
                self.ativar()
                return 0
            if mensagem == 0x8001:
                if outro in (0x205, 0x7b):
                    self._menu()
                return 0
            if mensagem == self.taskbar_created:
                self.adicionar_icone()
                return 0
            if mensagem == 0x10:
                self.ao_encerrar()
                self.user.DestroyWindow(hwnd)
                return 0
            if mensagem == 2:
                self.user.PostQuitMessage(0)
                return 0
        except Exception as erro:
            self.avisar(erro)
            return 0
        return self.user.DefWindowProcW(hwnd, mensagem, parametro, outro)

    def iniciar(self):
        self.mutex = self.kernel.CreateMutexW(None, False, self.nome_mutex)
        erro = c.get_last_error()
        if not self.mutex:
            raise c.WinError(erro)
        if erro == 183:
            self.fechar()
            return False
        try:
            classe = _ClasseJanela(procedimento=self.callback, instancia=self.instancia, nome=self.nome)
            if not self.user.RegisterClassW(c.byref(classe)):
                raise c.WinError(c.get_last_error())
            self.classe_registrada = True
            self.hwnd = self.user.CreateWindowExW(0, self.nome, self.nome, 0,
                                                 0, 0, 0, 0, None, None, self.instancia, None)
            if not self.hwnd:
                raise c.WinError(c.get_last_error())
            # CONTROL | ALT | NOREPEAT, tecla Z.
            if not self.user.RegisterHotKey(self.hwnd, 1, 0x4003, 0x5a):
                raise OSError("Ctrl+Alt+Z já está em uso por outro aplicativo.")
            self.registrado = True
            self.adicionar_icone()
            return True
        except BaseException:
            self.fechar()
            raise

    def executar(self):
        if not self.iniciar():
            return
        try:
            mensagem = w.MSG()
            while True:
                resultado = self.user.GetMessageW(c.byref(mensagem), None, 0, 0)
                if resultado == -1:
                    raise c.WinError(c.get_last_error())
                if resultado == 0:
                    break
                self.user.TranslateMessage(c.byref(mensagem))
                self.user.DispatchMessageW(c.byref(mensagem))
        finally:
            self.fechar()

    def fechar(self):
        if self.tem_icone:
            self.shell.Shell_NotifyIconW(2, c.byref(self._icone()))
            self.tem_icone = False
        if self.registrado:
            self.user.UnregisterHotKey(self.hwnd, 1)
            self.registrado = False
        if self.hwnd:
            self.user.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self.classe_registrada:
            self.user.UnregisterClassW(self.nome, self.instancia)
            self.classe_registrada = False
        if self.mutex:
            self.kernel.CloseHandle(self.mutex)
            self.mutex = None


def encerrar_receptor():
    user, _, _ = _bibliotecas()
    hwnd = user.FindWindowW(CLASSE, None)
    return bool(hwnd and user.PostMessageW(hwnd, 0x10, 0, 0))
