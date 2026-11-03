"""Ponto de entrada da aplicação desktop."""

from infraestructure.database import BancoDados
from presentation.interface import abrir_interface


def main() -> None:
    BancoDados().inicializar()
    abrir_interface()


if __name__ == "__main__":
    main()
