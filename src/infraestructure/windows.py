"""Inserção no destino original via Win32 e confirmação por UI Automation."""

import ctypes as c
from ctypes import wintypes as w
import os
import time

from infraestructure.uia import Automacao, CampoTexto


def normalizar(texto: str) -> str:
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def confirmar_texto(esperado: str, atual: str, espacos_web=False) -> bool:
    esperado, atual = normalizar(esperado), normalizar(atual)
    if esperado == atual:
        return True
    if not espacos_web or len(esperado) != len(atual):
        return False
    # Editores HTML podem converter um espaço comum para NBSP ao colar.
    # A equivalência é direcional: não apaga espaços, quebras ou caracteres,
    # nem transforma um NBSP solicitado pelo usuário em espaço comum.
    return all(e == a or (e == " " and a == "\u00a0") for e, a in zip(esperado, atual))


def confirmar_substituicao(original: str, inserido: str, atual: str) -> bool:
    """Confere uma inserção/substituição contígua preservando todo o entorno.

    Usado somente por ValuePattern, que não disponibiliza offsets de seleção.
    Não basta encontrar o script no campo: o restante precisa corresponder ao
    original, permitindo apenas a substituição de um intervalo selecionado.
    """
    original, inserido, atual = map(normalizar, (original, inserido, atual))
    if not inserido or atual == original or len(atual) - len(inserido) > len(original):
        return False
    prefixo = 0
    for antes, depois in zip(original, atual):
        if antes != depois:
            break
        prefixo += 1
    sufixo = 0
    for antes, depois in zip(reversed(original), reversed(atual)):
        if antes != depois:
            break
        sufixo += 1
    inicio = max(0, len(atual) - len(inserido) - sufixo)
    fim = min(prefixo, len(atual) - len(inserido))
    return inicio <= fim and atual.find(inserido, inicio, fim + len(inserido)) >= 0


class _Teclado(c.Structure):
    _fields_ = [("vk", w.WORD), ("scan", w.WORD), ("flags", w.DWORD),
                ("tempo", w.DWORD), ("extra", c.c_size_t)]


class _Mouse(c.Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG), ("dados", w.DWORD),
                ("flags", w.DWORD), ("tempo", w.DWORD), ("extra", c.c_size_t)]


class _Hardware(c.Structure):
    _fields_ = [("mensagem", w.DWORD), ("baixo", w.WORD), ("alto", w.WORD)]


class _Evento(c.Union):
    _fields_ = [("teclado", _Teclado), ("mouse", _Mouse), ("hardware", _Hardware)]


class _Input(c.Structure):
    _anonymous_ = ("evento",)
    _fields_ = [("tipo", w.DWORD), ("evento", _Evento)]


class _InfoGUI(c.Structure):
    _fields_ = [("tamanho", w.DWORD), ("flags", w.DWORD),
                ("ativo", w.HWND), ("foco", w.HWND), ("captura", w.HWND),
                ("menu", w.HWND), ("movendo", w.HWND), ("cursor", w.HWND),
                ("retangulo", w.RECT)]


