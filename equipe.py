import autenticacao
import banco
import banco_sms
from banco import BancoErro
from sms import normalizar_telefone
from usuario import email_valido, nome_valido, perfil_valido, senha_valida


def validar_funcionario(nome, email, senha, perfil):
    if not nome_valido(nome):
        return "Informe um nome entre 2 e 100 caracteres."
    if not email_valido(email):
        return "E-mail inválido."
    if not senha_valida(senha):
        return "A senha precisa ter de 8 a 128 caracteres, com letras e números."
    if not perfil_valido(perfil):
        return "Perfil inválido."
    return ""


def criar_funcionario(nome, email, senha, perfil, telefone=""):
    nome = nome.strip()
    email = email.strip().lower()

    erro = validar_funcionario(nome, email, senha, perfil)
    if erro:
        raise ValueError(erro)

    numero = ""
    if telefone:
        numero = normalizar_telefone(telefone)
        if numero is None:
            raise ValueError("Celular inválido. Exemplo: (67) 99999-8888")

    if banco.buscar_usuario_por_email(email) is not None:
        raise ValueError("Este e-mail já está cadastrado no sistema.")
    if autenticacao.buscar_conta_por_email(email) is not None:
        raise ValueError("Este e-mail já existe no Firebase. Use outro e-mail.")

    uid = autenticacao.criar_conta(email, senha, nome)
    try:
        banco.criar_usuario(uid, nome, email, perfil)
        if numero:
            banco_sms.definir_telefone(email, numero)
    except BancoErro:
        autenticacao.remover_conta(uid)
        raise
