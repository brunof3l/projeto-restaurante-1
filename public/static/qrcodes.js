document.addEventListener("DOMContentLoaded", function () {
    mostrarData();
    mostrarUsuario();
    mostrarLinkInicio();
    pegar("botao-sair").addEventListener("click", sair);
    pegar("botao-imprimir").addEventListener("click", imprimirQrCodes);
});

function imprimirQrCodes() {
    window.print();
}
