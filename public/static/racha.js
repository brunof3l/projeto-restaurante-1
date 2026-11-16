const MESA = Number(document.body.dataset.mesa);
const CODIGO = document.body.dataset.codigo;
const FORMAS_CLIENTE = ["PIX", "Google Pay", "Apple Pay"];
const DIVISOES = [[1, "Tudo"], [2, "Dividir por 2"], [3, "Por 3"], [4, "Por 4"]];

let conta = null;
let tela = "conta";
let aba = "item";
let selecao = {};
let valorLivre = "";
let comGorjeta = true;
let valorAPagar = 0;
let modoPagamento = "itens";
let formaEscolhida = "PIX";
let ultimaCompra = null;
let nota = 0;
let comentario = "";
let avaliacaoPublicada = false;
let ultimoJson = "";
let erroDaConta = "Esta mesa não tem conta aberta.";

document.addEventListener("DOMContentLoaded", function () {
    carregarConta();
    setInterval(atualizarEmSegundoPlano, 20000);
});

function arredondar(valor) {
    return Math.round(valor * 100) / 100;
}

async function carregarConta() {
    const resultado = await api("/api/mesa/" + MESA + "/conta?c=" + encodeURIComponent(CODIGO));
    if (resultado.offline) {
        mostrarMensagem("Sem conexão com o servidor.", true);
        return;
    }
    if (!resultado.ok) {
        conta = null;
        erroDaConta = resultado.dados.erro || erroDaConta;
        renderizar();
        return;
    }
    const texto = JSON.stringify(resultado.dados);
    if (texto === ultimoJson && conta) return;
    ultimoJson = texto;
    conta = resultado.dados;
    renderizar();
}

function atualizarEmSegundoPlano() {
    const digitando = document.activeElement && document.activeElement.tagName === "INPUT";
    if (document.hidden || digitando || tela !== "conta") return;
    carregarConta();
}

function renderizar() {
    if (tela === "pagar") renderizarPagamento();
    else if (tela === "avaliar") renderizarAvaliacao();
    else renderizarConta();
}

function mostrarRodape(botoes) {
    const rodape = pegar("rodape");
    limpar(rodape);
    rodape.hidden = botoes.length === 0;
    botoes.forEach(function (botao) { rodape.appendChild(botao); });
}

function criarBotao(texto, classe, aoClicar, desabilitado) {
    return el("button", {
        type: "button",
        class: "botao " + classe,
        texto: texto,
        disabled: desabilitado,
        onclick: aoClicar
    });
}

function valorDaParte(item, divisao) {
    if (divisao === 1) return item.falta;
    return Math.min(arredondar(item.total / divisao), item.falta);
}

function valorDaSelecao() {
    if (aba === "valor") {
        const digitado = arredondar(Number(valorLivre));
        if (!(digitado > 0)) return 0;
        return Math.min(digitado, conta.falta);
    }
    let total = 0;
    conta.itens.forEach(function (item) {
        if (selecao[item.nome] && item.falta > 0) total += valorDaParte(item, selecao[item.nome]);
    });
    return arredondar(total);
}

function valorDaGorjeta(valor) {
    return comGorjeta ? arredondar(valor * 0.10) : 0;
}

function renderizarConta() {
    const area = pegar("tela");
    limpar(area);

    if (conta === null) {
        area.appendChild(el("div", {class: "centro"},
            el("h2", {texto: erroDaConta}),
            el("p", {texto: "Se precisar, peça ajuda ao garçom e escaneie o QR Code da mesa novamente."})
        ));
        mostrarRodape([]);
        return;
    }

    const percentual = conta.total > 0 ? Math.round((conta.pago / conta.total) * 100) : 0;
    area.appendChild(el("div", {class: "racha-card"},
        el("div", {class: "barra"}, el("b", {style: "width:" + percentual + "%"})),
        el("div", {class: "racha-resumo"},
            el("span", null, "Pago ", el("strong", {texto: dinheiro.format(conta.pago)})),
            el("span", null, "Falta ", el("strong", {texto: dinheiro.format(conta.falta)}))
        )
    ));

    if (conta.falta <= 0) {
        area.appendChild(el("div", {class: "centro"},
            el("div", {class: "marca-ok", texto: "✓"}),
            el("h2", {texto: "Conta paga"}),
            el("p", {texto: "Obrigado pela visita! O caixa vai liberar a mesa."})
        ));
        mostrarRodape([]);
        return;
    }

    area.appendChild(criarAbas());
    if (aba === "item") area.appendChild(criarListaDeItens());
    else area.appendChild(criarCampoValor());
    area.appendChild(criarGorjeta());
    renderizarBotoesDaConta();
}

