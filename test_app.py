import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app as sistema
import autenticacao as modulo_autenticacao
import banco as modulo_banco
import cadastrar_usuario as modulo_cadastro
import equipe as modulo_equipe
import rotas_sms
import sms as modulo_sms
from autenticacao import ErroAutenticacao
from sms import ErroSMS
from banco import BancoErro
from caixa import Caixa
from carrinho import Carrinho
from estoque import Estoque
from mesa import Mesa
from seguranca import codigo_da_mesa
from usuario import email_valido, nome_valido, senha_valida


class BancoFalso:
    """Troca o Neon por um dicionário em memória nos testes."""

    def __init__(self):
        self.usuarios = {
            "uid-1": {"id": 1, "firebase_uid": "uid-1", "nome": "Kennedy Fernando", "email": "teste@exemplo.com", "ativo": True, "perfil": "gerente"}
        }
        self.recuperacoes_liberadas = True
        self.fora_do_ar = False
        self.logins = []

    def _conferir(self):
        if self.fora_do_ar:
            raise BancoErro("Neon fora do ar")

    def buscar_usuario_por_uid(self, uid):
        self._conferir()
        return self.usuarios.get(uid)

    def buscar_usuario_por_email(self, email):
        self._conferir()
        return next((u for u in self.usuarios.values() if u["email"] == email), None)

    def criar_usuario(self, uid, nome, email, perfil="gerente"):
        self._conferir()
        self.usuarios[uid] = {"id": len(self.usuarios) + 1, "firebase_uid": uid, "nome": nome, "email": email, "ativo": True, "perfil": perfil}

    def registrar_login(self, uid):
        self._conferir()
        self.logins.append(uid)

    def contar_usuarios(self):
        self._conferir()
        return len(self.usuarios)

    def listar_usuarios(self):
        self._conferir()
        return sorted(self.usuarios.values(), key=lambda u: u["nome"])

    def buscar_usuario_por_id(self, id_usuario):
        self._conferir()
        return next((u for u in self.usuarios.values() if u["id"] == id_usuario), None)

    def alterar_perfil(self, id_usuario, perfil):
        self.buscar_usuario_por_id(id_usuario)["perfil"] = perfil

    def alterar_ativo(self, id_usuario, ativo):
        self.buscar_usuario_por_id(id_usuario)["ativo"] = ativo

    def reservar_envio_recuperacao(self, email, intervalo_segundos=60):
        self._conferir()
        usuario = self.buscar_usuario_por_email(email)
        return bool(usuario and usuario["ativo"] and self.recuperacoes_liberadas)


class AutenticacaoFalsa:
    """Troca o Firebase por contas em memória nos testes."""

    def __init__(self):
        self.contas = {"teste@exemplo.com": {"uid": "uid-1", "senha": "Senha12345"}}
        self.relogio = 1000
        self.valido_apos = 0
        self.desativada = False
        self.indisponivel = False
        self.emails_enviados = []
        self.criadas = []
        self.removidas = []
        self.redefinir_senha_chamadas = []

    def entrar(self, email, senha):
        if self.indisponivel:
            raise ErroAutenticacao("indisponivel", "Firebase fora do ar")
        conta = self.contas.get(email)
        if conta is None or conta["senha"] != senha:
            raise ErroAutenticacao("credenciais", "E-mail ou senha incorretos.")
        self.relogio += 1
        return {"uid": conta["uid"], "email": email, "iat": self.relogio}

    def enviar_recuperacao(self, email):
        if self.indisponivel:
            raise ErroAutenticacao("indisponivel", "Firebase fora do ar")
        self.emails_enviados.append(email)

    def conta_ainda_valida(self, uid, iat):
        if self.indisponivel:
            raise ErroAutenticacao("indisponivel", "Firebase fora do ar")
        return not self.desativada and iat >= self.valido_apos

    def redefinir_senha(self, email, nova_senha):
        """Simula o que o Firebase faz quando a pessoa conclui o link do e-mail."""
        self.contas[email]["senha"] = nova_senha
        self.relogio += 1
        self.valido_apos = self.relogio

    def redefinir_senha(self, uid, nova_senha):
        if self.indisponivel:
            raise ErroAutenticacao("indisponivel", "Firebase fora do ar")
        email = next(e for e, conta in self.contas.items() if conta["uid"] == uid)
        self.redefinir_senha_chamadas.append((uid, nova_senha))
        self.redefinir_senha_de_conta(email, nova_senha)

    def redefinir_senha_de_conta(self, email, nova_senha):
        """Troca a senha e derruba as sessões antigas, como o Firebase faz."""
        self.contas[email]["senha"] = nova_senha
        self.relogio += 1
        self.valido_apos = self.relogio

    def buscar_conta_por_email(self, email):
        conta = self.contas.get(email)
        return SimpleNamespace(uid=conta["uid"]) if conta else None

    def criar_conta(self, email, senha, nome):
        uid = "uid-" + str(len(self.contas) + 1)
        self.contas[email] = {"uid": uid, "senha": senha}
        self.criadas.append(uid)
        return uid

    def remover_conta(self, uid):
        self.removidas.append(uid)


class BaseSistema(unittest.TestCase):
    def setUp(self):
        self.banco = BancoFalso()
        self.firebase = AutenticacaoFalsa()
        self.banco_real = sistema.banco
        self.autenticacao_real = sistema.autenticacao
        sistema.banco = self.banco
        sistema.autenticacao = self.firebase
        self.addCleanup(self.restaurar)

        sistema.app.config["TESTING"] = True
        sistema.tentativas_login = {}
        sistema.tentativas_recuperacao = {}
        sistema.tentativas_pagamento = {}
        sistema.tentativas_instalacao = {}
        sistema.tentativas_codigo = {}
        self.persistir_real = sistema.persistir_estado
        sistema.persistir_estado = False
        sistema.mesas = [Mesa("Livre", numero, False) for numero in range(1, 9)]
        sistema.pedidos = []
        sistema.caixa = Caixa()
        sistema.estoque = Estoque()
        sistema.numero_pedido = 1
        sistema.iniciar_sistema()
        self.cliente = sistema.app.test_client()
        self.cliente.post("/api/login", json={"email": "teste@exemplo.com", "senha": "Senha12345"})
        with self.cliente.session_transaction() as sessao:
            self.headers = {"X-CSRF-Token": sessao["token"]}

    def restaurar(self):
        sistema.persistir_estado = self.persistir_real
        sistema.banco = self.banco_real
        sistema.autenticacao = self.autenticacao_real

    def enviar(self, rota, dados):
        return self.cliente.post(rota, json=dados, headers=self.headers)

    def criar_pedido(self):
        return self.enviar("/api/pedidos", {"mesa": 1, "itens": [{"nome": "Pudim", "quantidade": 2}]})

    def logar(self, email="teste@exemplo.com", senha="Senha12345"):
        return sistema.app.test_client().post("/api/login", json={"email": email, "senha": senha})

    def forcar_conferencia(self):
        """Faz a próxima requisição conferir a sessão de novo no Firebase e no Neon."""
        with self.cliente.session_transaction() as sessao:
            sessao["tentou_em"] = 0


