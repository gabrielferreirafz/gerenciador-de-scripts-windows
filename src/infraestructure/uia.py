"""Leitura do campo e da seleção via UI Automation, usando apenas ctypes.

Os índices das interfaces COM seguem UIAutomationClient.h do Windows SDK.
Este módulo não envia texto nem escolhe outro destino durante a sessão.
"""

from contextlib import ExitStack
import ctypes as c
import time
from uuid import UUID


class ErroAutomacao(OSError):
    pass


class GUID(c.Structure):
    _fields_ = [("data1", c.c_uint32), ("data2", c.c_uint16),
                ("data3", c.c_uint16), ("data4", c.c_ubyte * 8)]

    @classmethod
    def de(cls, valor):
        return cls.from_buffer_copy(UUID(valor).bytes_le)


class _DadosVariant(c.Union):
    _fields_ = [("inteiro", c.c_int32), ("booleano", c.c_int16),
                ("alinhamento", c.c_void_p), ("dados", c.c_ubyte * (2 * c.sizeof(c.c_void_p)))]


class _Variant(c.Structure):
    _anonymous_ = ("valor",)
    _fields_ = [("tipo", c.c_uint16), ("reservado", c.c_uint16 * 3),
                ("valor", _DadosVariant)]


class _COM:
    def __init__(self, ponteiro):
        self.ptr = ponteiro if isinstance(ponteiro, c.c_void_p) else c.c_void_p(ponteiro)
        if not self.ptr.value:
            raise ErroAutomacao("Interface de acessibilidade indisponível.")

    def chamar(self, indice, tipos=(), argumentos=()):
        tabela = c.cast(self.ptr, c.POINTER(c.POINTER(c.c_void_p))).contents
        metodo = c.WINFUNCTYPE(c.c_long, c.c_void_p, *tipos)(tabela[indice])
        resultado = metodo(self.ptr, *argumentos)
        if resultado < 0:
            raise ErroAutomacao(f"Falha de acessibilidade: 0x{resultado & 0xffffffff:08x}")

    def objeto(self, indice, tipos=(), argumentos=()):
        saida = c.c_void_p()
        self.chamar(indice, (*tipos, c.POINTER(c.c_void_p)), (*argumentos, c.byref(saida)))
        if not saida.value:
            raise ErroAutomacao(f"Interface de acessibilidade indisponível (método {indice}).")
        return _COM(saida)

    def fechar(self):
        if self.ptr.value:
            tabela = c.cast(self.ptr, c.POINTER(c.POINTER(c.c_void_p))).contents
            c.WINFUNCTYPE(c.c_ulong, c.c_void_p)(tabela[2])(self.ptr)
            self.ptr = c.c_void_p()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()


