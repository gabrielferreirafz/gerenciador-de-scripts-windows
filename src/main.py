"""Ponto de entrada da aplicação desktop."""

from infraestructure.database import BancoDados
from infraestructure.repository import RepositorioPastasSQLite, RepositorioScriptsSQLite
from application.pasta import CasosDeUsoPastas
from application.scripts import CasosDeUsoScripts
from presentation.interface import abrir_interface


def main() -> None:
    banco = BancoDados()
    banco.inicializar()
    pastas = RepositorioPastasSQLite(banco)
    scripts = RepositorioScriptsSQLite(banco)
    abrir_interface(CasosDeUsoPastas(pastas), CasosDeUsoScripts(scripts, pastas))


if __name__ == "__main__":
    main()
