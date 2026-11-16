# Sistema de Restaurante — Restaurante BKV

Projeto acadêmico em Python para organizar o atendimento de um restaurante: controle de mesas, pedidos, pagamentos, estoque e funcionários. O sistema usa **Flask** para ligar as classes Python a uma interface web feita com HTML, CSS e JavaScript.

## Alunos responsáveis

- Bruno Ferreira
- Kennedy Fernando
- Vinicius dos Anjos
- Sthevan Vinicius

## Sumário

1. [Objetivo](#objetivo)
2. [O que foi desenvolvido](#o-que-foi-desenvolvido)
3. [Tecnologias](#tecnologias)
4. [Perfis de acesso](#perfis-de-acesso)
5. [Telas do sistema](#telas-do-sistema)
6. [Funcionamento](#funcionamento)
7. [Classes e arquivos](#classes-e-arquivos)
8. [Programação orientada a objetos no projeto](#programação-orientada-a-objetos-no-projeto)
9. [Como executar](#como-executar)
10. [Testes](#testes)
11. [Limitações](#limitações)

## Objetivo

Centralizar as informações usadas pelos funcionários e facilitar o atendimento. O fluxo principal é:

1. O funcionário entra com e-mail e senha.
2. Escolhe uma mesa e adiciona produtos ao pedido.
3. O sistema confere o estoque e envia o pedido para a cozinha.
4. A cozinha marca como **Pronto** e o garçom marca como **Entregue**.
5. O cliente pode dividir e pagar a conta pelo celular, ou o caixa recebe o pagamento.
6. O caixa fecha a conta, libera a mesa e o gerente acompanha as vendas e o estoque.

## O que foi desenvolvido

Partimos de um projeto com classes básicas (Mesa, Pedido, Caixa, Estoque, Usuário, Categoria), em que vários métodos estavam sem funcionamento. Nesta versão:

- Implementamos os métodos que estavam vazios (`Carrinho` e `Pedido`) e ligamos tudo a uma **interface web** com Flask.
- Criamos **login com Firebase Authentication**. As senhas ficam no Firebase, e o Neon (PostgreSQL) guarda quem está autorizado a usar o sistema.
- Criamos **perfis de acesso** (administrador, gerente, caixa, garçom e cozinha), com bloqueio feito no servidor.
- Criamos telas próprias para **caixa** e **cozinha**.
- Criamos o **Racha-conta**: o cliente escaneia o QR Code da mesa, divide a conta por item ou por valor, inclui 10% de gorjeta e paga (Pix, Google Pay e Apple Pay são simulados).
- Criamos **recuperação de senha** por e-mail (enviado pelo Firebase) e por SMS (opcional).
- Criamos o **cadastro da equipe** dentro do sistema e a **geração dos QR Codes das mesas**.
- Guardamos o estado do restaurante (mesas, pedidos, vendas e estoque) no banco, para os dados não se perderem.
- Adicionamos validações (quantidades, estoque, pagamentos duplicados) e **122 testes automatizados**.

## Tecnologias

| Tecnologia | Uso |
| --- | --- |
| Python | Classes, regras e validações |
| Flask | Rotas e comunicação entre o navegador e o Python |
| HTML, CSS e JavaScript | Interface (sem frameworks) |
| Neon (PostgreSQL) com psycopg | Banco de dados de usuários e estado do restaurante |
| Firebase Authentication (firebase-admin e requests) | Senhas, login e recuperação de senha |
| segno | Geração dos QR Codes |
| python-dotenv | Leitura das configurações do arquivo `.env` |
| unittest | Testes automatizados |

## Perfis de acesso

O perfil de cada funcionário fica na tabela `usuarios` do banco. O servidor confere o perfil em toda requisição (tabela `PERMISSOES` no `app.py`), então esconder um botão na tela não é a única proteção.

| Perfil | O que pode fazer |
| --- | --- |
| `administrador` | Tudo o que o gerente faz, e ainda cadastra gerentes e outros administradores |
| `gerente` | Garçom, pedidos, caixa, cozinha, estoque, relatórios, QR Codes e cadastro de caixa, garçom e cozinha |
| `caixa` | Ver contas, receber pagamentos e fechar mesas |
| `garcom` | Anotar pedidos, cancelar e marcar como entregue |
| `cozinha` | Ver pedidos em preparo e marcar como pronto |
| cliente | Não tem conta. Usa só a página da mesa (Racha-conta) |

O gerente não altera administradores nem outros gerentes, e ninguém altera o próprio acesso.

## Telas do sistema

| Tela | Quem usa | O que faz |
| --- | --- | --- |
| Login | Funcionários | Entrar e recuperar a senha |
| Garçom | Garçom, gerente e administrador | Mapa de mesas, cardápio por categoria e busca, comanda, aviso de estoque baixo |
| Pedidos | Garçom, cozinha, gerente e administrador | Quadro com Em preparo, Prontos e Entregues, e cancelamento com motivo |
| Cozinha (`/cozinha`) | Cozinha, gerente e administrador | Pedidos em preparo e prontos |
| Caixa (`/caixa`) | Caixa, gerente e administrador | Contas, pagamentos feitos pelo cliente, recebimento parcial e fechamento da mesa |
| Gerente | Gerente e administrador | Faturamento, ticket médio, vendas por forma de pagamento, estoque e reposição |
| Equipe (`/equipe`) | Gerente e administrador | Cadastrar funcionários, trocar perfil, bloquear e liberar acesso |
| QR Codes (`/qrcodes`) | Gerente e administrador | QR Code de cada mesa, pronto para imprimir |
| Racha-conta (`/mesa/<número>`) | Cliente | Ver a conta, dividir por item (inteiro, por 2, 3 ou 4) ou por valor livre, gorjeta de 10% e pagamento simulado |

Os QR Codes têm um código calculado com `hmac` a partir da chave secreta do sistema. Assim, ninguém consegue acessar a conta de uma mesa sem o QR Code dela.

## Funcionamento

### Criação do pedido

1. O funcionário seleciona a mesa e os produtos.
2. O servidor valida os dados e confere o estoque (itens repetidos são somados antes da conferência).
3. A mesa é ocupada, os itens entram no pedido e as quantidades saem do estoque.
4. O pedido fica **Em preparo**. Os preços usados são sempre os do cardápio do servidor.

Se a mesa já tem conta aberta, os novos itens entram no mesmo pedido.

### Status do pedido

| Status | Significado |
| --- | --- |
| Aguardando | Estado inicial do objeto Pedido |
| Em preparo | Enviado para a cozinha |
| Pronto | Preparo concluído (a cozinha marca) |
| Entregue | Entregue à mesa (o garçom marca) |
| Finalizado | Conta paga e fechada, com venda registrada |
| Cancelado | Cancelado, com devolução dos itens ao estoque |

A sequência é **Em preparo → Pronto → Entregue**. Administrador e gerente podem executar todas as etapas.

### Cancelamento

Só é possível cancelar um pedido que está **Em preparo**, informando um motivo de 5 a 200 caracteres. O sistema devolve os itens ao estoque, registra as entradas, muda o status e libera a mesa.

### Pagamento

Formas aceitas no caixa: Dinheiro, PIX, Débito e Crédito. O caixa pode receber pagamentos parciais e, ao receber o restante, registra a venda, soma ao total vendido, finaliza o pedido e libera a mesa. PIX e cartões são apenas registros da forma escolhida, sem integração bancária.

No Racha-conta, o servidor calcula o valor de cada parte. O navegador só informa quais itens e quantas divisões o cliente escolheu. A gorjeta de 10% é opcional, fica registrada no pagamento e não entra no saldo da conta.

### Estoque

Os produtos saem do estoque quando entram no pedido. A reposição soma unidades ao produto. Um produto está com **estoque baixo** quando a quantidade é menor ou igual ao mínimo (5 unidades). Ao iniciar, cada produto do cardápio começa com 15 unidades.

### Indicadores do gerente

Total vendido, quantidade de vendas, ticket médio (total vendido dividido pelo número de vendas), contas abertas, produtos com estoque baixo e total por forma de pagamento.

## Classes e arquivos

### Classes do restaurante

| Arquivo | Classe | Responsabilidade |
| --- | --- | --- |
| `carrinho.py` | `Carrinho` | Adicionar item, calcular total, escolher forma de pagamento e finalizar |
| `pedido.py` | `Pedido` (herda de `Carrinho`) | Número e mesa do pedido, remover item, alterar quantidade, atualizar status, registrar pagamentos parciais e dividir valores |
| `mesa.py` | `Mesa` | Ocupar, liberar, reservar e pedir a conta |
| `caixa.py` | `Caixa` | Abrir e fechar o caixa, registrar vendas e somar o total vendido |
| `estoque.py` | `Estoque` | Cadastrar produtos, registrar entradas e saídas, conferir disponibilidade, listar estoque baixo e guardar histórico |
| `categoria.py` | `Categoria` | Cardápio: entradas, pratos principais, bebidas e sobremesas |

### Arquivos de apoio

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Inicia o Flask, define as rotas, a tabela de permissões e o controle de sessão |
| `autenticacao.py` | Integração com o Firebase: login, recuperação de senha e conferência de sessões |
| `banco.py` | Conexão com o Neon e consultas da tabela `usuarios` |
| `banco_estado.py` e `estado.py` | Gravam e leem do banco as mesas, pedidos, vendas e estoque |
| `equipe.py` | Cadastro de funcionários |
| `usuario.py` | Validações de e-mail, nome, senha e perfil |
| `seguranca.py` | Código dos QR Codes, código de instalação e IP do cliente |
| `sms.py`, `banco_sms.py` e `rotas_sms.py` | Recuperação de senha por SMS |
| `cadastrar_usuario.py` | Cadastra funcionários pelo terminal |
| `verificar_configuracao.py` | Confere o `.env`, o Neon e o Firebase |
| `test_app.py` | Testes automatizados |
| `templates/` | Páginas HTML (login, sistema, caixa, cozinha, equipe, QR Codes e Racha-conta) |
| `public/static/` | CSS, JavaScript e imagens |

### Funções principais do `app.py`

| Função | Responsabilidade |
| --- | --- |
| `entrar()` | Confere as credenciais no Firebase, a permissão no Neon e cria a sessão |
| `verificar_acesso()` | Confere sessão, perfil e token de segurança a cada requisição |
| `sessao_valida()` | A cada 5 minutos, confere se a conta continua ativa |
| `criar_pedido()` | Valida os itens e cria ou atualiza o pedido |
| `mudar_status()` | Atualiza o andamento do pedido (Pronto e Entregue) |
| `cancelar_pedido()` | Cancela e devolve os itens ao estoque |
| `finalizar_pedido()` | Registra o que falta pagar, a venda e libera a mesa |
| `receber_pagamento()` | Registra um pagamento parcial feito no caixa |
| `pagar_da_mesa()` | Registra o pagamento do cliente no Racha-conta |
| `calcular_partes()` | Calcula quanto o cliente paga de cada item |
| `repor_estoque()` | Registra a entrada de produtos |
| `obter_dados()` | Entrega às telas só os dados que cada perfil pode ver |

## Programação orientada a objetos no projeto

- **Herança:** `Pedido` herda de `Carrinho` (`class Pedido(Carrinho)`) e reaproveita os métodos de itens, total e pagamento. O `super().__init__()` inicializa os atributos herdados.
- **Classes com responsabilidade única:** cada classe cuida de uma parte do restaurante (mesa, caixa, estoque, cardápio, pedido).
- **Validação nas regras:** quantidade inválida, estoque insuficiente, pagamento duplicado e cancelamento repetido são recusados pelo próprio código das classes e das rotas.

## Como executar

Requisitos: Python 3, um banco no **Neon** e um projeto no **Firebase** (Authentication com e-mail e senha ativado).

```bash
# 1. criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux ou macOS

# 2. instalar as dependências
python -m pip install -r requirements.txt
```

Crie um arquivo `.env` na pasta do projeto:

```env
CHAVE_SECRETA=uma-chave-longa-e-aleatoria
DATABASE_URL=postgresql://usuario:senha@host/banco?sslmode=require
FIREBASE_API_KEY=chave-de-api-da-web-do-firebase
FIREBASE_CREDENCIAIS=firebase-credenciais.json
CODIGO_INSTALACAO=um-codigo-so-seu
```

- `CHAVE_SECRETA`: gere com `python -c "import secrets; print(secrets.token_hex(32))"`.
- `FIREBASE_CREDENCIAIS`: arquivo JSON da conta de serviço (Firebase, Configurações do projeto, Contas de serviço).

```bash
# 3. conferir a configuração (todos os itens devem aparecer como [OK])
python verificar_configuracao.py

# 4. iniciar o sistema
python app.py
```

Abra `http://127.0.0.1:5000`. Em um sistema novo, o endereço leva para a tela `/instalacao`, onde se informa o `CODIGO_INSTALACAO`, o nome, o e-mail e a senha do primeiro **administrador**. Essa tela só funciona uma vez. Depois disso, o administrador e o gerente cadastram a equipe em **Equipe e acessos**.

Também é possível cadastrar usuários pelo terminal com `python cadastrar_usuario.py`.

## Testes

```bash
python -m unittest -v
```

São 122 testes que cobrem:

- login, bloqueio sem sessão, perfis e permissões;
- criação, status, cancelamento e pagamento de pedidos;
- estoque (itens repetidos, quantidades inválidas, devolução ao cancelar);
- Racha-conta (divisão de itens, valor livre, gorjeta, pagamentos inválidos);
- caixa (recebimento parcial e fechamento);
- cadastro de funcionários e recuperação de senha;
- `Carrinho` e a herança de `Pedido`.

Os testes usam Neon e Firebase simulados, então não precisam de internet nem do arquivo `.env`.

## Limitações

- Pix, Google Pay, Apple Pay e a avaliação do Google são **simulações**. Não há cobrança real.
- O cardápio é alterado diretamente no arquivo `categoria.py`, sem tela de cadastro.
- O estado do restaurante é guardado como um único texto JSON no banco. Se duas pessoas gravarem ao mesmo tempo, a segunda recebe um aviso e repete a ação.
- Não existe cancelamento parcial de itens.
- A reserva de mesas existe na classe `Mesa`, mas não tem tela.
- Os limites de tentativas de login ficam em memória do servidor.
