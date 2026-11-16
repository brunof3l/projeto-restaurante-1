let dadosCaixa = null;
let ultimoJson = "";
let pagamentoEscolhido = {};
let valorDigitado = {};

const INTERVALO_ATUALIZACAO = 10000;
const FORMAS_PAGAMENTO = ["Dinheiro", "PIX", "Débito", "Crédito"];

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
    dadosCaixa = resultado.dados;
    pegar("atualizacao").textContent = "Atualizado às " +
        new Date().toLocaleTimeString("pt-BR", {hour: "2-digit", minute: "2-digit"});

    if (texto === ultimoJson && !forcar) return;
    ultimoJson = texto;
    renderizarTudo();
}

function atualizarEmSegundoPlano() {
    const digitando = document.activeElement && document.activeElement.tagName === "INPUT";
    if (document.hidden || digitando) return;
    carregarDados();
}

function renderizarTudo() {
    renderizarIndicadores();
    renderizarMesas();
    renderizarContas();
    renderizarVendas();
}

function totalAReceber() {
    let total = 0;
    dadosCaixa.pedidos.forEach(function (pedido) {
        total += pedido.falta;
    });
    return total;
}

function renderizarIndicadores() {
    pegar("caixa-total").textContent = dinheiro.format(dadosCaixa.caixa.total_vendido);
    pegar("caixa-abertas").textContent = dadosCaixa.pedidos.length;
    pegar("caixa-receber").textContent = dinheiro.format(totalAReceber());
}

function pedidoDaMesa(numeroMesa) {
    return dadosCaixa.pedidos.find(function (p) { return p.mesa === numeroMesa; }) || null;
}

function renderizarMesas() {
    const area = pegar("lista-mesas-caixa");
    limpar(area);

    dadosCaixa.mesas.forEach(function (mesa) {
        const pedido = pedidoDaMesa(mesa.numero);
        let classe = "mesa";
        if (mesa.status === "Ocupada") classe += " ocupada";
        if (mesa.status === "Aguardando fechamento") classe += " conta";

        area.appendChild(el("button", {
            type: "button",
            class: classe,
            disabled: !pedido,
            onclick: function () { irParaConta(pedido.numero); }
        },
            el("span", {class: "mesa-numero", texto: mesa.numero}),
            el("span", {class: "mesa-estado", texto: mesa.status}),
            pedido ? el("span", {class: "mesa-total", texto: "Falta " + dinheiro.format(pedido.falta)}) : null
        ));
    });
}

function irParaConta(numeroPedido) {
    const conta = pegar("conta-" + numeroPedido);
    if (conta) conta.scrollIntoView({behavior: "smooth", block: "center"});
}

function renderizarContas() {
    const area = pegar("lista-contas");
    limpar(area);

    if (dadosCaixa.pedidos.length === 0) {
        area.appendChild(el("div", {class: "sem-registro", texto: "Nenhuma conta em aberto no momento."}));
        return;
    }

    dadosCaixa.pedidos.forEach(function (pedido) {
        area.appendChild(criarConta(pedido));
    });
}

function textoDoItem(item) {
    if (item.falta <= 0) return "Pago";
    if (item.pago > 0) return "Falta " + dinheiro.format(item.falta);
    return dinheiro.format(item.total);
}

function criarListaPagamentos(pedido) {
    if (pedido.pagamentos.length === 0) {
        return el("p", {class: "cartao-nota", texto: "Nenhum pagamento recebido ainda."});
    }

    return el("ul", null, pedido.pagamentos.map(function (pagamento) {
        let texto = pagamento.hora + " - " + pagamento.quem + " - " + pagamento.forma;
        if (pagamento.gorjeta > 0) texto += " (gorjeta " + dinheiro.format(pagamento.gorjeta) + ")";
        return el("li", null,
            el("span", {texto: texto}),
            el("span", {class: "preco", texto: dinheiro.format(pagamento.valor)})
        );
    }));
}

function criarOpcoesPagamento(pedido) {
    return FORMAS_PAGAMENTO.map(function (forma) {
        const id = "pg-" + pedido.numero + "-" + forma;
        return el("label", {"for": id},
            el("input", {
                type: "radio",
                id: id,
                name: "pagamento-" + pedido.numero,
                value: forma,
                checked: forma === pagamentoEscolhido[pedido.numero],
                onchange: function () {
                    pagamentoEscolhido[pedido.numero] = forma;
                    carregarDados(true);
                }
            }),
            el("span", {texto: forma})
        );
    });
}

