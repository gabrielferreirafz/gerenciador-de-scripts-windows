import ctypes as c
import json
import unittest
from unittest.mock import Mock, patch

from application.foco import FocoCapturado
from application.sessao import mesma_origem
from infraestructure.evento import EventoParada
from infraestructure.lancador import LancadorInterface
from infraestructure.residente import ReceptorWindows
import main


class TestOrigem(unittest.TestCase):
    def origem(self, **dados):
        valores = dict(janela=10, processo=20, controle=30, janela_estavel=True,
                       tipo_uia=50004, classe_uia="Edit", area_uia=(1, 2, 3, 4))
        valores.update(dados)
        return FocoCapturado(**valores)

    def test_recusa_janela_processo_controle_e_campo_diferentes(self):
        original = self.origem()
        self.assertTrue(mesma_origem(original, self.origem()))
        for dados in ({"janela": 99}, {"processo": 99}, {"controle": 99},
                      {"janela_estavel": False}, {"classe_uia": "Button"},
                      {"area_uia": (5, 6, 7, 8)}, {"tipo_uia": None}):
            with self.subTest(dados=dados):
                self.assertFalse(mesma_origem(original, self.origem(**dados)))

    def test_dados_win32_sem_uia_ainda_permitem_validar_origem(self):
        foco = self.origem(tipo_uia=None, classe_uia="", area_uia=None)
        self.assertTrue(mesma_origem(foco, foco))
        self.assertFalse(mesma_origem(FocoCapturado(), FocoCapturado()))

    def test_mesma_classe_e_posicao_nao_substituem_identidade_do_campo(self):
        original = self.origem(id_uia=(42, 1), tem_foco_uia=True)
        outro = self.origem(id_uia=(42, 2), tem_foco_uia=True)
        self.assertFalse(mesma_origem(original, outro))

    def test_mesmo_campo_pode_mover_sem_ser_confundido_com_outro(self):
        original = self.origem(id_uia=(42, 1), tem_foco_uia=True)
        movido = self.origem(id_uia=(42, 1), tem_foco_uia=True, area_uia=(8, 9, 3, 4))
        self.assertTrue(mesma_origem(original, movido))

    def test_captura_inicial_instavel_nao_pode_vincular_outro_campo_depois(self):
        self.assertFalse(mesma_origem(self.origem(campo_estavel=False), self.origem()))

    def test_interface_nao_recaptura_outro_destino_para_insercao(self):
        parada = Mock()
        parada.sinalizado.return_value = False
        with patch("infraestructure.foco.capturar_foco", return_value=self.origem(controle=99)), \
                patch("infraestructure.windows.InsercaoWindows.capturar") as capturar, \
                patch("infraestructure.database.BancoDados"), \
                patch("infraestructure.repository.RepositorioPastasSQLite"), \
                patch("infraestructure.repository.RepositorioScriptsSQLite"), \
                patch("presentation.interface.abrir_interface") as abrir:
            main.executar_interface(self.origem(), parada)
        capturar.assert_not_called()
        adaptador = abrir.call_args.args[2]._insercao
        self.assertIsNone(adaptador.campo)
        self.assertIn("destino mudou", adaptador.erro_captura)

    def test_encerramento_antes_da_abertura_nao_inicializa_banco(self):
        parada = Mock()
        parada.sinalizado.return_value = True
        with patch("infraestructure.database.BancoDados") as banco:
            main.executar_interface(self.origem(), parada)
        banco.assert_not_called()


