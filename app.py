import os
import secrets
import time
import segno
from flask import Flask, g, jsonify, render_template, request, session, redirect
from dotenv import load_dotenv
import autenticacao
import banco
from autenticacao import ErroAutenticacao
from banco import BancoErro
import banco_estado
import equipe
import estado
from seguranca import (
    codigo_da_mesa, codigo_da_mesa_valido, codigo_de_instalacao_valido, ip_do_cliente
)
from usuario import email_valido, pode_gerenciar, perfis_que_pode_cadastrar
from rotas_sms import bp_sms

from caixa import Caixa
from categoria import categoria
from estoque import Estoque
from mesa import Mesa
from pedido import Pedido


load_dotenv()
app = Flask(__name__, static_folder="public/static", static_url_path="/static")
if os.getenv("VERCEL") and not os.getenv("CHAVE_SECRETA"):
    raise RuntimeError("Defina a variável CHAVE_SECRETA nas configurações do projeto na Vercel.")
app.secret_key = os.getenv("CHAVE_SECRETA") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = bool(os.getenv("VERCEL"))
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 65536
app.register_blueprint(bp_sms)  # recuperação de senha por SMS (rotas em rotas_sms.py)
tentativas_login = {}
tentativas_recuperacao = {}
tentativas_pagamento = {}
tentativas_instalacao = {}
tentativas_codigo = {}

# De quanto em quanto tempo a sessão é conferida de novo no Firebase e no Neon.
INTERVALO_CONFERENCIA = 300  # 5 minutos
# Se o Firebase ou o Neon ficarem fora do ar, a sessão continua valendo por este tempo.
TOLERANCIA_FALHA = 1800  # 30 minutos

GERENCIA = ["administrador", "gerente"]

PERMISSOES = {
    "criar_pedido": GERENCIA + ["garcom"],
    "finalizar_pedido": GERENCIA + ["caixa"],
    "receber_pagamento": GERENCIA + ["caixa"],
    "repor_estoque": GERENCIA,
    "mudar_status": GERENCIA + ["garcom", "cozinha"],
    "cancelar_pedido": GERENCIA + ["garcom", "cozinha"],
    "pagina_caixa": GERENCIA + ["caixa"],
    "pagina_cozinha": GERENCIA + ["cozinha"],
    "pagina_equipe": GERENCIA,
    "listar_equipe": GERENCIA,
    "cadastrar_funcionario": GERENCIA,
    "alterar_perfil_funcionario": GERENCIA,
    "alterar_ativo_funcionario": GERENCIA,
    "pagina_qrcodes": GERENCIA
}

ROTAS_QUE_ALTERAM = [
    "criar_pedido", "finalizar_pedido", "receber_pagamento", "pagar_da_mesa",
    "repor_estoque", "mudar_status", "cancelar_pedido"
]
ROTAS_QUE_LEEM = ["obter_dados", "conta_da_mesa"]

QUANTIDADE_DE_MESAS = 8

POLITICA_DE_CONTEUDO = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'; "
    "form-action 'self'; base-uri 'self'"
)

FORMAS_CAIXA = ["Dinheiro", "PIX", "Débito", "Crédito"]
FORMAS_CLIENTE = ["PIX", "Google Pay", "Apple Pay"]


def ler_dados():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return {}
    return dados