class APIWindows:
    def __init__(self):
        self.user = c.WinDLL("user32", use_last_error=True)
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        assinaturas = {
            "GetForegroundWindow": ([], w.HWND),
            "GetWindowThreadProcessId": ([w.HWND, c.POINTER(w.DWORD)], w.DWORD),
            "GetGUIThreadInfo": ([w.DWORD, c.POINTER(_InfoGUI)], w.BOOL),
            "GetClassNameW": ([w.HWND, w.LPWSTR, c.c_int], c.c_int),
            "GetWindowTextW": ([w.HWND, w.LPWSTR, c.c_int], c.c_int),
            "GetAncestor": ([w.HWND, w.UINT], w.HWND),
            "GetWindowLongW": ([w.HWND, c.c_int], w.LONG),
            "IsWindowEnabled": ([w.HWND], w.BOOL),
            "SetFocus": ([w.HWND], w.HWND),
            "AttachThreadInput": ([w.DWORD, w.DWORD, w.BOOL], w.BOOL),
            "SendMessageTimeoutW": ([w.HWND, w.UINT, w.WPARAM, w.LPARAM,
                                      w.UINT, w.UINT, c.POINTER(c.c_size_t)], w.LPARAM),
            "IsWindow": ([w.HWND], w.BOOL),
            "IsWindowVisible": ([w.HWND], w.BOOL),
            "SetForegroundWindow": ([w.HWND], w.BOOL),
            "GetAsyncKeyState": ([c.c_int], c.c_short),
            "SendInput": ([w.UINT, c.POINTER(_Input), c.c_int], w.UINT),
            "OpenClipboard": ([w.HWND], w.BOOL),
            "EmptyClipboard": ([], w.BOOL),
            "CloseClipboard": ([], w.BOOL),
            "SetClipboardData": ([w.UINT, w.HANDLE], w.HANDLE),
            "CreateWindowExW": ([w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                 c.c_int, c.c_int, c.c_int, c.c_int,
                                 w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p], w.HWND),
            "DestroyWindow": ([w.HWND], w.BOOL),
        }
        for nome, (argumentos, retorno) in assinaturas.items():
            funcao = getattr(self.user, nome)
            funcao.argtypes, funcao.restype = argumentos, retorno
        for nome, argumentos, retorno in (
            ("GlobalAlloc", [w.UINT, c.c_size_t], w.HGLOBAL),
            ("GlobalLock", [w.HGLOBAL], c.c_void_p),
            ("GlobalUnlock", [w.HGLOBAL], w.BOOL),
            ("GlobalFree", [w.HGLOBAL], w.HGLOBAL),
            ("GetCurrentThreadId", [], w.DWORD),
        ):
            funcao = getattr(self.kernel, nome)
            funcao.argtypes, funcao.restype = argumentos, retorno
        self.dono_clipboard = None

    def fechar(self):
        if self.dono_clipboard:
            self.user.DestroyWindow(self.dono_clipboard)
            self.dono_clipboard = None

    def janela_atual(self):
        return self.user.GetForegroundWindow()

    def classe_janela(self, janela):
        nome = c.create_unicode_buffer(256)
        self.user.GetClassNameW(janela, nome, len(nome))
        return nome.value

    def titulo_janela(self, janela):
        titulo = c.create_unicode_buffer(512)
        self.user.GetWindowTextW(janela, titulo, len(titulo))
        return titulo.value

    def foco(self, janela):
        thread = self.user.GetWindowThreadProcessId(janela, None)
        informacao = _InfoGUI(tamanho=c.sizeof(_InfoGUI))
        if not thread or not self.user.GetGUIThreadInfo(thread, c.byref(informacao)):
            raise OSError("O campo originalmente em foco está indisponível.")
        return informacao.foco

    def mensagem(self, janela, codigo, parametro=0, outro=0):
        resultado = c.c_size_t()
        if not self.user.SendMessageTimeoutW(janela, codigo, parametro, outro,
                                             2, 300, c.byref(resultado)):
            raise OSError("O campo de texto não respondeu.")
        return resultado.value

    def capturar_campo_nativo(self, janela):
        foco = self.foco(janela)
        nome = c.create_unicode_buffer(256)
        self.user.GetClassNameW(foco, nome, len(nome))
        if nome.value.lower() != "edit" and not nome.value.lower().startswith("richedit"):
            return None
        return CampoNativo(self, janela, foco)

    def processo(self, janela):
        processo = w.DWORD()
        self.user.GetWindowThreadProcessId(janela, c.byref(processo))
        return processo.value

    def janela_valida(self, janela, processo):
        return bool(self.user.IsWindow(janela) and self.user.IsWindowVisible(janela)
                    and self.processo(janela) == processo)

    def restaurar(self, janela):
        self.user.SetForegroundWindow(janela)
        limite = time.monotonic() + 0.4
        while self.janela_atual() != janela and time.monotonic() < limite:
            time.sleep(0.02)
        return self.janela_atual() == janela

    def modificadores_livres(self):
        return not any(self.user.GetAsyncKeyState(tecla) & 0x8000
                       for tecla in (0x10, 0x11, 0x12, 0x5b, 0x5c))

    def copiar(self, texto):
        if not self.dono_clipboard:
            # Janela invisível do próprio processo para possuir o clipboard.
            self.dono_clipboard = self.user.CreateWindowExW(
                0, "STATIC", "", 0, 0, 0, 0, 0, w.HWND(-3), None, None, None)
            if not self.dono_clipboard:
                raise c.WinError(c.get_last_error())
        dados = (normalizar(texto).replace("\n", "\r\n") + "\0").encode("utf-16-le")
        memoria = self.kernel.GlobalAlloc(2, len(dados))
        if not memoria:
            raise MemoryError("Não foi possível preparar o texto para inserção.")
        transferida = False
        aberto = False
        try:
            ponteiro = self.kernel.GlobalLock(memoria)
            if not ponteiro:
                raise c.WinError(c.get_last_error())
            try:
                c.memmove(ponteiro, dados, len(dados))
            finally:
                self.kernel.GlobalUnlock(memoria)
            limite = time.monotonic() + 0.3
            while not aberto:
                aberto = bool(self.user.OpenClipboard(self.dono_clipboard))
                if not aberto:
                    if time.monotonic() >= limite:
                        raise OSError("A área de transferência está ocupada.")
                    time.sleep(0.02)
            if not self.user.EmptyClipboard() or not self.user.SetClipboardData(13, memoria):
                raise c.WinError(c.get_last_error())
            transferida = True
        finally:
            if aberto:
                self.user.CloseClipboard()
            if not transferida:
                self.kernel.GlobalFree(memoria)

    def colar(self):
        eventos = (_Input * 4)()
        for evento, (tecla, flags) in zip(eventos, ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2))):
            evento.tipo = 1
            evento.teclado = _Teclado(vk=tecla, flags=flags)
        enviados = self.user.SendInput(4, eventos, c.sizeof(_Input))
        if enviados != 4:
            # Libera teclas em um envio parcial; nunca repete a colagem.
            liberacoes = (_Input * 2)()
            for evento, tecla in zip(liberacoes, (0x56, 0x11)):
                evento.tipo = 1
                evento.teclado = _Teclado(vk=tecla, flags=2)
            self.user.SendInput(2, liberacoes, c.sizeof(_Input))
            return False
        return True