class TesteSistemaRestaurante(BaseSistema):
    # ---------- acesso ----------

    def test_paginas_e_acesso(self):
        pagina = self.cliente.get("/").data
        self.assertIn(b"Restaurante BKV", pagina)
        self.assertIn(b'data-nome="Kennedy Fernando"', pagina)
        anonimo = sistema.app.test_client()
        self.assertEqual(anonimo.get("/").status_code, 302)
        self.assertEqual(anonimo.get("/api/dados").status_code, 401)
        self.assertEqual(anonimo.get("/login").status_code, 200)
        self.assertEqual(self.cliente.post("/api/pedidos", json={}).status_code, 403)
        self.assertEqual(self.enviar("/api/sair", {}).status_code, 200)
        self.assertEqual(self.cliente.get("/api/dados").status_code, 401)

    def test_login_registra_horario_no_banco(self):
        self.assertEqual(self.banco.logins, ["uid-1"])

    def test_login_com_dados_incorretos(self):
        errada = self.logar(senha="Errada12345")
        desconhecido = self.logar(email="ausente@exemplo.com")
        self.assertEqual(errada.status_code, 401)
        self.assertEqual(errada.json, desconhecido.json)
        self.assertEqual(self.logar(email="sem-arroba").status_code, 401)
        self.assertEqual(self.logar(senha="").status_code, 401)

    def test_conta_do_firebase_sem_permissao_no_neon(self):
        self.firebase.contas["novo@exemplo.com"] = {"uid": "uid-novo", "senha": "Senha12345"}
        resposta = self.logar(email="novo@exemplo.com")
        self.assertEqual(resposta.status_code, 403)
        self.banco.usuarios["uid-novo"] = {"id": 2, "firebase_uid": "uid-novo", "nome": "Novo", "email": "novo@exemplo.com", "ativo": False, "perfil": "gerente"}
        self.assertEqual(self.logar(email="novo@exemplo.com").status_code, 403)
        self.banco.usuarios["uid-novo"]["ativo"] = True
        self.assertEqual(self.logar(email="novo@exemplo.com").status_code, 200)

    def test_falhas_dos_servicos_no_login(self):
        self.firebase.indisponivel = True
        self.assertEqual(self.logar().status_code, 503)
        self.firebase.indisponivel = False
        self.banco.fora_do_ar = True
        self.assertEqual(self.logar().status_code, 503)
        self.banco.fora_do_ar = False
        with patch.object(self.firebase, "entrar", side_effect=ErroAutenticacao("configuracao", "chave errada")):
            resposta = self.logar()
        self.assertEqual(resposta.status_code, 503)
        self.assertNotIn("chave errada", resposta.get_data(as_text=True))
        with patch.object(self.firebase, "entrar", side_effect=ErroAutenticacao("desativada", "x")):
            self.assertEqual(self.logar().status_code, 403)
        with patch.object(self.firebase, "entrar", side_effect=ErroAutenticacao("muitas_tentativas", "x")):
            self.assertEqual(self.logar().status_code, 429)

    def test_limite_login(self):
        for tentativa in range(9):
            self.cliente.post("/api/login", json={"email": "teste@exemplo.com", "senha": "errada"})
        self.assertEqual(self.cliente.post("/api/login", json={}).status_code, 429)

    # ---------- sessão conferida no Firebase e no Neon ----------

    def test_sessao_cai_depois_de_redefinir_a_senha(self):
        self.firebase.redefinir_senha_de_conta("teste@exemplo.com", "NovaSenha123")
        # Antes da próxima conferência periódica, a sessão ainda funciona.
        self.assertEqual(self.cliente.get("/api/dados").status_code, 200)
        self.forcar_conferencia()
        self.assertEqual(self.cliente.get("/api/dados").status_code, 401)
        self.assertEqual(self.logar(senha="Senha12345").status_code, 401)
        self.assertEqual(self.logar(senha="NovaSenha123").status_code, 200)

    def test_sessao_cai_se_usuario_for_desativado_ou_removido(self):
        self.banco.usuarios["uid-1"]["ativo"] = False
        self.forcar_conferencia()
        self.assertEqual(self.cliente.get("/api/dados").status_code, 401)

        self.banco.usuarios["uid-1"]["ativo"] = True
        cliente = sistema.app.test_client()
        cliente.post("/api/login", json={"email": "teste@exemplo.com", "senha": "Senha12345"})
        self.firebase.desativada = True
        with cliente.session_transaction() as sessao:
            sessao["tentou_em"] = 0
        self.assertEqual(cliente.get("/api/dados").status_code, 401)

    def test_servicos_fora_do_ar_nao_derrubam_a_sessao_de_imediato(self):
        self.firebase.indisponivel = True
        self.forcar_conferencia()
        self.assertEqual(self.cliente.get("/api/dados").status_code, 200)
        self.banco.fora_do_ar = True
        self.forcar_conferencia()
        self.assertEqual(self.cliente.get("/api/dados").status_code, 200)
        with self.cliente.session_transaction() as sessao:
            sessao["tentou_em"] = 0
            sessao["verificado_em"] = time.time() - sistema.TOLERANCIA_FALHA - 1
        self.assertEqual(self.cliente.get("/api/dados").status_code, 401)

    # ---------- esqueci minha senha ----------

    def test_recuperacao_envia_email_pelo_firebase(self):
        resposta = self.cliente.post("/api/recuperar-senha", json={"email": "Teste@Exemplo.com"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.firebase.emails_enviados, ["teste@exemplo.com"])

    def test_recuperacao_nao_revela_quem_esta_cadastrado(self):
        conhecido = self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"})
        desconhecido = self.cliente.post("/api/recuperar-senha", json={"email": "ausente@exemplo.com"})
        self.assertEqual(conhecido.json, desconhecido.json)
        self.assertEqual(self.firebase.emails_enviados, ["teste@exemplo.com"])

    def test_recuperacao_so_para_conta_ativa_e_sem_pedido_recente(self):
        self.banco.recuperacoes_liberadas = False  # simula o intervalo de 1 minuto
        resposta = self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.firebase.emails_enviados, [])
        self.banco.recuperacoes_liberadas = True
        self.banco.usuarios["uid-1"]["ativo"] = False
        self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"})
        self.assertEqual(self.firebase.emails_enviados, [])

    def test_recuperacao_com_falha_no_firebase_ou_no_neon(self):
        normal = self.cliente.post("/api/recuperar-senha", json={"email": "ausente@exemplo.com"})
        self.firebase.indisponivel = True
        falha_firebase = self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"})
        self.firebase.indisponivel = False
        self.banco.fora_do_ar = True
        falha_banco = self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"})
        self.assertEqual(falha_firebase.status_code, 200)
        self.assertEqual(falha_firebase.json, normal.json)
        self.assertEqual(falha_banco.json, normal.json)

    def test_recuperacao_valida_email_e_limita_pedidos(self):
        self.assertEqual(self.cliente.post("/api/recuperar-senha", json={"email": "sem-arroba"}).status_code, 400)
        self.assertEqual(self.cliente.post("/api/recuperar-senha", json={}).status_code, 400)
        for pedido in range(5):
            self.assertEqual(self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"}).status_code, 200)
        self.assertEqual(self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"}).status_code, 429)

    def test_rota_antiga_de_codigo_nao_existe_mais(self):
        self.assertEqual(self.cliente.post("/api/alterar-senha", json={}, headers=self.headers).status_code, 404)

    # ---------- restaurante (sem mudanças) ----------

    def test_fluxo_completo_de_venda(self):
        resposta = self.criar_pedido()
        self.assertEqual(resposta.status_code, 201)
        numero = resposta.json["pedido"]["numero"]
        rota = f"/api/pedidos/{numero}/finalizar"
        self.assertEqual(self.enviar(rota, {"forma_pagamento": "PIX"}).status_code, 200)
        self.assertEqual(self.enviar(rota, {"forma_pagamento": "PIX"}).status_code, 404)
        dados = self.cliente.get("/api/dados").json
        self.assertEqual(dados["caixa"]["total_vendido"], 24)
        self.assertEqual(sistema.estoque.produtos_prontos["Pudim"]["quantidade"], 13)

    def test_itens_repetidos_e_estoque(self):
        resposta = self.enviar("/api/pedidos", {"mesa": 1, "itens": [
            {"nome": "Pudim", "quantidade": 10}, {"nome": "Pudim", "quantidade": 10}
        ]})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(sistema.estoque.produtos_prontos["Pudim"]["quantidade"], 15)
        self.assertEqual(sistema.pedidos, [])
        resposta = self.enviar("/api/pedidos", {"mesa": 1, "itens": [
            {"nome": "Pudim", "quantidade": 2}, {"nome": "Pudim", "quantidade": 3}
        ]})
        self.assertEqual(resposta.json["pedido"]["total"], 60)

    def test_entradas_invalidas(self):
        for quantidade in [True, 1.5, "1.5", 0, -1, None, {}, 10001]:
            resposta = self.enviar("/api/pedidos", {"mesa": 1, "itens": [{"nome": "Pudim", "quantidade": quantidade}]})
            self.assertEqual(resposta.status_code, 400)
        for itens in [None, {}, [None], ["Pudim"], []]:
            resposta = self.enviar("/api/pedidos", {"mesa": 1, "itens": itens})
            self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.cliente.post("/api/pedidos", json=[], headers=self.headers).status_code, 400)
        self.assertEqual(self.enviar("/api/estoque/entrada", {"nome": [], "quantidade": 2}).status_code, 400)

    def test_cancelar(self):
        self.criar_pedido()
        self.assertEqual(self.enviar("/api/pedidos/1/cancelar", {"motivo": "Cliente desistiu"}).status_code, 200)
        self.assertEqual(sistema.estoque.produtos_prontos["Pudim"]["quantidade"], 15)
        self.assertEqual(sistema.mesas[0].status, "Livre")
        self.assertEqual(self.enviar("/api/pedidos/1/cancelar", {"motivo": "Cliente desistiu"}).status_code, 400)
        self.assertEqual(self.enviar("/api/pedidos/1/finalizar", {"forma_pagamento": "PIX"}).status_code, 404)

    def test_status(self):
        self.criar_pedido()
        self.assertEqual(self.enviar("/api/pedidos/1/status", {"status": "Entregue"}).status_code, 400)
        self.assertEqual(self.enviar("/api/pedidos/1/status", {"status": "Pronto"}).status_code, 200)
        self.assertEqual(self.enviar("/api/pedidos/1/status", {"status": "Entregue"}).status_code, 200)

    def test_carrinho(self):
        carrinho = Carrinho()
        carrinho.adicionar_item("Água", 5, 2)
        carrinho.adicionar_item("Água", 5, 1)
        self.assertEqual(carrinho.calcular_total(), 15)
        carrinho.escolher_pagamento("PIX")
        self.assertEqual(carrinho.finalizar_compra(), 15)
        with self.assertRaises(ValueError):
            carrinho.finalizar_compra()
        self.criar_pedido()
        self.assertIsInstance(sistema.pedidos[0], Carrinho)


class TesteValidacoes(unittest.TestCase):
    def test_senha_email_e_nome(self):
        self.assertTrue(senha_valida("Senha12345"))
        for senha in ["curta1", "somenteletras", "12345678", "a1" * 65, None, 12345678]:
            self.assertFalse(senha_valida(senha))
        self.assertTrue(email_valido("a@b.com"))
        for email in ["sem-arroba", "a@b", "a b@c.com", "@c.com", "a@.com", "a@c.", None]:
            self.assertFalse(email_valido(email))
        self.assertTrue(nome_valido("Ana"))
        for nome in ["", " a ", "x" * 101, None]:
            self.assertFalse(nome_valido(nome))


class TesteBancoNeon(unittest.TestCase):
    def test_sem_endereco_configurado(self):
        with patch.dict("os.environ", {"DATABASE_URL": ""}):
            with self.assertRaises(BancoErro):
                modulo_banco.buscar_usuario_por_uid("x")

    def test_falha_de_conexao_vira_banco_erro(self):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://u:p@localhost/db"}):
            with patch("banco.psycopg.connect", side_effect=modulo_banco.psycopg.OperationalError("sem rede")):
                with self.assertRaises(BancoErro):
                    modulo_banco.buscar_usuario_por_uid("x")


def resposta_http(status, corpo):
    resposta = MagicMock()
    resposta.status_code = status
    resposta.json.return_value = corpo
    return resposta


def erro_firebase(status, mensagem):
    return resposta_http(status, {"error": {"code": status, "message": mensagem}})


@patch.dict("os.environ", {"FIREBASE_API_KEY": "chave-de-teste"})
class TesteIntegracaoFirebase(unittest.TestCase):
    def test_login_correto_devolve_uid_e_momento_do_token(self):
        with patch("autenticacao.requests.post", return_value=resposta_http(200, {"idToken": "token"})) as post, \
                patch("autenticacao._app"), \
                patch("autenticacao.auth.verify_id_token", return_value={"uid": "u1", "email": "a@b.com", "iat": 123}):
            conta = modulo_autenticacao.entrar("a@b.com", "Senha12345")
        self.assertEqual(conta, {"uid": "u1", "email": "a@b.com", "iat": 123})
        self.assertEqual(post.call_args.kwargs["params"], {"key": "chave-de-teste"})
        self.assertEqual(post.call_args.kwargs["json"]["password"], "Senha12345")

    def test_erros_do_login_sao_traduzidos(self):
        casos = {
            "INVALID_LOGIN_CREDENTIALS": "credenciais",
            "EMAIL_NOT_FOUND": "credenciais",
            "INVALID_PASSWORD": "credenciais",
            "USER_DISABLED": "desativada",
            "TOO_MANY_ATTEMPTS_TRY_LATER : Access to this account has been temporarily disabled": "muitas_tentativas",
            "API_KEY_INVALID": "configuracao",
            "OPERATION_NOT_ALLOWED : Password sign-in is disabled for this project.": "configuracao",
        }
        for mensagem, tipo in casos.items():
            with patch("autenticacao.requests.post", return_value=erro_firebase(400, mensagem)):
                with self.assertRaises(ErroAutenticacao) as contexto:
                    modulo_autenticacao.entrar("a@b.com", "x")
            self.assertEqual(contexto.exception.tipo, tipo, mensagem)

    def test_sem_internet_ou_sem_chave(self):
        with patch("autenticacao.requests.post", side_effect=modulo_autenticacao.requests.ConnectionError()):
            with self.assertRaises(ErroAutenticacao) as contexto:
                modulo_autenticacao.entrar("a@b.com", "x")
        self.assertEqual(contexto.exception.tipo, "indisponivel")
        with patch.dict("os.environ", {"FIREBASE_API_KEY": ""}):
            with self.assertRaises(ErroAutenticacao) as contexto:
                modulo_autenticacao.entrar("a@b.com", "x")
        self.assertEqual(contexto.exception.tipo, "configuracao")

    def test_token_de_outro_projeto_e_recusado_com_mensagem_clara(self):
        with patch("autenticacao.requests.post", return_value=resposta_http(200, {"idToken": "token"})), \
                patch("autenticacao._app"), \
                patch("autenticacao.auth.verify_id_token", side_effect=ValueError("audience errada")):
            with self.assertRaises(ErroAutenticacao) as contexto:
                modulo_autenticacao.entrar("a@b.com", "x")
        self.assertEqual(contexto.exception.tipo, "configuracao")

    def test_pedido_de_recuperacao(self):
        with patch("autenticacao.requests.post", return_value=resposta_http(200, {"email": "a@b.com"})) as post:
            modulo_autenticacao.enviar_recuperacao("a@b.com")
        self.assertEqual(post.call_args.kwargs["json"], {"requestType": "PASSWORD_RESET", "email": "a@b.com"})
        self.assertEqual(post.call_args.kwargs["headers"]["X-Firebase-Locale"], "pt-BR")
        self.assertTrue(post.call_args.args[0].endswith("accounts:sendOobCode"))
        with patch("autenticacao.requests.post", return_value=erro_firebase(400, "EMAIL_NOT_FOUND")):
            modulo_autenticacao.enviar_recuperacao("a@b.com")  # não deve levantar erro
        with patch("autenticacao.requests.post", return_value=erro_firebase(400, "API_KEY_INVALID")):
            with self.assertRaises(ErroAutenticacao):
                modulo_autenticacao.enviar_recuperacao("a@b.com")

    def test_conferencia_da_sessao(self):
        def conta(desativada=False, valido_apos_ms=None):
            return SimpleNamespace(disabled=desativada, tokens_valid_after_timestamp=valido_apos_ms)

        with patch("autenticacao._app"):
            with patch("autenticacao.auth.get_user", return_value=conta(valido_apos_ms=1_000_000)):
                self.assertTrue(modulo_autenticacao.conta_ainda_valida("u1", 1000))
                self.assertFalse(modulo_autenticacao.conta_ainda_valida("u1", 999))
            with patch("autenticacao.auth.get_user", return_value=conta()):
                self.assertTrue(modulo_autenticacao.conta_ainda_valida("u1", 1))
            with patch("autenticacao.auth.get_user", return_value=conta(desativada=True)):
                self.assertFalse(modulo_autenticacao.conta_ainda_valida("u1", 10**10))
            with patch("autenticacao.auth.get_user", side_effect=modulo_autenticacao.auth.UserNotFoundError("sumiu")):
                self.assertFalse(modulo_autenticacao.conta_ainda_valida("u1", 10**10))

    def test_chave_de_api_confere_com_login_falso(self):
        with patch("autenticacao.requests.post", return_value=erro_firebase(400, "INVALID_LOGIN_CREDENTIALS")):
            modulo_autenticacao.testar_chave_api()  # chave boa: não levanta erro
        with patch("autenticacao.requests.post", return_value=erro_firebase(400, "API_KEY_INVALID")):
            with self.assertRaises(ErroAutenticacao):
                modulo_autenticacao.testar_chave_api()


class BancoSMSFalso:
    """Troca a parte de SMS do Neon por um dicionário em memória, com as mesmas regras do SQL."""

    def __init__(self, banco):
        self.banco = banco
        self.dados = {}

    def _linha(self, email):
        return self.dados.setdefault(email, {"telefone": None, "hash": None, "validade": 0, "tentativas": 0, "ultimo_envio": 0})

    def _usuario(self, email):
        return self.banco.buscar_usuario_por_email(email)

    def _falhar_se_fora(self):
        if self.banco.fora_do_ar:
            raise BancoErro("Neon fora do ar")

    def definir_telefone(self, email, telefone):
        self._falhar_se_fora()
        if self._usuario(email) is None:
            return False
        self._linha(email)["telefone"] = telefone
        return True

    def buscar_telefone(self, email):
        return self._linha(email)["telefone"]

    def reservar_envio(self, email, intervalo_segundos=60):
        self._falhar_se_fora()
        usuario, linha = self._usuario(email), self._linha(email)
        if not usuario or not usuario["ativo"] or not linha["telefone"]:
            return None
        if time.time() - linha["ultimo_envio"] < intervalo_segundos:
            return None
        linha.update(ultimo_envio=time.time(), hash=None, validade=0, tentativas=0)
        return {"firebase_uid": usuario["firebase_uid"], "telefone": linha["telefone"]}

    def guardar_codigo(self, email, codigo_hash, validade_segundos=600):
        self._falhar_se_fora()
        self._linha(email).update(hash=codigo_hash, validade=time.time() + validade_segundos, tentativas=0)

    def consumir_tentativa(self, email):
        self._falhar_se_fora()
        usuario, linha = self._usuario(email), self._linha(email)
        if not usuario or not usuario["ativo"] or not linha["hash"] or linha["validade"] <= time.time() or linha["tentativas"] >= 5:
            return None
        linha["tentativas"] += 1
        return {"firebase_uid": usuario["firebase_uid"], "sms_codigo_hash": linha["hash"]}

    def invalidar_codigo(self, email, codigo_hash):
        self._falhar_se_fora()
        linha = self._linha(email)
        if linha["hash"] != codigo_hash:
            return False
        linha.update(hash=None, validade=0, tentativas=0)
        return True


class TesteRecuperacaoPorSMS(unittest.TestCase):
    """Rotas /api/sms/*. O Neon, o Firebase e o provedor de SMS são simulados."""

    def setUp(self):
        self.banco = BancoFalso()
        self.firebase = AutenticacaoFalsa()
        self.sms_banco = BancoSMSFalso(self.banco)
        self.sms_banco.definir_telefone("teste@exemplo.com", "5567999998888")
        self.envios = []
        self.provedor = SimpleNamespace(enviar_codigo=lambda telefone, codigo: self.envios.append((telefone, codigo)))

        substituicoes = [
            (sistema, "banco", self.banco), (sistema, "autenticacao", self.firebase),
            (rotas_sms, "banco_sms", self.sms_banco), (rotas_sms, "autenticacao", self.firebase),
            (rotas_sms, "sms", self.provedor), (sistema, "persistir_estado", False),
        ]
        for modulo, nome, falso in substituicoes:
            original = getattr(modulo, nome)
            setattr(modulo, nome, falso)
            self.addCleanup(setattr, modulo, nome, original)

        sistema.app.config["TESTING"] = True
        sistema.tentativas_login = {}
        rotas_sms.tentativas_envio.clear()
        rotas_sms.tentativas_confirmacao.clear()
        self.cliente = sistema.app.test_client()

    def solicitar(self, email="teste@exemplo.com"):
        return self.cliente.post("/api/sms/solicitar", json={"email": email})

    def confirmar(self, codigo, senha="NovaSenha123", confirmacao=None, email="teste@exemplo.com"):
        return self.cliente.post("/api/sms/confirmar", json={
            "email": email, "codigo": codigo, "senha": senha,
            "confirmacao": senha if confirmacao is None else confirmacao,
        })

    def pedir_codigo(self):
        self.assertEqual(self.solicitar().status_code, 200)
        return self.envios[-1][1]

    def liberar_novo_pedido(self):
        self.sms_banco.dados["teste@exemplo.com"]["ultimo_envio"] = 0

    # ---------- pedir o código ----------

    def test_envia_codigo_para_o_sms_registrado(self):
        codigo = self.pedir_codigo()
        self.assertEqual(self.envios[0][0], "5567999998888")
        self.assertRegex(codigo, r"^\d{4}$")
        guardado = self.sms_banco.dados["teste@exemplo.com"]["hash"]
        self.assertNotIn(codigo, guardado)  # só o hash fica guardado
        self.assertGreater(self.sms_banco.dados["teste@exemplo.com"]["validade"], time.time() + 590)

    def test_nao_revela_quem_esta_cadastrado(self):
        conhecido = self.solicitar()
        self.assertEqual(len(self.envios), 1)
        desconhecido = self.solicitar("ausente@exemplo.com")
        self.banco.usuarios["uid-2"] = {"id": 2, "firebase_uid": "uid-2", "nome": "Sem Celular", "email": "semcelular@exemplo.com", "ativo": True}
        sem_telefone = self.solicitar("semcelular@exemplo.com")
        self.banco.usuarios["uid-1"]["ativo"] = False
        self.liberar_novo_pedido()
        inativo = self.solicitar()
        self.assertEqual(conhecido.json, desconhecido.json)
        self.assertEqual(conhecido.json, sem_telefone.json)
        self.assertEqual(conhecido.json, inativo.json)
        self.assertEqual(len(self.envios), 1)  # só o primeiro pedido enviou algo

    def test_um_codigo_por_minuto(self):
        self.pedir_codigo()
        self.solicitar()
        self.assertEqual(len(self.envios), 1)
        self.liberar_novo_pedido()
        self.solicitar()
        self.assertEqual(len(self.envios), 2)

    def test_falha_do_provedor_nao_deixa_codigo_valido(self):
        def falhar(telefone, codigo):
            raise ErroSMS("falha", "modelo inexistente")
        self.provedor.enviar_codigo = falhar
        normal = self.solicitar("ausente@exemplo.com")
        resposta = self.solicitar()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json, normal.json)
        self.assertIsNone(self.sms_banco.dados["teste@exemplo.com"]["hash"])

    def test_banco_fora_do_ar_ao_pedir(self):
        normal = self.solicitar("ausente@exemplo.com")
        self.banco.fora_do_ar = True
        resposta = self.solicitar()
        self.assertEqual((resposta.status_code, resposta.json), (200, normal.json))
        self.assertEqual(self.envios, [])

    def test_valida_email_e_limita_pedidos_por_ip(self):
        self.assertEqual(self.cliente.post("/api/sms/solicitar", json={"email": "sem-arroba"}).status_code, 400)
        self.assertEqual(self.cliente.post("/api/sms/solicitar", json={}).status_code, 400)
        for pedido in range(5):
            self.assertEqual(self.solicitar().status_code, 200)
        self.assertEqual(self.solicitar().status_code, 429)

    # ---------- confirmar o código e trocar a senha ----------

    def test_troca_de_senha_completa(self):
        entrou = self.cliente.post("/api/login", json={"email": "teste@exemplo.com", "senha": "Senha12345"})
        self.assertEqual(entrou.status_code, 200)
        codigo = self.pedir_codigo()

        self.assertEqual(self.confirmar(codigo).status_code, 200)
        self.assertEqual(self.firebase.redefinir_senha_chamadas, [("uid-1", "NovaSenha123")])
        # o código é de uso único
        self.assertEqual(self.confirmar(codigo).status_code, 400)
        self.assertEqual(len(self.firebase.redefinir_senha_chamadas), 1)
        # a resposta limpa a sessão do navegador que fez a troca
        self.assertEqual(self.cliente.get("/api/dados").status_code, 401)
        # senha antiga deixa de valer, a nova funciona
        anonimo = sistema.app.test_client()
        self.assertEqual(anonimo.post("/api/login", json={"email": "teste@exemplo.com", "senha": "Senha12345"}).status_code, 401)
        self.assertEqual(anonimo.post("/api/login", json={"email": "teste@exemplo.com", "senha": "NovaSenha123"}).status_code, 200)

    def test_sessao_aberta_em_outro_aparelho_cai_depois_da_troca(self):
        outro = sistema.app.test_client()
        outro.post("/api/login", json={"email": "teste@exemplo.com", "senha": "Senha12345"})
        self.assertEqual(outro.get("/api/dados").status_code, 200)
        self.assertEqual(self.confirmar(self.pedir_codigo()).status_code, 200)
        with outro.session_transaction() as sessao:
            sessao["tentou_em"] = 0  # força a conferência periódica
        self.assertEqual(outro.get("/api/dados").status_code, 401)

    def test_codigo_errado_e_limite_de_cinco_tentativas(self):
        codigo = self.pedir_codigo()
        errado = "0000" if codigo != "0000" else "1111"
        for tentativa in range(5):
            resposta = self.confirmar(errado)
            self.assertEqual((resposta.status_code, resposta.json["erro"]), (400, rotas_sms.MENSAGEM_CODIGO_INVALIDO))
        self.assertEqual(self.confirmar(codigo).status_code, 400)  # até o código certo é recusado
        self.assertEqual(self.firebase.redefinir_senha_chamadas, [])
        self.liberar_novo_pedido()
        novo = self.pedir_codigo()
        self.assertEqual(self.confirmar(novo).status_code, 200)

    def test_codigo_expirado(self):
        codigo = self.pedir_codigo()
        self.sms_banco.dados["teste@exemplo.com"]["validade"] = time.time() - 1
        self.assertEqual(self.confirmar(codigo).status_code, 400)
        self.assertEqual(self.firebase.redefinir_senha_chamadas, [])

    def test_novo_codigo_substitui_o_anterior(self):
        antigo = self.pedir_codigo()
        self.liberar_novo_pedido()
        with patch("rotas_sms.secrets.randbelow", return_value=6543):
            novo = self.pedir_codigo()
        self.assertEqual(novo, "6543")
        if antigo != novo:
            self.assertEqual(self.confirmar(antigo).status_code, 400)
        self.assertEqual(self.confirmar(novo).status_code, 200)

    def test_dados_invalidos_nao_gastam_tentativas(self):
        codigo = self.pedir_codigo()
        self.assertEqual(self.confirmar(codigo, senha="NovaSenha123", confirmacao="Diferente123").status_code, 400)
        self.assertEqual(self.confirmar(codigo, senha="curta1").status_code, 400)
        self.assertEqual(self.confirmar(codigo, senha="somente-letras").status_code, 400)
        self.assertEqual(self.confirmar("123").status_code, 400)
        self.assertEqual(self.confirmar("abcd").status_code, 400)
        self.assertEqual(self.cliente.post("/api/sms/confirmar", json={}).status_code, 400)
        self.assertEqual(self.sms_banco.dados["teste@exemplo.com"]["tentativas"], 0)
        self.assertEqual(self.confirmar(codigo).status_code, 200)

    def test_email_desconhecido_recebe_a_mesma_resposta(self):
        codigo = self.pedir_codigo()
        conhecido = self.confirmar("0000" if codigo != "0000" else "1111")
        desconhecido = self.confirmar("0000", email="ausente@exemplo.com")
        self.assertEqual((conhecido.status_code, conhecido.json), (desconhecido.status_code, desconhecido.json))

    def test_conta_bloqueada_depois_do_pedido_nao_troca_a_senha(self):
        codigo = self.pedir_codigo()
        self.banco.usuarios["uid-1"]["ativo"] = False
        self.assertEqual(self.confirmar(codigo).status_code, 400)
        self.assertEqual(self.firebase.redefinir_senha_chamadas, [])

    def test_firebase_fora_do_ar_na_troca(self):
        codigo = self.pedir_codigo()
        self.firebase.indisponivel = True
        resposta = self.confirmar(codigo)
        self.assertEqual(resposta.status_code, 503)
        self.assertIn("novo código", resposta.json["erro"])
        self.firebase.indisponivel = False
        self.assertEqual(self.confirmar(codigo).status_code, 400)  # o código já foi gasto

    def test_banco_fora_do_ar_na_confirmacao(self):
        codigo = self.pedir_codigo()
        self.banco.fora_do_ar = True
        self.assertEqual(self.confirmar(codigo).status_code, 503)

    def test_limite_de_confirmacoes_por_ip(self):
        for tentativa in range(20):
            self.confirmar("0000")
        self.assertEqual(self.confirmar("0000").status_code, 429)

    def test_rotas_sao_publicas_e_o_resto_continua_protegido(self):
        self.assertEqual(self.solicitar().status_code, 200)
        self.assertEqual(self.cliente.get("/api/dados").status_code, 401)
        self.assertEqual(self.cliente.post("/api/pedidos", json={}).status_code, 401)

    def test_recuperacao_por_email_continua_funcionando(self):
        resposta = self.cliente.post("/api/recuperar-senha", json={"email": "teste@exemplo.com"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.firebase.emails_enviados, ["teste@exemplo.com"])


@patch.dict("os.environ", {}, clear=False)
class TesteEnvioSMS(unittest.TestCase):
    def ambiente(self, **variaveis):
        padrao = {nome: "" for nome in (
            "SMS_PROVEDOR", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_SMS_DE",
            "TWILIO_MESSAGING_SERVICE_SID", "ZENVIA_TOKEN", "ZENVIA_REMETENTE",
            "VONAGE_API_KEY", "VONAGE_API_SECRET", "VONAGE_REMETENTE")}
        padrao.update(variaveis)
        return patch.dict("os.environ", padrao)

    def resposta(self, status=200, corpo=None):
        return resposta_http(status, corpo or {})

    def test_telefones(self):
        casos = {
            "(67) 99999-8888": "5567999998888", "67999998888": "5567999998888", "+55 67 99999-8888": "5567999998888",
            "5567999998888": "5567999998888", "(67) 9999-8888": "556799998888", "0055 67 99999-8888": "5567999998888",
            "+1 555 123 4567": "15551234567",
        }
        for digitado, esperado in casos.items():
            self.assertEqual(modulo_sms.normalizar_telefone(digitado), esperado, digitado)
        for invalido in ["", "abc", "9999-8888", "(07) 99999-8888", "+55 67 999", "123", None, 5567999998888, "9" * 41, "+1234"]:
            self.assertIsNone(modulo_sms.normalizar_telefone(invalido), invalido)
        self.assertEqual(modulo_sms.mascarar_telefone("5567999998888"), "*********8888")

    def test_sem_provedor_ou_provedor_desconhecido(self):
        for valor in ["", "outro"]:
            with self.ambiente(SMS_PROVEDOR=valor):
                with self.assertRaises(ErroSMS) as contexto:
                    modulo_sms.enviar_codigo("5567999998888", "1234")
            self.assertEqual(contexto.exception.tipo, "configuracao")

    def test_texto_curto_sem_acentos(self):
        texto = modulo_sms.TEXTO_MENSAGEM.format(codigo="1234")
        self.assertIn("1234", texto)
        self.assertTrue(texto.isascii())  # sem acento: cabe em 1 SMS
        self.assertLessEqual(len(texto), 70)

    def test_twilio_com_numero_e_com_messaging_service(self):
        base = dict(SMS_PROVEDOR="twilio", TWILIO_ACCOUNT_SID="AC1", TWILIO_AUTH_TOKEN="tok", TWILIO_SMS_DE="+12025550123")
        with self.ambiente(**base):
            with patch("sms.requests.post", return_value=self.resposta()) as post:
                modulo_sms.enviar_codigo("5567999998888", "1234")
        self.assertEqual(post.call_args.args[0], "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages.json")
        self.assertEqual(post.call_args.kwargs["auth"], ("AC1", "tok"))
        dados = post.call_args.kwargs["data"]
        self.assertEqual((dados["From"], dados["To"]), ("+12025550123", "+5567999998888"))
        self.assertIn("1234", dados["Body"])
        self.assertNotIn("MessagingServiceSid", dados)

        with self.ambiente(TWILIO_MESSAGING_SERVICE_SID="MG1", **base):
            with patch("sms.requests.post", return_value=self.resposta()) as post:
                modulo_sms.enviar_codigo("5567999998888", "1234")
        dados = post.call_args.kwargs["data"]
        self.assertEqual(dados["MessagingServiceSid"], "MG1")
        self.assertNotIn("From", dados)

    def test_zenvia(self):
        with self.ambiente(SMS_PROVEDOR="zenvia", ZENVIA_TOKEN="TOK", ZENVIA_REMETENTE="bkv"):
            with patch("sms.requests.post", return_value=self.resposta()) as post:
                modulo_sms.enviar_codigo("5567999998888", "1234")
        self.assertEqual(post.call_args.args[0], "https://api.zenvia.com/v2/channels/sms/messages")
        self.assertEqual(post.call_args.kwargs["headers"], {"X-API-TOKEN": "TOK"})
        corpo = post.call_args.kwargs["json"]
        self.assertEqual((corpo["from"], corpo["to"]), ("bkv", "5567999998888"))
        self.assertEqual(corpo["contents"][0]["type"], "text")
        self.assertIn("1234", corpo["contents"][0]["text"])

    def test_vonage(self):
        ok = self.resposta(200, {"messages": [{"status": "0"}]})
        with self.ambiente(SMS_PROVEDOR="vonage", VONAGE_API_KEY="K", VONAGE_API_SECRET="S"):
            with patch("sms.requests.post", return_value=ok) as post:
                modulo_sms.enviar_codigo("5567999998888", "1234")
        self.assertEqual(post.call_args.args[0], "https://rest.nexmo.com/sms/json")
        dados = post.call_args.kwargs["data"]
        self.assertEqual((dados["api_key"], dados["api_secret"], dados["from"], dados["to"]), ("K", "S", "BKV", "5567999998888"))
        self.assertIn("1234", dados["text"])

    def test_vonage_recusa_com_status_200(self):
        casos = [("4", "configuracao"), ("9", "configuracao"), ("1", "indisponivel"), ("5", "indisponivel"), ("3", "falha")]
        for status, tipo in casos:
            corpo = {"messages": [{"status": status, "error-text": "motivo"}]}
            with self.ambiente(SMS_PROVEDOR="vonage", VONAGE_API_KEY="K", VONAGE_API_SECRET="S"):
                with patch("sms.requests.post", return_value=self.resposta(200, corpo)):
                    with self.assertRaises(ErroSMS) as contexto:
                        modulo_sms.enviar_codigo("5567999998888", "1234")
            self.assertEqual(contexto.exception.tipo, tipo, status)
        with self.ambiente(SMS_PROVEDOR="vonage", VONAGE_API_KEY="K", VONAGE_API_SECRET="S"):
            with patch("sms.requests.post", return_value=self.resposta(200, {"inesperado": 1})):
                with self.assertRaises(ErroSMS) as contexto:
                    modulo_sms.enviar_codigo("5567999998888", "1234")
        self.assertEqual(contexto.exception.tipo, "falha")

    def test_variaveis_obrigatorias(self):
        for provedor in ["twilio", "zenvia", "vonage"]:
            with self.ambiente(SMS_PROVEDOR=provedor):
                with self.assertRaises(ErroSMS) as contexto:
                    modulo_sms.enviar_codigo("5567999998888", "1234")
            self.assertEqual(contexto.exception.tipo, "configuracao", provedor)
        # Twilio sem remetente (nem número, nem Messaging Service)
        with self.ambiente(SMS_PROVEDOR="twilio", TWILIO_ACCOUNT_SID="A", TWILIO_AUTH_TOKEN="T"):
            with self.assertRaises(ErroSMS) as contexto:
                modulo_sms.enviar_codigo("5567999998888", "1234")
        self.assertIn("TWILIO_SMS_DE", contexto.exception.mensagem)

    def test_erros_do_provedor(self):
        casos = [
            (401, {"message": "Authenticate"}, "configuracao"),
            (403, {}, "configuracao"),
            (400, {"message": "Invalid 'To' Phone Number"}, "falha"),
            (429, {}, "indisponivel"),
            (500, {}, "indisponivel"),
        ]
        for status, corpo, tipo in casos:
            with self.ambiente(SMS_PROVEDOR="zenvia", ZENVIA_TOKEN="T", ZENVIA_REMETENTE="R"):
                with patch("sms.requests.post", return_value=self.resposta(status, corpo)):
                    with self.assertRaises(ErroSMS) as contexto:
                        modulo_sms.enviar_codigo("5567999998888", "1234")
            self.assertEqual(contexto.exception.tipo, tipo, (status, corpo))
        # o motivo da recusa aparece no terminal
        with self.ambiente(SMS_PROVEDOR="zenvia", ZENVIA_TOKEN="T", ZENVIA_REMETENTE="R"):
            with patch("sms.requests.post", return_value=self.resposta(400, {"message": "Invalid 'To' Phone Number"})):
                with self.assertRaises(ErroSMS) as contexto:
                    modulo_sms.enviar_codigo("5567999998888", "1234")
        self.assertIn("Invalid 'To' Phone Number", contexto.exception.mensagem)

    def test_sem_internet_nao_vaza_o_segredo_na_mensagem(self):
        erro_rede = modulo_sms.requests.ConnectionError("falha em https://api.zenvia.com/?token=SEGREDO")
        for provedor, variaveis in [
            ("zenvia", dict(ZENVIA_TOKEN="SEGREDO", ZENVIA_REMETENTE="R")),
            ("twilio", dict(TWILIO_ACCOUNT_SID="AC", TWILIO_AUTH_TOKEN="SEGREDO", TWILIO_SMS_DE="+1")),
            ("vonage", dict(VONAGE_API_KEY="K", VONAGE_API_SECRET="SEGREDO")),
        ]:
            with self.ambiente(SMS_PROVEDOR=provedor, **variaveis):
                with patch("sms.requests.post", side_effect=erro_rede):
                    with self.assertRaises(ErroSMS) as contexto:
                        modulo_sms.enviar_codigo("5567999998888", "1234")
            self.assertEqual(contexto.exception.tipo, "indisponivel", provedor)
            self.assertNotIn("SEGREDO", contexto.exception.mensagem)
            self.assertIsNone(contexto.exception.__cause__)


class TesteStatusDoSMS(unittest.TestCase):
    def test_botao_so_aparece_com_provedor_configurado(self):
        cliente = sistema.app.test_client()
        for valor, esperado in [("", False), ("outro", False), ("zenvia", True), ("TWILIO", True), ("vonage", True), ("meta", False), ("zapi", False)]:
            with patch.dict("os.environ", {"SMS_PROVEDOR": valor}):
                resposta = cliente.get("/api/sms/status")
            self.assertEqual((resposta.status_code, resposta.json), (200, {"ativo": esperado}), valor)


class TesteRedefinirSenhaNoFirebase(unittest.TestCase):
    def test_atualiza_a_senha_e_derruba_as_sessoes(self):
        with patch("autenticacao._app"), patch("autenticacao.auth.update_user") as atualizar, \
                patch("autenticacao.auth.revoke_refresh_tokens") as revogar:
            modulo_autenticacao.redefinir_senha("u1", "NovaSenha123")
        self.assertEqual(atualizar.call_args.args, ("u1",))
        self.assertEqual(atualizar.call_args.kwargs["password"], "NovaSenha123")
        self.assertEqual(revogar.call_args.args, ("u1",))

    def test_erros_viram_erro_de_autenticacao(self):
        with patch("autenticacao._app"):
            with patch("autenticacao.auth.update_user", side_effect=modulo_autenticacao.auth.UserNotFoundError("sumiu")):
                with self.assertRaises(ErroAutenticacao):
                    modulo_autenticacao.redefinir_senha("u1", "NovaSenha123")
            with patch("autenticacao.auth.update_user", side_effect=ValueError("senha curta")):
                with self.assertRaises(ErroAutenticacao) as contexto:
                    modulo_autenticacao.redefinir_senha("u1", "x")
            self.assertEqual(contexto.exception.tipo, "indisponivel")


class TesteCadastroDeUsuario(unittest.TestCase):
    def setUp(self):
        self.banco = BancoFalso()
        self.banco.usuarios = {}
        self.firebase = AutenticacaoFalsa()
        self.firebase.contas = {"ja-existe@exemplo.com": {"uid": "uid-antigo", "senha": "Qualquer123"}}
        self.sms_banco = BancoSMSFalso(self.banco)
        for nome, valor in (("banco", self.banco), ("autenticacao", self.firebase), ("banco_sms", self.sms_banco)):
            original = getattr(modulo_cadastro, nome)
            setattr(modulo_cadastro, nome, valor)
            self.addCleanup(setattr, modulo_cadastro, nome, original)
        patcher = patch("cadastrar_usuario.load_dotenv")
        patcher.start()
        self.addCleanup(patcher.stop)

    def cadastrar(self, entradas, senhas=("Senha12345", "Senha12345")):
        with patch("builtins.input", side_effect=entradas), patch("cadastrar_usuario.getpass", side_effect=list(senhas)), \
                patch("builtins.print"):
            modulo_cadastro.cadastrar_usuario()

    def test_cria_conta_no_firebase_e_registro_no_neon(self):
        self.cadastrar(["Ana Souza", "Ana@Exemplo.com", "caixa", "(67) 99999-8888"])
        self.assertEqual(self.firebase.contas["ana@exemplo.com"]["senha"], "Senha12345")
        self.assertEqual(self.sms_banco.buscar_telefone("ana@exemplo.com"), "5567999998888")
        usuario = self.banco.buscar_usuario_por_email("ana@exemplo.com")
        self.assertEqual(usuario["nome"], "Ana Souza")
        self.assertEqual(usuario["perfil"], "caixa")
        self.assertEqual(usuario["firebase_uid"], self.firebase.contas["ana@exemplo.com"]["uid"])

    def test_dados_invalidos_nao_criam_nada(self):
        self.cadastrar(["A", "ana@exemplo.com", "caixa"])
        self.cadastrar(["Ana", "sem-arroba", "caixa"])
        self.cadastrar(["Ana", "ana@exemplo.com", "chefe"])
        self.cadastrar(["Ana", "ana@exemplo.com", "caixa"], senhas=("curta", "curta"))
        self.cadastrar(["Ana", "ana@exemplo.com", "caixa"], senhas=("Senha12345", "Diferente123"))
        self.assertEqual(self.banco.usuarios, {})
        self.assertEqual(self.firebase.criadas, [])

    def test_desfaz_a_conta_do_firebase_se_o_neon_falhar(self):
        self.banco.criar_usuario = MagicMock(side_effect=BancoErro("Neon fora do ar"))
        self.cadastrar(["Ana", "ana@exemplo.com", "caixa"])
        self.assertEqual(self.firebase.removidas, self.firebase.criadas)
        self.assertEqual(len(self.firebase.removidas), 1)

    def test_libera_conta_que_ja_existe_no_firebase(self):
        self.cadastrar(["Bia", "ja-existe@exemplo.com", "garcom", "s", ""], senhas=())
        self.assertEqual(self.banco.buscar_usuario_por_email("ja-existe@exemplo.com")["firebase_uid"], "uid-antigo")
        self.assertEqual(self.firebase.contas["ja-existe@exemplo.com"]["senha"], "Qualquer123")
        self.assertEqual(self.firebase.criadas, [])
        self.assertIsNone(self.sms_banco.buscar_telefone("ja-existe@exemplo.com"))  # Enter pulou o SMS

    def test_sms_invalido_pergunta_de_novo(self):
        self.cadastrar(["Ana", "ana@exemplo.com", "caixa", "123", "abc", "+55 67 99999-8888"])
        self.assertEqual(self.sms_banco.buscar_telefone("ana@exemplo.com"), "5567999998888")

    def test_nao_cadastra_duas_vezes_o_mesmo_email(self):
        self.cadastrar(["Ana", "ana@exemplo.com", "caixa", ""])
        self.cadastrar(["Ana", "ana@exemplo.com", "caixa"])
        self.assertEqual(len(self.firebase.criadas), 1)


class TesteDefinirTelefone(unittest.TestCase):
    def setUp(self):
        import definir_telefone as modulo
        self.modulo = modulo
        self.banco = BancoFalso()
        self.sms_banco = BancoSMSFalso(self.banco)
        for nome, valor in (("banco", self.banco), ("banco_sms", self.sms_banco)):
            original = getattr(modulo, nome)
            setattr(modulo, nome, valor)
            self.addCleanup(setattr, modulo, nome, original)
        patcher = patch("definir_telefone.load_dotenv")
        patcher.start()
        self.addCleanup(patcher.stop)

    def rodar(self, entradas):
        with patch("builtins.input", side_effect=entradas), patch("builtins.print") as imprimir:
            self.modulo.definir_telefone()
        return " ".join(str(chamada.args[0]) for chamada in imprimir.call_args_list if chamada.args)

    def test_registra_e_troca_o_numero(self):
        self.assertIn("registrado", self.rodar(["teste@exemplo.com", "(67) 99999-8888"]))
        self.assertEqual(self.sms_banco.buscar_telefone("teste@exemplo.com"), "5567999998888")
        saida = self.rodar(["TESTE@exemplo.com", "(11) 98888-7777"])
        self.assertIn("8888", saida)  # mostra o número atual mascarado
        self.assertNotIn("5567999998888", saida)
        self.assertEqual(self.sms_banco.buscar_telefone("teste@exemplo.com"), "5511988887777")

    def test_recusa_dados_invalidos_e_nao_altera(self):
        self.assertIn("inválido", self.rodar(["sem-arroba"]))
        self.assertIn("não está cadastrado", self.rodar(["ausente@exemplo.com"]))
        self.assertIn("inválido", self.rodar(["teste@exemplo.com", "123"]))
        self.assertIn("Nada foi alterado", self.rodar(["teste@exemplo.com", ""]))
        self.assertIsNone(self.sms_banco.buscar_telefone("teste@exemplo.com"))

    def test_banco_fora_do_ar(self):
        self.banco.fora_do_ar = True
        self.assertIn("Não foi possível salvar", self.rodar(["teste@exemplo.com", "(67) 99999-8888"]))


class TesteAcessoPorPerfil(BaseSistema):
    def entrar_como(self, perfil):
        email = perfil + "@exemplo.com"
        self.firebase.contas[email] = {"uid": "uid-" + perfil, "senha": "Senha12345"}
        self.banco.usuarios["uid-" + perfil] = {
            "id": 9, "firebase_uid": "uid-" + perfil, "nome": perfil.title(),
            "email": email, "ativo": True, "perfil": perfil
        }
        cliente = sistema.app.test_client()
        cliente.post("/api/login", json={"email": email, "senha": "Senha12345"})
        with cliente.session_transaction() as sessao:
            cabecalhos = {"X-CSRF-Token": sessao["token"]}
        return cliente, cabecalhos

    def test_caixa_e_cozinha_vao_para_as_proprias_telas(self):
        caixa, _ = self.entrar_como("caixa")
        cozinha, _ = self.entrar_como("cozinha")
        self.assertEqual(caixa.get("/").headers["Location"], "/caixa")
        self.assertEqual(cozinha.get("/").headers["Location"], "/cozinha")
        self.assertEqual(caixa.get("/caixa").status_code, 200)
        self.assertEqual(cozinha.get("/cozinha").status_code, 200)

    def test_pagina_bloqueada_volta_para_o_inicio(self):
        garcom, _ = self.entrar_como("garcom")
        self.assertEqual(garcom.get("/caixa").status_code, 302)
        self.assertEqual(garcom.get("/cozinha").status_code, 302)
        self.assertEqual(self.cliente.get("/caixa").status_code, 200)
        self.assertEqual(self.cliente.get("/cozinha").status_code, 200)

    def test_garcom_cria_pedido_mas_nao_recebe_nem_repoe(self):
        garcom, cabecalhos = self.entrar_como("garcom")
        pedido = {"mesa": 2, "itens": [{"nome": "Pudim", "quantidade": 1}]}
        self.assertEqual(garcom.post("/api/pedidos", json=pedido, headers=cabecalhos).status_code, 201)
        resposta = garcom.post("/api/pedidos/1/finalizar", json={"forma_pagamento": "PIX"}, headers=cabecalhos)
        self.assertEqual(resposta.status_code, 403)
        resposta = garcom.post("/api/estoque/entrada", json={"nome": "Pudim", "quantidade": 5}, headers=cabecalhos)
        self.assertEqual(resposta.status_code, 403)

    def test_caixa_recebe_mas_nao_cria_pedido(self):
        caixa, cabecalhos = self.entrar_como("caixa")
        resposta = caixa.post("/api/pedidos", json={"mesa": 2, "itens": [{"nome": "Pudim", "quantidade": 1}]}, headers=cabecalhos)
        self.assertEqual(resposta.status_code, 403)
        self.criar_pedido()
        resposta = caixa.post("/api/pedidos/1/finalizar", json={"forma_pagamento": "PIX"}, headers=cabecalhos)
        self.assertEqual(resposta.status_code, 200)

    def test_so_a_cozinha_marca_pronto_e_so_o_garcom_marca_entregue(self):
        self.criar_pedido()
        garcom, cab_garcom = self.entrar_como("garcom")
        cozinha, cab_cozinha = self.entrar_como("cozinha")
        resposta = garcom.post("/api/pedidos/1/status", json={"status": "Pronto"}, headers=cab_garcom)
        self.assertEqual(resposta.status_code, 403)
        resposta = cozinha.post("/api/pedidos/1/status", json={"status": "Pronto"}, headers=cab_cozinha)
        self.assertEqual(resposta.status_code, 200)
        resposta = cozinha.post("/api/pedidos/1/status", json={"status": "Entregue"}, headers=cab_cozinha)
        self.assertEqual(resposta.status_code, 403)
        resposta = garcom.post("/api/pedidos/1/status", json={"status": "Entregue"}, headers=cab_garcom)
        self.assertEqual(resposta.status_code, 200)

    def test_sessao_antiga_sem_perfil_recebe_o_perfil_do_banco(self):
        with self.cliente.session_transaction() as sessao:
            del sessao["usuario_id"]
        self.assertEqual(self.cliente.get("/caixa").status_code, 200)
        with self.cliente.session_transaction() as sessao:
            self.assertEqual(sessao["usuario_id"], 1)

    def test_mudanca_de_perfil_vale_na_proxima_conferencia(self):
        self.banco.usuarios["uid-1"]["perfil"] = "cozinha"
        self.forcar_conferencia()
        self.assertEqual(self.cliente.post("/api/pedidos", json={}, headers=self.headers).status_code, 403)


class TesteRachaConta(BaseSistema):
    def abrir_conta(self):
        self.enviar("/api/pedidos", {"mesa": 3, "itens": [
            {"nome": "Lasanha bolonhesa", "quantidade": 1},
            {"nome": "Coca-cola", "quantidade": 1}
        ]})
        self.anonimo = sistema.app.test_client()

    def pagar(self, dados):
        return self.anonimo.post("/api/mesa/3/pagar?c=" + codigo_da_mesa(3), json=dados)

    def test_cliente_ve_a_conta_sem_login(self):
        self.abrir_conta()
        resposta = self.anonimo.get("/api/mesa/3/conta?c=" + codigo_da_mesa(3))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["total"], 36.0)
        self.assertEqual(resposta.json["falta"], 36.0)
        self.assertEqual(self.anonimo.get("/mesa/3?c=" + codigo_da_mesa(3)).status_code, 200)
        self.assertEqual(self.anonimo.get("/api/mesa/5/conta?c=" + codigo_da_mesa(5)).status_code, 404)
        self.assertEqual(self.anonimo.get("/api/dados").status_code, 401)

    def test_pagar_um_item_inteiro(self):
        self.abrir_conta()
        resposta = self.pagar({"modo": "itens", "forma": "PIX", "itens": [{"nome": "Coca-cola", "divisao": 1}]})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["conta"]["pago"], 8.0)
        self.assertEqual(resposta.json["conta"]["falta"], 28.0)

    def test_dividir_um_item_ao_meio_duas_vezes(self):
        self.abrir_conta()
        dados = {"modo": "itens", "forma": "Google Pay", "itens": [{"nome": "Lasanha bolonhesa", "divisao": 2}]}
        self.assertEqual(self.pagar(dados).json["valor_pago"], 14.0)
        self.assertEqual(self.pagar(dados).json["conta"]["itens"][0]["falta"], 0.0)
        self.assertEqual(self.pagar(dados).status_code, 400)

    def test_valor_livre_e_pagar_tudo(self):
        self.abrir_conta()
        self.assertEqual(self.pagar({"modo": "valor", "forma": "Apple Pay", "valor": 10}).json["conta"]["falta"], 26.0)
        resposta = self.pagar({"modo": "tudo", "forma": "PIX"})
        self.assertEqual(resposta.json["conta"]["falta"], 0.0)
        self.assertEqual(len(resposta.json["conta"]["pagamentos"]), 2)

    def test_gorjeta_nao_entra_no_saldo(self):
        self.abrir_conta()
        resposta = self.pagar({"modo": "tudo", "forma": "PIX", "gorjeta": True})
        self.assertEqual(resposta.json["valor_pago"], 39.6)
        self.assertEqual(resposta.json["conta"]["pago"], 36.0)
        self.assertEqual(resposta.json["conta"]["pagamentos"][0]["gorjeta"], 3.6)

    def test_pagamentos_invalidos(self):
        self.abrir_conta()
        self.assertEqual(self.pagar({"modo": "tudo", "forma": "Dinheiro"}).status_code, 400)
        self.assertEqual(self.pagar({"modo": "valor", "forma": "PIX", "valor": -5}).status_code, 400)
        self.assertEqual(self.pagar({"modo": "valor", "forma": "PIX", "valor": "10"}).status_code, 400)
        self.assertEqual(self.pagar({"modo": "itens", "forma": "PIX", "itens": [{"nome": "Coca-cola", "divisao": 7}]}).status_code, 400)
        self.assertEqual(self.pagar({"modo": "itens", "forma": "PIX", "itens": [{"nome": "Pizza", "divisao": 1}]}).status_code, 400)
        self.assertEqual(self.pagar({"modo": "outro", "forma": "PIX"}).status_code, 400)
        self.assertEqual(sistema.pedidos[0].total_pago(), 0)

    def test_caixa_ve_o_pago_e_fecha_a_mesa_com_o_restante_em_dinheiro(self):
        self.abrir_conta()
        self.pagar({"modo": "itens", "forma": "PIX", "itens": [{"nome": "Lasanha bolonhesa", "divisao": 1}]})
        dados = self.cliente.get("/api/dados").json
        self.assertEqual(dados["pedidos"][0]["pago"], 28.0)
        self.assertEqual(dados["pedidos"][0]["falta"], 8.0)
        sem_forma = self.enviar("/api/pedidos/1/finalizar", {})
        self.assertEqual(sem_forma.status_code, 400)
        resposta = self.enviar("/api/pedidos/1/finalizar", {"forma_pagamento": "Dinheiro"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["pedido"]["forma_pagamento"], "PIX + Dinheiro")
        self.assertEqual(sistema.caixa.total_vendido, 36.0)
        self.assertEqual(sistema.mesas[2].status, "Livre")
        self.assertEqual(self.anonimo.get("/api/mesa/3/conta?c=" + codigo_da_mesa(3)).status_code, 404)

    def test_caixa_recebe_parte_sem_fechar_e_fecha_conta_toda_paga(self):
        self.abrir_conta()
        resposta = self.enviar("/api/pedidos/1/pagamento", {"forma": "Dinheiro", "valor": 20})
        self.assertEqual(resposta.json["pedido"]["falta"], 16.0)
        self.assertEqual(self.enviar("/api/pedidos/1/pagamento", {"forma": "Dinheiro", "valor": 99}).status_code, 400)
        self.assertEqual(self.enviar("/api/pedidos/1/pagamento", {"forma": "Pix", "valor": 5}).status_code, 400)
        self.pagar({"modo": "tudo", "forma": "PIX"})
        resposta = self.enviar("/api/pedidos/1/finalizar", {})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["pedido"]["forma_pagamento"], "Dinheiro + PIX")

    def test_conta_com_pagamento_nao_pode_ser_cancelada(self):
        self.abrir_conta()
        self.pagar({"modo": "valor", "forma": "PIX", "valor": 5})
        resposta = self.enviar("/api/pedidos/1/cancelar", {"motivo": "Cliente desistiu"})
        self.assertEqual(resposta.status_code, 400)

    def test_novo_item_aumenta_o_que_falta(self):
        self.abrir_conta()
        self.pagar({"modo": "tudo", "forma": "PIX"})
        self.enviar("/api/pedidos", {"mesa": 3, "itens": [{"nome": "Pudim", "quantidade": 1}]})
        conta = self.anonimo.get("/api/mesa/3/conta?c=" + codigo_da_mesa(3)).json
        self.assertEqual(conta["falta"], 12.0)

    def test_limite_de_tentativas_de_pagamento(self):
        self.abrir_conta()
        codigos = [self.pagar({"modo": "valor", "forma": "PIX", "valor": 0.01}).status_code for _ in range(31)]
        self.assertEqual(codigos[-1], 429)


