"""Interface compacta escura, inspirada no histórico do Windows 11."""

import sqlite3
import sys
import tkinter as tk
from tkinter import ttk

from application.erros import ConfirmacaoNecessaria, EntidadeNaoEncontrada
from application.inserir_script import InserirScript
from application.pasta import CasosDeUsoPastas
from application.scripts import CasosDeUsoScripts
from domain.erros import ErroDominio
from domain.pasta import Pasta
from domain.script import Script
from presentation.dialogos import (Dialogo, EditorPasta, EditorScript, campo_texto,
                                    confirmar, informar)
from presentation.tema import (FUNDO, CARTAO, BORDA, TEXTO, SECUNDARIO, DESTAQUE,
                                Cartao, ListaRolavel, aplicar_tema, barra_escura,
                                texto)
from presentation.painel import mostrar_painel


class Interface:
    def __init__(self, janela: tk.Tk, pastas: CasosDeUsoPastas,
                 scripts: CasosDeUsoScripts, insercao: InserirScript | None = None):
        self.janela = janela
        self.pastas = pastas
        self.scripts = scripts
        self.insercao = insercao
        self.pasta_id: int | None = None
        self._pastas: list[Pasta] = []
        aplicar_tema(janela)
        janela.title("Gerenciador de Scripts")
        largura, altura = 400, min(540, janela.winfo_screenheight() - 100)
        janela.geometry(f"{largura}x{altura}")
        janela.minsize(360, min(400, altura))
        janela.attributes("-topmost", True)
        janela.protocol("WM_DELETE_WINDOW", janela.destroy)
        self._montar()
        janela.bind("<MouseWheel>", self._rolar)
        janela.bind("<Control-n>", lambda _: self.editar_script())
        janela.bind("<Control-Shift-N>", lambda _: self.editar_pasta())
        self._executar(self.atualizar)
        barra_escura(janela)

    def _montar(self):
        acoes = tk.Frame(self.janela, bg=FUNDO, padx=20, pady=14)
        acoes.pack(fill="x")
        self.botao_voltar = ttk.Button(acoes, text="← Voltar", command=self.voltar,
                                      style="Arredondado.TButton")
        self.pasta_atual = texto(self.janela, "", negrito=True, wraplength=350)
        self.botao_novo = ttk.Button(acoes, text="+ Nova pasta", style="ArredondadoDestaque.TButton",
                                     command=self._novo)
        self.botao_novo.pack(side="right")
        self.botao_subpasta = ttk.Button(acoes, text="+ Subpasta",
                                        style="Arredondado.TButton", command=self.editar_pasta)
        self.lista = ListaRolavel(self.janela)
        self.lista.pack(fill="both", expand=True, padx=(20, 12), pady=(0, 12))

    def _executar(self, acao, pai=None) -> bool:
        try:
            acao()
            return True
        except (ErroDominio, EntidadeNaoEncontrada, ConfirmacaoNecessaria) as erro:
            informar(pai or self.janela, "Não foi possível concluir", str(erro))
        except (sqlite3.Error, OSError):
            informar(pai or self.janela, "Dados indisponíveis",
                     "Não foi possível acessar os dados. Tente novamente.")
        return False

    def _rolar(self, evento):
        if evento.widget.winfo_toplevel() == self.janela:
            self.lista.rolar(evento)

    def abrir_pasta(self, pasta_id: int):
        def abrir():
            self.pastas.obter(pasta_id)
            self.pasta_id = pasta_id
            self.atualizar()
        self._executar(abrir)

    def voltar(self):
        def subir():
            if self.pasta_id is not None:
                self.pasta_id = self.pastas.obter(self.pasta_id).pai_id
            self.atualizar()
        self._executar(subir)

    def atualizar(self):
        self._pastas = self.pastas.listar()
        if not any(p.id == self.pasta_id for p in self._pastas):
            self.pasta_id = None
        self.botao_novo.configure(text="+ Nova pasta" if self.pasta_id is None else "+ Novo script")
        self.lista.limpar()
        if self.pasta_id is not None:
            self.botao_voltar.pack(side="left")
            self.botao_subpasta.pack(side="right", padx=(0, 6))
            pasta = next(p for p in self._pastas if p.id == self.pasta_id)
            caminho = [pasta.nome or "Sem nome"]
            por_id = {p.id: p for p in self._pastas}
            while pasta.pai_id is not None:
                pasta = por_id[pasta.pai_id]
                caminho.append(pasta.nome or "Sem nome")
            self.pasta_atual.configure(text=" / ".join(reversed(caminho)))
            self.pasta_atual.pack(fill="x", padx=20, pady=(0, 12), before=self.lista)
            filhas = [p for p in self._pastas if p.pai_id == self.pasta_id]
            for filha in filhas:
                self._cartao_pasta(filha)
            itens = self.scripts.listar(self.pasta_id)
            for script in itens:
                self._cartao_script(script)
            if not itens and not filhas:
                self._vazio()
        else:
            self.botao_voltar.pack_forget()
            self.botao_subpasta.pack_forget()
            self.pasta_atual.pack_forget()
            for pasta in self._pastas:
                if pasta.pai_id is None:
                    self._cartao_pasta(pasta)

    def _novo(self):
        self.editar_pasta() if self.pasta_id is None else self.editar_script()

    def _vazio(self):
        quadro = tk.Frame(self.lista.corpo, bg=FUNDO, pady=25)
        quadro.pack(fill="x")
        texto(quadro, "Esta pasta está vazia.", cor=SECUNDARIO).pack()

    def _cartao_script(self, script: Script):
        cartao = Cartao(self.lista.corpo)
        cartao.pack(fill="x", padx=8, pady=(0, 8))
        linha = tk.Frame(cartao.corpo, bg=CARTAO)
        linha.pack(fill="x")
        titulo = texto(linha, " ".join(script.titulo.split()) or "Sem título", negrito=True,
                       height=1, wraplength=265, cursor="hand2")
        titulo.pack(side="left", fill="x", expand=True)
        titulo.bind("<Configure>", lambda evento: titulo.configure(
            wraplength=max(100, evento.width - 4)))
        menu = ttk.Button(linha, text="···", width=3)
        menu.configure(command=lambda: self._menu_script(script, menu))
        menu.pack(side="right")
        # A prévia não herda quebras de linha que aumentariam o cartão.
        # O texto original permanece intacto no banco e na visualização completa.
        previa = " ".join(script.conteudo.split())
        previa = previa[:150] + ("…" if len(previa) > 150 else "")
        conteudo = texto(cartao.corpo, previa or "Sem conteúdo", cor=SECUNDARIO,
                         height=3, anchor="nw", wraplength=325, cursor="hand2")
        conteudo.pack(fill="x", pady=(8, 0))
        conteudo.bind("<Configure>", lambda evento: conteudo.configure(
            wraplength=max(100, evento.width - 4)))
        self._tornar_clicavel(cartao, lambda: self.usar_script(script.id)
                             if self.insercao is not None else self.visualizar(script.id))

    def _mostrar_menu(self, opcoes, ancora=None):
        anterior = getattr(self, "_menu", None)
        if anterior is not None:
            anterior.destroy()
        menu = tk.Menu(self.janela, tearoff=False, bg=CARTAO, fg=TEXTO,
                       activebackground=BORDA, activeforeground=TEXTO, bd=0)
        for legenda, comando, permitido in opcoes:
            menu.add_command(label=legenda, command=comando,
                             state="normal" if permitido else "disabled")
        self._menu = menu
        try:
            x = ancora.winfo_rootx() if ancora else self.janela.winfo_pointerx()
            y = ancora.winfo_rooty() + ancora.winfo_height() if ancora else self.janela.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _menu_script(self, script: Script, ancora=None):
        self._mostrar_menu([
            ("Ver script", lambda: self.visualizar(script.id), True),
            ("Editar script", lambda: self.editar_script(script.id), True),
            ("Excluir script", lambda: self.excluir_script(script.id), True),
        ], ancora)

    def _menu_pasta(self, pasta: Pasta, ancora=None):
        self._mostrar_menu([
            ("Abrir pasta", lambda: self.abrir_pasta(pasta.id), True),
            ("Editar pasta", lambda: self.editar_pasta(pasta.id), not pasta.sistema),
            ("Excluir pasta", lambda: self.excluir_pasta(pasta.id), not pasta.sistema),
        ], ancora)

    def _tornar_clicavel(self, cartao: Cartao, comando):
        def acionar(_evento):
            comando()
            return "break"

        def vincular(widget):
            if isinstance(widget, ttk.Button):
                return
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", acionar)
            for filho in widget.winfo_children():
                vincular(filho)

        vincular(cartao)
        cartao.configure(takefocus=True)
        cartao.bind("<Return>", acionar)
        cartao.bind("<space>", acionar)
        cartao.bind("<FocusIn>", lambda _: cartao.itemconfigure(cartao.superficie, outline=DESTAQUE))
        cartao.bind("<FocusOut>", lambda _: cartao.itemconfigure(cartao.superficie, outline=BORDA))

    def _cartao_pasta(self, pasta: Pasta):
        cartao = Cartao(self.lista.corpo)
        cartao.pack(fill="x", padx=8, pady=(0, 8))
        menu = ttk.Button(cartao.corpo, text="···", width=3)
        menu.configure(command=lambda: self._menu_pasta(pasta, menu))
        menu.pack(side="right", padx=(8, 0))
        nome = texto(cartao.corpo, pasta.nome or "Sem nome", tamanho=12,
                     negrito=True, wraplength=265)
        nome.pack(side="left", fill="x", expand=True)
        nome.bind("<Configure>", lambda evento: nome.configure(wraplength=max(100, evento.width - 4)))
        self._tornar_clicavel(cartao, lambda: self.abrir_pasta(pasta.id))

    def editar_pasta(self, pasta_id: int | None = None):
        def abrir():
            pasta = self.pastas.obter(pasta_id) if pasta_id is not None else None

            def salvar(nome):
                def gravar():
                    if pasta:
                        self.pastas.renomear(pasta.id, nome)
                    else:
                        self.pastas.criar(nome, self.pasta_id)
                    self.atualizar()
                return self._executar(gravar, editor)

            editor = EditorPasta(self.janela, salvar, pasta,
                                 subpasta=(pasta.pai_id if pasta else self.pasta_id) is not None)
        self._executar(abrir)

    def editar_script(self, script_id: int | None = None):
        def abrir():
            script = self.scripts.obter(script_id) if script_id is not None else None

            def salvar(titulo, conteudo, pasta_id):
                def gravar():
                    if script:
                        self.scripts.editar(script.id, titulo, conteudo)
                    else:
                        self.scripts.criar(titulo, conteudo, pasta_id)
                    self.pasta_id = pasta_id
                    self.atualizar()
                return self._executar(gravar, editor)

            pastas = self.pastas.listar()
            pasta_id = script.pasta_id if script else self.pasta_id
            if pasta_id is None:
                pasta_id = next(p.id for p in pastas if p.sistema)
            editor = EditorScript(self.janela, pastas, pasta_id,
                                  salvar, script)
        self._executar(abrir)

    def excluir_pasta(self, pasta_id: int):
        def excluir():
            aviso = self.pastas.solicitar_exclusao(pasta_id)
            if confirmar(self.janela, "Excluir pasta?", aviso):
                pai_id = self.pastas.obter(pasta_id).pai_id
                self.pastas.excluir(pasta_id, confirmado=True)
                if self.pasta_id == pasta_id:
                    self.pasta_id = pai_id
                self.atualizar()
        self._executar(excluir)

    def excluir_script(self, script_id: int):
        def excluir():
            script = self.scripts.obter(script_id)
            if confirmar(self.janela, "Excluir script?", f'Excluir "{script.titulo or "Sem título"}"? Essa ação não pode ser desfeita.'):
                self.scripts.excluir(script_id)
                self.atualizar()
        self._executar(excluir)

    def visualizar(self, script_id: int):
        def abrir():
            script = self.scripts.obter(script_id)
            dialogo = Dialogo(self.janela, "Visualizar script")
            texto(dialogo.corpo, script.titulo or "Sem título", negrito=True,
                  wraplength=340).pack(fill="x", pady=(0, 12))
            campo = campo_texto(dialogo.corpo)
            campo.insert("1.0", script.conteudo)
            campo.configure(state="disabled")
            if self.insercao is None:
                texto(dialogo.corpo, "Inserção automática indisponível nesta versão.",
                      cor=SECUNDARIO, tamanho=9, wraplength=340).pack(pady=(10, 0))
            linha = dialogo.botoes()
            ttk.Button(linha, text="Inserir texto", style="Destaque.TButton",
                       state="normal" if self.insercao else "disabled",
                       command=lambda: self.usar_script(script.id, dialogo)).pack(side="right")
            ttk.Button(linha, text="Fechar", command=dialogo.destroy).pack(side="right", padx=(0, 8))
            dialogo.mostrar()
        self._executar(abrir)

    def usar_script(self, script_id: int, dialogo: Dialogo | None = None):
        if self.insercao is None:
            return

        if dialogo is not None:
            dialogo.grab_release()
            dialogo.withdraw()
        # Oculta imediatamente; mantém os recursos até enviar a colagem.
        self.janela.withdraw()
        self.janela.update_idletasks()
        try:
            self.insercao.executar(script_id)
        except (ErroDominio, EntidadeNaoEncontrada, sqlite3.Error, OSError):
            pass  # O clique encerra a interface também quando não é possível colar.
        finally:
            self.janela.destroy()


def abrir_interface(pastas: CasosDeUsoPastas, scripts: CasosDeUsoScripts,
                    insercao: InserirScript | None = None,
                    parada=None) -> None:
    if parada is not None and parada.sinalizado():
        return
    janela = tk.Tk()
    janela.withdraw()
    if sys.platform == "win32":
        janela.attributes("-toolwindow", True)
    Interface(janela, pastas, scripts, insercao)
    mostrar_painel(janela)
    if parada is not None:
        # Apenas enquanto a interface está aberta. O receptor ocioso não
        # usa timers nem consultas periódicas ao foco/teclado/banco.
        tarefa = None
        def conferir_parada():
            nonlocal tarefa
            tarefa = None
            if parada.sinalizado():
                janela.destroy()
            else:
                tarefa = janela.after(500, conferir_parada)
        def cancelar_parada(evento):
            if evento.widget is janela and tarefa is not None:
                janela.after_cancel(tarefa)
        janela.bind("<Destroy>", cancelar_parada, add="+")
        conferir_parada()
    janela.mainloop()