class CampoNativo:
    """Edit/RichEdit: texto e seleção obtidos sem depender de TextPattern."""

    def __init__(self, api, janela, campo):
        self.api, self.janela, self.campo = api, janela, campo
        self.processo = api.processo(campo)
        if not self.editavel():
            raise OSError("O campo é protegido ou somente leitura.")
        self.original = self.ler()
        inicio, fim = w.DWORD(), w.DWORD()
        api.mensagem(campo, 0xb0, c.addressof(inicio), c.addressof(fim))
        self.inicio, self.fim = inicio.value, fim.value
        codificado = self.original.encode("utf-16-le")
        try:
            self.prefixo = codificado[:self.inicio * 2].decode("utf-16-le")
            self.sufixo = codificado[self.fim * 2:].decode("utf-16-le")
        except UnicodeError as erro:
            raise OSError("Não foi possível preservar a seleção Unicode.") from erro

    def fechar(self):
        pass

    def editavel(self):
        estilo = self.api.user.GetWindowLongW(self.campo, -16)
        return (self.api.janela_valida(self.campo, self.processo)
                and self.api.user.GetAncestor(self.campo, 2) == self.janela
                and bool(self.api.user.IsWindowEnabled(self.campo))
                and not (estilo & (0x800 | 0x20)))

    def ler(self):
        tamanho = self.api.mensagem(self.campo, 0x0e)
        buffer = c.create_unicode_buffer(tamanho + 1)
        self.api.mensagem(self.campo, 0x0d, len(buffer), c.addressof(buffer))
        return buffer.value

    def restaurar(self):
        atual = self.api.kernel.GetCurrentThreadId()
        destino = self.api.user.GetWindowThreadProcessId(self.campo, None)
        conectado = atual != destino
        if conectado and not self.api.user.AttachThreadInput(atual, destino, True):
            raise OSError("Não foi possível restaurar o foco do campo.")
        try:
            self.api.user.SetFocus(self.campo)
            self.api.mensagem(self.campo, 0xb1, self.inicio, self.fim)
        finally:
            if conectado:
                self.api.user.AttachThreadInput(atual, destino, False)

    def esta_focado(self):
        if self.api.foco(self.janela) != self.campo:
            return False
        inicio, fim = w.DWORD(), w.DWORD()
        self.api.mensagem(self.campo, 0xb0, c.addressof(inicio), c.addressof(fim))
        return (inicio.value, fim.value) == (self.inicio, self.fim)


