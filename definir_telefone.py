"""Registra (ou troca) o celular de um funcionário já cadastrado.

O número é usado só na recuperação de senha por código por SMS.
Uso:  python definir_telefone.py
"""
from dotenv import load_dotenv

import banco
import banco_sms
from banco import BancoErro
from usuario import email_valido
from sms import mascarar_telefone, normalizar_telefone


def definir_telefone():
    load_dotenv()
    email = input("E-mail do funcionário: ").strip().lower()
    if not email_valido(email):
        print("E-mail inválido.")
        return

    try:
        if banco.buscar_usuario_por_email(email) is None:
            print("Esse e-mail não está cadastrado. Cadastre antes com: python cadastrar_usuario.py")
            return

        atual = banco_sms.buscar_telefone(email)
        if atual:
            print("Celular atual: " + mascarar_telefone(atual))

        digitado = input("Novo celular com DDD, ex.: (67) 99999-8888 (Enter para cancelar): ").strip()
        if not digitado:
            print("Nada foi alterado.")
            return
        numero = normalizar_telefone(digitado)
        if numero is None:
            print("Número inválido. Use DDD e número, ex.: (67) 99999-8888. Para outro país, comece com +.")
            return

        banco_sms.definir_telefone(email, numero)
        print("Celular registrado: " + mascarar_telefone(numero))
    except BancoErro as erro:
        print("Não foi possível salvar:", erro)
        print("Rode 'python verificar_configuracao.py' para encontrar o problema.")


if __name__ == "__main__":
    definir_telefone()