class EntradaPorPerfil(BaseSistema):
    def setUp(self):
        super().setUp()
        self.trocar_equipe_por_falsos()

    def entrar_como(self, perfil):
        email = perfil + "@exemplo.com"
        uid = "uid-" + perfil
        self.firebase.contas[email] = {"uid": uid, "senha": "Senha12345"}
        self.banco.usuarios[uid] = {
            "id": len(self.banco.usuarios) + 10, "firebase_uid": uid, "nome": perfil.title(),
            "email": email, "ativo": True, "perfil": perfil
        }
        cliente = sistema.app.test_client()
        cliente.post("/api/login", json={"email": email, "senha": "Senha12345"})
        with cliente.session_transaction() as sessao:
            cabecalhos = {"X-CSRF-Token": sessao["token"]}
        return cliente, cabecalhos

    def trocar_equipe_por_falsos(self):
        sms_banco = BancoSMSFalso(self.banco)
        for nome, falso in (("banco", self.banco), ("autenticacao", self.firebase), ("banco_sms", sms_banco)):
            original = getattr(modulo_equipe, nome)
            setattr(modulo_equipe, nome, falso)
            self.addCleanup(setattr, modulo_equipe, nome, original)

    def novo_funcionario(self, nome="Maria Souza", email="maria@exemplo.com", perfil="caixa"):
        return {"nome": nome, "email": email, "senha": "Senha12345", "perfil": perfil}