class InsercaoWindows:
    def __init__(self, api=None):
        self.api = api
        self.automacao = None
        self.campo = None
        self.janela = None
        self.processo = None
        self.tentou_colar = False
        self.erro_captura = None
        self.motivo_recusa = ""

    @classmethod
    def capturar(cls, origem=None):
        """Chamar antes de criar qualquer janela ou inicializar o banco."""
        instancia = cls()
        try:
            instancia.api = APIWindows()
            instancia.janela = instancia.api.janela_atual()
            instancia.processo = instancia.api.processo(instancia.janela)
            if not instancia.janela or instancia.processo == os.getpid():
                instancia.erro_captura = "Não havia uma janela externa ativa ao iniciar."
                return instancia
            if origem is not None:
                if ((instancia.janela, instancia.processo) != (origem.janela, origem.processo)
                        or (origem.controle and instancia.api.foco(instancia.janela) != origem.controle)):
                    instancia.erro_captura = "O destino mudou antes da preparação da inserção."
                    return instancia
            try:
                instancia.campo = instancia.api.capturar_campo_nativo(instancia.janela)
            except OSError:
                # Alguns RichEdit modernos não implementam as mensagens clássicas.
                # Isso não impede tentar o provedor de acessibilidade do mesmo campo.
                instancia.campo = None
            if instancia.campo is None:
                instancia.automacao = Automacao()
                instancia.automacao.id_foco_esperado = origem.id_uia if origem is not None else None
                try:
                    instancia.automacao.controle_foco = instancia.api.foco(instancia.janela)
                except OSError:
                    pass  # A consulta global ainda pode identificar o campo.
                # Navegadores podem ativar a árvore de acessibilidade sob demanda.
                # A primeira consulta pode devolver a janela/documento, antes do
                # campo realmente focado. Aguarda brevemente, sem trocar de janela.
                for tentativa in range(4):
                    if instancia.api.janela_atual() != instancia.janela:
                        raise OSError("A janela original perdeu o foco durante a captura.")
                    try:
                        instancia.campo = instancia.automacao.capturar_campo()
                        break
                    except OSError:
                        if tentativa == 3:
                            raise
                        time.sleep(0.08)
            if instancia.api.janela_atual() != instancia.janela:
                instancia.campo.fechar()
                instancia.campo = None
                instancia.erro_captura = "A janela original mudou durante a captura."
        except OSError as erro:
            instancia.erro_captura = str(erro)
            instancia.fechar()
        return instancia

    def fechar(self):
        if self.campo is not None:
            self.campo.fechar()
            self.campo = None
        if self.automacao is not None:
            self.automacao.fechar()
            self.automacao = None
        if self.api is not None:
            self.api.fechar()

    def destino_valido(self):
        try:
            if self.campo is None:
                self.motivo_recusa = self.erro_captura or "Nenhum campo compatível foi capturado ao iniciar."
            elif self.tentou_colar:
                self.motivo_recusa = "Uma colagem já foi tentada nesta sessão. Reabra o programa para evitar duplicação."
            elif not self.api.janela_valida(self.janela, self.processo):
                self.motivo_recusa = "A janela de destino foi fechada ou não está visível."
            elif not self.campo.editavel():
                self.motivo_recusa = "O campo deixou de estar disponível para edição."
            elif normalizar(self.campo.ler()) != normalizar(self.campo.original):
                self.motivo_recusa = "O texto do campo mudou desde que o programa foi aberto."
            else:
                self.motivo_recusa = ""
                return True
            return False
        except OSError as erro:
            self.motivo_recusa = str(erro)
            return False

    def diagnostico_falha(self):
        return self.motivo_recusa or self.erro_captura or ""

    def _recusar(self, motivo):
        self.motivo_recusa = motivo
        return False

    def _recusar_foco(self, motivo):
        detalhe = getattr(self.campo, "motivo_foco", "")
        if isinstance(detalhe, str) and detalhe:
            motivo += " " + detalhe
        return self._recusar(motivo)

    def inserir(self, conteudo):
        if not conteudo or "\0" in conteudo or not self.destino_valido():
            return False
        esperado = (normalizar(self.campo.prefixo + conteudo + self.campo.sufixo)
                    if self.campo.prefixo is not None else None)
        espacos_web = (isinstance(self.campo, CampoTexto)
                       and self.api.classe_janela(self.janela) == "Chrome_WidgetWin_1")
        if esperado is not None and esperado == normalizar(self.campo.original):
            return False
        etapa = "restaurar a janela de destino"
        try:
            if not self.api.restaurar(self.janela):
                return self._recusar("Não foi possível reativar a janela de destino.")
            etapa = "restaurar o campo e a seleção"
            self.campo.restaurar()
            if not self._foco_correto():
                return self._recusar_foco("O foco ou a seleção não retornou ao campo original.")
            if not self.destino_valido():
                return False
            etapa = "preparar a área de transferência"
            self.api.copiar(conteudo)
            if not self._foco_correto():
                return self._recusar_foco("O foco ou a seleção mudou durante a preparação da colagem.")
            if not self.destino_valido():
                return False
            if not self.api.modificadores_livres():
                return self._recusar("Ainda havia uma tecla modificadora pressionada antes da colagem.")
            self.tentou_colar = True
            etapa = "enviar a colagem"
            if not self.api.colar():
                return self._recusar("O Windows não confirmou o envio completo das teclas de colagem. Confira o campo antes de repetir.")
            etapa = "conferir o resultado pela acessibilidade"
            limite = time.monotonic() + 1
            while True:
                atual = self.campo.ler()
                confirmado = (confirmar_texto(esperado, atual, espacos_web) if esperado is not None else
                              confirmar_substituicao(self.campo.original, conteudo, atual))
                if confirmado:
                    return True
                if time.monotonic() >= limite:
                    return self._recusar("A colagem foi solicitada, mas o texto retornado pela acessibilidade não confirmou o resultado esperado. Confira se o texto apareceu antes de repetir.")
                time.sleep(0.025)
        except OSError as erro:
            return self._recusar(f"Falha ao {etapa}: {erro}")

    def _foco_correto(self):
        return (self.api.janela_atual() == self.janela
                and self.api.janela_valida(self.janela, self.processo)
                and self.campo.esta_focado())
