let dadosEquipe = null;

const NOMES_DOS_PERFIS = {
    administrador: "Administrador",
    gerente: "Gerente",
    caixa: "Caixa",
    garcom: "Garçom",
    cozinha: "Cozinha"
};

document.addEventListener("DOMContentLoaded", function () {
    mostrarData();
    mostrarUsuario();
    mostrarLinkInicio();
    pegar("botao-sair").addEventListener("click", sair);
    pegar("form-funcionario").addEventListener("submit", cadastrarFuncionario);
    carregarEquipe();
});

async function carregarEquipe() {
    const resultado = await api("/api/equipe");

    if (resultado.offline) {
        pegar("aviso-conexao").hidden = false;
        return;
    }
    pegar("aviso-conexao").hidden = true;
    if (!resultado.ok) {
        mostrarMensagem(resultado.dados.erro, true);
        return;
    }

    dadosEquipe = resultado.dados;
    renderizarPerfis();
    renderizarLista();
}

function renderizarPerfis() {
    const select = pegar("func-perfil");
    limpar(select);
    dadosEquipe.perfis.forEach(function (perfil) {
        select.appendChild(el("option", {value: perfil, texto: NOMES_DOS_PERFIS[perfil]}));
    });
}

function renderizarLista() {
    const area = pegar("lista-equipe");
    limpar(area);

    if (dadosEquipe.usuarios.length === 0) {
        area.appendChild(el("div", {class: "sem-registro", texto: "Nenhum funcionário cadastrado."}));
        return;
    }

    dadosEquipe.usuarios.forEach(function (usuario) {
        area.appendChild(criarLinha(usuario));
    });
}

function criarSeletorDePerfil(usuario) {
    return el("select", {
        class: "campo",
        "aria-label": "Perfil de " + usuario.nome,
        onchange: function (evento) { alterarPerfil(usuario.id, evento.target.value); }
    }, dadosEquipe.perfis.map(function (perfil) {
        return el("option", {value: perfil, selected: perfil === usuario.perfil, texto: NOMES_DOS_PERFIS[perfil]});
    }));
}

function criarAcoes(usuario) {
    if (!usuario.pode_gerenciar) {
        return el("div", {class: "acoes-equipe"},
            el("span", {class: "etiqueta", texto: NOMES_DOS_PERFIS[usuario.perfil]})
        );
    }

    return el("div", {class: "acoes-equipe"},
        criarSeletorDePerfil(usuario),
        el("button", {
            type: "button",
            class: "botao botao-secundario",
            texto: usuario.ativo ? "Desativar acesso" : "Reativar acesso",
            onclick: function () { alternarAcesso(usuario); }
        })
    );
}

function criarLinha(usuario) {
    return el("article", {class: "conta"},
        el("div", {class: "conta-topo"},
            el("h3", {texto: usuario.nome + (usuario.voce ? " (você)" : "")}),
            el("span", {class: "etiqueta " + (usuario.ativo ? "pronto" : "preparo"), texto: usuario.ativo ? "Ativo" : "Desativado"})
        ),
        el("p", {class: "cartao-nota", texto: usuario.email}),
        criarAcoes(usuario)
    );
}

async function cadastrarFuncionario(evento) {
    evento.preventDefault();
    const corpo = {
        nome: pegar("func-nome").value,
        email: pegar("func-email").value,
        telefone: pegar("func-telefone").value,
        perfil: pegar("func-perfil").value,
        senha: pegar("func-senha").value
    };

    const resultado = await api("/api/equipe", corpo);
    mostrarMensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
    if (resultado.ok) {
        pegar("form-funcionario").reset();
        await carregarEquipe();
    }
}

async function alterarPerfil(id, perfil) {
    const resultado = await api("/api/equipe/" + id + "/perfil", {perfil: perfil});
    mostrarMensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
    await carregarEquipe();
}

async function alternarAcesso(usuario) {
    const resultado = await api("/api/equipe/" + usuario.id + "/ativo", {ativo: !usuario.ativo});
    mostrarMensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
    await carregarEquipe();
}
