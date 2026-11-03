"""Regras do núcleo verificadas com adaptadores em memória, sem SQLite/Win32."""

from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import create_autospec

from application.contratos import InsercaoTexto
from application.erros import ConfirmacaoNecessaria, EntidadeNaoEncontrada
from application.inserir_script import InserirScript, ResultadoInsercao
from application.pasta import CasosDeUsoPastas
from application.scripts import CasosDeUsoScripts
from domain.erros import ErroDominio, PastaProtegida
from domain.pasta import Pasta
from domain.script import Script


class PastasEmMemoria:
    def __init__(self, scripts: "ScriptsEmMemoria") -> None:
        self.dados: dict[int, Pasta] = {}
        self.scripts = scripts
        self.proximo_id = 20  # Geral não depende de ID=1.

    def garantir_geral(self) -> Pasta:
        for pasta in self.dados.values():
            if pasta.sistema:
                return pasta
        pasta = Pasta(self.proximo_id, "Geral", True)
        self.proximo_id += 1
        self.dados[pasta.id] = pasta
        return pasta

    def criar(self, nome: str) -> Pasta:
        pasta = Pasta(self.proximo_id, nome, False)
        self.proximo_id += 1
        self.dados[pasta.id] = pasta
        return pasta

    def obter(self, pasta_id: int) -> Pasta | None:
        return self.dados.get(pasta_id)

    def listar(self) -> list[Pasta]:
        return list(self.dados.values())

    def atualizar(self, pasta: Pasta) -> None:
        self.dados[pasta.id] = pasta

    def excluir_com_scripts(self, pasta_id: int) -> None:
        del self.dados[pasta_id]
        self.scripts.dados = {
            chave: script for chave, script in self.scripts.dados.items()
            if script.pasta_id != pasta_id
        }


class ScriptsEmMemoria:
    def __init__(self) -> None:
        self.dados: dict[int, Script] = {}
        self.proximo_id = 1

    def criar(self, titulo: str, conteudo: str, pasta_id: int) -> Script:
        script = Script(self.proximo_id, titulo, conteudo, pasta_id)
        self.proximo_id += 1
        self.dados[script.id] = script
        return script

    def obter(self, script_id: int) -> Script | None:
        return self.dados.get(script_id)

    def listar(self, pasta_id: int | None = None) -> list[Script]:
        return [
            script for script in self.dados.values()
            if pasta_id is None or script.pasta_id == pasta_id
        ]

    def atualizar(self, script: Script) -> None:
        self.dados[script.id] = script

    def excluir(self, script_id: int) -> None:
        del self.dados[script_id]


class TestDominio(unittest.TestCase):
    def test_script_exige_uma_identidade_de_pasta(self):
        for pasta_id in (None, [1, 2], True, "1"):
            with self.subTest(pasta_id=pasta_id), self.assertRaises(ErroDominio):
                Script(1, "Título", "Texto", pasta_id)

    def test_edicao_preserva_pasta_e_conteudo_literal(self):
        original = Script(1, "Título", "Original", 20)
        atualizado = original.editar("Novo título", "  Texto\ncom quebra  ")
        self.assertEqual(atualizado.pasta_id, 20)
        self.assertEqual(atualizado.conteudo, "  Texto\ncom quebra  ")
        self.assertEqual(original.conteudo, "Original")

    def test_entidades_nao_permitem_mutacao_direta(self):
        pasta = Pasta(20, "Geral", True)
        with self.assertRaises(FrozenInstanceError):
            pasta.nome = "Outro nome"
        script = Script(1, "Título", "Texto", 20)
        with self.assertRaises(FrozenInstanceError):
            script.pasta_id = 30

    def test_protecao_existe_no_dominio(self):
        pasta = Pasta(20, "Geral", True)
        with self.assertRaises(PastaProtegida):
            pasta.renomear("Outro nome")
        with self.assertRaises(PastaProtegida):
            pasta.verificar_exclusao()