class Automacao:
    def __init__(self):
        self.ole = c.WinDLL("ole32")
        self.ole.CoInitializeEx.argtypes = [c.c_void_p, c.c_uint32]
        self.ole.CoInitializeEx.restype = c.c_long
        self.ole.CoCreateInstance.argtypes = [c.POINTER(GUID), c.c_void_p, c.c_uint32,
                                             c.POINTER(GUID), c.POINTER(c.c_void_p)]
        self.ole.CoCreateInstance.restype = c.c_long
        self.ole.CoUninitialize.argtypes = []
        self.ole.CoUninitialize.restype = None
        self.automacao = None
        self.controle_foco = None
        self.motivo_busca_foco = ""
        self.inicializada = False
        resultado = self.ole.CoInitializeEx(None, 2)
        if resultado < 0:
            raise ErroAutomacao("Não foi possível inicializar a acessibilidade.")
        self.inicializada = True
        try:
            saida = c.c_void_p()
            resultado = self.ole.CoCreateInstance(
                c.byref(GUID.de("ff48dba4-60ef-4201-aa87-54103eef594e")), None, 1,
                c.byref(GUID.de("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")), c.byref(saida))
            if resultado < 0:
                raise ErroAutomacao("Não foi possível criar o cliente UI Automation.")
            self.automacao = _COM(saida)
            self.oleaut = c.WinDLL("oleaut32")
            self.oleaut.VariantClear.argtypes = [c.POINTER(_Variant)]
            self.oleaut.VariantClear.restype = c.c_long
            self.oleaut.SysStringLen.argtypes = [c.c_void_p]
            self.oleaut.SysStringLen.restype = c.c_uint
            self.oleaut.SysFreeString.argtypes = [c.c_void_p]
            self.oleaut.SysFreeString.restype = None
            self.oleaut.SafeArrayGetLBound.argtypes = [c.c_void_p, c.c_uint, c.POINTER(c.c_long)]
            self.oleaut.SafeArrayGetUBound.argtypes = [c.c_void_p, c.c_uint, c.POINTER(c.c_long)]
            self.oleaut.SafeArrayGetElement.argtypes = [c.c_void_p, c.POINTER(c.c_long), c.c_void_p]
        except OSError:
            self.fechar()
            raise

    def fechar(self):
        if self.automacao is not None:
            self.automacao.fechar()
            self.automacao = None
        if self.inicializada:
            self.ole.CoUninitialize()
            self.inicializada = False

    def focado(self):
        principal = self.automacao.objeto(8)
        controle = getattr(self, "controle_foco", None)
        self.motivo_busca_foco = ""
        if not controle:
            return principal
        try:
            if self.propriedade(principal, 30008):
                return principal
            try:
                alternativo = self._focado_no_controle(controle)
            except OSError as erro:
                self.motivo_busca_foco = str(erro)
                return principal
            principal.fechar()
            return alternativo
        except BaseException:
            principal.fechar()
            raise

    def _focado_no_controle(self, controle):
        # WebViews hospedadas em WinUI podem devolver o painel ponte em
        # GetFocusedElement. Procure foco explícito somente no HWND que o
        # Win32 informou para a janela de origem, nunca por nome/aparência.
        with self.automacao.objeto(6, (c.c_void_p,), (controle,)) as raiz:
            if self.propriedade(raiz, 30008):
                return self.automacao.objeto(6, (c.c_void_p,), (controle,))
            valor = _Variant(tipo=11)
            valor.booleano = -1  # VARIANT_TRUE
            with self.automacao.objeto(23, (c.c_int, _Variant), (30008, valor)) as condicao:
                with raiz.objeto(6, (c.c_int, c.c_void_p), (4, condicao.ptr)) as elementos:
                    quantidade = c.c_int()
                    elementos.chamar(3, (c.POINTER(c.c_int),), (c.byref(quantidade),))
                    if quantidade.value != 1:
                        raise ErroAutomacao(
                            "O controle Win32 não expôs um único descendente com foco de teclado "
                            f"({quantidade.value} encontrados).")
                    candidato = elementos.objeto(4, (c.c_int,), (0,))
                    try:
                        if not self.propriedade(candidato, 30008):
                            raise ErroAutomacao("O descendente deixou de informar foco de teclado.")
                        return candidato
                    except BaseException:
                        candidato.fechar()
                        raise

    def mesmo_elemento(self, primeiro, segundo):
        igual = c.c_int()
        self.automacao.chamar(3, (c.c_void_p, c.c_void_p, c.POINTER(c.c_int)),
                              (primeiro.ptr, segundo.ptr, c.byref(igual)))
        return bool(igual.value)

    def focado_estavel(self, intervalo=0.04, tentativas=4):
        """Retorna uma referência própria após duas leituras iguais com foco.

        Só aguarda durante a ativação/captura; não instala observação contínua.
        Uma troca reinicia a comparação, sem aceitar a referência anterior.
        """
        anterior = self.focado()
        try:
            for _ in range(tentativas):
                time.sleep(intervalo)
                atual = self.focado()
                try:
                    estavel = (self.mesmo_elemento(anterior, atual)
                               and self.propriedade(atual, 30008) is True)
                except BaseException:
                    atual.fechar()
                    raise
                anterior.fechar()
                anterior = atual
                if estavel:
                    resultado, anterior = anterior, None
                    return resultado
            raise ErroAutomacao("O elemento com foco não estabilizou. Clique no campo e tente novamente.")
        finally:
            if anterior is not None:
                anterior.fechar()

    def identificador_elemento(self, elemento):
        array = c.c_void_p()
        elemento.chamar(4, (c.POINTER(c.c_void_p),), (c.byref(array),))
        if not array.value:
            return None
        self.oleaut.SafeArrayDestroy.argtypes = [c.c_void_p]
        self.oleaut.SafeArrayDestroy.restype = c.c_long
        try:
            inicio, fim = c.c_long(), c.c_long()
            if (self.oleaut.SafeArrayGetLBound(array, 1, c.byref(inicio)) < 0
                    or self.oleaut.SafeArrayGetUBound(array, 1, c.byref(fim)) < 0):
                return None
            if not 0 < fim.value - inicio.value + 1 <= 64:
                return None
            resultado = []
            for indice in range(inicio.value, fim.value + 1):
                posicao, numero = c.c_long(indice), c.c_int()
                if self.oleaut.SafeArrayGetElement(array, c.byref(posicao), c.byref(numero)) < 0:
                    return None
                resultado.append(numero.value)
            return tuple(resultado)
        finally:
            self.oleaut.SafeArrayDestroy(array)

    def propriedade(self, elemento, identificador):
        valor = _Variant()
        try:
            elemento.chamar(10, (c.c_int, c.POINTER(_Variant)),
                             (identificador, c.byref(valor)))
            return self._valor(valor)
        finally:
            self.oleaut.VariantClear(c.byref(valor))

    def classe_elemento(self, elemento):
        valor = _Variant()
        try:
            elemento.chamar(10, (c.c_int, c.POINTER(_Variant)), (30012, c.byref(valor)))
            if valor.tipo != 8:
                return ""
            ponteiro = valor.alinhamento
            return c.string_at(ponteiro, self.oleaut.SysStringLen(ponteiro) * 2).decode("utf-16-le") if ponteiro else ""
        finally:
            self.oleaut.VariantClear(c.byref(valor))

    def area_elemento(self, elemento):
        """Lê somente o retângulo UIA; não solicita padrões nem conteúdo."""
        valor = _Variant()
        try:
            elemento.chamar(10, (c.c_int, c.POINTER(_Variant)), (30001, c.byref(valor)))
            if valor.tipo != 0x2005 or not valor.alinhamento:
                return None
            inicio, fim = c.c_long(), c.c_long()
            array = valor.alinhamento
            if (self.oleaut.SafeArrayGetLBound(array, 1, c.byref(inicio)) < 0
                    or self.oleaut.SafeArrayGetUBound(array, 1, c.byref(fim)) < 0
                    or fim.value - inicio.value != 3):
                return None
            coordenadas = []
            for indice in range(inicio.value, fim.value + 1):
                posicao, numero = c.c_long(indice), c.c_double()
                if self.oleaut.SafeArrayGetElement(array, c.byref(posicao), c.byref(numero)) < 0:
                    return None
                coordenadas.append(numero.value)
            return tuple(coordenadas)
        finally:
            self.oleaut.VariantClear(c.byref(valor))

    @staticmethod
    def _valor(valor):
        if valor.tipo == 11:
            return bool(valor.booleano)
        if valor.tipo == 3:
            return valor.inteiro
        raise ErroAutomacao("Propriedade de acessibilidade não suportada.")

    def atributo(self, intervalo, identificador):
        valor = _Variant()
        try:
            intervalo.chamar(9, (c.c_int, c.POINTER(_Variant)),
                              (identificador, c.byref(valor)))
            return self._valor(valor)
        finally:
            self.oleaut.VariantClear(c.byref(valor))

    def texto(self, intervalo):
        return self._ler_bstr(intervalo, 12, (c.c_int,), (-1,))

    def texto_valor(self, padrao):
        return self._ler_bstr(padrao, 4)

    def _ler_bstr(self, objeto, indice, tipos=(), argumentos=()):
        bstr = c.c_void_p()
        try:
            objeto.chamar(indice, (*tipos, c.POINTER(c.c_void_p)),
                           (*argumentos, c.byref(bstr)))
            return c.string_at(bstr, self.oleaut.SysStringLen(bstr) * 2).decode("utf-16-le") if bstr.value else ""
        finally:
            if bstr.value:
                self.oleaut.SysFreeString(bstr)

    def capturar_campo(self):
        with ExitStack() as pilha:
            elemento = pilha.enter_context(self.focado_estavel())
            esperado = getattr(self, "id_foco_esperado", None)
            if esperado is not None and self.identificador_elemento(elemento) != esperado:
                raise ErroAutomacao("O campo mudou entre a captura do atalho e a preparação da inserção.")
            # O papel visual (Edit, Group, Custom etc.) varia entre provedores.
            # A compatibilidade depende de foco, proteção e TextPattern gravável.
            papel = self.propriedade(elemento, 30003)
            for identificador, esperado, motivo in (
                (30008, True, "O elemento não informa foco de teclado"),
                (30009, True, "O elemento não aceita foco de teclado"),
                (30010, True, "O campo está desabilitado"),
                (30019, False, "O campo é protegido por senha"),
            ):
                if self.propriedade(elemento, identificador) is not esperado:
                    detalhe = getattr(self, "motivo_busca_foco", "") if identificador == 30008 else ""
                    raise ErroAutomacao(f"{motivo} (UIA {papel})." + (" " + detalhe if detalhe else ""))
            # Na barra vazia do Chrome, TextPattern pode expor o placeholder
            # (até parcialmente durante a atualização), enquanto ValuePattern
            # informa o valor realmente vazio. Não tratar o aviso como texto.
            if self.classe_elemento(elemento) == "OmniboxViewViews":
                try:
                    vazio = self._capturar_valor(elemento, pilha, apenas_vazio=True)
                    if vazio is not None:
                        return vazio
                except OSError:
                    pass  # Provedores sem ValuePattern seguem a rota de texto.
            try:
                padrao_texto = elemento.objeto(
                    14, (c.c_int, c.POINTER(GUID)),
                    (10014, c.byref(GUID.de("32eba289-3583-42c9-9c59-3b6d9a1e9b6a"))))
            except OSError:
                return self._capturar_valor(elemento, pilha)
            padrao = pilha.enter_context(padrao_texto)
            with padrao.objeto(7) as documento:
                if self.atributo(documento, 40015) is not False:
                    raise ErroAutomacao("O destino está em modo somente leitura.")
                original = self.texto(documento)
                with padrao.objeto(5) as selecoes:
                    quantidade = c.c_int()
                    selecoes.chamar(3, (c.POINTER(c.c_int),), (c.byref(quantidade),))
                    if quantidade.value != 1:
                        raise ErroAutomacao("Não foi possível identificar o cursor.")
                    selecao = pilha.enter_context(selecoes.objeto(4, (c.c_int,), (0,)))
                with documento.objeto(3) as inicio, documento.objeto(3) as fim:
                    inicio.chamar(15, (c.c_int, c.c_void_p, c.c_int), (1, selecao.ptr, 0))
                    fim.chamar(15, (c.c_int, c.c_void_p, c.c_int), (0, selecao.ptr, 1))
                    prefixo, sufixo = self.texto(inicio), self.texto(fim)
            recursos = pilha.pop_all()
            return CampoTexto(self, elemento, padrao, selecao, original, prefixo, sufixo, recursos)

    def _capturar_valor(self, elemento, pilha, apenas_vazio=False):
        try:
            padrao = pilha.enter_context(elemento.objeto(
                14, (c.c_int, c.POINTER(GUID)),
                (10002, c.byref(GUID.de("a94cd8b1-0844-4cd6-9d2d-640537ab39e9")))))
        except OSError as erro:
            raise ErroAutomacao("O campo não disponibiliza TextPattern nem ValuePattern.") from erro
        somente_leitura = c.c_int()
        padrao.chamar(5, (c.POINTER(c.c_int),), (c.byref(somente_leitura),))
        if somente_leitura.value:
            raise ErroAutomacao("O campo está em modo somente leitura.")
        original = self.texto_valor(padrao)
        if apenas_vazio and original != "":
            return None
        return CampoValor(self, elemento, padrao, original, pilha.pop_all())


