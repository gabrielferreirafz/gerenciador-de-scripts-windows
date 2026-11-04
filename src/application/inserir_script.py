"""Coordena a inserção sem presumir que enviar eventos significa sucesso."""

from enum import Enum

from application.contratos import InsercaoTexto, RepositorioScripts
from application.erros import EntidadeNaoEncontrada


class ResultadoInsercao(Enum):
    SEM_DESTINO_VALIDO = "sem_destino_valido"
    FALHA = "falha"
    SUCESSO = "sucesso"

    @property
    def deve_encerrar(self) -> bool:
        """Fecha a interface após sucesso confirmado; o receptor permanece."""
        return self is ResultadoInsercao.SUCESSO


class InserirScript:
    def __init__(
        self, repositorio: RepositorioScripts, insercao: InsercaoTexto
    ) -> None:
        self._repositorio = repositorio
        self._insercao = insercao

    def executar(self, script_id: int) -> ResultadoInsercao:
        script = self._repositorio.obter(script_id)
        if script is None:
            raise EntidadeNaoEncontrada(f"Script {script_id} não encontrado.")
        if not self._insercao.destino_valido():
            return ResultadoInsercao.SEM_DESTINO_VALIDO
        if self._insercao.inserir(script.conteudo) is True:
            return ResultadoInsercao.SUCESSO
        return ResultadoInsercao.FALHA

    def diagnostico_falha(self) -> str:
        detalhe = self._insercao.diagnostico_falha()
        return detalhe if isinstance(detalhe, str) else ""
