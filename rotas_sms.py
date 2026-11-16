"""Rotas da recuperação de senha por SMS (somem do caminho do e-mail, que continua igual).

POST /api/sms/solicitar   envia um código de 4 números ao celular registrado na conta
POST /api/sms/confirmar   confere o código e define a nova senha no Firebase

As duas rotas são públicas (quem esqueceu a senha não tem sessão).
"""
import secrets
import time

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import autenticacao
import banco_sms
import sms
from autenticacao import ErroAutenticacao
from banco import BancoErro
from usuario import email_valido, senha_valida
from seguranca import ip_do_cliente
from sms import ErroSMS

bp_sms = Blueprint("sms", __name__, url_prefix="/api/sms")

VALIDADE_CODIGO = 600   # o código vale 10 minutos
INTERVALO_ENVIO = 60    # no máximo um código por minuto para cada conta

tentativas_envio = {}
tentativas_confirmacao = {}

MENSAGEM_ENVIO = "Se o e-mail estiver cadastrado e tiver um celular registrado, enviaremos um código de 4 números."
MENSAGEM_CODIGO_INVALIDO = "Código inválido ou expirado. Solicite outro."

# Hash de mentira, usado para gastar o mesmo tempo quando o e-mail não tem código ativo.
_HASH_FALSO = generate_password_hash("0000")


def _ler_dados():
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}


def _passou_do_limite(tabela, chave, maximo, janela):
    """Conta uma tentativa. Devolve True quando o limite da janela (em segundos) já foi atingido."""
    agora = time.time()
    registro = tabela.get(chave)
    if registro is None or agora > registro["validade"]:
        registro = {"quantidade": 0, "validade": agora + janela}
        tabela[chave] = registro
    if registro["quantidade"] >= maximo:
        return True
    registro["quantidade"] += 1
    return False


@bp_sms.route("/status")
def status():
    """Diz à tela de login se a recuperação por SMS está configurada (para mostrar ou esconder o botão)."""
    return jsonify({"ativo": sms.provedor_configurado() in sms.PROVEDORES})


@bp_sms.route("/solicitar", methods=["POST"])
def solicitar():
    email = _ler_dados().get("email", "")
    if not email_valido(email):
        return jsonify({"erro": "Informe um e-mail válido."}), 400

    if _passou_do_limite(tentativas_envio, ip_do_cliente(), 5, 600):
        return jsonify({"erro": "Muitos pedidos seguidos. Aguarde alguns minutos."}), 429

    # A resposta é sempre a mesma, para não revelar quais e-mails estão cadastrados.
    email = email.strip().lower()
    try:
        destino = banco_sms.reservar_envio(email, INTERVALO_ENVIO)
        if destino:
            codigo = str(secrets.randbelow(10000)).zfill(4)
            sms.enviar_codigo(destino["telefone"], codigo)
            banco_sms.guardar_codigo(email, generate_password_hash(codigo), VALIDADE_CODIGO)
    except (BancoErro, ErroSMS) as erro:
        current_app.logger.error("Não foi possível enviar o código por SMS: %s", erro)
    return jsonify({"mensagem": MENSAGEM_ENVIO})


@bp_sms.route("/confirmar", methods=["POST"])
def confirmar():
    dados = _ler_dados()
    email = dados.get("email", "")
    codigo = dados.get("codigo", "")
    senha = dados.get("senha", "")
    confirmacao = dados.get("confirmacao", "")
    if not email_valido(email) or not isinstance(codigo, str) or len(codigo) != 4 or not codigo.isdigit():
        return jsonify({"erro": "Informe e-mail e código de 4 números."}), 400
    if not senha_valida(senha):
        return jsonify({"erro": "Use de 8 a 128 caracteres, com letras e números."}), 400
    if senha != confirmacao:
        return jsonify({"erro": "As senhas não são iguais."}), 400

    if _passou_do_limite(tentativas_confirmacao, ip_do_cliente(), 20, 600):
        return jsonify({"erro": "Muitas tentativas seguidas. Aguarde alguns minutos."}), 429

    email = email.strip().lower()
    try:
        registro = banco_sms.consumir_tentativa(email)
    except BancoErro as erro:
        current_app.logger.error("Falha ao consultar o banco na confirmação por SMS: %s", erro)
        return jsonify({"erro": "Não foi possível consultar o banco de dados. Tente novamente."}), 503

    hash_do_codigo = registro["sms_codigo_hash"] if registro else _HASH_FALSO
    codigo_certo = check_password_hash(hash_do_codigo, codigo)
    if registro is None or not codigo_certo:
        return jsonify({"erro": MENSAGEM_CODIGO_INVALIDO}), 400

    try:
        # Apaga o código antes de trocar a senha: ele só vale uma vez, mesmo com requisições simultâneas.
        if not banco_sms.invalidar_codigo(email, registro["sms_codigo_hash"]):
            return jsonify({"erro": MENSAGEM_CODIGO_INVALIDO}), 400
        autenticacao.redefinir_senha(registro["firebase_uid"], senha)
    except BancoErro as erro:
        current_app.logger.error("Falha ao consultar o banco na confirmação por SMS: %s", erro)
        return jsonify({"erro": "Não foi possível consultar o banco de dados. Tente novamente."}), 503
    except ErroAutenticacao as erro:
        current_app.logger.error("Falha ao definir a nova senha no Firebase: %s", erro.mensagem)
        return jsonify({"erro": "Não foi possível alterar a senha agora. Peça um novo código."}), 503

    session.clear()
    return jsonify({"mensagem": "Senha alterada. Entre com sua nova senha."})
