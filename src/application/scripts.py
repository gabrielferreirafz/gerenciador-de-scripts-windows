"""Casos de uso de scripts, sem dependência de interface ou banco concreto."""

from application.contratos import RepositorioPastas, RepositorioScripts
from application.erros import EntidadeNaoEncontrada
from application.pasta import CasosDeUsoPastas
from domain.script import Script


class CasosDeUsoScripts:
    def __init__(
        self, repositorio: RepositorioScripts, pastas: RepositorioPastas
    ) -> None:
        self._repositorio = repositorio
        self._pastas = CasosDeUsoPastas(pastas)

    def criar(
        self, titulo: str, conteudo: str, pasta_id: int | None = None
    ) -> Script:
        pasta = (
            self._pastas.garantir_geral()
            if pasta_id is None
            else self._pastas.obter(pasta_id)
        )
        return self._repositorio.criar(titulo, conteudo, pasta.id)

    def obter(self, script_id: int) -> Script:
        script = self._repositorio.obter(script_id)
        if script is None:
            raise EntidadeNaoEncontrada(f"Script {script_id} não encontrado.")
        return script

    def listar(self, pasta_id: int | None = None) -> list[Script]:
        if pasta_id is not None:
            self._pastas.obter(pasta_id)
        return self._repositorio.listar(pasta_id)

    def editar(self, script_id: int, titulo: str, conteudo: str) -> Script:
        script = self.obter(script_id).editar(titulo, conteudo)
        self._repositorio.atualizar(script)
        return script

    def excluir(self, script_id: int) -> None:
        self.obter(script_id)
        self._repositorio.excluir(script_id)