class TesteEquipe(EntradaPorPerfil):
    def test_administrador_cadastra_qualquer_perfil(self):
        admin, cab = self.entrar_como("administrador")
        for perfil in ["administrador", "gerente", "caixa", "garcom", "cozinha"]:
            dados = self.novo_funcionario("Pessoa " + perfil, perfil + "-novo@exemplo.com", perfil)
            self.assertEqual(admin.post("/api/equipe", json=dados, headers=cab).status_code, 201)
        self.assertEqual(self.banco.buscar_usuario_por_email("gerente-novo@exemplo.com")["perfil"], "gerente")
        self.assertIn("gerente-novo@exemplo.com", self.firebase.contas)

    def test_gerente_cadastra_so_caixa_garcom_e_cozinha(self):
        gerente, cab = self.entrar_como("gerente")
        for perfil in ["caixa", "garcom", "cozinha"]:
            dados = self.novo_funcionario("Pessoa " + perfil, perfil + "-novo@exemplo.com", perfil)
            self.assertEqual(gerente.post("/api/equipe", json=dados, headers=cab).status_code, 201)
        for perfil in ["gerente", "administrador"]:
            dados = self.novo_funcionario("Outro " + perfil, perfil + "-x@exemplo.com", perfil)
            self.assertEqual(gerente.post("/api/equipe", json=dados, headers=cab).status_code, 403)

    def test_outros_perfis_nao_usam_a_equipe(self):
        for perfil in ["caixa", "garcom", "cozinha"]:
            cliente, cab = self.entrar_como(perfil)
            self.assertEqual(cliente.get("/api/equipe").status_code, 403)
            self.assertEqual(cliente.get("/equipe").status_code, 302)
            resposta = cliente.post("/api/equipe", json=self.novo_funcionario(), headers=cab)
            self.assertEqual(resposta.status_code, 403)

    def test_cadastro_com_dados_invalidos(self):
        admin, cab = self.entrar_como("administrador")
        senha_fraca = dict(self.novo_funcionario(), senha="curta")
        email_ruim = dict(self.novo_funcionario(), email="sem-arroba")
        celular_ruim = dict(self.novo_funcionario(), telefone="123")
        sem_nome = {"email": "a@exemplo.com", "senha": "Senha12345", "perfil": "caixa"}
        for dados in [senha_fraca, email_ruim, celular_ruim, sem_nome]:
            self.assertEqual(admin.post("/api/equipe", json=dados, headers=cab).status_code, 400)
        self.assertEqual(self.firebase.criadas, [])

    def test_nao_cadastra_email_repetido(self):
        admin, cab = self.entrar_como("administrador")
        dados = self.novo_funcionario(email="teste@exemplo.com")
        self.assertEqual(admin.post("/api/equipe", json=dados, headers=cab).status_code, 400)

    def test_lista_mostra_quem_pode_ser_alterado(self):
        gerente, cab = self.entrar_como("gerente")
        self.entrar_como("caixa")
        lista = gerente.get("/api/equipe").json
        por_email = {u["email"]: u for u in lista["usuarios"]}
        self.assertTrue(por_email["gerente@exemplo.com"]["voce"])
        self.assertFalse(por_email["gerente@exemplo.com"]["pode_gerenciar"])
        self.assertTrue(por_email["caixa@exemplo.com"]["pode_gerenciar"])
        self.assertFalse(por_email["teste@exemplo.com"]["pode_gerenciar"])
        self.assertEqual(lista["perfis"], ["caixa", "garcom", "cozinha"])

    def test_alterar_perfil_respeita_a_hierarquia(self):
        gerente, cab = self.entrar_como("gerente")
        self.entrar_como("caixa")
        caixa = self.banco.buscar_usuario_por_email("caixa@exemplo.com")
        outro_gerente = self.banco.buscar_usuario_por_email("teste@exemplo.com")
        voce = self.banco.buscar_usuario_por_email("gerente@exemplo.com")
        rota = "/api/equipe/%d/perfil"
        self.assertEqual(gerente.post(rota % caixa["id"], json={"perfil": "cozinha"}, headers=cab).status_code, 200)
        self.assertEqual(caixa["perfil"], "cozinha")
        self.assertEqual(gerente.post(rota % caixa["id"], json={"perfil": "gerente"}, headers=cab).status_code, 403)
        self.assertEqual(gerente.post(rota % outro_gerente["id"], json={"perfil": "caixa"}, headers=cab).status_code, 403)
        self.assertEqual(gerente.post(rota % voce["id"], json={"perfil": "caixa"}, headers=cab).status_code, 403)
        self.assertEqual(gerente.post(rota % 9999, json={"perfil": "caixa"}, headers=cab).status_code, 404)

    def test_administrador_altera_gerente_mas_nao_a_si_mesmo(self):
        admin, cab = self.entrar_como("administrador")
        gerente = self.banco.buscar_usuario_por_email("teste@exemplo.com")
        voce = self.banco.buscar_usuario_por_email("administrador@exemplo.com")
        self.assertEqual(admin.post("/api/equipe/%d/perfil" % gerente["id"], json={"perfil": "garcom"}, headers=cab).status_code, 200)
        self.assertEqual(admin.post("/api/equipe/%d/ativo" % voce["id"], json={"ativo": False}, headers=cab).status_code, 403)

    def test_bloquear_impede_o_login_e_reativar_libera(self):
        gerente, cab = self.entrar_como("gerente")
        self.entrar_como("caixa")
        caixa = self.banco.buscar_usuario_por_email("caixa@exemplo.com")
        rota = "/api/equipe/%d/ativo" % caixa["id"]
        self.assertEqual(gerente.post(rota, json={"ativo": False}, headers=cab).status_code, 200)
        entrada = {"email": "caixa@exemplo.com", "senha": "Senha12345"}
        self.assertEqual(sistema.app.test_client().post("/api/login", json=entrada).status_code, 403)
        self.assertEqual(gerente.post(rota, json={"ativo": "sim"}, headers=cab).status_code, 400)
        self.assertEqual(gerente.post(rota, json={"ativo": True}, headers=cab).status_code, 200)
        self.assertEqual(sistema.app.test_client().post("/api/login", json=entrada).status_code, 200)