function criarAbas() {
    const abas = [["item", "Por item"], ["valor", "Valor livre"]];
    return el("div", {class: "racha-abas"}, abas.map(function (opcao) {
        return el("button", {
            type: "button",
            class: aba === opcao[0] ? "ativa" : "",
            texto: opcao[1],
            onclick: function () { aba = opcao[0]; renderizarConta(); }
        });
    }));
}

function criarListaDeItens() {
    return el("div", null, conta.itens.map(function (item) {
        if (item.falta <= 0) {
            return el("div", {class: "item-racha paga"},
                el("div", {class: "item-linha"},
                    el("strong", {texto: item.quantidade + "x " + item.nome}),
                    el("b", {texto: dinheiro.format(item.total)})
                ),
                el("p", {class: "item-nota ok", texto: "Pago"})
            );
        }
        return criarCartaoDoItem(item);
    }));
}

function criarCartaoDoItem(item) {
    const divisao = selecao[item.nome] || 0;
    return el("div", {class: "item-racha" + (divisao ? " escolhido" : "")},
        el("div", {class: "item-linha"},
            el("strong", {texto: item.quantidade + "x " + item.nome}),
            el("b", {texto: dinheiro.format(item.falta)})
        ),
        el("div", {class: "opcoes-divisao"}, DIVISOES.map(function (opcao) {
            return el("button", {
                type: "button",
                class: divisao === opcao[0] ? "ativa" : "",
                texto: opcao[1],
                onclick: function () { escolherDivisao(item.nome, opcao[0]); }
            });
        })),
        item.pago > 0 ? el("p", {class: "item-nota ok", texto: "Já pago: " + dinheiro.format(item.pago)}) : null,
        divisao ? el("p", {class: "item-nota", texto: "Sua parte: " + dinheiro.format(valorDaParte(item, divisao))}) : null
    );
}

function escolherDivisao(nome, divisao) {
    if (selecao[nome] === divisao) delete selecao[nome];
    else selecao[nome] = divisao;
    renderizarConta();
}

function criarCampoValor() {
    return el("div", {class: "racha-card"},
        el("strong", {texto: "Quanto você quer pagar?"}),
        el("p", {class: "item-nota", texto: "Use quando o grupo prefere dividir o total em partes iguais."}),
        el("input", {
            class: "campo",
            type: "number",
            min: "0.01",
            max: conta.falta,
            step: "0.01",
            inputmode: "decimal",
            placeholder: "0,00",
            "aria-label": "Valor a pagar",
            value: valorLivre,
            oninput: function (evento) { valorLivre = evento.target.value; atualizarBotoes(); }
        })
    );
}

function criarGorjeta() {
    return el("label", {class: "gorjeta"},
        el("span", {id: "texto-gorjeta"}),
        el("input", {
            type: "checkbox",
            checked: comGorjeta,
            onchange: function (evento) { comGorjeta = evento.target.checked; atualizarBotoes(); }
        })
    );
}

function atualizarBotoes() {
    renderizarBotoesDaConta();
}

