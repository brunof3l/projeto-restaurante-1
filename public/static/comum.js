/* ==========================================================
   Restaurante BKV - funções usadas por todas as telas
   ========================================================== */

const dinheiro = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
});

/* ---------- 2. Funções utilitárias ---------- */

// Cria um elemento HTML de forma segura (usa textContent, nunca innerHTML).
// Assim, nomes de produtos ou motivos digitados não conseguem injetar código.
function el(tag, props, ...filhos) {
    const no = document.createElement(tag);
    Object.entries(props || {}).forEach(function ([chave, valor]) {
        if (valor === null || valor === undefined || valor === false) return;
        if (chave === "class") no.className = valor;
        else if (chave === "texto") no.textContent = valor;
        else if (chave.startsWith("on")) no.addEventListener(chave.slice(2), valor);
        else no.setAttribute(chave, valor === true ? "" : valor);
    });
    filhos.flat().forEach(function (filho) {
        if (filho === null || filho === undefined || filho === false) return;
        no.append(filho.nodeType ? filho : document.createTextNode(filho));
    });
    return no;
}

// Cria um ícone SVG a partir da biblioteca definida no index.html.
function icone(nome) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icone");
    svg.setAttribute("aria-hidden", "true");
    const uso = document.createElementNS("http://www.w3.org/2000/svg", "use");
    uso.setAttribute("href", "#i-" + nome);
    svg.appendChild(uso);
    return svg;
}

function pegar(id) {
    return document.getElementById(id);
}

function limpar(no) {
    no.replaceChildren();
}

function tokenCsrf() {
    const meta = document.querySelector('meta[name="token"]');
    return meta ? meta.content : "";
}

// Única função que fala com o servidor. Trata login expirado (401) e falta de conexão.
async function api(rota, corpo) {
    const opcoes = {};
    if (corpo !== undefined) {
        opcoes.method = "POST";
        opcoes.headers = {"Content-Type": "application/json", "X-CSRF-Token": tokenCsrf()};
        opcoes.body = JSON.stringify(corpo);
    }

    let resposta;
    try {
        resposta = await fetch(rota, opcoes);
    } catch (erro) {
        return {ok: false, dados: {erro: "Sem conexão com o servidor."}, offline: true};
    }

    if (resposta.status === 401) {
        window.location.href = "/login";
        return {ok: false, dados: {}};
    }

    let dados = {};
    try {
        dados = await resposta.json();
    } catch (erro) {
        dados = {};
    }
    return {ok: resposta.ok, dados: dados};
}

/* ---------- 11. Aviso na tela e saída do sistema ---------- */
let temporizadorAviso = null;

function mostrarMensagem(texto, erro) {
    const aviso = pegar("mensagem");
    aviso.textContent = texto;
    aviso.className = "aviso" + (erro ? " erro" : "");
    aviso.hidden = false;

    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(function () { aviso.hidden = true; }, 4000);
}

async function sair() {
    const resultado = await api("/api/sair", {});
    if (resultado.ok) window.location.href = "/login";
}

function mostrarData() {
    pegar("data-atual").textContent = new Date().toLocaleDateString("pt-BR", {
        weekday: "long",
        day: "2-digit",
        month: "long"
    });
}

// O back-end guarda nome e e-mail na sessão (vêm do cadastro no Neon).
// Se o nome não vier, usamos a parte do e-mail antes do "@".
function mostrarUsuario() {
    const email = document.body.dataset.email || "";
    const nomeCadastrado = (document.body.dataset.nome || "").trim();
    const nome = nomeCadastrado || email.split("@")[0].replace(/[._-]+/g, " ").trim() || "Usuário";
    const exibido = nome.charAt(0).toUpperCase() + nome.slice(1);
    pegar("nome-usuario").textContent = exibido;
    pegar("avatar").textContent = exibido.slice(0, 2).toUpperCase();
}

function mostrarLinkInicio() {
    const link = pegar("link-inicio");
    if (link && (document.body.dataset.perfil === "gerente" || document.body.dataset.perfil === "administrador")) link.hidden = false;
}
