/* ==========================================================
   Restaurante BKV - recuperação de senha por SMS
   Complementa o login.js (usa pegar, mostrarTela, mostrarMensagem
   e enviarDados, definidas lá). O fluxo por e-mail não é alterado.
   ========================================================== */

(function () {
    const ESPERA_SMS = 60; // segundos; o back-end também bloqueia pedidos em 60 s
    let temporizadorSms = null;

    /* ---------- Só mostra a opção se o SMS estiver configurado no servidor ---------- */
    fetch("/api/sms/status")
        .then(function (resposta) { return resposta.json(); })
        .then(function (dados) {
            if (!dados.ativo) return;
            pegar("ou-sms").hidden = false;
            pegar("botao-sms").hidden = false;
        })
        .catch(function () { /* sem resposta: a opção continua escondida */ });

    /* ---------- Regras da nova senha, marcadas enquanto digita ---------- */
    function atualizarRegrasSms() {
        const senha = pegar("nova-senha-sms").value;
        const confirmacao = pegar("confirmacao-sms").value;
        const regras = {
            tamanho: senha.length >= 8 && senha.length <= 128,
            letra: /[A-Za-zÀ-ÿ]/.test(senha),
            numero: /[0-9]/.test(senha),
            igual: senha !== "" && senha === confirmacao
        };
        document.querySelectorAll("#regras-senha-sms li").forEach(function (item) {
            item.classList.toggle("ok", regras[item.dataset.regra]);
        });
    }
    pegar("nova-senha-sms").addEventListener("input", atualizarRegrasSms);
    pegar("confirmacao-sms").addEventListener("input", atualizarRegrasSms);

    // O código só aceita números.
    pegar("codigo-sms").addEventListener("input", function () {
        this.value = this.value.replace(/\D/g, "").slice(0, 4);
    });

    /* ---------- Contagem de 60 segundos no botão "Enviar código" ---------- */
    function iniciarContagemSms() {
        const botao = pegar("botao-enviar-sms");
        let restante = ESPERA_SMS;
        botao.disabled = true;
        botao.textContent = "Enviar de novo em " + restante + " s";

        clearInterval(temporizadorSms);
        temporizadorSms = setInterval(function () {
            restante -= 1;
            if (restante <= 0) {
                clearInterval(temporizadorSms);
                temporizadorSms = null;
                botao.disabled = false;
                botao.textContent = "Enviar código";
                return;
            }
            botao.textContent = "Enviar de novo em " + restante + " s";
        }, 1000);
    }

    /* ---------- Passo 1: pedir o código ---------- */
    pegar("form-sms").addEventListener("submit", async function (evento) {
        evento.preventDefault();
        const email = pegar("email-sms").value;
        const sucesso = await enviarDados("/api/sms/solicitar", {email: email}, this);
        if (sucesso) {
            pegar("email-sms-codigo").value = email;
            iniciarContagemSms();
        }
    });

    /* ---------- Passo 2: código + nova senha ---------- */
    pegar("form-sms-codigo").addEventListener("submit", async function (evento) {
        evento.preventDefault();
        const dados = {
            email: pegar("email-sms-codigo").value,
            codigo: pegar("codigo-sms").value,
            senha: pegar("nova-senha-sms").value,
            confirmacao: pegar("confirmacao-sms").value
        };
        const sucesso = await enviarDados("/api/sms/confirmar", dados, this);
        if (sucesso) {
            this.reset();
            atualizarRegrasSms();
            mostrarTela("acesso");
            mostrarMensagem("Senha alterada. Entre com sua nova senha.", false);
        }
    });
})();