class TesteInstalacao(EntradaPorPerfil):
    def setUp(self):
        super().setUp()
        patcher = patch.dict("os.environ", {"CODIGO_INSTALACAO": "codigo-secreto-123"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.banco.usuarios = {}
        self.anonimo = sistema.app.test_client()
        self.dados = {"codigo": "codigo-secreto-123", "nome": "Ana Admin", "email": "Ana@Exemplo.com", "senha": "Senha12345"}

    def test_sistema_vazio_leva_para_a_instalacao(self):
        self.assertEqual(self.anonimo.get("/login").headers["Location"], "/instalacao")
        self.assertEqual(self.anonimo.get("/instalacao").status_code, 200)

    def test_cria_o_administrador_com_o_codigo_certo(self):
        resposta = self.anonimo.post("/api/instalacao", json=self.dados)
        self.assertEqual(resposta.status_code, 201)
        admin = self.banco.buscar_usuario_por_email("ana@exemplo.com")
        self.assertEqual(admin["perfil"], "administrador")
        self.assertEqual(self.firebase.contas["ana@exemplo.com"]["senha"], "Senha12345")

    def test_codigo_errado_ou_ausente_nao_cria_nada(self):
        for codigo in ["errado", "", None, 123]:
            resposta = self.anonimo.post("/api/instalacao", json=dict(self.dados, codigo=codigo))
            self.assertEqual(resposta.status_code, 403)
        self.assertEqual(self.banco.usuarios, {})

    def test_sem_codigo_configurado_ninguem_instala(self):
        with patch.dict("os.environ", {"CODIGO_INSTALACAO": ""}):
            resposta = self.anonimo.post("/api/instalacao", json=dict(self.dados, codigo=""))
        self.assertEqual(resposta.status_code, 403)

    def test_depois_do_primeiro_usuario_a_instalacao_fecha(self):
        self.assertEqual(self.anonimo.post("/api/instalacao", json=self.dados).status_code, 201)
        outro = dict(self.dados, email="outro@exemplo.com")
        self.assertEqual(self.anonimo.post("/api/instalacao", json=outro).status_code, 403)
        self.assertEqual(self.anonimo.get("/instalacao").headers["Location"], "/login")
        self.assertEqual(self.anonimo.get("/login").status_code, 200)

    def test_dados_invalidos_e_limite_de_tentativas(self):
        self.assertEqual(self.anonimo.post("/api/instalacao", json=dict(self.dados, senha="curta")).status_code, 400)
        self.assertEqual(self.anonimo.post("/api/instalacao", json={"codigo": "codigo-secreto-123"}).status_code, 400)
        for tentativa in range(10):
            resposta = self.anonimo.post("/api/instalacao", json=dict(self.dados, codigo="errado"))
        self.assertEqual(resposta.status_code, 429)


class TesteCodigoDaMesa(EntradaPorPerfil):
    def abrir_conta(self):
        self.enviar("/api/pedidos", {"mesa": 3, "itens": [{"nome": "Pudim", "quantidade": 1}]})
        self.anonimo = sistema.app.test_client()

    def test_sem_codigo_ou_com_codigo_errado_nao_ve_a_conta(self):
        self.abrir_conta()
        self.assertEqual(self.anonimo.get("/api/mesa/3/conta").status_code, 403)
        self.assertEqual(self.anonimo.get("/api/mesa/3/conta?c=errado").status_code, 403)
        outra_mesa = "/api/mesa/3/conta?c=" + codigo_da_mesa(4)
        self.assertEqual(self.anonimo.get(outra_mesa).status_code, 403)
        self.assertEqual(self.anonimo.get("/api/mesa/3/conta?c=" + codigo_da_mesa(3)).status_code, 200)

    def test_sem_codigo_nao_paga(self):
        self.abrir_conta()
        pagamento = {"modo": "tudo", "forma": "PIX"}
        self.assertEqual(self.anonimo.post("/api/mesa/3/pagar", json=pagamento).status_code, 403)
        self.assertEqual(sistema.pedidos[0].total_pago(), 0)

    def test_mesa_que_nao_existe(self):
        self.assertEqual(self.anonimo_get("/api/mesa/99/conta?c=" + codigo_da_mesa(99)), 404)

    def anonimo_get(self, rota):
        return sistema.app.test_client().get(rota).status_code

    def test_pagina_do_cliente_so_recebe_o_codigo_certo(self):
        anonimo = sistema.app.test_client()
        certo = anonimo.get("/mesa/3?c=" + codigo_da_mesa(3)).get_data(as_text=True)
        errado = anonimo.get("/mesa/3?c=errado").get_data(as_text=True)
        self.assertIn('data-codigo="' + codigo_da_mesa(3) + '"', certo)
        self.assertIn('data-codigo=""', errado)

    def test_limite_de_tentativas_de_codigo(self):
        anonimo = sistema.app.test_client()
        codigos = [anonimo.get("/api/mesa/3/conta?c=errado").status_code for _ in range(21)]
        self.assertEqual(codigos[0], 403)
        self.assertEqual(codigos[-1], 429)

    def test_codigos_diferentes_para_cada_mesa(self):
        codigos = {codigo_da_mesa(numero) for numero in range(1, 9)}
        self.assertEqual(len(codigos), 8)

    def test_pagina_de_qr_codes_so_para_a_gerencia(self):
        gerente, _ = self.entrar_como("gerente")
        caixa, _ = self.entrar_como("caixa")
        self.assertEqual(caixa.get("/qrcodes").status_code, 302)
        self.assertEqual(sistema.app.test_client().get("/qrcodes").status_code, 302)
        pagina = gerente.get("/qrcodes").get_data(as_text=True)
        self.assertGreaterEqual(pagina.count("<svg"), 8)
        self.assertIn("/mesa/3?c=" + codigo_da_mesa(3), pagina)
        self.assertIn("/mesa/8?c=" + codigo_da_mesa(8), pagina)


class TesteSegurancaDasTelas(EntradaPorPerfil):
    def test_visitante_so_abre_as_paginas_publicas(self):
        anonimo = sistema.app.test_client()
        for pagina in ["/", "/caixa", "/cozinha", "/equipe", "/qrcodes"]:
            self.assertEqual(anonimo.get(pagina).status_code, 302)
        for rota in ["/api/dados", "/api/equipe"]:
            self.assertEqual(anonimo.get(rota).status_code, 401)
        self.assertEqual(anonimo.post("/api/pedidos", json={}).status_code, 401)
        self.assertEqual(anonimo.get("/login").status_code, 200)

    def test_cada_perfil_so_abre_as_proprias_telas(self):
        telas = {
            "administrador": {"/": 200, "/caixa": 200, "/cozinha": 200, "/equipe": 200, "/qrcodes": 200},
            "gerente": {"/": 200, "/caixa": 200, "/cozinha": 200, "/equipe": 200, "/qrcodes": 200},
            "caixa": {"/caixa": 200, "/cozinha": 302, "/equipe": 302, "/qrcodes": 302},
            "garcom": {"/": 200, "/caixa": 302, "/cozinha": 302, "/equipe": 302, "/qrcodes": 302},
            "cozinha": {"/cozinha": 200, "/caixa": 302, "/equipe": 302, "/qrcodes": 302}
        }
        for perfil, paginas in telas.items():
            cliente, _ = self.entrar_como(perfil)
            for pagina, esperado in paginas.items():
                self.assertEqual(cliente.get(pagina).status_code, esperado, perfil + " " + pagina)

    def test_dados_sensiveis_so_para_quem_precisa(self):
        self.criar_pedido()
        cozinha, _ = self.entrar_como("cozinha")
        garcom, _ = self.entrar_como("garcom")
        caixa, _ = self.entrar_como("caixa")
        dados_cozinha = cozinha.get("/api/dados").json
        self.assertEqual(dados_cozinha["pedidos"][0]["total"], 0)
        self.assertEqual(dados_cozinha["vendas"], [])
        self.assertEqual(dados_cozinha["estoque"], [])
        self.assertEqual(garcom.get("/api/dados").json["vendas"], [])
        self.assertGreater(len(garcom.get("/api/dados").json["estoque"]), 0)
        self.assertEqual(caixa.get("/api/dados").json["estoque"], [])
        self.assertGreater(caixa.get("/api/dados").json["pedidos"][0]["total"], 0)

    def test_cabecalhos_de_seguranca(self):
        resposta = sistema.app.test_client().get("/login")
        self.assertEqual(resposta.headers["X-Frame-Options"], "DENY")
        self.assertEqual(resposta.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", resposta.headers["Content-Security-Policy"])
        self.assertEqual(resposta.headers["Cache-Control"], "no-store")


class BancoEstadoFalso:
    def __init__(self):
        self.linha = None
        self.recusar = False

    def buscar_estado(self):
        return None if self.linha is None else dict(self.linha)

    def criar_estado(self, dados):
        if self.linha is None:
            self.linha = {"versao": 1, "dados": dados}

    def salvar_estado(self, dados, versao):
        if self.recusar or self.linha["versao"] != versao:
            return False
        self.linha = {"versao": versao + 1, "dados": dados}
        return True


class TesteEstadoNoBanco(EntradaPorPerfil):
    def setUp(self):
        super().setUp()
        self.estado_banco = BancoEstadoFalso()
        self.original = sistema.banco_estado
        sistema.banco_estado = self.estado_banco
        sistema.persistir_estado = True
        self.addCleanup(setattr, sistema, "banco_estado", self.original)

    def esquecer_a_memoria(self):
        sistema.mesas = []
        sistema.pedidos = []
        sistema.caixa = Caixa()
        sistema.estoque = Estoque()
        sistema.numero_pedido = 99

    def test_pedido_sobrevive_a_uma_nova_instancia(self):
        self.criar_pedido()
        self.esquecer_a_memoria()
        dados = self.cliente.get("/api/dados").json
        self.assertEqual(len(dados["pedidos"]), 1)
        self.assertEqual(dados["pedidos"][0]["mesa"], 1)
        self.assertEqual(dados["mesas"][0]["status"], "Ocupada")

    def test_pagamentos_vendas_e_estoque_sobrevivem(self):
        self.criar_pedido()
        codigo = codigo_da_mesa(1)
        anonimo = sistema.app.test_client()
        self.esquecer_a_memoria()
        pago = anonimo.post("/api/mesa/1/pagar?c=" + codigo, json={"modo": "valor", "forma": "PIX", "valor": 5})
        self.assertEqual(pago.status_code, 200)
        self.esquecer_a_memoria()
        self.assertEqual(self.enviar("/api/pedidos/1/finalizar", {"forma_pagamento": "Dinheiro"}).status_code, 200)
        self.esquecer_a_memoria()
        dados = self.cliente.get("/api/dados").json
        self.assertEqual(dados["pedidos"], [])
        self.assertEqual(dados["caixa"]["total_vendido"], 24.0)
        self.assertEqual(dados["vendas"][0]["forma_pagamento"], "PIX + Dinheiro")
        pudim = next(item for item in dados["estoque"] if item["nome"] == "Pudim")
        self.assertEqual(pudim["quantidade"], 13)

    def test_numero_do_pedido_continua_depois_de_reiniciar(self):
        self.criar_pedido()
        self.esquecer_a_memoria()
        resposta = self.enviar("/api/pedidos", {"mesa": 2, "itens": [{"nome": "Pudim", "quantidade": 1}]})
        self.assertEqual(resposta.json["pedido"]["numero"], 2)

    def test_alteracao_simultanea_devolve_409_e_nao_guarda(self):
        self.criar_pedido()
        versao = self.estado_banco.linha["versao"]
        self.estado_banco.recusar = True
        resposta = self.enviar("/api/pedidos", {"mesa": 2, "itens": [{"nome": "Pudim", "quantidade": 1}]})
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(self.estado_banco.linha["versao"], versao)

    def test_erro_do_pedido_nao_grava_nada(self):
        self.criar_pedido()
        antes = self.estado_banco.buscar_estado()
        self.enviar("/api/pedidos", {"mesa": 99, "itens": []})
        self.assertEqual(self.estado_banco.buscar_estado(), antes)

    def test_banco_fora_do_ar_devolve_503(self):
        self.estado_banco.buscar_estado = MagicMock(side_effect=BancoErro("Neon fora do ar"))
        self.assertEqual(self.cliente.get("/api/dados").status_code, 503)


if __name__ == "__main__":
    unittest.main()