class TestCasosDeUso(unittest.TestCase):
    def setUp(self):
        self.repo_scripts = ScriptsEmMemoria()
        self.repo_pastas = PastasEmMemoria(self.repo_scripts)
        self.pastas = CasosDeUsoPastas(self.repo_pastas)
        self.scripts = CasosDeUsoScripts(self.repo_scripts, self.repo_pastas)

    def test_geral_e_idempotente_e_aparece_na_listagem(self):
        geral = self.pastas.garantir_geral()
        self.assertEqual(self.pastas.garantir_geral(), geral)
        self.assertEqual(self.pastas.listar(), [geral])

    def test_nome_igual_nao_identifica_pasta_protegida(self):
        usuario = self.pastas.criar("Geral")
        geral = self.pastas.garantir_geral()
        self.assertNotEqual(usuario.id, geral.id)
        self.assertFalse(usuario.sistema)
        self.assertTrue(geral.sistema)

    def test_cadastro_sem_escolha_utiliza_geral(self):
        script = self.scripts.criar("Título", "Texto")
        self.assertEqual(script.pasta_id, self.pastas.garantir_geral().id)

    def test_cadastro_com_pasta_explicita(self):
        pasta = self.pastas.criar("Atendimento")
        script = self.scripts.criar("Título", "Texto", pasta.id)
        self.assertEqual(self.scripts.listar(pasta.id), [script])
        self.assertEqual(self.scripts.listar(self.pastas.garantir_geral().id), [])

    def test_pasta_inexistente_nao_cria_script(self):
        with self.assertRaises(EntidadeNaoEncontrada):
            self.scripts.criar("Título", "Texto", 999)
        self.assertEqual(self.scripts.listar(), [])

    def test_crud_pasta_do_usuario(self):
        pasta = self.pastas.criar("Inicial")
        atualizada = self.pastas.renomear(pasta.id, "Final")
        self.assertEqual(self.pastas.obter(pasta.id), atualizada)
        self.assertEqual(atualizada.nome, "Final")
        self.pastas.excluir(pasta.id, confirmado=True)
        with self.assertRaises(EntidadeNaoEncontrada):
            self.pastas.obter(pasta.id)

    def test_geral_protegida_nos_casos_de_uso(self):
        geral = self.pastas.garantir_geral()
        for operacao in (
            lambda: self.pastas.renomear(geral.id, "Outro nome"),
            lambda: self.pastas.solicitar_exclusao(geral.id),
            lambda: self.pastas.excluir(geral.id, confirmado=True),
        ):
            with self.assertRaises(PastaProtegida):
                operacao()
        self.assertEqual(self.pastas.obter(geral.id), geral)

    def test_exclusao_sem_confirmacao_preserva_pasta_e_scripts(self):
        pasta = self.pastas.criar("Atendimento")
        script = self.scripts.criar("Título", "Texto", pasta.id)
        aviso = self.pastas.solicitar_exclusao(pasta.id)
        self.assertIn("Todos os scripts associados também serão excluídos", aviso)
        for confirmado in (False, None, "sim", 1):
            with self.assertRaises(ConfirmacaoNecessaria):
                self.pastas.excluir(pasta.id, confirmado=confirmado)
        self.assertEqual(self.pastas.obter(pasta.id), pasta)
        self.assertEqual(self.scripts.obter(script.id), script)

    def test_exclusao_confirmada_remove_somente_os_scripts_associados(self):
        pasta = self.pastas.criar("Atendimento")
        removido = self.scripts.criar("Título", "Texto", pasta.id)
        preservado = self.scripts.criar("Outro", "Conteúdo")
        self.pastas.excluir(pasta.id, confirmado=True)
        self.assertIsNone(self.repo_pastas.obter(pasta.id))
        self.assertIsNone(self.repo_scripts.obter(removido.id))
        self.assertEqual(self.scripts.listar(), [preservado])

    def test_crud_script_preserva_associacao_na_edicao(self):
        script = self.scripts.criar("Inicial", "Texto")
        atualizado = self.scripts.editar(script.id, "Final", "Novo texto")
        self.assertEqual(atualizado.pasta_id, script.pasta_id)
        self.assertEqual(self.scripts.obter(script.id), atualizado)
        self.scripts.excluir(script.id)
        self.assertEqual(self.scripts.listar(), [])

    def test_nomes_e_titulos_duplicados_nao_sao_proibidos(self):
        self.pastas.criar("Atendimento")
        self.pastas.criar("Atendimento")
        primeiro = self.scripts.criar("Título", "Texto")
        segundo = self.scripts.criar("Título", "Texto")
        self.assertNotEqual(primeiro.id, segundo.id)

    def test_operacoes_sobre_entidades_inexistentes(self):
        for operacao in (
            lambda: self.pastas.renomear(999, "Nome"),
            lambda: self.pastas.excluir(999, confirmado=True),
            lambda: self.scripts.obter(999),
            lambda: self.scripts.editar(999, "Título", "Texto"),
            lambda: self.scripts.excluir(999),
            lambda: self.scripts.listar(999),
        ):
            with self.assertRaises(EntidadeNaoEncontrada):
                operacao()


class TestInsercao(unittest.TestCase):
    def setUp(self):
        self.repo = ScriptsEmMemoria()
        self.script = self.repo.criar("Título", "Olá!\nComo posso ajudar?", 20)
        self.porta = create_autospec(InsercaoTexto, instance=True)
        self.caso = InserirScript(self.repo, self.porta)

    def test_sem_destino_nao_envia_nem_solicita_encerramento(self):
        self.porta.destino_valido.return_value = False
        resultado = self.caso.executar(self.script.id)
        self.assertIs(resultado, ResultadoInsercao.SEM_DESTINO_VALIDO)
        self.assertFalse(resultado.deve_encerrar)
        self.porta.inserir.assert_not_called()

    def test_sucesso_confirmado_solicita_encerramento(self):
        self.porta.destino_valido.return_value = True
        self.porta.inserir.return_value = True
        resultado = self.caso.executar(self.script.id)
        self.assertIs(resultado, ResultadoInsercao.SUCESSO)
        self.assertTrue(resultado.deve_encerrar)
        self.porta.inserir.assert_called_once_with(self.script.conteudo)

    def test_falha_ou_resultado_incerto_mantem_aplicacao_aberta(self):
        self.porta.destino_valido.return_value = True
        for resposta in (False, None, 1):
            with self.subTest(resposta=resposta):
                self.porta.inserir.return_value = resposta
                resultado = self.caso.executar(self.script.id)
                self.assertIs(resultado, ResultadoInsercao.FALHA)
                self.assertFalse(resultado.deve_encerrar)

    def test_script_inexistente_nao_interage_com_destino(self):
        with self.assertRaises(EntidadeNaoEncontrada):
            self.caso.executar(999)
        self.porta.destino_valido.assert_not_called()
        self.porta.inserir.assert_not_called()

    def test_erro_tecnico_nao_e_convertido_em_sucesso(self):
        self.porta.destino_valido.return_value = True
        self.porta.inserir.side_effect = RuntimeError("Falha técnica")
        with self.assertRaises(RuntimeError):
            self.caso.executar(self.script.id)


if __name__ == "__main__":
    unittest.main()