class CampoTexto:
    def __init__(self, api, elemento, padrao, selecao, original, prefixo, sufixo, recursos):
        self.api, self.elemento, self.padrao, self.selecao = api, elemento, padrao, selecao
        self.original, self.prefixo, self.sufixo = original, prefixo, sufixo
        self.recursos = recursos
        self.motivo_foco = ""

    def fechar(self):
        self.recursos.close()

    def ler(self):
        with self.padrao.objeto(7) as documento:
            return self.api.texto(documento)

    def editavel(self):
        if (not self.api.propriedade(self.elemento, 30010)
                or self.api.propriedade(self.elemento, 30019)):
            return False
        with self.padrao.objeto(7) as documento:
            return self.api.atributo(documento, 40015) is False

    def restaurar(self):
        self.elemento.chamar(3)  # SetFocus
        # Não selecione um intervalo antigo se o próprio editor já preservou
        # a posição correta: referências de intervalo podem acompanhar uma
        # atualização do DOM e passar a apontar para outra posição.
        if self.esta_focado():
            return
        if not self._mesma_posicao_textual(self.selecao):
            raise ErroAutomacao("O intervalo original não preservou a posição textual capturada.")
        self.selecao.chamar(16)  # Select: restaura o cursor/seleção original.

    def esta_focado(self):
        self.motivo_foco = ""
        with self.api.focado() as atual:
            if not self.api.mesmo_elemento(self.elemento, atual):
                self.motivo_foco = "O elemento de acessibilidade atual não é o editor capturado."
                return False
        with self.padrao.objeto(5) as selecoes:
            quantidade = c.c_int()
            selecoes.chamar(3, (c.POINTER(c.c_int),), (c.byref(quantidade),))
            if quantidade.value != 1:
                self.motivo_foco = "O editor não informou uma única seleção."
                return False
            with selecoes.objeto(4, (c.c_int,), (0,)) as atual:
                # Compare entre intervalos vivos pode aceitar referências que
                # se moveram juntas. Confira sempre a posição textual capturada.
                return self._mesma_posicao_textual(atual)

    def _mesma_posicao_textual(self, selecao_atual):
        # Não troca de elemento nem move a seleção. Confere texto completo e
        # posição lógica, para não depender apenas da identidade do intervalo
        # preservado por um editor que pode reconstruir seus nós internos.
        with self.padrao.objeto(7) as documento:
            if self.api.texto(documento) != self.original:
                self.motivo_foco = "O conteúdo do editor mudou durante a restauração."
                return False
            with documento.objeto(3) as inicio, documento.objeto(3) as fim:
                inicio.chamar(15, (c.c_int, c.c_void_p, c.c_int), (1, selecao_atual.ptr, 0))
                fim.chamar(15, (c.c_int, c.c_void_p, c.c_int), (0, selecao_atual.ptr, 1))
                igual = self.api.texto(inicio) == self.prefixo and self.api.texto(fim) == self.sufixo
        if not igual:
            self.motivo_foco = "A posição textual do cursor ou da seleção mudou."
        return igual


