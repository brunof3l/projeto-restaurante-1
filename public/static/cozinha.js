let dadosCozinha = null;
let ultimoJson = "";

const INTERVALO_ATUALIZACAO = 8000;

document.addEventListener("DOMContentLoaded", function () {
    mostrarData();
    mostrarUsuario();
    mostrarLinkInicio();
    pegar("botao-sair").addEventListener("click", sair);
    carregarDados();
    setInterval(atualizarEmSegundoPlano, INTERVALO_ATUALIZACAO);
});

async function carregarDados(forcar) {
    const resultado = await api("/api/dados");

    if (resultado.offline) {
        pegar("aviso-conexao").hidden = false;
        return;
    }
    pegar("aviso-conexao").hidden = true;
    if (!resultado.ok) return;

    const texto = JSON.stringify(resultado.dados);
    dadosCozinha = resultado.dados;
    pegar("atualizacao").textContent = "Atualizado às " +
        new Date().toLocaleTimeString("pt-BR", {hour: "2-digit", minute: "2-digit"});

    if (texto === ultimoJson && !forcar) return;
    ultimoJson = texto;
    renderizarCozinha();
}

function atualizarEmSegundoPlano() {
    if (document.hidden) return;
    carregarDados();
}

function renderizarCozinha() {
    const area = pegar("quadro-cozinha");
    const colunas = [
        {status: "Em preparo", classe: "preparo", titulo: "Em preparo"},
        {status: "Pronto", classe: "pronto", titulo: "Prontos para o garçom"}
    ];

    limpar(area);
    colunas.forEach(function (coluna) {
        const pedidos = dadosCozinha.pedidos.filter(function (p) { return p.status === coluna.status; });
        const lista = el("div", {class: "coluna-lista"});

        if (pedidos.length === 0) {
            lista.appendChild(el("div", {class: "sem-registro", texto: "Nenhum pedido aqui."}));
        }
        pedidos.forEach(function (pedido) {
            lista.appendChild(criarCartao(pedido));
        });

        area.appendChild(el("section", {class: "coluna " + coluna.classe, "aria-label": coluna.titulo},
            el("div", {class: "coluna-topo"},
                el("h2", {texto: coluna.titulo}),
                el("span", {texto: pedidos.length})
            ),
            lista
        ));
    });
}

function criarCartao(pedido) {
    const acoes = el("div", {class: "cartao-acoes"});

    if (pedido.status === "Em preparo") {
        acoes.appendChild(el("button", {
            type: "button",
            class: "botao botao-principal",
            texto: "Marcar como pronto",
            onclick: function () { marcarPronto(pedido.numero); }
        }));
    }

    return el("article", {class: "cartao"},
        el("div", {class: "cartao-topo"},
            el("h3", {texto: "Mesa " + pedido.mesa}),
            el("span", {class: "cartao-numero", texto: "Pedido " + pedido.numero})
        ),
        el("ul", {class: "itens-cozinha"}, pedido.itens.map(function (item) {
            return el("li", null, el("b", {texto: item.quantidade + "x"}), item.nome);
        })),
        pedido.status === "Pronto"
            ? el("p", {class: "cartao-nota", texto: "Aguardando o garçom retirar."})
            : null,
        acoes
    );
}

async function marcarPronto(numero) {
    const resultado = await api("/api/pedidos/" + numero + "/status", {status: "Pronto"});
    mostrarMensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
    if (resultado.ok) await carregarDados(true);
}