function renderizarBotoesDaConta() {
    const valor = valorDaSelecao();
    const gorjeta = valorDaGorjeta(valor);
    pegar("texto-gorjeta").textContent = "Gorjeta de 10% (" + dinheiro.format(gorjeta) + ")";

    const textoMinha = valor > 0
        ? "Pagar minha seleção · " + dinheiro.format(valor + gorjeta)
        : "Escolha o que vai pagar";
    const gorjetaRestante = valorDaGorjeta(conta.falta);
    const textoTudo = (conta.pago > 0 ? "Pagar o restante · " : "Pagar a conta toda · ") +
        dinheiro.format(conta.falta + gorjetaRestante);

    mostrarRodape([
        criarBotao(textoMinha, "botao-principal", function () { irParaPagamento(aba === "item" ? "itens" : "valor", valor); }, valor <= 0),
        criarBotao(textoTudo, "botao-secundario", function () { irParaPagamento("tudo", conta.falta); }, false)
    ]);
}

function irParaPagamento(modo, valor) {
    modoPagamento = modo;
    valorAPagar = valor;
    tela = "pagar";
    renderizar();
}

function desenharQr() {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 91 91");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    for (let k = 0; k < 169; k++) {
        const linha = Math.floor(k / 13);
        const coluna = k % 13;
        const canto = (linha < 3 && coluna < 3) || (linha < 3 && coluna > 9) || (linha > 9 && coluna < 3);
        if (canto || (k * 7 + (k % 5) * 3) % 3 === 0) {
            const quadrado = document.createElementNS(ns, "rect");
            quadrado.setAttribute("x", coluna * 7);
            quadrado.setAttribute("y", linha * 7);
            quadrado.setAttribute("width", 7);
            quadrado.setAttribute("height", 7);
            svg.appendChild(quadrado);
        }
    }
    const caixa = el("div", {class: "qr"});
    caixa.appendChild(svg);
    return caixa;
}

function renderizarPagamento() {
    const area = pegar("tela");
    limpar(area);
    const total = arredondar(valorAPagar + valorDaGorjeta(valorAPagar));

    area.appendChild(el("div", {class: "centro"},
        el("p", {texto: "Total a pagar"}),
        el("div", {class: "valor-grande", texto: dinheiro.format(total)})
    ));

    area.appendChild(el("div", {class: "formas"}, FORMAS_CLIENTE.map(function (forma) {
        return el("button", {
            type: "button",
            class: forma === formaEscolhida ? "ativa" : "",
            texto: forma,
            onclick: function () { formaEscolhida = forma; renderizarPagamento(); }
        });
    })));

    if (formaEscolhida === "PIX") area.appendChild(criarAreaPix());
    else area.appendChild(criarAreaCarteira());

    const textoConfirmar = formaEscolhida === "PIX" ? "Simular pagamento confirmado" : "Confirmar com " + formaEscolhida;
    mostrarRodape([
        criarBotao(textoConfirmar, "botao-principal", confirmarPagamento, false),
        criarBotao("Voltar", "botao-secundario", function () { tela = "conta"; renderizar(); }, false)
    ]);
}

function criarAreaPix() {
    const botaoCopiar = criarBotao("Copiar código Pix", "botao-secundario", function () {
        botaoCopiar.textContent = "Código copiado";
    }, false);
    return el("div", {class: "centro"},
        desenharQr(),
        el("p", {class: "item-nota", texto: "Escaneie ou copie o código no app do seu banco."}),
        botaoCopiar
    );
}

function criarAreaCarteira() {
    const instrucao = formaEscolhida === "Google Pay" ? "Confirme com sua digital ou PIN" : "Confirme com Face ID";
    return el("div", {class: "carteira"},
        el("small", {texto: formaEscolhida}),
        el("strong", {texto: "Visa •••• 4242"}),
        el("small", {texto: instrucao})
    );
}

function montarCorpoDoPagamento() {
    const corpo = {modo: modoPagamento, forma: formaEscolhida, gorjeta: comGorjeta};
    if (modoPagamento === "itens") {
        corpo.itens = Object.keys(selecao).map(function (nome) {
            return {nome: nome, divisao: selecao[nome]};
        });
    }
    if (modoPagamento === "valor") corpo.valor = valorAPagar;
    return corpo;
}

