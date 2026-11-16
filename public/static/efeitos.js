/* ==========================================================
   Restaurante BKV - efeitos da interface principal
   Só observa a tela e acrescenta detalhes visuais. Não altera dados,
   nem as funções do script.js. Se este arquivo for removido, o sistema
   continua funcionando igual.
   ========================================================== */

(function () {
    const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* ---------- 1. Ícone e cor de cada prato ---------- */
    const ICONE_CATEGORIA = {
        "Entradas": "🥗",
        "Pratos principais": "🍽️",
        "Bebidas": "🥤",
        "Sobremesas": "🍨"
    };

    // Palavras do nome do prato (sem acento, minúsculas) -> ícone
    const ICONE_PALAVRA = [
        ["cerveja", "🍺"], ["caipirinha", "🍹"], ["vinho", "🍷"], ["cafe", "☕"], ["cha ", "🍵"],
        ["agua", "💧"], ["limonada", "🍋"], ["suco", "🧃"], ["coca", "🥤"], ["guarana", "🥤"],
        ["brownie", "🍫"], ["pudim", "🍮"], ["sorvete", "🍨"], ["banana", "🍌"], ["petit", "🍰"],
        ["mousse", "🍮"], ["torta", "🥧"],
        ["feijoada", "🍲"], ["moqueca", "🍲"], ["lasanha", "🍝"], ["risoto", "🍚"], ["arroz", "🍚"],
        ["strogonoff", "🍛"], ["parmegiana", "🍛"], ["salmao", "🐟"], ["costela", "🍖"], ["picanha", "🥩"],
        ["salada", "🥗"], ["bruschetta", "🍞"], ["bolinho", "🧆"], ["carpaccio", "🥩"], ["pastel", "🥟"],
        ["batata", "🍟"], ["caldo", "🥣"]
    ];

    function semAcento(texto) {
        return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase() + " ";
    }

    function iconeDoPrato(nome, categoria) {
        const base = semAcento(nome);
        for (const [palavra, icone] of ICONE_PALAVRA) {
            if (base.includes(palavra)) return icone;
        }
        return ICONE_CATEGORIA[categoria] || "🍴";
    }

    function enfeitarProdutos() {
        document.querySelectorAll("#lista-cardapio .produto").forEach(function (botao) {
            if (botao.querySelector(".produto-icone")) return;
            const categoria = (botao.querySelector(".produto-categoria") || {}).textContent || "";
            const nome = (botao.querySelector(".produto-nome") || {}).textContent || "";
            botao.dataset.cat = categoria;
            const icone = document.createElement("span");
            icone.className = "produto-icone";
            icone.setAttribute("aria-hidden", "true");
            icone.textContent = iconeDoPrato(nome, categoria);
            botao.appendChild(icone);
        });
    }

    const listaCardapio = document.getElementById("lista-cardapio");
    if (listaCardapio) {
        // O script.js redesenha a lista inteira quando algo muda; enfeita de novo a cada vez.
        new MutationObserver(enfeitarProdutos).observe(listaCardapio, {childList: true});
        enfeitarProdutos();
    }

    /* ---------- 2. "+1" ao tocar num prato (só se entrou na comanda) ---------- */
    const totalPedido = document.getElementById("total-pedido");

    if (listaCardapio && totalPedido && !reduzido) {
        // Captura: roda antes do clique do prato, para guardar o total de antes.
        listaCardapio.addEventListener("click", function (evento) {
            const botao = evento.target.closest(".produto");
            if (!botao || botao.disabled) return;
            const antes = totalPedido.textContent;
            const x = evento.clientX, y = evento.clientY;
            setTimeout(function () {
                if (totalPedido.textContent === antes) return; // o sistema recusou (estoque)
                botao.classList.remove("adicionado");
                void botao.offsetWidth; // reinicia a animação em cliques seguidos
                botao.classList.add("adicionado");
                const voa = document.createElement("span");
                voa.className = "voa-mais";
                voa.textContent = "+1";
                voa.style.left = x + "px";
                voa.style.top = y + "px";
                voa.addEventListener("animationend", function () { voa.remove(); });
                document.body.appendChild(voa);
            }, 0);
        }, true);
    }

    /* ---------- 3. Comanda: só o item novo (ou alterado) "imprime" ---------- */
    const itensPedido = document.getElementById("itens-pedido");
    let anteriores = {};

    function lerItens() {
        const itens = {};
        itensPedido.querySelectorAll(".item-pedido").forEach(function (linha) {
            const nome = (linha.querySelector("strong") || {}).textContent || "";
            const qtd = (linha.querySelector(".controle-quantidade span") || {}).textContent || "";
            itens[nome] = {linha: linha, qtd: qtd};
        });
        return itens;
    }

    if (itensPedido && !reduzido) {
        new MutationObserver(function () {
            const atuais = lerItens();
            Object.keys(atuais).forEach(function (nome) {
                const antes = anteriores[nome];
                if (!antes || antes.qtd !== atuais[nome].qtd) atuais[nome].linha.classList.add("novo");
            });
            anteriores = atuais;
        }).observe(itensPedido, {childList: true});
        anteriores = lerItens();
    }

    // O total da comanda dá uma batida quando muda.
    if (totalPedido && !reduzido) {
        let textoTotal = totalPedido.textContent;
        new MutationObserver(function () {
            if (totalPedido.textContent === textoTotal) return;
            textoTotal = totalPedido.textContent;
            totalPedido.classList.remove("subiu");
            void totalPedido.offsetWidth;
            totalPedido.classList.add("subiu");
        }).observe(totalPedido, {childList: true, characterData: true, subtree: true});
    }

    /* ---------- 4. Indicadores: o número conta até o valor ---------- */
    const IDS_INDICADORES = ["caixa-total", "caixa-vendas", "caixa-abertas", "gerente-total", "ticket-medio", "estoque-baixo"];
    const NUMERO = /\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?/;
    const DURACAO = 700;

    function valorDoTexto(texto) {
        const m = texto.match(NUMERO);
        if (!m) return null;
        return {
            valor: parseFloat(m[0].replace(/\./g, "").replace(",", ".")),
            casas: m[0].includes(",") ? m[0].split(",")[1].length : 0,
            antes: texto.slice(0, m.index),
            depois: texto.slice(m.index + m[0].length)
        };
    }

    function contarAte(no) {
        const inicial = valorDoTexto(no.textContent);
        no._exibido = inicial ? inicial.valor : 0;

        const observador = new MutationObserver(function () {
            const alvoTexto = no.textContent;
            const alvo = valorDoTexto(alvoTexto);
            cancelAnimationFrame(no._quadro);
            if (!alvo || alvo.valor === no._exibido) {
                if (alvo) no._exibido = alvo.valor;
                return;
            }

            const de = no._exibido;
            const inicio = performance.now();
            const formato = new Intl.NumberFormat("pt-BR", {minimumFractionDigits: alvo.casas, maximumFractionDigits: alvo.casas});

            function passo(agora) {
                const p = Math.min((agora - inicio) / DURACAO, 1);
                const suave = 1 - Math.pow(1 - p, 3);
                no._exibido = de + (alvo.valor - de) * suave;
                no.textContent = p < 1 ? alvo.antes + formato.format(no._exibido) + alvo.depois : alvoTexto;
                observador.takeRecords(); // descarta o aviso das minhas próprias escritas
                if (p < 1) no._quadro = requestAnimationFrame(passo);
                else no._exibido = alvo.valor;
            }
            no._quadro = requestAnimationFrame(passo);
        });
        observador.observe(no, {childList: true, characterData: true, subtree: true});
    }

    if (!reduzido) {
        IDS_INDICADORES.forEach(function (id) {
            const no = document.getElementById(id);
            if (no) contarAte(no);
        });
    }
})();
