import hmac
import os

from flask import request


def ip_do_cliente():
    if os.getenv("VERCEL"):
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        return ip.split(",")[0].strip()
    return request.remote_addr


def codigo_da_mesa(numero):
    chave = os.getenv("CHAVE_SECRETA", "chave-de-teste")
    return hmac.new(chave.encode(), str(numero).encode(), "sha256").hexdigest()[:12]


def codigo_da_mesa_valido(numero, codigo):
    if not isinstance(codigo, str):
        return False
    return hmac.compare_digest(codigo_da_mesa(numero), codigo)


def codigo_de_instalacao_valido(codigo):
    esperado = os.getenv("CODIGO_INSTALACAO", "")
    if not esperado or not isinstance(codigo, str):
        return False
    return hmac.compare_digest(esperado.encode(), codigo.encode())