def ler_valor(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return 0
    if valor <= 0 or valor > 100000:
        return 0
    return round(valor, 2)


def ler_quantidade(valor):
    if isinstance(valor, bool) or not isinstance(valor, (str, int)):
        return 0
    try:
        quantidade = int(valor)
    except ValueError:
        return 0
    if quantidade < 1 or quantidade > 10000:
        return 0
    return quantidade


def passou_do_limite(tabela, chave, maximo, janela):
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


def sessao_valida():
    """Confere se a sessão pertence a um funcionário que ainda pode usar o sistema.

    A cada INTERVALO_CONFERENCIA a sessão é conferida de novo: a conta precisa continuar
    ativa no Neon e não pode ter sido desativada, apagada ou ter a senha redefinida no
    Firebase depois do login. Se o Firebase ou o Neon estiverem fora do ar, a sessão
    continua valendo por até TOLERANCIA_FALHA, para não parar o restaurante.
    """
    uid = session.get("uid")
    if not uid:
        return False

    agora = time.time()
    if agora - session.get("tentou_em", 0) >= INTERVALO_CONFERENCIA or "usuario_id" not in session:
        session["tentou_em"] = agora
        try:
            usuario = banco.buscar_usuario_por_uid(uid)
            if usuario is None or not usuario["ativo"]:
                return False
            session["perfil"] = usuario["perfil"]
            session["usuario_id"] = usuario["id"]
            if not autenticacao.conta_ainda_valida(uid, session.get("iat", 0)):
                return False
            session["verificado_em"] = agora
        except (BancoErro, ErroAutenticacao) as erro:
            app.logger.warning("Não foi possível conferir a sessão agora: %s", erro)

    return agora - session.get("verificado_em", 0) < TOLERANCIA_FALHA


@app.before_request
def verificar_acesso():
    rotas_publicas = [
        "login", "entrar", "recuperar_senha", "static",
        "pagina_instalacao", "instalar",
        "pagina_mesa", "conta_da_mesa", "pagar_da_mesa"
    ]
    if request.endpoint is None or request.endpoint in rotas_publicas or request.blueprint == "sms":
        return

    if not sessao_valida():
        session.clear()
        if request.method == "GET" and not request.path.startswith("/api/"):
            return redirect("/login")
        return jsonify({"erro": "Faça login para continuar."}), 401

    perfis_permitidos = PERMISSOES.get(request.endpoint)
    if perfis_permitidos and session.get("perfil") not in perfis_permitidos:
        if request.method == "GET" and not request.path.startswith("/api/"):
            return redirect("/")
        return jsonify({"erro": "Seu perfil não tem permissão para esta ação."}), 403

    if request.method == "POST":
        token = request.headers.get("X-CSRF-Token")
        if not token or token != session.get("token"):
            return jsonify({"erro": "Atualize a página e tente novamente."}), 403


@app.errorhandler(BancoErro)
def erro_do_banco(erro):
    app.logger.error("Falha no banco de dados: %s", erro)
    return jsonify({"erro": "Não foi possível acessar o banco de dados agora. Tente novamente."}), 503


@app.errorhandler(ErroAutenticacao)
def erro_do_firebase(erro):
    app.logger.error("Falha no Firebase: %s", erro.mensagem)
    return jsonify({"erro": "Não foi possível falar com o serviço de login. Tente novamente."}), 503


@app.after_request
def cabecalhos_de_seguranca(resposta):
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "same-origin"
    resposta.headers["Content-Security-Policy"] = POLITICA_DE_CONTEUDO
    if request.endpoint != "static":
        resposta.headers["Cache-Control"] = "no-store"
    if os.getenv("VERCEL"):
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resposta


def ainda_sem_usuarios():
    try:
        return banco.contar_usuarios() == 0
    except BancoErro:
        return False


@app.route("/login")
def login():
    if ainda_sem_usuarios():
        return redirect("/instalacao")
    return render_template("login.html")


@app.route("/instalacao")
def pagina_instalacao():
    if not ainda_sem_usuarios():
        return redirect("/login")
    return render_template("instalacao.html")


@app.route("/api/instalacao", methods=["POST"])
def instalar():
    if passou_do_limite(tentativas_instalacao, ip_do_cliente(), 10, 600):
        return jsonify({"erro": "Muitas tentativas. Aguarde alguns minutos."}), 429
    if not ainda_sem_usuarios():
        return jsonify({"erro": "O sistema já foi configurado. Entre com o seu usuário."}), 403

    dados = ler_dados()
    if not codigo_de_instalacao_valido(dados.get("codigo")):
        return jsonify({"erro": "Código de instalação incorreto."}), 403

    campos = [dados.get("nome"), dados.get("email"), dados.get("senha")]
    if not all(isinstance(campo, str) for campo in campos):
        return jsonify({"erro": "Preencha nome, e-mail e senha."}), 400

    try:
        equipe.criar_funcionario(dados["nome"], dados["email"], dados["senha"], "administrador")
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    return jsonify({"mensagem": "Administrador criado. Entre no sistema."}), 201


def erro_de_login(erro):
    """Converte uma falha do Firebase em resposta para a tela de login."""
    if erro.tipo == "credenciais":
        return jsonify({"erro": "E-mail ou senha incorretos."}), 401
    if erro.tipo == "desativada":
        return jsonify({"erro": "Sua conta está desativada. Fale com o gerente."}), 403
    if erro.tipo == "muitas_tentativas":
        return jsonify({"erro": "Muitas tentativas. Aguarde alguns minutos ou use \"Esqueci minha senha\"."}), 429
    app.logger.error("Falha no login pelo Firebase: %s", erro.mensagem)
    if erro.tipo == "configuracao":
        return jsonify({"erro": "O login não está configurado corretamente. Avise o responsável pelo sistema."}), 503
    return jsonify({"erro": "Não foi possível falar com o serviço de login. Tente novamente."}), 503


@app.route("/api/login", methods=["POST"])
def entrar():
    dados = ler_dados()
    email = dados.get("email", "")
    senha = dados.get("senha", "")
    if not isinstance(email, str) or not isinstance(senha, str) or len(senha) > 128:
        return jsonify({"erro": "Informe e-mail e senha válidos."}), 400

    if passou_do_limite(tentativas_login, ip_do_cliente(), 10, 300):
        return jsonify({"erro": "Aguarde 5 minutos antes de tentar novamente."}), 429

    email = email.strip().lower()
    if not email_valido(email) or not senha:
        return jsonify({"erro": "E-mail ou senha incorretos."}), 401

    try:
        conta = autenticacao.entrar(email, senha)
        usuario = banco.buscar_usuario_por_uid(conta["uid"])
    except ErroAutenticacao as erro:
        return erro_de_login(erro)
    except BancoErro as erro:
        app.logger.error("Falha ao consultar o banco no login: %s", erro)
        return jsonify({"erro": "Não foi possível consultar o banco de dados. Tente novamente."}), 503

    if usuario is None or not usuario["ativo"]:
        return jsonify({"erro": "Seu acesso não está liberado. Fale com o gerente."}), 403

    agora = time.time()
    session.clear()
    session["uid"] = conta["uid"]
    session["email"] = usuario["email"]
    session["nome"] = usuario["nome"]
    session["perfil"] = usuario["perfil"]
    session["usuario_id"] = usuario["id"]
    session["iat"] = conta["iat"]
    session["token"] = secrets.token_hex(16)
    session["verificado_em"] = agora
    session["tentou_em"] = agora
    try:
        banco.registrar_login(conta["uid"])
    except BancoErro as erro:
        app.logger.warning("Não foi possível registrar o horário do login: %s", erro)
    return jsonify({"mensagem": "Login realizado."})


@app.route("/api/sair", methods=["POST"])
def sair():
    session.clear()
    return jsonify({"mensagem": "Você saiu do sistema."})


@app.route("/api/recuperar-senha", methods=["POST"])
def recuperar_senha():
    dados = ler_dados()
    email = dados.get("email", "")
    if not email_valido(email):
        return jsonify({"erro": "Informe um e-mail válido."}), 400

    if passou_do_limite(tentativas_recuperacao, ip_do_cliente(), 5, 600):
        return jsonify({"erro": "Muitos pedidos seguidos. Aguarde alguns minutos."}), 429

    # A resposta é sempre a mesma, para não revelar quais e-mails estão cadastrados.
    mensagem = "Se o e-mail estiver cadastrado, enviaremos um link para redefinir a senha."
    email = email.strip().lower()
    try:
        # Só funcionário ativo no Neon recebe o e-mail, no máximo um por minuto.
        if banco.reservar_envio_recuperacao(email, 60):
            autenticacao.enviar_recuperacao(email)
    except (BancoErro, ErroAutenticacao) as erro:
        app.logger.error("Não foi possível enviar o e-mail de recuperação: %s", erro)
    return jsonify({"mensagem": mensagem})


mesas = [Mesa("Livre", numero, False) for numero in range(1, QUANTIDADE_DE_MESAS + 1)]
pedidos = []
caixa = Caixa()
estoque = Estoque()
numero_pedido = 1

cardapio = (
    categoria.entrada
    + categoria.prato_principal
    + categoria.bebida
    + categoria.sobremesa
)


persistir_estado = True


def carregar_estado():
    global mesas, pedidos, caixa, estoque, numero_pedido
    linha = banco_estado.buscar_estado()
    if linha is None:
        banco_estado.criar_estado(estado.estado_para_texto(mesas, pedidos, caixa, estoque, numero_pedido))
        linha = banco_estado.buscar_estado()
    mesas, pedidos, caixa, estoque, numero_pedido = estado.texto_para_estado(linha["dados"])
    g.versao_do_estado = linha["versao"]


@app.before_request
def preparar_estado():
    if not persistir_estado:
        return
    if request.endpoint in ROTAS_QUE_ALTERAM or request.endpoint in ROTAS_QUE_LEEM:
        carregar_estado()


@app.after_request
def guardar_estado(resposta):
    if not persistir_estado or request.endpoint not in ROTAS_QUE_ALTERAM:
        return resposta
    if resposta.status_code >= 400 or "versao_do_estado" not in g:
        return resposta
    texto = estado.estado_para_texto(mesas, pedidos, caixa, estoque, numero_pedido)
    if not banco_estado.salvar_estado(texto, g.versao_do_estado):
        resposta = jsonify({"erro": "Outra pessoa alterou os dados ao mesmo tempo. Tente de novo."})
        resposta.status_code = 409
        return resposta
    return resposta


def iniciar_sistema():
    caixa.abrir_caixa()

    for produto in cardapio:
        estoque.cadastrar_produto_pronto(
            produto["nome"],
            quantidade_inicial=15,
            unidade="un",
            estoque_minimo=5
        )


def buscar_pedido(numero):
    for pedido in pedidos:
        if pedido.numero == numero:
            return pedido
    return None


def buscar_produto(nome):
    for produto in cardapio:
        if produto["nome"] == nome:
            return produto
    return None


def itens_da_conta(pedido):
    lista = []
    for item in pedido.itens:
        lista.append({
            "nome": item["nome"],
            "preco": item["preco"],
            "quantidade": item["quantidade"],
            "total": pedido.total_do_item(item["nome"]),
            "pago": round(pedido.pago_por_item.get(item["nome"], 0), 2),
            "falta": pedido.falta_do_item(item["nome"])
        })
    return lista


def pedido_para_json(pedido):
    return {
        "numero": pedido.numero,
        "mesa": pedido.mesa.numero,
        "itens": pedido.itens,
        "detalhe": itens_da_conta(pedido),
        "total": pedido.calcular_total(),
        "pago": pedido.total_pago(),
        "falta": pedido.calcular_falta(),
        "pagamentos": pedido.pagamentos,
        "status": pedido.status,
        "forma_pagamento": pedido.forma_pagamento
    }


def pedido_da_cozinha(pedido_json):
    return {
        "numero": pedido_json["numero"],
        "mesa": pedido_json["mesa"],
        "itens": pedido_json["itens"],
        "status": pedido_json["status"],
        "total": 0,
        "pago": 0,
        "falta": 0,
        "pagamentos": [],
        "detalhe": []
    }


def buscar_pedido_da_mesa(numero):
    for pedido in pedidos:
        if pedido.mesa.numero == numero and pedido.status not in ["Finalizado", "Cancelado"]:
            return pedido
    return None


@app.route("/")
def pagina_inicial():
    perfil = session["perfil"]
    if perfil == "caixa":
        return redirect("/caixa")
    if perfil == "cozinha":
        return redirect("/cozinha")
    return render_template("index.html", token=session["token"], perfil=perfil)


@app.route("/equipe")
def pagina_equipe():
    return render_template("equipe.html", token=session["token"], perfil=session["perfil"])


def funcionario_para_json(usuario):
    eh_voce = usuario["id"] == session.get("usuario_id")
    return {
        "id": usuario["id"],
        "nome": usuario["nome"],
        "email": usuario["email"],
        "perfil": usuario["perfil"],
        "ativo": usuario["ativo"],
        "voce": eh_voce,
        "pode_gerenciar": not eh_voce and pode_gerenciar(session["perfil"], usuario["perfil"])
    }


@app.route("/api/equipe")
def listar_equipe():
    usuarios = banco.listar_usuarios()
    return jsonify({
        "usuarios": [funcionario_para_json(usuario) for usuario in usuarios],
        "perfis": perfis_que_pode_cadastrar(session["perfil"])
    })


@app.route("/api/equipe", methods=["POST"])
def cadastrar_funcionario():
    dados = ler_dados()
    perfil = dados.get("perfil")
    if perfil not in perfis_que_pode_cadastrar(session["perfil"]):
        return jsonify({"erro": "Você não pode cadastrar este perfil."}), 403

    campos = [dados.get("nome"), dados.get("email"), dados.get("senha")]
    if not all(isinstance(campo, str) for campo in campos):
        return jsonify({"erro": "Preencha nome, e-mail e senha."}), 400
    telefone = dados.get("telefone", "")
    if not isinstance(telefone, str):
        telefone = ""

    try:
        equipe.criar_funcionario(dados["nome"], dados["email"], dados["senha"], perfil, telefone)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400
    return jsonify({"mensagem": "Funcionário cadastrado."}), 201


def funcionario_que_pode_alterar(id_usuario):
    usuario = banco.buscar_usuario_por_id(id_usuario)
    if usuario is None:
        return None, (jsonify({"erro": "Funcionário não encontrado."}), 404)
    eh_voce = usuario["id"] == session.get("usuario_id")
    if eh_voce or not pode_gerenciar(session["perfil"], usuario["perfil"]):
        return None, (jsonify({"erro": "Você não pode alterar este funcionário."}), 403)
    return usuario, None


@app.route("/api/equipe/<int:id_usuario>/perfil", methods=["POST"])
def alterar_perfil_funcionario(id_usuario):
    usuario, erro = funcionario_que_pode_alterar(id_usuario)
    if erro:
        return erro
    perfil = ler_dados().get("perfil")
    if perfil not in perfis_que_pode_cadastrar(session["perfil"]):
        return jsonify({"erro": "Você não pode dar este perfil."}), 403
    banco.alterar_perfil(id_usuario, perfil)
    return jsonify({"mensagem": "Perfil alterado. Vale em até 5 minutos."})


@app.route("/api/equipe/<int:id_usuario>/ativo", methods=["POST"])
def alterar_ativo_funcionario(id_usuario):
    usuario, erro = funcionario_que_pode_alterar(id_usuario)
    if erro:
        return erro
    ativo = ler_dados().get("ativo")
    if not isinstance(ativo, bool):
        return jsonify({"erro": "Informe se o acesso fica ativo."}), 400
    banco.alterar_ativo(id_usuario, ativo)
    return jsonify({"mensagem": "Acesso atualizado. Vale em até 5 minutos."})


def endereco_do_site():
    return os.getenv("URL_PUBLICA", "").strip().rstrip("/") or request.host_url.rstrip("/")


@app.route("/qrcodes")
def pagina_qrcodes():
    lista = []
    for numero in range(1, QUANTIDADE_DE_MESAS + 1):
        endereco = endereco_do_site() + "/mesa/" + str(numero) + "?c=" + codigo_da_mesa(numero)
        imagem = segno.make(endereco, error="m").svg_inline(scale=6, border=2)
        lista.append({"numero": numero, "endereco": endereco, "imagem": imagem})
    return render_template("qrcodes.html", mesas=lista)


@app.route("/caixa")
def pagina_caixa():
    return render_template("caixa.html", token=session["token"])


@app.route("/cozinha")
def pagina_cozinha():
    return render_template("cozinha.html", token=session["token"])


@app.route("/api/dados")
def obter_dados():
    pedidos_abertos = [
        pedido_para_json(pedido)
        for pedido in pedidos
        if pedido.status not in ["Finalizado", "Cancelado"]
    ]

    vendas = [pedido_para_json(pedido) for pedido in caixa.vendas]

    itens_estoque = []
    for item in estoque.produtos_prontos.values():
        itens_estoque.append({
            "nome": item["nome"],
            "quantidade": item["quantidade"],
            "unidade": item["unidade"],
            "estoque_minimo": item["estoque_minimo"],
            "baixo": item["quantidade"] <= item["estoque_minimo"]
        })

    quantidade_vendas = len(caixa.vendas)
    ticket_medio = 0
    if quantidade_vendas > 0:
        ticket_medio = caixa.total_vendido / quantidade_vendas

    perfil = session.get("perfil")
    total_vendido = caixa.total_vendido
    if perfil not in GERENCIA + ["caixa"]:
        vendas = []
        total_vendido = 0
        quantidade_vendas = 0
        ticket_medio = 0
    if perfil not in GERENCIA + ["garcom"]:
        itens_estoque = []
    if perfil == "cozinha":
        pedidos_abertos = [pedido_da_cozinha(pedido) for pedido in pedidos_abertos]

    return jsonify({
        "mesas": [
            {"numero": mesa.numero, "status": mesa.status}
            for mesa in mesas
        ],
        "cardapio": cardapio,
        "pedidos": pedidos_abertos,
        "vendas": vendas,
        "caixa": {
            "status": caixa.status,
            "total_vendido": total_vendido,
            "quantidade_vendas": quantidade_vendas,
            "ticket_medio": ticket_medio
        },
        "estoque": itens_estoque
    })


@app.route("/api/pedidos", methods=["POST"])
def criar_pedido():
    global numero_pedido

    dados = ler_dados()
    numero_mesa = dados.get("mesa")
    itens = dados.get("itens", [])

    numero_mesa = ler_quantidade(numero_mesa)
    if numero_mesa == 0:
        return jsonify({"erro": "Informe uma mesa válida."}), 400

    mesa_escolhida = next(
        (mesa for mesa in mesas if mesa.numero == numero_mesa),
        None
    )

    if mesa_escolhida is None:
        return jsonify({"erro": "Mesa não encontrada."}), 404

    if not isinstance(itens, list) or not itens or len(itens) > 100:
        return jsonify({"erro": "Adicione pelo menos um item ao pedido."}), 400

    itens_agrupados = {}
    for item in itens:
        if not isinstance(item, dict):
            return jsonify({"erro": "Existe um item inválido no pedido."}), 400
        nome = item.get("nome")
        quantidade = ler_quantidade(item.get("quantidade"))
        if not isinstance(nome, str) or quantidade == 0:
            return jsonify({"erro": "Informe produto e quantidade inteira válida."}), 400
        if nome not in itens_agrupados:
            itens_agrupados[nome] = 0
        itens_agrupados[nome] += quantidade

    itens_validados = []
    for nome in itens_agrupados:
        produto = buscar_produto(nome)
        quantidade = itens_agrupados[nome]
        if produto is None:
            return jsonify({"erro": "Produto não encontrado."}), 400
        disponivel, mensagem = estoque.verificar_disponibilidade(produto, quantidade)
        if not disponivel:
            return jsonify({"erro": mensagem}), 400
        itens_validados.append((produto, quantidade))

    pedido = next(
        (
            pedido
            for pedido in pedidos
            if pedido.mesa.numero == numero_mesa
            and pedido.status not in ["Finalizado", "Cancelado"]
        ),
        None
    )

    if pedido is None:
        if mesa_escolhida.status != "Livre":
            return jsonify({"erro": "Essa mesa não está disponível."}), 400

        mesa_escolhida.ocupar()
        pedido = Pedido(numero_pedido, mesa_escolhida)
        pedidos.append(pedido)
        numero_pedido += 1

    for produto, quantidade in itens_validados:
        estoque.baixar_produto(produto, quantidade, pedido.numero)
        pedido.adicionar_item(
            produto["nome"],
            produto["preco"],
            quantidade
        )

    pedido.atualizar_status("Em preparo")

    return jsonify({
        "mensagem": f"Pedido {pedido.numero} enviado com sucesso.",
        "pedido": pedido_para_json(pedido)
    }), 201


@app.route("/api/pedidos/<int:numero>/finalizar", methods=["POST"])
def finalizar_pedido(numero):
    pedido = buscar_pedido(numero)
    dados = ler_dados()
    forma_pagamento = dados.get("forma_pagamento")

    formas_validas = FORMAS_CAIXA

    if pedido is None or pedido.status in ["Finalizado", "Cancelado"]:
        return jsonify({"erro": "Pedido aberto não encontrado."}), 404

    falta = pedido.calcular_falta()
    if falta > 0 and forma_pagamento not in formas_validas:
        return jsonify({"erro": "Escolha uma forma de pagamento válida."}), 400

    if caixa.status != "Aberto":
        return jsonify({"erro": "O caixa está fechado."}), 400

    if falta > 0:
        pedido.registrar_pagamento(forma_pagamento, falta, "Caixa")

    pedido.mesa.pedir_conta()
    pedido.forma_pagamento = pedido.resumo_pagamento()
    caixa.registrar_venda(pedido)
    pedido.mesa.liberar()

    return jsonify({
        "mensagem": f"Conta da mesa {pedido.mesa.numero} finalizada.",
        "pedido": pedido_para_json(pedido)
    })


@app.route("/api/pedidos/<int:numero>/pagamento", methods=["POST"])
def receber_pagamento(numero):
    pedido = buscar_pedido(numero)
    if pedido is None or pedido.status in ["Finalizado", "Cancelado"]:
        return jsonify({"erro": "Pedido aberto não encontrado."}), 404

    dados = ler_dados()
    forma = dados.get("forma")
    valor = ler_valor(dados.get("valor"))
    if forma not in FORMAS_CAIXA:
        return jsonify({"erro": "Escolha uma forma de pagamento válida."}), 400
    if valor == 0:
        return jsonify({"erro": "Informe um valor maior que zero."}), 400

    try:
        pedido.registrar_pagamento(forma, valor, "Caixa")
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    return jsonify({
        "mensagem": f"Pagamento de R$ {valor:.2f} registrado na mesa {pedido.mesa.numero}.",
        "pedido": pedido_para_json(pedido)
    })


def conta_para_json(pedido):
    return {
        "mesa": pedido.mesa.numero,
        "itens": itens_da_conta(pedido),
        "total": pedido.calcular_total(),
        "pago": pedido.total_pago(),
        "falta": pedido.calcular_falta(),
        "status": pedido.status,
        "pagamentos": pedido.pagamentos
    }


def calcular_partes(pedido, dados):
    modo = dados.get("modo")
    if modo == "tudo":
        return pedido.dividir_valor(pedido.calcular_falta())
    if modo == "valor":
        return pedido.dividir_valor(ler_valor(dados.get("valor")))
    if modo != "itens" or not isinstance(dados.get("itens"), list):
        return {}
    partes = {}
    for item in dados["itens"]:
        if not isinstance(item, dict):
            return {}
        nome = item.get("nome")
        divisao = item.get("divisao")
        if not isinstance(nome, str) or divisao not in [1, 2, 3, 4]:
            return {}
        if pedido.falta_do_item(nome) <= 0:
            return {}
        partes[nome] = pedido.valor_da_parte(nome, divisao)
    return partes


def verificar_codigo_da_mesa(numero):
    if numero < 1 or numero > QUANTIDADE_DE_MESAS:
        return jsonify({"erro": "Mesa não encontrada."}), 404
    if codigo_da_mesa_valido(numero, request.args.get("c", "")):
        return None
    if passou_do_limite(tentativas_codigo, ip_do_cliente(), 20, 300):
        return jsonify({"erro": "Muitas tentativas. Aguarde alguns minutos."}), 429
    return jsonify({"erro": "QR Code inválido. Escaneie o QR Code da sua mesa."}), 403


@app.route("/mesa/<int:numero>")
def pagina_mesa(numero):
    codigo = request.args.get("c", "")
    if not codigo_da_mesa_valido(numero, codigo):
        codigo = ""
    return render_template("racha.html", mesa=numero, codigo=codigo)


@app.route("/api/mesa/<int:numero>/conta")
def conta_da_mesa(numero):
    erro = verificar_codigo_da_mesa(numero)
    if erro:
        return erro
    pedido = buscar_pedido_da_mesa(numero)
    if pedido is None:
        return jsonify({"erro": "Esta mesa não tem conta aberta."}), 404
    return jsonify(conta_para_json(pedido))


@app.route("/api/mesa/<int:numero>/pagar", methods=["POST"])
def pagar_da_mesa(numero):
    erro = verificar_codigo_da_mesa(numero)
    if erro:
        return erro
    if passou_do_limite(tentativas_pagamento, ip_do_cliente(), 30, 300):
        return jsonify({"erro": "Muitas tentativas. Aguarde alguns minutos."}), 429

    pedido = buscar_pedido_da_mesa(numero)
    if pedido is None:
        return jsonify({"erro": "Esta mesa não tem conta aberta."}), 404

    dados = ler_dados()
    forma = dados.get("forma")
    if forma not in FORMAS_CLIENTE:
        return jsonify({"erro": "Escolha uma forma de pagamento válida."}), 400

    partes = calcular_partes(pedido, dados)
    valor = round(sum(partes.values()), 2)
    if valor <= 0:
        return jsonify({"erro": "Escolha o que você quer pagar."}), 400

    gorjeta = 0
    if dados.get("gorjeta") is True:
        gorjeta = round(valor * 0.10, 2)

    try:
        pedido.registrar_pagamento(forma, valor, "Cliente", gorjeta, partes)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    return jsonify({
        "mensagem": "Pagamento confirmado.",
        "valor_pago": round(valor + gorjeta, 2),
        "forma": forma,
        "conta": conta_para_json(pedido)
    })


@app.route("/api/estoque/entrada", methods=["POST"])
def repor_estoque():
    dados = ler_dados()
    nome = dados.get("nome")
    if not isinstance(nome, str):
        return jsonify({"erro": "Informe um produto válido."}), 400

    quantidade = ler_quantidade(dados.get("quantidade"))

    if quantidade <= 0:
        return jsonify({"erro": "A quantidade deve ser maior que zero."}), 400

    sucesso = estoque.entrada(
        nome,
        quantidade,
        tipo="produto_pronto",
        motivo="Reposição do gerente"
    )

    if not sucesso:
        return jsonify({"erro": "Produto não encontrado no estoque."}), 404

    return jsonify({"mensagem": f"Foram adicionadas {quantidade} unidades de {nome}."})


@app.route("/api/pedidos/<int:numero>/status", methods=["POST"])
def mudar_status(numero):
    pedido = buscar_pedido(numero)
    if pedido is None:
        return jsonify({"erro": "Pedido não encontrado."}), 404
    dados = ler_dados()
    novo_status = dados.get("status")
    perfil = session.get("perfil")
    if novo_status == "Pronto" and perfil not in GERENCIA + ["cozinha"]:
        return jsonify({"erro": "Só a cozinha marca o pedido como pronto."}), 403
    if novo_status == "Entregue" and perfil not in GERENCIA + ["garcom"]:
        return jsonify({"erro": "Só o garçom marca o pedido como entregue."}), 403
    if pedido.status == "Em preparo" and novo_status == "Pronto":
        pedido.atualizar_status("Pronto")
    elif pedido.status == "Pronto" and novo_status == "Entregue":
        pedido.atualizar_status("Entregue")
    else:
        return jsonify({"erro": "Mudança de status inválida."}), 400
    return jsonify({"mensagem": "Status atualizado.", "pedido": pedido_para_json(pedido)})


@app.route("/api/pedidos/<int:numero>/cancelar", methods=["POST"])
def cancelar_pedido(numero):
    pedido = buscar_pedido(numero)
    if pedido is None:
        return jsonify({"erro": "Pedido não encontrado."}), 404
    if pedido.status != "Em preparo":
        return jsonify({"erro": "Só é possível cancelar um pedido em preparo."}), 400
    if pedido.pagamentos:
        return jsonify({"erro": "Esta conta já tem pagamento registrado e não pode ser cancelada."}), 400
    dados = ler_dados()
    motivo = dados.get("motivo", "")
    if not isinstance(motivo, str) or len(motivo.strip()) < 5 or len(motivo.strip()) > 200:
        return jsonify({"erro": "Informe um motivo entre 5 e 200 caracteres."}), 400
    for item in pedido.itens:
        estoque.entrada(item["nome"], item["quantidade"], "produto_pronto", "Cancelamento: " + motivo.strip())
    pedido.atualizar_status("Cancelado")
    pedido.mesa.liberar()
    return jsonify({"mensagem": "Pedido cancelado. Estoque devolvido."})


iniciar_sistema()


if __name__ == "__main__":
    app.run(debug=False, threaded=False)
