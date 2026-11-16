"""Envio do código de recuperação de senha por SMS.

O sistema funciona com três provedores. Escolha um em SMS_PROVEDOR no .env:

    twilio   Twilio
    zenvia   Zenvia (empresa brasileira)
    vonage   Vonage

Cada provedor usa as próprias variáveis (veja .env.example e GUIA_SMS.md).
Nenhum dado de acesso aparece nos registros (logs) do sistema.
"""
import json
import os
import re

import requests

TEMPO_LIMITE = 10  # segundos esperando o provedor responder

TEXTO_MENSAGEM = "BKV: seu codigo e {codigo}. Vale por 10 minutos."


class ErroSMS(Exception):
    """Falha ao enviar a mensagem. O atributo `tipo` diz o que aconteceu:

    configuracao   variáveis do .env ausentes ou credenciais recusadas
    falha          o provedor recusou a mensagem (número inválido, remetente não aprovado...)
    indisponivel   sem comunicação com o provedor
    """

    def __init__(self, tipo, mensagem):
        super().__init__(mensagem)
        self.tipo = tipo
        self.mensagem = mensagem


# ---------- telefone ----------

def normalizar_telefone(valor):
    """Converte o que a pessoa digitou em número internacional, só com dígitos.

    "(67) 99999-8888"   -> "5567999998888"   (sem código do país: assume Brasil)
    "+55 67 99999-8888" -> "5567999998888"
    "+1 555 123 4567"   -> "15551234567"     (com "+" vale qualquer país)
    Devolve None quando o número não parece válido.
    """
    if not isinstance(valor, str) or len(valor) > 40:
        return None
    texto = valor.strip()
    internacional = texto.startswith("+") or texto.startswith("00")
    digitos = re.sub(r"\D", "", texto)
    if texto.startswith("00"):
        digitos = digitos[2:]

    if internacional:
        if not 8 <= len(digitos) <= 15:
            return None
    else:
        if len(digitos) in (10, 11):
            digitos = "55" + digitos
        if not (digitos.startswith("55") and len(digitos) in (12, 13)):
            return None

    if digitos.startswith("55"):
        # Brasil: 55 + DDD (2 dígitos, não começa com 0) + número de 8 ou 9 dígitos
        if len(digitos) not in (12, 13) or digitos[2] == "0":
            return None
    return digitos


def mascarar_telefone(telefone):
    """Esconde o número, mostrando só os 4 últimos dígitos (para telas e mensagens do terminal)."""
    if not telefone:
        return ""
    return "*" * max(len(telefone) - 4, 0) + telefone[-4:]


# ---------- envio ----------

def _exigir(nome, ajuda=""):
    valor = os.getenv(nome, "").strip()
    if not valor:
        raise ErroSMS("configuracao", "Configure " + nome + " no .env." + (" " + ajuda if ajuda else ""))
    return valor


def _detalhe(resposta):
    """Resumo curto do motivo da recusa, para o terminal (sem credenciais)."""
    try:
        corpo = resposta.json()
    except ValueError:
        return (resposta.text or "")[:200]
    if isinstance(corpo, dict):
        erro = corpo.get("error", corpo)
        if isinstance(erro, dict):
            erro = erro.get("message") or erro.get("error") or json.dumps(erro, ensure_ascii=False)
        return str(erro)[:300]
    return str(corpo)[:300]


def _enviar(url, **opcoes):
    try:
        resposta = requests.post(url, timeout=TEMPO_LIMITE, **opcoes)
    except requests.RequestException:
        # A mensagem original do requests pode conter a URL, que em alguns provedores leva o token.
        raise ErroSMS("indisponivel", "Não foi possível falar com o provedor de SMS.") from None

    if 200 <= resposta.status_code < 300:
        return resposta
    if resposta.status_code in (401, 403):
        raise ErroSMS("configuracao", "O provedor recusou as credenciais (" + _detalhe(resposta) + ").")
    if resposta.status_code >= 500 or resposta.status_code == 429:
        raise ErroSMS("indisponivel", "O provedor respondeu com erro " + str(resposta.status_code) + ".")
    raise ErroSMS("falha", "O provedor recusou a mensagem (" + _detalhe(resposta) + ").")


def _twilio(telefone, codigo):
    sid = _exigir("TWILIO_ACCOUNT_SID")
    token = _exigir("TWILIO_AUTH_TOKEN")
    dados = {"To": "+" + telefone, "Body": TEXTO_MENSAGEM.format(codigo=codigo)}

    # Com um "Messaging Service" a Twilio escolhe o remetente; senão, usa o número informado.
    servico = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "").strip()
    if servico:
        dados["MessagingServiceSid"] = servico
    else:
        dados["From"] = _exigir("TWILIO_SMS_DE", "Número da Twilio que envia o SMS, exemplo: +12025550123.")

    _enviar(
        "https://api.twilio.com/2010-04-01/Accounts/" + sid + "/Messages.json",
        data=dados,
        auth=(sid, token),
    )


def _zenvia(telefone, codigo):
    token = _exigir("ZENVIA_TOKEN", "Token da API, no painel da Zenvia.")
    remetente = _exigir("ZENVIA_REMETENTE", "Código do remetente (from) criado na Zenvia.")
    _enviar(
        "https://api.zenvia.com/v2/channels/sms/messages",
        json={
            "from": remetente,
            "to": telefone,
            "contents": [{"type": "text", "text": TEXTO_MENSAGEM.format(codigo=codigo)}],
        },
        headers={"X-API-TOKEN": token},
    )


def _vonage(telefone, codigo):
    chave = _exigir("VONAGE_API_KEY")
    segredo = _exigir("VONAGE_API_SECRET")
    remetente = os.getenv("VONAGE_REMETENTE", "").strip() or "BKV"
    resposta = _enviar(
        "https://rest.nexmo.com/sms/json",
        data={
            "api_key": chave,
            "api_secret": segredo,
            "from": remetente,
            "to": telefone,
            "text": TEXTO_MENSAGEM.format(codigo=codigo),
        },
    )
    # A Vonage responde 200 mesmo quando recusa; o resultado vem em messages[0].status ("0" = enviado).
    try:
        mensagem = resposta.json()["messages"][0]
        situacao = str(mensagem.get("status", ""))
        detalhe = str(mensagem.get("error-text", ""))[:200]
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ErroSMS("falha", "Resposta inesperada do provedor.") from None
    if situacao == "0":
        return
    if situacao in ("4", "9"):
        raise ErroSMS("configuracao", "O provedor recusou as credenciais ou a conta (" + detalhe + ").")
    if situacao in ("1", "5"):
        raise ErroSMS("indisponivel", "O provedor está limitando ou com erro (" + detalhe + ").")
    raise ErroSMS("falha", "O provedor recusou a mensagem (" + detalhe + ").")


PROVEDORES = {"twilio": _twilio, "zenvia": _zenvia, "vonage": _vonage}


def provedor_configurado():
    return os.getenv("SMS_PROVEDOR", "").strip().lower()


def enviar_codigo(telefone, codigo):
    """Envia o código de 4 números ao `telefone` (já normalizado, só dígitos)."""
    nome = provedor_configurado()
    if nome not in PROVEDORES:
        raise ErroSMS(
            "configuracao",
            "Configure SMS_PROVEDOR no .env com twilio, zenvia ou vonage.",
        )
    PROVEDORES[nome](telefone, codigo)