class CampoValor:
    """Valor legível sem TextPattern; mantém o cursor lembrado pelo aplicativo.

    Nunca chama SetValue nem seleciona todo o texto. Se a ativação da janela
    não devolver o foco ao mesmo campo, recusa a colagem, pois não pode recuperar
    a posição do cursor por esse provedor.
    """

    prefixo = None
    sufixo = None

    def __init__(self, api, elemento, padrao, original, recursos):
        self.api, self.elemento, self.padrao = api, elemento, padrao
        self.original, self.recursos = original, recursos

    def fechar(self):
        self.recursos.close()

    def ler(self):
        return self.api.texto_valor(self.padrao)

    def editavel(self):
        if (not self.api.propriedade(self.elemento, 30010)
                or self.api.propriedade(self.elemento, 30019)):
            return False
        somente_leitura = c.c_int()
        self.padrao.chamar(5, (c.POINTER(c.c_int),), (c.byref(somente_leitura),))
        return not somente_leitura.value

    def restaurar(self):
        limite = time.monotonic() + 0.4
        while not self.esta_focado():
            if time.monotonic() >= limite:
                raise ErroAutomacao("O navegador não devolveu o foco ao campo original.")
            time.sleep(0.02)

    def esta_focado(self):
        with self.api.focado() as atual:
            return self.api.mesmo_elemento(self.elemento, atual)
