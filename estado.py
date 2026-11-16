import json

from caixa import Caixa
from estoque import Estoque
from mesa import Mesa
from pedido import Pedido


def pedido_para_dicionario(pedido):
    return {
        "numero": pedido.numero,
        "mesa": pedido.mesa.numero,
        "itens": pedido.itens,
        "forma_pagamento": pedido.forma_pagamento,
        "status": pedido.status,
        "pagamentos": pedido.pagamentos,
        "pago_por_item": pedido.pago_por_item
    }


def dicionario_para_pedido(dados, mesas):
    mesa = next(m for m in mesas if m.numero == dados["mesa"])
    pedido = Pedido(dados["numero"], mesa)
    pedido.itens = dados["itens"]
    pedido.forma_pagamento = dados["forma_pagamento"]
    pedido.status = dados["status"]
    pedido.pagamentos = dados["pagamentos"]
    pedido.pago_por_item = dados["pago_por_item"]
    return pedido


def estado_para_texto(mesas, pedidos, caixa, estoque, numero_pedido):
    dados = {
        "mesas": [
            {"numero": m.numero, "status": m.status, "reservada": m.reservada}
            for m in mesas
        ],
        "pedidos": [pedido_para_dicionario(p) for p in pedidos],
        "caixa": {
            "status": caixa.status,
            "total_vendido": caixa.total_vendido,
            "vendas": [p.numero for p in caixa.vendas]
        },
        "estoque": {
            "ingredientes": estoque.ingredientes,
            "produtos_prontos": estoque.produtos_prontos,
            "movimentacoes": estoque.movimentacoes
        },
        "numero_pedido": numero_pedido
    }
    return json.dumps(dados)


def texto_para_estado(texto):
    dados = json.loads(texto)

    mesas = [Mesa(m["status"], m["numero"], m["reservada"]) for m in dados["mesas"]]
    pedidos = [dicionario_para_pedido(p, mesas) for p in dados["pedidos"]]

    caixa = Caixa()
    caixa.status = dados["caixa"]["status"]
    caixa.total_vendido = dados["caixa"]["total_vendido"]
    for numero in dados["caixa"]["vendas"]:
        caixa.vendas.append(next(p for p in pedidos if p.numero == numero))

    estoque = Estoque()
    estoque.ingredientes = dados["estoque"]["ingredientes"]
    estoque.produtos_prontos = dados["estoque"]["produtos_prontos"]
    estoque.movimentacoes = dados["estoque"]["movimentacoes"]

    return mesas, pedidos, caixa, estoque, dados["numero_pedido"]
