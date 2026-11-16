/* ==========================================================
   Restaurante BKV - efeito do azulejo na página de acesso
   Os losangos acendem em dourado perto do cursor. Sem mouse
   (celular) ou parado por alguns segundos, a luz passeia sozinha.
   Só mexe nas variáveis --mx e --my do painel; não toca no formulário.
   ========================================================== */

(function () {
    const painel = document.querySelector(".azulejo");
    const marca = document.querySelector(".marca");
    if (!painel || !marca) return;

    const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduzido) return; // fica a luz estática do CSS

    let alvoX = 0.5, alvoY = 0.4;     // posição desejada (0 a 1)
    let x = -0.2, y = 0.4;            // posição atual: a luz entra pela esquerda ao abrir a página
    let ultimoMovimento = 0;          // quando o mouse mexeu pela última vez
    let quadro = 0;

    marca.addEventListener("pointermove", function (evento) {
        const caixa = painel.getBoundingClientRect();
        alvoX = (evento.clientX - caixa.left) / caixa.width;
        alvoY = (evento.clientY - caixa.top) / caixa.height;
        ultimoMovimento = performance.now();
    });

    function animar(agora) {
        // Parado por 4 s (ou sem mouse): a luz desenha uma volta lenta sobre o painel.
        if (agora - ultimoMovimento > 4000) {
            alvoX = 0.5 + 0.32 * Math.sin(agora / 2600);
            alvoY = 0.38 + 0.2 * Math.sin(agora / 1900 + 1.2);
        }
        // Segue o alvo com suavidade.
        x += (alvoX - x) * 0.08;
        y += (alvoY - y) * 0.08;
        painel.style.setProperty("--mx", (x * 100).toFixed(1) + "%");
        painel.style.setProperty("--my", (y * 100).toFixed(1) + "%");
        quadro = requestAnimationFrame(animar);
    }

    // Não gasta bateria com a aba escondida.
    document.addEventListener("visibilitychange", function () {
        cancelAnimationFrame(quadro);
        if (!document.hidden) quadro = requestAnimationFrame(animar);
    });
    quadro = requestAnimationFrame(animar);
})();
