"""Receptor leve de Ctrl+Alt+Z; a interface é carregada somente sob demanda."""

import argparse
import sys


def executar_interface(origem, parada):
    from application.sessao import mesma_origem
    from infraestructure.foco import capturar_foco
    from infraestructure.windows import InsercaoWindows
    from infraestructure.database import BancoDados
    from infraestructure.repository import RepositorioPastasSQLite, RepositorioScriptsSQLite
    from application.pasta import CasosDeUsoPastas
    from application.scripts import CasosDeUsoScripts
    from application.inserir_script import InserirScript
    from application.organizacao import CasosDeUsoOrganizacao
    from infraestructure.repository import RepositorioOrganizacaoSQLite

    # Antes de importar Tkinter/criar janelas ou inicializar o banco.
    if parada.sinalizado():
        return
    atual = capturar_foco()
    origem_compativel = mesma_origem(origem, atual)
    insercao = InsercaoWindows.capturar(origem=origem) if origem_compativel else InsercaoWindows()
    if origem_compativel and (insercao.janela, insercao.processo) != (origem.janela, origem.processo):
        insercao.fechar()
        insercao = InsercaoWindows()
        origem_compativel = False
    if not origem_compativel:
        insercao.erro_captura = "O destino mudou entre o Ctrl+Alt+Z e a abertura. Feche a janela e tente novamente."
    try:
        if parada.sinalizado():
            return
        banco = BancoDados()
        banco.inicializar()
        pastas = RepositorioPastasSQLite(banco)
        scripts = RepositorioScriptsSQLite(banco)
        from presentation.interface import abrir_interface
        abrir_interface(CasosDeUsoPastas(pastas), CasosDeUsoScripts(scripts, pastas),
                        InserirScript(scripts, insercao), parada=parada,
                        organizacao=CasosDeUsoOrganizacao(RepositorioOrganizacaoSQLite(banco)))
    finally:
        insercao.fechar()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modos = parser.add_mutually_exclusive_group()
    modos.add_argument("--interface", action="store_true", help=argparse.SUPPRESS)
    modos.add_argument("--encerrar", action="store_true", help="Encerrar o receptor de Ctrl+Alt+Z.")
    args = parser.parse_args()
    if args.interface:
        import json
        from application.foco import FocoCapturado
        from infraestructure.evento import EventoParada
        mensagem = json.loads(sys.stdin.buffer.read(65536).decode("utf-8"))
        dados = mensagem["foco"]
        if dados.get("area_uia") is not None:
            dados["area_uia"] = tuple(dados["area_uia"])
        if dados.get("id_uia") is not None:
            dados["id_uia"] = tuple(dados["id_uia"])
        try:
            parada = EventoParada(mensagem["evento_parada"])
        except OSError:
            return  # O receptor já encerrou antes do início deste processo.
        try:
            executar_interface(FocoCapturado(**dados), parada)
        except Exception as erro:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(erro), "Não foi possível abrir o gerenciador", 0x10)
        finally:
            parada.fechar()
        return
    from infraestructure.residente import ReceptorWindows, encerrar_receptor
    if args.encerrar:
        encerrar_receptor()
        return
    from infraestructure.lancador import LancadorInterface
    lancador = LancadorInterface()
    receptor = ReceptorWindows(lancador.ativar, lancador.encerrar)
    try:
        receptor.executar()
    except OSError as erro:
        # pythonw não tem terminal: falhas de registro devem ficar visíveis.
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(erro), "Gerenciador de Scripts", 0x10)
    finally:
        lancador.encerrar()


if __name__ == "__main__":
    main()
