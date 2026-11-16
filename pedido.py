import time

from carrinho import Carrinho


def hora_atual():
    agora = time.time() - 4 * 3600
    return time.strftime("%H:%M", time.gmtime(agora))


class Pedido(Carrinho):
    def __init__(self, numero, mesa):
        super().__init__()
        self.numero = numero
        self.mesa = mesa
        self.status = "Aguardando"
        self.pagamentos = []
        self.pago_por_item = {}

    def remover_item(self, indice):
        if 0 <= indice < len(self.itens):
            self.itens.pop(indice)

    def alterar_quantidade(self, indice, quantidade):
        if 0 <= indice < len(self.itens):
            if quantidade > 0:
                self.itens[indice]["quantidade"] = quantidade
            else:
                self.remover_item(indice)

    def atualizar_status(self, status):
        self.status = status

    def total_do_item(self, nome):
        for item in self.itens:
            if item["nome"] == nome:
                return round(item["preco"] * item["quantidade"], 2)
        return 0

    def falta_do_item(self, nome):
        pago = self.pago_por_item.get(nome, 0)
        return round(self.total_do_item(nome) - pago, 2)

    def total_pago(self):
        total = 0
        for pagamento in self.pagamentos:
            total += pagamento["valor"]
        return round(total, 2)

    def calcular_falta(self):
        return round(self.calcular_total() - self.total_pago(), 2)

    def valor_da_parte(self, nome, divisao):
        falta = self.falta_do_item(nome)
        if divisao == 1:
            return falta
        parte = round(self.total_do_item(nome) / divisao, 2)
        return min(parte, falta)

    def dividir_valor(self, valor):
        partes = {}
        restante = valor
        for item in self.itens:
            usado = min(self.falta_do_item(item["nome"]), restante)
            if usado > 0:
                partes[item["nome"]] = usado
                restante = round(restante - usado, 2)
        return partes

    def registrar_pagamento(self, forma, valor, quem, gorjeta=0, partes=None):
        if self.status in ["Finalizado", "Cancelado"]:
            raise ValueError("Este pedido já foi encerrado.")
        valor = round(valor, 2)
        if valor <= 0:
            raise ValueError("Informe um valor maior que zero.")
        if valor > self.calcular_falta():
            raise ValueError("O valor é maior do que falta pagar.")
        if partes is None:
            partes = self.dividir_valor(valor)
        for nome in partes:
            pago = self.pago_por_item.get(nome, 0)
            self.pago_por_item[nome] = round(pago + partes[nome], 2)
        self.pagamentos.append({
            "forma": forma,
            "valor": valor,
            "gorjeta": gorjeta,
            "quem": quem,
            "hora": hora_atual()
        })

    def resumo_pagamento(self):
        formas = []
        for pagamento in self.pagamentos:
            if pagamento["forma"] not in formas:
                formas.append(pagamento["forma"])
        return " + ".join(formas)

    def mostrar_pedido(self):
        print("----- PEDIDO -----")
        print(f"Pedido: {self.numero}")
        print(f"Mesa: {self.mesa.numero}")

        for item in self.itens:
            subtotal = item["preco"] * item["quantidade"]
            print(
                f"{item['quantidade']}x "
                f"{item['nome']} - "
                f"R$ {subtotal:.2f}"
            )

        print(f"Total: R$ {self.calcular_total():.2f}")
        print(f"Pagamento: {self.forma_pagamento}")
        print(f"Status: {self.status}")
