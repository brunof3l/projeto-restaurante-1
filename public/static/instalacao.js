function pegar(id) {
    return document.getElementById(id);
}

function mostrarMensagem(texto, erro) {
    const mensagem = pegar("mensagem");
    mensagem.textContent = texto;
    mensagem.className = erro ? "erro" : "";
}

document.querySelectorAll(".ver-senha").forEach(function (botao) {
    botao.addEventListener("click", function () {
        const campo = pegar(botao.dataset.alvo);
        const visivel = campo.type === "text";
        campo.type = visivel ? "password" : "text";
        botao.textContent = visivel ? "Mostrar" : "Ocultar";
        botao.setAttribute("aria-pressed", visivel ? "false" : "true");
    });
});

async function criarAdministrador(evento) {
    evento.preventDefault();

    if (pegar("senha-admin").value !== pegar("confirmacao-admin").value) {
        mostrarMensagem("As senhas não são iguais.", true);
        return;
    }

    const corpo = {
        codigo: pegar("codigo-instalacao").value,
        nome: pegar("nome-admin").value,
        email: pegar("email-admin").value,
        senha: pegar("senha-admin").value
    };

    pegar("botao-instalar").disabled = true;
    try {
        const resposta = await fetch("/api/instalacao", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(corpo)
        });
        const dados = await resposta.json();
        mostrarMensagem(dados.mensagem || dados.erro, !resposta.ok);
        if (resposta.ok) {
            window.location.href = "/login";
            return;
        }
    } catch (erro) {
        mostrarMensagem("Sem conexão com o servidor. Tente novamente.", true);
    }
    pegar("botao-instalar").disabled = false;
}

pegar("form-instalacao").addEventListener("submit", criarAdministrador);