class TestLancador(unittest.TestCase):
    def preparar(self):
        foco = FocoCapturado(janela=10, processo=20, janela_estavel=True)
        captura, criar = Mock(return_value=foco), Mock()
        processo = criar.return_value
        processo.poll.return_value = None
        return LancadorInterface(captura, criar), captura, criar, foco

    def test_transmite_destino_sem_arquivo_e_nao_duplica_interface(self):
        lancador, captura, criar, foco = self.preparar()
        try:
            lancador.ativar()
            enviado = json.loads(criar.return_value.stdin.write.call_args.args[0])
            self.assertEqual(enviado["foco"]["janela"], foco.janela)
            self.assertTrue(enviado["evento_parada"])
            criar.return_value.stdin.close.assert_called_once()
            lancador.ativar()
            captura.assert_called_once()
            criar.assert_called_once()
        finally:
            lancador.encerrar()

    def test_fecha_sinal_anterior_e_captura_destino_novo_ao_reabrir(self):
        lancador, captura, criar, _ = self.preparar()
        try:
            lancador.ativar()
            anterior = lancador.parada
            criar.return_value.poll.return_value = 0
            lancador.ativar()
            self.assertIsNone(anterior.handle)
            self.assertEqual(captura.call_count, 2)
        finally:
            lancador.encerrar()

    def test_nao_inicia_interface_se_captura_mudar(self):
        lancador, captura, criar, _ = self.preparar()
        captura.return_value = FocoCapturado(janela=10, janela_estavel=False)
        with self.assertRaises(OSError):
            lancador.ativar()
        criar.assert_not_called()

    def test_falha_de_criacao_libera_sinal(self):
        lancador, _, criar, _ = self.preparar()
        criar.side_effect = OSError("Falha de criação")
        with self.assertRaises(OSError):
            lancador.ativar()
        self.assertIsNone(lancador.parada)


class TestEvento(unittest.TestCase):
    def test_sinal_entre_handles_e_encerramento_antes_da_abertura(self):
        dono = EventoParada()
        leitura = EventoParada(dono.nome)
        try:
            self.assertFalse(leitura.sinalizado())
            dono.sinalizar()
            dono.fechar()
            self.assertTrue(leitura.sinalizado())
        finally:
            dono.fechar()
            leitura.fechar()
        with self.assertRaises(OSError):
            EventoParada(dono.nome)


class TestReceptor(unittest.TestCase):
    def preparar(self):
        user, kernel, shell = Mock(), Mock(), Mock()
        kernel.CreateMutexW.return_value = 123
        kernel.GetModuleHandleW.return_value = 1
        user.LoadIconW.return_value = 1
        user.CreateWindowExW.return_value = 456
        user.RegisterClassW.return_value = 1
        user.RegisterWindowMessageW.return_value = 0xc001
        c.set_last_error(0)
        return user, kernel, shell

    def test_espera_bloqueante_e_libera_hotkey_mutex_e_icone(self):
        user, kernel, shell = self.preparar()
        user.GetMessageW.side_effect = [1, 0]
        with patch("infraestructure.residente._bibliotecas", return_value=(user, kernel, shell)):
            receptor = ReceptorWindows(Mock())
            receptor.executar()
        self.assertEqual(user.GetMessageW.call_count, 2)
        user.DispatchMessageW.assert_called_once()
        user.RegisterHotKey.assert_called_once_with(456, 1, 0x4003, 0x5a)
        user.UnregisterHotKey.assert_called_once_with(456, 1)
        kernel.CloseHandle.assert_called_once_with(123)
        self.assertEqual([call.args[0] for call in shell.Shell_NotifyIconW.call_args_list], [0, 2])

    def test_instancia_duplicada_nao_registra_atalho(self):
        user, kernel, shell = self.preparar()
        c.set_last_error(183)
        with patch("infraestructure.residente._bibliotecas", return_value=(user, kernel, shell)):
            receptor = ReceptorWindows(Mock())
            self.assertFalse(receptor.iniciar())
        user.RegisterHotKey.assert_not_called()
        kernel.CloseHandle.assert_called_once_with(123)

    def test_conflito_de_atalho_libera_recursos(self):
        user, kernel, shell = self.preparar()
        user.RegisterHotKey.return_value = False
        with patch("infraestructure.residente._bibliotecas", return_value=(user, kernel, shell)):
            receptor = ReceptorWindows(Mock())
            with self.assertRaisesRegex(OSError, r"Ctrl\+Alt\+Z já está em uso"):
                receptor.iniciar()
        user.DestroyWindow.assert_called_once_with(456)
        kernel.CloseHandle.assert_called_once_with(123)

    def test_comando_real_de_hotkey_e_erro_informado_sem_encerrar(self):
        user, kernel, shell = self.preparar()
        ativar = Mock(side_effect=OSError("Falha de captura"))
        with patch("infraestructure.residente._bibliotecas", return_value=(user, kernel, shell)):
            receptor = ReceptorWindows(ativar)
            with patch.object(receptor, "avisar") as avisar:
                receptor._procedimento(456, 0x312, 1, 0)
                ativar.assert_called_once()
                avisar.assert_called_once()