async function confirmarPagamento() {
    const resultado = await api("/api/mesa/" + MESA + "/pagar?c=" + encodeURIComponent(CODIGO), montarCorpoDoPagamento());
    if (!resultado.ok) {
        mostrarMensagem(resultado.dados.erro || "Não foi possível pagar.", true);
        await carregarConta();
        tela = "conta";
        renderizar();
        return;
    }
    conta = resultado.dados.conta;
    ultimoJson = JSON.stringify(conta);
    ultimaCompra = {valor: resultado.dados.valor_pago, forma: resultado.dados.forma};
    selecao = {};
    valorLivre = "";
    nota = 0;
    comentario = "";
    avaliacaoPublicada = false;
    tela = "avaliar";
    renderizar();
}

function criarLogoGoogle() {
    const cores = [["G", "#4285f4"], ["o", "#ea4335"], ["o", "#fbbc05"], ["g", "#4285f4"], ["l", "#34a853"], ["e", "#ea4335"]];
    return el("div", {class: "google-logo"}, cores.map(function (letra) {
        return el("span", {style: "color:" + letra[1], texto: letra[0]});
    }));
}

function textoDoSaldo() {
    if (conta.falta > 0) return "Ainda faltam " + dinheiro.format(conta.falta) + " para fechar a mesa.";
    return "A conta da mesa está paga.";
}

function renderizarAvaliacao() {
    const area = pegar("tela");
    limpar(area);

    if (avaliacaoPublicada) {
        area.appendChild(el("div", {class: "google"},
            criarLogoGoogle(),
            el("div", {class: "centro"},
                el("div", {class: "marca-ok", texto: "✓"}),
                el("h2", {texto: "Avaliação publicada"}),
                el("p", {class: "google-nota", texto: "Obrigado por avaliar o BKV no Google."}),
                el("p", {texto: textoDoSaldo()})
            )
        ));
        mostrarRodape([criarBotao(conta.falta > 0 ? "Voltar à conta" : "Concluir", "botao-principal", voltarParaConta, false)]);
        return;
    }

    area.appendChild(el("div", {class: "google"},
        criarLogoGoogle(),
        el("div", {class: "google-aviso", texto: "Pagamento de " + dinheiro.format(ultimaCompra.valor) + " confirmado. " + textoDoSaldo()}),
        el("div", {class: "google-card"},
            el("div", {class: "google-local"},
                el("img", {src: "/static/img/logo-bkv.png", alt: "BKV"}),
                el("div", null, el("strong", {texto: "BKV Restaurante"}), el("br"), el("small", {texto: "Como foi sua experiência?"}))
            ),
            el("div", {class: "google-usuario"},
                el("div", {class: "google-avatar", texto: "C"}),
                el("div", null, el("strong", {texto: "Cliente da Mesa " + MESA}), el("br"), el("small", {texto: "Avaliação pública"}))
            ),
            criarEstrelas(),
            criarCampoComentario()
        ),
        el("p", {class: "google-nota centro", texto: "Simulação da página de avaliação do Google"})
    ));
    renderizarBotoesDaAvaliacao();
}

function criarEstrelas() {
    return el("div", {class: "estrelas"}, [1, 2, 3, 4, 5].map(function (numero) {
        return el("button", {
            type: "button",
            class: numero <= nota ? "ativa" : "",
            "aria-label": numero + " estrelas",
            texto: "★",
            onclick: function () { nota = numero; renderizarAvaliacao(); }
        });
    }));
}

function criarCampoComentario() {
    const campo = el("textarea", {
        placeholder: "Compartilhe detalhes da sua experiência neste local (opcional)",
        "aria-label": "Comentário",
        oninput: function (evento) { comentario = evento.target.value; }
    });
    campo.value = comentario;
    return campo;
}

function renderizarBotoesDaAvaliacao() {
    const publicar = el("button", {
        type: "button",
        class: "botao botao-google",
        texto: "Publicar",
        disabled: nota === 0,
        onclick: function () { avaliacaoPublicada = true; renderizarAvaliacao(); }
    });
    mostrarRodape([publicar, criarBotao("Agora não", "botao-secundario", voltarParaConta, false)]);
}

function voltarParaConta() {
    tela = "conta";
    renderizar();
}
