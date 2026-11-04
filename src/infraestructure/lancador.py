"""Interface descartável: apenas o receptor permanece entre ativações."""

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys


class LancadorInterface:
    def __init__(self, capturar=None, criar_processo=None):
        self._capturar = capturar
        self._criar_processo = criar_processo or subprocess.Popen
        self.processo = None
        self.parada = None

    def ativar(self):
        if self.processo is not None and self.processo.poll() is None:
            return  # Não substituir o destino de uma interface em uso.
        if self.parada is not None:
            self.parada.fechar()
            self.parada = None
        if self._capturar is None:
            from infraestructure.foco import capturar_foco
            capturar = capturar_foco
        else:
            capturar = self._capturar
        foco = capturar()
        if not foco.janela or not foco.janela_estavel:
            raise OSError("A janela mudou durante a captura. Posicione o cursor e tente Ctrl+Alt+Z novamente.")
        entrada = Path(__file__).resolve().parents[1] / "main.py"
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        from infraestructure.evento import EventoParada
        self.parada = EventoParada()
        try:
            processo = self._criar_processo(
                [str(pythonw), "-B", str(entrada), "--interface"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.processo = processo
            try:
                processo.stdin.write(json.dumps({"foco": asdict(foco),
                                                "evento_parada": self.parada.nome}).encode("utf-8"))
            finally:
                processo.stdin.close()
        except BaseException:
            self.encerrar()
            raise

    def encerrar(self):
        if self.parada is not None:
            try:
                self.parada.sinalizar()
            finally:
                self.parada.fechar()
                self.parada = None