function criarAcoesDaConta(pedido) {
    if (pedido.falta <= 0) {
        return el("div", null,
            el("p", {class: "cartao-nota", texto: "Conta toda paga. Confira e feche a mesa."}),
            el("button", {
                type: "button",
                class: "botao botao-principal",
                texto: "Fechar mesa",
                onclick: function () { fecharConta(pedido.numero); }
            })
        );
    }

    const escolhida = pagamentoEscolhido[pedido.numero] || "";
    const valor = valorDigitado[pedido.numero] !== undefined ? valorDigitado[pedido.numero] : pedido.falta.toFixed(2);

    return el("div", null,
        el("fieldset", {class: "pagamento"},
            el("legend", {texto: "Forma de pagamento"}),
            el("div", {class: "pagamento-opcoes"}, criarOpcoesPagamento(pedido))
        ),
        el("label", {"for": "valor-" + pedido.numero, class: "rotulo-valor", texto: "Valor a receber agora"}),
        el("input", {
            id: "valor-" + pedido.numero,
            class: "campo",
            type: "number",
            min: "0.01",
            max: pedido.falta,
            step: "0.01",
            inputmode: "decimal",
            value: valor,
            oninput: function (evento) { valorDigitado[pedido.numero] = evento.target.value; }
        }),
        el("button", {
            type: "button",
            class: "botao botao-secundario",
            texto: "Receber este valor",
            disabled: !escolhida,
            onclick: function () { receberPagamento(pedido.numero); }
        }),
        el("button", {
            type: "button",
            class: "botao botao-principal",
            texto: "Receber o restante e fechar mesa",
            disabled: !escolhida,
            onclick: function () { fecharConta(pedido.numero); }
        })
    );
}

function criarConta(pedido) {
    return el("article", {class: "conta", id: "conta-" + pedido.numero},
        el("div", {class: "conta-topo"},
            el("h3", {texto: "Mesa " + pedido.mesa}),
            el("span", {class: "etiqueta " + classeStatus(pedido.status), texto: pedido.status})
        ),
        el("ul", null, pedido.detalhe.map(function (item) {
            return el("li", null,
                el("span", {texto: item.quantidade + "x " + item.nome}),
                el("span", {class: "preco", texto: textoDoItem(item)})
            );
        })),
        el("div", {class: "conta-total"},
            el("span", {texto: "Total"}),
            el("strong", {texto: dinheiro.format(pedido.total)})
        ),
        el("div", {class: "conta-resumo"},
            el("span", {texto: "Já pago"}),
            el("b", {class: "preco", texto: dinheiro.format(pedido.pago)})
        ),
        el("div", {class: "conta-resumo falta"},
            el("span", {texto: "Falta pagar"}),
            el("b", {class: "preco", texto: dinheiro.format(pedido.falta)})
        ),
        criarListaPagamentos(pedido),
        criarAcoesDaConta(pedido),
        el("a", {class: "link-cliente", href: "/mesa/" + pedido.mesa, target: "_blank", rel: "noopener", texto: "Abrir a tela do cliente desta mesa"})
    );
}

function classeStatus(status) {
    if (status === "Em preparo") return "preparo";
    if (status === "Pronto") return "pronto";
    return "";
}

async function receberPagamento(numero) {
    const forma = pagamentoEscolhido[numero];
    const valor = Number(pegar("valor-" + numero).value);

    if (!forma || !(valor > 0)) {
        mostrarMensagem("Escolha a forma de pagamento e informe um valor maior que zero.", true);
        return;
    }

    const resultado = await api("/api/pedidos/" + numero + "/pagamento", {forma: forma, valor: valor});
    mostrarMensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
    if (resultado.ok) {
        delete valorDigitado[numero];
        await carregarDados(true);
    }
}

async function fecharConta(numero) {
    const pedido = dadosCaixa.pedidos.find(function (p) { return p.numero === numero; });
    const forma = pagamentoEscolhido[numero];

    if (pedido.falta > 0 && !forma) {
        mostrarMensagem("Escolha a forma de pagamento.", true);
        return;
    }

    const resultado = await api("/api/pedidos/" + numero + "/finalizar", {forma_pagamento: forma});
    mostrarMensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
    if (resultado.ok) {
        delete pagamentoEscolhido[numero];
        delete valorDigitado[numero];
        await carregarDados(true);
    }
}

function renderizarVendas() {
    const area = pegar("lista-vendas");
    limpar(area);

    if (dadosCaixa.vendas.length === 0) {
        area.appendChild(el("div", {class: "sem-registro", texto: "Nenhuma venda finalizada hoje."}));
        return;
    }

    dadosCaixa.vendas.slice().reverse().forEach(function (venda) {
        area.appendChild(el("div", {class: "venda"},
            el("div", null,
                el("strong", {texto: "Pedido " + venda.numero + ", mesa " + venda.mesa}),
                el("small", {texto: "Pago em " + venda.forma_pagamento})
            ),
            el("strong", {texto: dinheiro.format(venda.total)})
        ));
    });
}
