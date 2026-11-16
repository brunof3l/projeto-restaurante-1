"""Telefone e códigos de recuperação por SMS, guardados no Neon.

Acrescenta colunas à tabela `usuarios` (criadas sozinhas na primeira vez, sem apagar nada):

    telefone         celular do funcionário, só dígitos, com código do país (5567999998888)
    sms_codigo_hash   hash do código de 4 números (o código em si nunca é guardado)
    sms_validade      até quando o código vale
    sms_tentativas    quantas vezes já tentaram confirmar o código atual
    sms_ultimo_envio  quando o último código foi pedido (limita 1 por minuto)
"""
import threading
from contextlib import contextmanager

import banco

COLUNAS = """
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS telefone        TEXT,
    ADD COLUMN IF NOT EXISTS sms_codigo_hash  TEXT,
    ADD COLUMN IF NOT EXISTS sms_validade     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sms_tentativas   INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS sms_ultimo_envio TIMESTAMPTZ
"""

MAX_TENTATIVAS = 5

_colunas_prontas = False
_trava = threading.Lock()


@contextmanager
def _conexao():
    """Abre a conexão do banco.py e garante, uma vez por execução, que as colunas existem."""
    global _colunas_prontas
    with banco.conexao() as conn:
        if not _colunas_prontas:
            with _trava:
                if not _colunas_prontas:
                    conn.execute(COLUNAS)
                    _colunas_prontas = True
        yield conn


def preparar():
    """Usada pelo verificar_configuracao.py: cria as colunas se ainda não existirem."""
    with _conexao():
        pass


def definir_telefone(email, telefone):
    """Registra o celular de um funcionário. Devolve False se o e-mail não existir."""
    with _conexao() as conn:
        linha = conn.execute(
            "UPDATE usuarios SET telefone = %s WHERE email = %s RETURNING id",
            (telefone, email),
        ).fetchone()
        return linha is not None


def buscar_telefone(email):
    with _conexao() as conn:
        linha = conn.execute("SELECT telefone FROM usuarios WHERE email = %s", (email,)).fetchone()
        return linha["telefone"] if linha else None


def reservar_envio(email, intervalo_segundos=60):
    """Libera o envio de um código, se for permitido.

    Devolve {"firebase_uid", "telefone"} quando o e-mail é de um funcionário ativo, com
    celular registrado e sem pedido no último intervalo. Caso contrário devolve None.
    Também apaga o código anterior, então um novo pedido invalida o antigo. Tudo em um
    único comando SQL: dois pedidos ao mesmo tempo não passam juntos.
    """
    with _conexao() as conn:
        return conn.execute(
            """
            UPDATE usuarios
               SET sms_ultimo_envio = now(),
                   sms_codigo_hash = NULL,
                   sms_validade = NULL,
                   sms_tentativas = 0
             WHERE email = %s
               AND ativo
               AND telefone IS NOT NULL
               AND (sms_ultimo_envio IS NULL
                    OR sms_ultimo_envio < now() - make_interval(secs => %s))
            RETURNING firebase_uid, telefone
            """,
            (email, intervalo_segundos),
        ).fetchone()


def guardar_codigo(email, codigo_hash, validade_segundos=600):
    with _conexao() as conn:
        conn.execute(
            """
            UPDATE usuarios
               SET sms_codigo_hash = %s,
                   sms_validade = now() + make_interval(secs => %s),
                   sms_tentativas = 0
             WHERE email = %s
            """,
            (codigo_hash, validade_segundos, email),
        )


def consumir_tentativa(email):
    """Conta uma tentativa de confirmação e devolve {"firebase_uid", "sms_codigo_hash"}.

    Devolve None quando não há código válido: não foi pedido, já foi usado, expirou ou
    as tentativas acabaram. Contar e conferir os limites é um único comando, então
    tentativas simultâneas não passam do máximo.
    """
    with _conexao() as conn:
        return conn.execute(
            """
            UPDATE usuarios
               SET sms_tentativas = sms_tentativas + 1
             WHERE email = %s
               AND ativo
               AND sms_codigo_hash IS NOT NULL
               AND sms_validade > now()
               AND sms_tentativas < %s
            RETURNING firebase_uid, sms_codigo_hash
            """,
            (email, MAX_TENTATIVAS),
        ).fetchone()


def invalidar_codigo(email, codigo_hash):
    """Apaga o código para ele não ser usado de novo.

    Devolve True só para quem conseguiu apagar: se duas requisições chegarem juntas com o
    mesmo código, apenas uma passa.
    """
    with _conexao() as conn:
        linha = conn.execute(
            """
            UPDATE usuarios
               SET sms_codigo_hash = NULL, sms_validade = NULL, sms_tentativas = 0
             WHERE email = %s AND sms_codigo_hash = %s
            RETURNING id
            """,
            (email, codigo_hash),
        ).fetchone()
        return linha is not None
