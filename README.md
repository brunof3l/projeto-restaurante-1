# Sistema de Restaurante — Restaurante BKV

Projeto acadêmico desenvolvido em Python para organizar o atendimento de um restaurante, permitindo controlar mesas, pedidos, pagamentos, estoque e usuários.

O sistema utiliza Flask para conectar as classes Python à interface feita em HTML, CSS e JavaScript.

Esta versão mantém a estrutura do projeto original e acrescenta login com **Firebase Authentication**, usuários em um banco **Neon (PostgreSQL)**, recuperação de senha por e-mail enviado pelo Firebase **ou por código no SMS**, validações e melhorias nos pedidos. A interface também foi redesenhada (novo visual, tela de acompanhamento de pedidos e atualização automática), sem alterar o código Python.

Nesta versão também foram acrescentados **perfis de acesso** (gerente, caixa, garçom e cozinha), uma **tela própria para o caixa**, uma **tela da cozinha** e o **Racha-conta**: o cliente escaneia o QR Code da mesa, paga a sua parte (Pix, Google Pay ou Apple Pay simulados) e avalia o restaurante em uma página que simula o Google.

## Alunos responsáveis

- Bruno Ferreira
- Kennedy Fernando
- Vinicius dos Anjos

## Sumário

- [Objetivo](#objetivo)
- [Tecnologias utilizadas](#tecnologias-utilizadas)
- [Funcionalidades](#funcionalidades)
- [Perfis de acesso](#perfis-de-acesso)
- [Racha-conta (tela do cliente)](#racha-conta-tela-do-cliente)
- [Tela do caixa](#tela-do-caixa)
- [Tela da cozinha](#tela-da-cozinha)
- [Interface do front-end](#interface-do-front-end)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Publicar na Vercel](#publicar-na-vercel)
- [Primeiro acesso e equipe](#primeiro-acesso-e-equipe)
- [QR Codes das mesas](#qr-codes-das-mesas)
- [Segurança do sistema](#segurança-do-sistema)
- [Instalação e execução](#instalação-e-execução)
- [Cadastro de usuários](#cadastro-de-usuários)
- [Configuração do Neon e do Firebase](#configuração-do-neon-e-do-firebase)
- [Recuperação de senha](#recuperação-de-senha)
- [Recuperação de senha por SMS](#recuperação-de-senha-por-sms)
- [Funcionamento do sistema](#funcionamento-do-sistema)
- [Classes e arquivos Python](#classes-e-arquivos-python)
- [Modificações implementadas](#modificações-implementadas)
- [Rotas da aplicação](#rotas-da-aplicação)
- [Armazenamento dos dados](#armazenamento-dos-dados)
- [Testes](#testes)
- [Problemas comuns](#problemas-comuns)
- [Limitações atuais](#limitações-atuais)
- [Documentação complementar](#documentação-complementar)

## Objetivo

Facilitar o atendimento dentro do restaurante e centralizar as informações utilizadas pelos funcionários.

O fluxo principal permite:

1. Entrar no sistema com e-mail e senha.
2. Selecionar uma mesa.
3. Adicionar produtos ao pedido.
4. Conferir a disponibilidade no estoque.
5. Enviar os itens para preparo.
6. Atualizar o andamento do pedido.
7. Registrar o pagamento.
8. Liberar a mesa e acompanhar as vendas.

A aplicação possui as seguintes áreas:

- Garçom.
- Pedidos.
- Caixa (tela própria em `/caixa`, além da aba do gerente).
- Cozinha (tela própria em `/cozinha`).
- Gerente.
- Cliente (Racha-conta, em `/mesa/<número>`, sem login).

Cada funcionário entra com um **perfil** (gerente, caixa, garçom ou cozinha), que define quais telas e operações ele pode usar. Veja [Perfis de acesso](#perfis-de-acesso).

## Tecnologias utilizadas

| Tecnologia | Utilização |
| --- | --- |
| Python | Classes, validações e regras do sistema |
| Flask | Rotas e comunicação entre navegador e backend |
| HTML | Estrutura das páginas, com modelos Jinja do Flask |
| CSS | Aparência, grades e adaptação a tablet e celular |
| JavaScript | Desenho das telas, interação dos botões, atualização automática e envio de requisições |
| Google Fonts | Fontes Bricolage Grotesque e IBM Plex Mono, carregadas pela internet (há fontes alternativas sem conexão) |
| Neon (PostgreSQL) | Banco de dados com os funcionários autorizados a usar o sistema |
| psycopg | Conexão do Python com o Neon |
| Firebase Authentication | Guarda as senhas, confere o login e envia o e-mail de recuperação |
| SMS (Twilio, Zenvia ou Vonage) | Envio do código de recuperação por SMS, via `requests` |
| firebase-admin | Validação dos tokens e gerenciamento das contas do Firebase |
| requests | Chamadas à API REST do Firebase (login e recuperação) |
| python-dotenv | Leitura das configurações do arquivo `.env` |
| unittest | Testes automatizados |

Bibliotecas como `json`, `secrets`, `time` e `threading` fazem parte da biblioteca padrão do Python.

## Funcionalidades

### Acesso ao sistema

- Cadastro de funcionários pelo terminal (conta no Firebase e registro no Neon).
- Login com e-mail e senha, conferidos pelo Firebase.
- Permissão de uso controlada pela tabela `usuarios` do Neon (conta ativa ou bloqueada).
- Encerramento da sessão.
- Bloqueio de acesso aos dados sem autenticação.
- Recuperação de senha por link enviado por e-mail pelo Firebase.
- Recuperação de senha por código de 4 números enviado ao celular registrado na conta (opcional).
- Invalidação das sessões anteriores após a troca de senha, conta bloqueada ou removida.

### Perfis e telas novas

- Perfil de cada funcionário guardado na coluna `perfil` da tabela `usuarios` do Neon.
- Bloqueio no back-end das rotas que o perfil não pode usar (resposta 403).
- Redirecionamento após o login: caixa vai para `/caixa` e cozinha vai para `/cozinha`.
- Tela do caixa com mesas, contas, pagamentos já feitos pelo cliente e fechamento da mesa.
- Tela da cozinha com os pedidos em preparo e prontos.
- Racha-conta para o cliente pagar a própria parte pelo celular.

### Atendimento do garçom

- Visualização das mesas.
- Consulta ao cardápio por categoria e por busca.
- Aviso de estoque baixo ("Restam N") e de produto esgotado no cardápio.
- Seleção da mesa, com o total da conta aparecendo nas mesas ocupadas.
- Inclusão de produtos na comanda, limitada ao estoque disponível.
- Ajuste das quantidades antes do envio.
- Visualização do total.
- Visualização dos itens que a mesa já pediu.
- Envio dos itens para preparo.
- Inclusão de novos itens em uma conta aberta.

### Acompanhamento dos pedidos

- Quadro com três colunas: Em preparo, Prontos para entregar e Entregues.
- Atualização para Pronto e Entregue.
- Cancelamento de pedidos em preparo, com motivo informado em um diálogo.
- Contador de pedidos em andamento na aba.

### Caixa

- Consulta às contas abertas.
- Visualização dos produtos e valores.
- Visualização do status de cada pedido.
- Escolha da forma de pagamento por botões.
- Finalização da conta.
- Liberação da mesa.
- Consulta ao total vendido e à quantidade de vendas.

### Gerenciamento e estoque

- Consulta ao faturamento.
- Acompanhamento do ticket médio.
- Consulta às vendas registradas.
- Visualização das quantidades em estoque.
- Identificação dos produtos com estoque baixo.
- Filtro dos produtos que precisam de reposição.
- Registro de entrada de produtos, com atalhos de +5, +10 e +20.
- Barras de quantidade e alerta de estoque baixo na aba.
- Total vendido por forma de pagamento.
- Histórico de movimentações mantido pela classe Estoque (sem tela na interface).

## Perfis de acesso

Os perfis ficam na coluna `perfil` da tabela `usuarios` do **Neon**. O Firebase continua cuidando só do e-mail e da senha. O Neon já era o lugar que diz quem pode usar o sistema, então o perfil foi guardado ali, sem código extra no Firebase (o Firebase também permite guardar perfis nas contas, os chamados *custom claims*, mas isso exigiria mais código e uma segunda fonte de permissões).

| Perfil | O que pode fazer |
| --- | --- |
| `administrador` | Tudo o que o gerente faz, e ainda cadastra gerentes e outros administradores |
| `gerente` | Tudo: garçom, pedidos, caixa, estoque, relatórios, telas da cozinha e do caixa, QR Codes e cadastro de caixa, garçom e cozinha |
| `caixa` | Tela do caixa: ver contas, receber pagamentos e fechar mesas |
| `garcom` | Abas Garçom e Pedidos: anotar pedidos, cancelar e marcar como entregue |
| `cozinha` | Tela da cozinha: ver pedidos e marcar como pronto |
| cliente | Não tem conta: usa só a página `/mesa/<número>` (Racha-conta) |

A tabela `PERMISSOES` do `app.py` liga cada rota aos perfis permitidos. A função `verificar_acesso()` consulta essa tabela a cada requisição. O perfil é guardado na sessão no login e conferido de novo a cada 5 minutos, junto com a conferência da conta.

Quem cadastra quem: o administrador cadastra qualquer perfil, e o gerente cadastra apenas caixa, garçom e cozinha. Ninguém altera o próprio acesso. O gerente não mexe em administradores nem em outros gerentes.

Usuários criados antes desta versão recebem o perfil `gerente` automaticamente, para não perderem acesso.

Para mudar o perfil de alguém, no SQL Editor do Neon:

```sql
UPDATE usuarios SET perfil = 'caixa' WHERE email = 'funcionario@exemplo.com';
```

A mudança vale em até 5 minutos para quem já está logado.

## Racha-conta (tela do cliente)

Cada mesa tem um QR Code que aponta para `/mesa/<número>` (por exemplo, `http://127.0.0.1:5000/mesa/3`). O gerente encontra os links de todas as mesas na aba **Gerente**, em **Telas por perfil**. Para gerar o QR Code, use qualquer gerador que transforme o link em imagem.

A página não exige login, pois o cliente não é funcionário. Ela só mostra a conta da mesa se existir um pedido aberto.

O cliente pode:

- Ver os itens, o que já foi pago e o que falta.
- Escolher **Tudo**, **Dividir por 2**, **Por 3** ou **Por 4** em cada item (por exemplo, dividir uma Coca-Cola ao meio).
- Usar **Valor livre** para pagar um valor qualquer.
- Pagar a **conta toda** ou o **restante** com um botão sempre visível.
- Incluir gorjeta de 10% (opcional). A gorjeta fica registrada no pagamento e não entra no saldo da conta.
- Pagar com **Pix** (QR Code simulado), **Google Pay** ou **Apple Pay** (cartão fictício). Nenhuma cobrança real é feita.
- Avaliar o restaurante em uma página que **simula o Google** (estrelas e comentário). A avaliação não é salva em nenhum lugar.

O servidor calcula os valores. O navegador envia só quais itens e quantas divisões o cliente escolheu, e o back-end calcula quanto cada parte vale.

Depois que a conta fica totalmente paga, a mesa continua aberta até o caixa fechá-la.

## Tela do caixa

Abre em `/caixa` para os perfis `caixa` e `gerente`. Mostra:

- Faturamento do dia, quantidade de contas abertas e quanto ainda falta receber.
- Mapa das mesas. Tocar em uma mesa ocupada leva até a conta dela.
- Em cada conta: itens (marcando os que já foram pagos), total, já pago, falta pagar e a lista de pagamentos com horário, quem pagou, forma e gorjeta.
- **Receber este valor**: registra um pagamento parcial em dinheiro, Pix, débito ou crédito sem fechar a mesa.
- **Receber o restante e fechar mesa**: registra o que falta, registra a venda e libera a mesa.
- **Fechar mesa**: aparece quando o cliente já pagou tudo pelo celular.
- Link para abrir a tela do cliente daquela mesa.
- Vendas finalizadas do dia.

A tela atualiza sozinha a cada 10 segundos, sem apagar o que está sendo digitado.

## Tela da cozinha

Abre em `/cozinha` para os perfis `cozinha` e `gerente`. Mostra duas colunas: **Em preparo** e **Prontos para o garçom**. O botão **Marcar como pronto** atualiza o status, e o garçom marca como entregue depois. A tela atualiza a cada 8 segundos.

## Interface do front-end

A aparência moderna fica em uma camada separada, que carrega depois dos estilos originais e só acrescenta: `static/moderno.css` e `static/efeitos.js` (sistema) e `static/moderno-login.css` e `static/efeitos-login.js` (login). Para voltar ao visual anterior, remova essas linhas de `templates/index.html` e `templates/login.html`. Os efeitos respeitam a preferência do sistema por menos movimento.

- Azulejo da marca aceso em dourado perto do cursor, na página de acesso.
- Faixa de azulejo dourado na barra superior.
- Ícone e cor de categoria em cada prato.
- Efeito de "+1" ao adicionar um prato e comanda que "imprime" cada item novo.
- Números dos indicadores que contam até o valor.
- Mesa aguardando pagamento com marcador pulsando.

O front-end usa HTML, CSS e JavaScript puros, sem bibliotecas ou frameworks, e consome as mesmas rotas do back-end.

- Barra superior com as abas Garçom, Pedidos, Caixa e Gerente. No celular, as abas ficam na parte inferior. Cada perfil vê só as abas que pode usar (garçom: Garçom e Pedidos).
- Comanda com aparência de nota de papel na tela do garçom.
- Atualização automática dos dados a cada 15 segundos, sem redesenhar a tela quando nada mudou.
- Faixa de aviso quando a conexão com o servidor falha.
- Nome e iniciais do usuário vindos do cadastro no Neon (guardados na sessão).
- Textos inseridos na página como texto puro, sem `innerHTML`, para evitar injeção de código.
- Foco visível, rótulos para leitores de tela e respeito à preferência de reduzir animações.

## Estrutura do projeto

| Arquivo ou pasta | Responsabilidade |
| --- | --- |
| `app.py` | Inicia a aplicação, configura o acesso e define as rotas |
| `usuario.py` | Validações de e-mail, nome e senha |
| `banco.py` | Conexão com o Neon e consultas da tabela `usuarios` |
| `autenticacao.py` | Integração com o Firebase: login, e-mail de recuperação e conferência de sessões |
| `schema.sql` | Comando SQL que cria a tabela `usuarios` (o sistema também a cria sozinho) |
| `verificar_configuracao.py` | Confere o `.env`, o Neon e o Firebase |
| `GUIA_CONFIGURACAO.md` | Passo a passo para conectar o Neon e o Firebase |
| `GUIA_SMS.md` | Passo a passo para ativar a recuperação por SMS |
| `sms.py` | Envio do código pelos provedores `twilio`, `zenvia` e `vonage` e normalização de telefones |
| `banco_sms.py` | Telefone e códigos de recuperação por SMS no Neon |
| `rotas_sms.py` | Rotas `/api/sms/*` (Blueprint do Flask) |
| `definir_telefone.py` | Registra o celular de um funcionário já cadastrado |
| `static/sms.js` | Telas e envio do fluxo por SMS na página de acesso |
| `static/moderno.css`, `static/efeitos.js` | Camada visual moderna do sistema |
| `static/moderno-login.css`, `static/efeitos-login.js` | Camada visual moderna da página de acesso |
| `cadastrar_usuario.py` | Cadastra funcionários pelo terminal no Firebase e no Neon |
| `carrinho.py` | Implementa os comportamentos compartilhados de itens e pagamento |
| `pedido.py` | Representa a conta de uma mesa e herda de Carrinho |
| `caixa.py` | Controla o caixa e o registro de vendas |
| `mesa.py` | Representa as mesas e seus estados |
| `estoque.py` | Controla produtos, quantidades e movimentações |
| `categoria.py` | Define as categorias e os produtos do cardápio |
| `test_app.py` | Contém os testes automatizados |
| `requirements.txt` | Lista as dependências externas |
| `.env.example` | Modelo das configurações necessárias |
| `.gitignore` | Define arquivos que não devem ser enviados ao Git |
| `templates/index.html` | Estrutura da interface principal: barra superior, quatro telas, diálogo de cancelamento e avisos |
| `templates/caixa.html` | Tela própria do caixa |
| `templates/cozinha.html` | Tela da cozinha |
| `templates/racha.html` | Tela do cliente (Racha-conta) |
| `templates/login.html` | Formulários de login e recuperação de senha |
| `static/comum.js` | Funções usadas por todas as telas: criar elementos, falar com o servidor, avisos, nome do usuário e saída |
| `static/script.js` | Interface principal (garçom, pedidos, caixa e gerente) |
| `static/caixa.js` | Lógica da tela do caixa |
| `static/cozinha.js` | Lógica da tela da cozinha |
| `static/racha.js` | Lógica do Racha-conta, do pagamento simulado e da avaliação simulada do Google |
| `static/racha.css` | Aparência do Racha-conta e da página de avaliação |
| `static/style.css` | Aparência da interface principal, incluindo a versão para celular |
| `static/login.js` | Validações e comunicação dos formulários de acesso com o backend |
| `static/login.css` | Aparência da página de acesso |
| `firebase-credenciais.json` | Chave da conta de serviço do Firebase. Você baixa no console e ela não vai para o Git |
| `DOCUMENTACAO.pdf` | Documentação preservada da versão original |

Os arquivos `.env` e `firebase-credenciais.json` são criados pelo responsável pela configuração e não acompanham o projeto. Nunca os envie ao repositório.

## Publicar na Vercel

O sistema foi preparado para rodar na Vercel, sem precisar rodar no computador. O passo a passo completo está no arquivo `GUIA_VERCEL.md`. Em resumo:

1. Coloque o projeto em um repositório do GitHub (sem o `.env` e sem o JSON do Firebase).
2. Na Vercel, clique em **Add New > Project** e importe o repositório.
3. Em **Environment Variables**, cadastre as variáveis do `.env.example`: `CHAVE_SECRETA`, `CODIGO_INSTALACAO`, `URL_PUBLICA`, `DATABASE_URL`, `FIREBASE_API_KEY` e `FIREBASE_CREDENCIAIS_JSON`.
4. Clique em **Deploy** e abra o endereço que a Vercel mostrar.

Arquivos usados na publicação:

| Arquivo | Para que serve |
| --- | --- |
| `vercel.json` | Manda todas as páginas para a função Python e inclui a pasta `templates` |
| `api/index.py` | Ponto de entrada da Vercel: importa o `app` do `app.py` |
| `public/static/` | CSS, JavaScript e imagens, servidos direto pela Vercel |
| `requirements.txt` | Bibliotecas instaladas na publicação |
| `.vercelignore` | Arquivos que não vão para a Vercel (testes, PDFs, `.env`) |

## Primeiro acesso e equipe

Em um sistema novo, ainda não existe nenhum usuário. Ao abrir o endereço, o sistema leva para `/instalacao`:

1. Informe o **código de instalação** (a variável `CODIGO_INSTALACAO`, que só quem publicou o sistema conhece), o nome, o e-mail e a senha.
2. O sistema cria a conta no Firebase e o registro no Neon com o perfil `administrador`.
3. A tela de instalação se fecha para sempre: depois do primeiro usuário, `/instalacao` volta para o login e a rota recusa novos pedidos.

Depois, o administrador e o gerente abrem **Equipe e acessos** (`/equipe`) para:

- Cadastrar funcionários (nome, e-mail, celular opcional, perfil e senha inicial).
- Trocar o perfil de um funcionário.
- Bloquear e liberar o acesso (o bloqueio vale em até 5 minutos para quem já está logado).

O código está em `equipe.py` (função `criar_funcionario`), nas rotas `/api/equipe` do `app.py` e em `usuario.py` (funções `perfis_que_pode_cadastrar` e `pode_gerenciar`).

## QR Codes das mesas

Em **QR Codes das mesas** (`/qrcodes`, para administrador e gerente) o sistema gera um QR Code para cada mesa, pronto para imprimir. Cada QR Code leva para `/mesa/<número>?c=<código>`.

O código `c` é calculado pela função `codigo_da_mesa()` do `seguranca.py`: ela mistura o número da mesa com a `CHAVE_SECRETA` usando a função `hmac` do Python. Por isso:

- Cada mesa tem um código diferente, e ninguém consegue inventar o código de uma mesa sem a chave secreta.
- Sem o código certo, o cliente não vê a conta, não paga e não descobre se a mesa existe.
- Erros de código são limitados por IP (20 a cada 5 minutos).

Defina `URL_PUBLICA` com o endereço da Vercel para os QR Codes não mudarem se o sistema for aberto por outro endereço. Mude a `CHAVE_SECRETA` apenas se quiser invalidar todos os QR Codes impressos.

## Segurança do sistema

- **Cliente isolado:** quem escaneia o QR Code só acessa `/mesa/<número>` e as duas rotas dessa mesa. Todas as outras páginas e rotas exigem login.
- **Perfis no servidor:** a tabela `PERMISSOES` do `app.py` decide quem usa cada rota. Esconder botões na tela é só visual.
- **Dados por perfil:** a cozinha não recebe valores nem vendas, o caixa não recebe estoque e o garçom não recebe vendas (função `obter_dados`).
- **Instalação protegida:** a criação do primeiro administrador exige o código de instalação e só funciona uma vez.
- **Cadastro com hierarquia:** o gerente não cadastra nem altera administradores e gerentes, e ninguém altera o próprio acesso.
- **Cabeçalhos de segurança** em todas as respostas: política de conteúdo (só carrega scripts do próprio sistema), bloqueio de uso em quadros (`X-Frame-Options`), sem cache nas respostas e HTTPS obrigatório na Vercel.
- **Cookie de sessão** com `HttpOnly`, `SameSite` e `Secure` (na Vercel).
- **Limites de tentativas** por IP no login, na recuperação de senha, na instalação, nos códigos de mesa e nos pagamentos.
- **Proteção contra CSRF** em todos os envios de funcionários logados.
- **Erros tratados:** falha do Neon ou do Firebase devolve uma mensagem simples, sem mostrar detalhes técnicos.

## Instalação e execução

### 1. Abrir a pasta

Extraia o projeto e abra sua pasta no VS Code.

Abra o terminal na pasta em que estão `app.py` e `requirements.txt`.

### 2. Criar o ambiente virtual

```bash
python -m venv .venv
```

O ambiente virtual separa as dependências deste projeto das demais instalações do computador.

### 3. Ativar o ambiente

No Prompt de Comando do Windows:

```bat
.venv\Scripts\activate
```

No PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
source .venv/bin/activate
```

Se não conseguir ativar no Windows, utilize o executável do ambiente diretamente:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nos demais comandos, também é possível substituir `python` por `.venv\Scripts\python.exe`.

### 4. Instalar as dependências

```bash
python -m pip install -r requirements.txt
```

### 5. Configurar o Neon e o Firebase

Crie o banco no Neon e o projeto no Firebase seguindo o **[GUIA_CONFIGURACAO.md](GUIA_CONFIGURACAO.md)**.

Depois copie `.env.example`, renomeie a cópia para `.env` e preencha as configurações:

```env
CHAVE_SECRETA=coloque-a-chave-gerada-aqui
DATABASE_URL=postgresql://usuario:senha@ep-xxxx-pooler.regiao.aws.neon.tech/neondb?sslmode=require
FIREBASE_API_KEY=coloque-a-chave-de-api-da-web-aqui
FIREBASE_CREDENCIAIS=firebase-credenciais.json
```

Para gerar a chave da sessão:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copie o resultado para `CHAVE_SECRETA`.

A chave deve permanecer igual entre as execuções para que a assinatura das sessões seja mantida.

### 6. Verificar a configuração

```bash
python verificar_configuracao.py
```

O script confere as variáveis, a conexão com o Neon e as credenciais do Firebase. Todos os itens devem aparecer como `[OK]`.

### 7. Cadastrar o primeiro usuário

```bash
python cadastrar_usuario.py
```

Preencha os dados solicitados.

### 8. Iniciar o sistema

```bash
python app.py
```

### 9. Abrir no navegador

Acesse:

http://127.0.0.1:5000

Entre com o e-mail e a senha cadastrados.

Para encerrar o servidor, pressione `Ctrl + C` no terminal.

## Cadastro de usuários

O projeto não possui usuário ou senha padrão.

O cadastro é feito com:

```bash
python cadastrar_usuario.py
```

O programa solicita:

1. Nome.
2. E-mail.
3. Perfil (`gerente`, `caixa`, `garcom` ou `cozinha`).
4. Senha.
5. Confirmação da senha.

### Regras do cadastro

- Nome entre 2 e 100 caracteres.
- E-mail com formato básico válido.
- Perfil igual a um dos quatro permitidos.
- E-mail ainda não cadastrado.
- Senha entre 8 e 128 caracteres.
- Senha com pelo menos uma letra e um número.
- Confirmação igual à senha.

O e-mail é salvo em letras minúsculas.

A senha não aparece no terminal durante a digitação porque o cadastro utiliza `getpass`.

### O que o cadastro faz

1. Cria a conta no Firebase Authentication, que passa a guardar a senha.
2. Registra o funcionário na tabela `usuarios` do Neon, com o identificador (`firebase_uid`) da conta e o perfil escolhido.

Se o registro no Neon falhar, a conta recém-criada no Firebase é removida, para não ficar uma conta sem permissão.

Se o e-mail já existir no Firebase (por exemplo, criado pelo console), o programa oferece liberar o acesso dele ao sistema sem alterar a senha.

O cadastro pode ser feito com o servidor ligado, porque os usuários ficam no banco.

Os usuários do antigo `dados/usuarios.json` não são migrados, pois o Firebase não reaproveita aqueles hashes. Cadastre cada pessoa novamente.

### Bloquear um funcionário

No SQL Editor do Neon:

```sql
UPDATE usuarios SET ativo = FALSE WHERE email = 'funcionario@exemplo.com';
```

A sessão aberta dessa pessoa deixa de valer em até 5 minutos.

## Configuração do Neon e do Firebase

O passo a passo completo, com os caminhos de cada tela, está em **[GUIA_CONFIGURACAO.md](GUIA_CONFIGURACAO.md)**.

| Configuração | Onde obter | Significado |
| --- | --- | --- |
| `CHAVE_SECRETA` | Gerada com `secrets.token_hex(32)` | Chave de assinatura das sessões do Flask |
| `DATABASE_URL` | Neon: botão **Connect** | Endereço de conexão com o banco |
| `FIREBASE_API_KEY` | Firebase: Configurações do projeto > Geral | Chave de API da Web, usada no login e no pedido de recuperação |
| `FIREBASE_CREDENCIAIS` | Firebase: Configurações do projeto > Contas de serviço | Caminho do arquivo JSON da conta de serviço |
| `FIREBASE_CREDENCIAIS_JSON` | O mesmo arquivo JSON | Alternativa para hospedagens sem arquivos: o conteúdo em uma linha |

O envio de e-mails é feito pelo próprio Firebase, sem servidor SMTP. O modelo da mensagem (idioma, remetente e assunto) é ajustado em **Authentication > Modelos**.

Os arquivos `.env` e `firebase-credenciais.json` não devem ser publicados no repositório.

Para conferir tudo de uma vez:

```bash
python verificar_configuracao.py
```

## Recuperação de senha

### Como utilizar

1. Abra a página de login.
2. Clique em **Esqueci minha senha**.
3. Informe o e-mail cadastrado.
4. Clique em **Enviar link**. O botão fica bloqueado por 60 segundos, o mesmo intervalo exigido pelo servidor.
5. Consulte sua caixa de entrada e a pasta de spam.
6. Clique no link do e-mail. Abre uma página do Firebase.
7. Digite a nova senha e salve.
8. Volte à tela de login e entre com a nova senha.

### Regras da recuperação

- Só recebe o e-mail quem está cadastrado e ativo na tabela `usuarios` do Neon.
- Intervalo mínimo de um minuto entre solicitações para a mesma conta, controlado no Neon.
- Até 5 solicitações a cada 10 minutos por endereço de IP.
- O link é gerado, enviado e validado pelo Firebase, tem validade limitada e só pode ser usado uma vez.
- A regra de tamanho da nova senha é a política de senha configurada no Firebase.
- Depois da troca, as sessões abertas antes dela deixam de valer em até 5 minutos.

A resposta da solicitação é genérica para não informar se um e-mail está cadastrado. Por isso, a mensagem exibida na tela não confirma a entrega do e-mail.

Se o envio falhar, o servidor registra o motivo no terminal. O intervalo de um minuto continua sendo aplicado.

### Integração entre os arquivos

1. `static/login.js` envia o e-mail ao backend.
2. `app.py` valida o e-mail e aplica os limites.
3. `banco.py` confere se o funcionário está ativo e se já passou o intervalo de um minuto.
4. `autenticacao.py` pede ao Firebase o envio do e-mail de recuperação.
5. O funcionário define a nova senha na página do Firebase.
6. O Firebase invalida os tokens antigos, e a sessão antiga cai na próxima conferência periódica de `app.py`.

## Recuperação de senha por SMS

O passo a passo de configuração está em **[GUIA_SMS.md](GUIA_SMS.md)**. Aqui, o resumo do funcionamento.

### Como utilizar

1. Abra a página de login e clique em **Esqueci minha senha**.
2. Clique em **Receber código por SMS** (o botão só aparece com um provedor configurado).
3. Informe o e-mail cadastrado e clique em **Enviar código**.
4. Clique em **Já recebi o código**, digite o código, a nova senha e a confirmação.
5. Clique em **Alterar senha** e entre com a nova senha.

### Regras

- O código é enviado por SMS ao **celular registrado na conta**. Quem pede não digita o número.
- Só funcionário ativo e com celular registrado recebe o código.
- Código de 4 números (para ser fácil de digitar), validade de 10 minutos e uso único.
- Até cinco tentativas por código. Um novo pedido aceito invalida o anterior.
- Intervalo mínimo de um minuto entre pedidos da mesma conta, controlado no Neon.
- Até 5 pedidos e 20 confirmações a cada 10 minutos por endereço de IP.
- O código é guardado como hash. O texto original só aparece na mensagem enviada.
- A resposta do pedido é sempre a mesma, exista ou não o e-mail, para não revelar quem está cadastrado.
- A nova senha segue a regra do sistema (8 a 128 caracteres, com letras e números) e é gravada no Firebase, que derruba as sessões abertas antes da troca.

### Provedores

| Valor de `SMS_PROVEDOR` | Serviço |
| --- | --- |
| `twilio` | Twilio |
| `zenvia` | Zenvia (empresa brasileira) |
| `vonage` | Vonage |

Cada provedor usa as próprias variáveis, listadas no `.env.example`.

### Registrar o celular dos funcionários

- Funcionário novo: `python cadastrar_usuario.py` pergunta o número (Enter pula).
- Funcionário existente: `python definir_telefone.py`.

### Integração entre os arquivos

1. `static/sms.js` consulta `/api/sms/status` para mostrar ou esconder o botão e envia o e-mail ao backend.
2. `rotas_sms.py` valida os dados e aplica os limites.
3. `banco_sms.py` libera o envio só para conta ativa, com telefone e fora do intervalo de um minuto.
4. `sms.py` envia a mensagem pelo provedor escolhido.
5. Na confirmação, `banco_sms.py` conta a tentativa e confere o código, e `autenticacao.py` define a nova senha no Firebase.

## Funcionamento do sistema

### Inicialização

Ao iniciar o programa, o sistema:

- Cria oito mesas, numeradas de 1 a 8.
- Inicia a lista de pedidos.
- Cria o caixa e o estoque.
- Abre o caixa.
- Cadastra cada produto do cardápio com 15 unidades.
- Define o estoque mínimo de cada produto como 5 unidades.

### Criação de um pedido

1. O funcionário seleciona uma mesa.
2. Escolhe os produtos.
3. Confere as quantidades.
4. Envia o pedido.
5. O backend valida os dados.
6. O estoque é conferido.
7. A mesa é ocupada, caso seja uma nova conta.
8. Os itens são adicionados ao pedido.
9. As quantidades são retiradas do estoque.
10. O pedido passa para **Em preparo**.

Os preços utilizados vêm do cardápio do servidor.

Se a mesa já possui uma conta aberta, os novos itens são adicionados ao mesmo pedido. A inclusão de novos itens retorna o status da conta para **Em preparo**.

### Status dos pedidos

| Status | Significado |
| --- | --- |
| Aguardando | Estado inicial do objeto Pedido |
| Em preparo | Pedido enviado para preparação |
| Pronto | Preparação concluída |
| Entregue | Pedido entregue à mesa |
| Finalizado | Conta encerrada com registro de venda |
| Cancelado | Pedido cancelado com devolução ao estoque |

A atualização manual segue:

**Em preparo → Pronto → Entregue**

Os botões ficam nos cartões da tela **Pedidos**. Só a cozinha (ou o gerente) marca como Pronto, e só o garçom (ou o gerente) marca como Entregue.

Atualizar para Entregue não registra pagamento nem libera a mesa. Essas ações acontecem no fechamento da conta.

O status representa o pedido inteiro, não o andamento individual de cada item.

### Cancelamento

Um pedido pode ser cancelado enquanto estiver **Em preparo**.

Na tela **Pedidos**, o funcionário clica em **Cancelar pedido** e informa um motivo entre 5 e 200 caracteres em um diálogo. O botão de confirmação só é habilitado com um motivo válido.

O sistema:

1. Localiza o pedido.
2. Verifica seu estado.
3. Valida o motivo.
4. Devolve as quantidades ao estoque.
5. Registra as movimentações de entrada.
6. Altera o status para Cancelado.
7. Libera a mesa.

Não é permitido repetir o cancelamento nem cancelar uma conta finalizada.

O cancelamento representa a devolução integral dos produtos. Deve ser utilizado quando os itens puderem retornar ao estoque.

### Pagamento

As formas aceitas são:

- Dinheiro.
- PIX.
- Débito.
- Crédito.

Ao finalizar a conta:

1. O sistema verifica se o pedido está aberto.
2. Confere a forma de pagamento.
3. Verifica se o caixa está aberto.
4. Registra a venda.
5. Soma o valor ao total vendido.
6. Altera o pedido para Finalizado.
7. Libera a mesa.

PIX e cartões são registros da forma de pagamento informada pelo operador. Não existe cobrança automática ou integração bancária.

### Estoque

Os produtos são retirados do estoque quando entram no pedido.

A reposição adiciona unidades ao produto selecionado.

Um produto é considerado com estoque baixo quando sua quantidade é menor ou igual ao estoque mínimo.

A classe Estoque também possui recursos para ingredientes e receitas. O cardápio atual utiliza produtos do tipo `produto_pronto`.

### Indicadores

O sistema apresenta:

- Total vendido.
- Quantidade de vendas.
- Ticket médio.
- Contas abertas.
- Produtos com estoque baixo.

O ticket médio é calculado dividindo o total vendido pela quantidade de vendas. Quando não há vendas, o valor apresentado é zero.

## Classes e arquivos Python

### app.py

Conecta a interface às classes e define as rotas.

| Função | Responsabilidade |
| --- | --- |
| `ler_dados()` | Lê um objeto JSON da requisição |
| `ler_quantidade()` | Valida e converte quantidades inteiras |
| `verificar_acesso()` | Confere sessão e token das operações protegidas |
| `ler_valor()` | Valida e arredonda um valor em reais |
| `login()` | Abre a página de acesso |
| `entrar()` | Confere as credenciais no Firebase, a permissão no Neon e cria a sessão |
| `sair()` | Encerra a sessão |
| `recuperar_senha()` | Aplica os limites e pede o e-mail de recuperação |
| `passou_do_limite()` | Controla o limite de tentativas por IP |
| `sessao_valida()` | Confere a sessão e, a cada 5 minutos, revalida a conta no Neon e no Firebase |
| `erro_de_login()` | Converte falhas do Firebase em mensagens da tela |
| `iniciar_sistema()` | Abre o caixa e prepara o estoque inicial |
| `buscar_pedido()` | Localiza um pedido pelo número |
| `buscar_produto()` | Localiza um produto pelo nome |
| `itens_da_conta()` | Monta a lista de itens com total, valor pago e valor que falta |
| `pedido_para_json()` | Converte os dados do pedido para a resposta da API, com pagamentos e saldo |
| `buscar_pedido_da_mesa()` | Localiza a conta aberta de uma mesa |
| `conta_para_json()` | Monta a resposta da conta mostrada ao cliente |
| `calcular_partes()` | Calcula quanto o cliente paga de cada item, conforme o modo escolhido |
| `pagina_inicial()` | Abre a interface principal ou redireciona caixa e cozinha para suas telas |
| `pagina_caixa()` e `pagina_cozinha()` | Abrem as telas do caixa e da cozinha |
| `pagina_mesa()` | Abre o Racha-conta da mesa |
| `conta_da_mesa()` | Entrega a conta da mesa ao cliente |
| `pagar_da_mesa()` | Registra o pagamento do cliente |
| `receber_pagamento()` | Registra um pagamento parcial feito no caixa |
| `obter_dados()` | Retorna os dados utilizados pelas telas |
| `criar_pedido()` | Valida os itens e cria ou atualiza uma conta |
| `finalizar_pedido()` | Registra o que falta pagar, a venda e libera a mesa |
| `repor_estoque()` | Registra a entrada de produtos |
| `mudar_status()` | Atualiza o andamento do pedido |
| `cancelar_pedido()` | Cancela e devolve os itens ao estoque |

### usuario.py

Contém as regras de formato dos dados.

| Função | Responsabilidade |
| --- | --- |
| `perfil_valido()` | Confere se o perfil é gerente, caixa, garcom ou cozinha |
| `senha_valida()` | Verifica tamanho, letras e números |
| `email_valido()` | Verifica o formato básico do endereço |
| `nome_valido()` | Verifica o tamanho do nome |

### banco.py

Conecta ao Neon com `psycopg` e mantém a tabela `usuarios`.

| Função | Responsabilidade |
| --- | --- |
| `conexao()` | Abre a conexão e cria a tabela na primeira vez |
| `buscar_usuario_por_uid()` | Procura o funcionário pelo identificador do Firebase |
| `buscar_usuario_por_email()` | Procura o funcionário pelo e-mail |
| `criar_usuario()` | Registra um funcionário, com o perfil (padrão: gerente) |
| `registrar_login()` | Guarda o horário do último login |
| `reservar_envio_recuperacao()` | Libera o e-mail de recuperação só para conta ativa e fora do intervalo de um minuto, em um único comando SQL |
| `testar_conexao()` | Usada pelo `verificar_configuracao.py` |

Falhas de conexão ou de consulta viram `BancoErro`.

### autenticacao.py

Integração com o Firebase.

| Função | Responsabilidade |
| --- | --- |
| `entrar()` | Confere e-mail e senha pela API REST e valida o token com o Admin SDK |
| `enviar_recuperacao()` | Pede ao Firebase o e-mail de redefinição, em português |
| `conta_ainda_valida()` | Confere se a conta continua ativa e se a senha não foi redefinida depois do login |
| `buscar_conta_por_email()`, `criar_conta()`, `remover_conta()` | Usadas pelo cadastro de funcionários |
| `testar_credenciais_admin()`, `testar_chave_api()` | Usadas pelo `verificar_configuracao.py` |

Falhas viram `ErroAutenticacao`, com um tipo (`credenciais`, `desativada`, `muitas_tentativas`, `configuracao` ou `indisponivel`).

### cadastrar_usuario.py

Executa o cadastro pelo terminal.

A função `cadastrar_usuario()` lê os dados, valida os campos, impede e-mail duplicado, cria a conta no Firebase e registra o funcionário no Neon. Se o Neon falhar, remove a conta criada no Firebase.

### verificar_configuracao.py

Confere o `.env`, a conexão com o Neon, a conta de serviço e a chave de API do Firebase. Não altera dados nem envia e-mails.

### carrinho.py

Implementa os métodos que antes estavam sem funcionamento.

| Método | Responsabilidade |
| --- | --- |
| `adicionar_item()` | Valida e adiciona um produto ou soma sua quantidade |
| `calcular_total()` | Soma preço multiplicado pela quantidade |
| `escolher_pagamento()` | Valida e armazena a forma escolhida |
| `finalizar_compra()` | Confere itens e pagamento e encerra o carrinho |

O total é arredondado para duas casas decimais.

O Carrinho é uma classe reutilizável. Não existe uma loja online integrada nesta versão.

### pedido.py

A classe `Pedido` herda de `Carrinho`:

```python
class Pedido(Carrinho):
```

Assim, utiliza os métodos compartilhados de itens, total e pagamento.

O Pedido acrescenta número e mesa, além de manter:

- Remoção de itens.
- Alteração de quantidades.
- Atualização de status.
- Exibição do pedido no terminal.

O uso de `super().__init__()` inicializa os atributos herdados.

Para o Racha-conta, o Pedido também guarda os pagamentos (`pagamentos`) e quanto já foi pago de cada item (`pago_por_item`). Os métodos novos são:

| Método | Responsabilidade |
| --- | --- |
| `total_do_item()` | Preço vezes quantidade de um item |
| `falta_do_item()` | Total do item menos o que já foi pago |
| `total_pago()` | Soma dos pagamentos |
| `calcular_falta()` | Total da conta menos o total pago |
| `valor_da_parte()` | Valor de uma parte de um item (inteiro ou dividido em 2, 3 ou 4) |
| `dividir_valor()` | Distribui um valor livre pelos itens que ainda faltam |
| `registrar_pagamento()` | Valida e guarda um pagamento, atualizando o que falta de cada item |
| `resumo_pagamento()` | Junta as formas usadas, por exemplo "PIX + Dinheiro" |

### caixa.py

Controla:

- Abertura do caixa.
- Registro de vendas.
- Total vendido.
- Lista de vendas.
- Fechamento do caixa.
- Exibição do saldo.

O registro recusa pedidos finalizados ou cancelados para impedir que a mesma conta seja contabilizada novamente.

### mesa.py

Representa cada mesa e mantém os métodos:

- `ocupar()`.
- `liberar()`.
- `reservar()`.
- `pedir_conta()`.

A classe possui o comportamento de reserva, mas não foi criada uma operação de reserva na interface ou na API desta versão.

### estoque.py

Controla ingredientes, produtos prontos e movimentações.

Seus principais métodos permitem:

- Cadastrar produtos e ingredientes.
- Registrar entradas.
- Registrar saídas.
- Conferir disponibilidade.
- Baixar produtos ou pedidos.
- Consultar estoque.
- Identificar estoque baixo.
- Consultar o histórico.

As operações e estruturas originais foram preservadas.

### categoria.py

Armazena o cardápio nas categorias:

- Entradas.
- Pratos principais.
- Bebidas.
- Sobremesas.

Cada produto possui nome, preço, categoria e tipo.

A alteração dos produtos e preços é feita diretamente nesse arquivo. Não existe uma tela de cadastro de cardápio.

## Modificações implementadas

| Parte | Situação anterior | Alteração |
| --- | --- | --- |
| Usuários | Classe com atributos básicos | Contas no Firebase Authentication e permissões na tabela `usuarios` do Neon |
| Perfis | Todos os usuários podiam tudo | Coluna `perfil`, tabela `PERMISSOES` e redirecionamento por perfil |
| Pagamento | Uma forma de pagamento para a conta inteira | Pagamentos parciais, divisão por item e fechamento pelo caixa |
| Caixa | Aba dentro da tela principal | Tela própria com pagamentos do cliente e recebimento do restante |
| Cozinha | Tela de pedidos compartilhada | Tela própria da cozinha |
| Cliente | Não existia | Racha-conta com Pix, Google Pay e Apple Pay simulados e avaliação simulada do Google |
| Funções do front-end | Repetidas no `script.js` | Reunidas em `comum.js` |
| Cadastro | Sem fluxo funcional de cadastro | Cadastro administrativo pelo terminal |
| Login | Telas sem autenticação | Login conferido pelo Firebase, com sessão e botão de saída |
| Recuperação | Não implementada | Link enviado pelo Firebase, sem servidor SMTP |
| Senhas | Sem rotina de proteção implementada | Guardadas e conferidas pelo Firebase |
| Carrinho | Métodos com reticências | Inclusão de itens, total, pagamento e fechamento |
| Pedido | Métodos de itens e pagamento próprios | Reaproveitamento por herança de Carrinho |
| Quantidades | Conversões com verificações limitadas | Validação de inteiros positivos |
| Itens repetidos | Conferência separada de cada linha | Soma antes de consultar o estoque |
| Status | Pedido enviado para preparo | Atualização para Pronto e Entregue |
| Cancelamento | Sem rota específica | Cancelamento com motivo e devolução ao estoque |
| Caixa | Registro do fluxo original | Verificações adicionais contra encerramento repetido |
| Interface | Três telas operacionais | Tela de acesso, tela de pedidos e novos botões |
| Documentação | Descrição da versão inicial | Guia de instalação e detalhamento das alterações |

### Correção dos itens repetidos

Considere um estoque com 15 unidades de Pudim.

Um pedido contém:

- 10 unidades em uma linha.
- 10 unidades em outra linha.

Verificar cada linha separadamente poderia considerar as duas quantidades possíveis.

Agora, o sistema agrupa os itens pelo nome:

```text
Pudim: 10 + 10 = 20 unidades
```

Como 20 é maior que 15, o pedido é recusado antes de baixar o estoque.

### Validação de quantidades

A função `ler_quantidade()` aceita inteiros ou textos que representem inteiros.

São recusados:

- Zero.
- Números negativos.
- Números fracionários.
- Valores booleanos.
- Listas e dicionários.
- Valores acima de 10000.

A validação também é utilizada na reposição.

### Sessão e proteção das operações

Após o login, a sessão guarda e-mail, versão da conta e um token aleatório.

As operações POST protegidas exigem o cabeçalho `X-CSRF-Token`. A interface recebe esse token na página principal e o envia junto com as requisições.

O token ajuda a impedir alterações originadas de outro site enquanto o funcionário está autenticado.

O login permite até 10 tentativas por IP em uma janela de cinco minutos. Ao atingir o limite, novas tentativas são bloqueadas até o fim dessa janela.

## Rotas da aplicação

| Método | Rota | Finalidade |
| --- | --- | --- |
| GET | `/login` | Abrir a página de acesso |
| POST | `/api/login` | Entrar no sistema |
| POST | `/api/sair` | Encerrar a sessão |
| POST | `/api/recuperar-senha` | Solicitar o link de redefinição por e-mail |
| GET | `/api/sms/status` | Informar se a recuperação por SMS está configurada |
| POST | `/api/sms/solicitar` | Solicitar o código por SMS |
| POST | `/api/sms/confirmar` | Conferir o código e definir uma nova senha |
| GET | `/` | Abrir o sistema autenticado |
| GET | `/api/dados` | Consultar os dados das telas (todos os perfis) |
| GET | `/caixa` | Abrir a tela do caixa (caixa e gerente) |
| GET | `/cozinha` | Abrir a tela da cozinha (cozinha e gerente) |
| GET | `/mesa/<numero>` | Abrir o Racha-conta (público) |
| GET | `/api/mesa/<numero>/conta` | Consultar a conta da mesa (público) |
| POST | `/api/mesa/<numero>/pagar` | Pagar uma parte da conta (público, simulado) |
| POST | `/api/pedidos/<numero>/pagamento` | Receber pagamento parcial no caixa (caixa e gerente) |
| POST | `/api/pedidos` | Criar ou atualizar um pedido |
| POST | `/api/pedidos/<numero>/status` | Atualizar o status |
| POST | `/api/pedidos/<numero>/cancelar` | Cancelar o pedido |
| POST | `/api/pedidos/<numero>/finalizar` | Receber o restante e fechar a mesa (caixa e gerente) |
| POST | `/api/estoque/entrada` | Repor produtos (gerente) |

Os POSTs da API recebem um objeto JSON.

As rotas de saída e de operação do restaurante exigem sessão e token. Login, recuperação de senha por e-mail e as três rotas do SMS são públicos.

### Exemplo de criação de pedido

```json
{
  "mesa": 1,
  "itens": [
    {
      "nome": "Pudim",
      "quantidade": 2
    }
  ]
}
```

### Exemplo de atualização de status

```json
{
  "status": "Pronto"
}
```

### Exemplo de cancelamento

```json
{
  "motivo": "Cliente desistiu do pedido"
}
```

### Exemplo de pagamento

```json
{
  "forma_pagamento": "PIX"
}
```

### Exemplo de pagamento do cliente

Pagar metade de um item:

```json
{
  "modo": "itens",
  "forma": "PIX",
  "gorjeta": true,
  "itens": [{"nome": "Coca-cola", "divisao": 2}]
}
```

Os modos são `itens` (divisão de 1 a 4), `valor` (com o campo `valor`) e `tudo`. As formas aceitas são `PIX`, `Google Pay` e `Apple Pay`.

### Exemplo de pagamento parcial no caixa

```json
{
  "forma": "Dinheiro",
  "valor": 20
}
```

### Exemplo de reposição

```json
{
  "nome": "Pudim",
  "quantidade": 5
}
```

### Exemplo de login

Os valores abaixo são apenas exemplos de formato:

```json
{
  "email": "funcionario@exemplo.com",
  "senha": "SenhaExemplo123"
}
```

### Exemplo de recuperação de senha

```json
{
  "email": "funcionario@exemplo.com"
}
```

## Armazenamento dos dados

### Dados persistentes

O banco Neon guarda a tabela `usuarios`:

- Identificador da conta no Firebase.
- Perfil (administrador, gerente, caixa, garçom ou cozinha).
- Nome.
- E-mail.
- Situação (ativo ou bloqueado).
- Data de criação.
- Horário do último login.
- Horário do último pedido de recuperação de senha.
- Celular do funcionário (só dígitos, com código do país).
- Hash do código de recuperação por SMS, validade, tentativas e horário do último envio.

As senhas **não** ficam no Neon nem neste projeto. Quem as guarda é o Firebase Authentication.

A tabela é criada automaticamente na primeira conexão. O arquivo `schema.sql` traz o mesmo comando.

### Estado do restaurante (mesas, pedidos, vendas e estoque)

Na Vercel o servidor não guarda nada entre uma requisição e outra, então mesas, pedidos, pagamentos, vendas, caixa e estoque ficam na tabela `estado_restaurante` do Neon, que tem uma linha só: `id`, `versao` e `dados` (um texto JSON). O arquivo `estado.py` converte os objetos (Mesa, Pedido, Caixa e Estoque) para texto e de volta. O arquivo `banco_estado.py` lê e grava essa linha.

Como funciona em cada requisição que mexe nos dados:

1. Antes da rota, `carregar_estado()` lê o texto do Neon e recria os objetos.
2. A rota roda normalmente, como sempre rodou.
3. Depois da rota, `guardar_estado()` grava o texto de volta, só se a rota deu certo.
4. A coluna `versao` evita que duas pessoas gravem ao mesmo tempo. Se outra pessoa gravou antes, a resposta é o erro 409 ("tente de novo") e nada se perde nem se mistura.

Os dados do cardápio continuam no `categoria.py`. A variável `persistir_estado` do `app.py` liga e desliga esse recurso (os testes desligam).

### Dados que continuam só em memória

- Tentativas de login, de recuperação, de pagamento e de código por IP (os limites valem por instância do servidor).

O restante já fica no Neon.

### Sessões

A sessão guarda o identificador do funcionário, nome, e-mail e o momento em que o Firebase emitiu o token do login.

A cada 5 minutos o sistema confere de novo se o funcionário continua ativo no Neon e se a conta não foi desativada, apagada ou teve a senha redefinida no Firebase. Se o Neon ou o Firebase estiverem fora do ar, a sessão continua valendo por até 30 minutos.

### Arquivos ignorados pelo Git

O `.gitignore` exclui:

- Ambiente virtual.
- Cache do Python.
- Arquivos `.pyc`.
- Arquivo `.env`.
- Pasta `dados`.
- Arquivos de credenciais do Firebase.

Isso evita publicar credenciais.

## Testes

Para executar:

```bash
python -m unittest -v
```

O projeto possui 122 testes automatizados, cobrindo:

- Acesso autenticado e bloqueio sem sessão.
- Proteção das operações POST e saída.
- Login com dados incorretos, conta sem permissão no Neon, conta bloqueada e serviços fora do ar.
- Limite de tentativas de login.
- Queda da sessão após troca de senha, bloqueio do funcionário e tolerância a falhas.
- Envio do e-mail de recuperação somente para funcionário ativo.
- Resposta idêntica para e-mails cadastrados e desconhecidos.
- Intervalo e limite de pedidos de recuperação, e falhas do Firebase ou do Neon.
- Tradução dos erros da API do Firebase e conferência da chave de API.
- Falhas de conexão com o Neon.
- Cadastro de funcionários, com remoção da conta do Firebase quando o Neon falha.
- Criação e pagamento de pedidos.
- Bloqueio de pagamento duplicado.
- Produtos repetidos e disponibilidade de estoque.
- Quantidades e formatos inválidos.
- Cancelamento e devolução ao estoque.
- Sequência dos status.
- Funcionamento do Carrinho e herança de Pedido.
- Perfis: redirecionamento, bloqueio de rotas e de mudanças de status por perfil.
- Racha-conta: divisão de itens, valor livre, pagar tudo, gorjeta, pagamentos inválidos, limite de tentativas e conta nova aumentando o saldo.
- Caixa: recebimento parcial, fechamento com forma mista e conta cancelada com pagamento.
- Recuperação por SMS: envio ao número registrado, resposta idêntica para qualquer e-mail, limites, código errado, expirado, de uso único e substituído.
- Troca de senha por código, com queda das sessões antigas e falhas do Firebase e do Neon.
- Formato das mensagens de cada provedor (Twilio, Zenvia e Vonage), tradução dos erros e proteção das chaves.
- Normalização de telefones e o script `definir_telefone.py`.

Os testes substituem o Neon, o Firebase e os provedores de SMS por versões simuladas. Não enviam e-mails nem mensagens reais, não acessam a internet e não precisam do arquivo `.env`.

## Problemas comuns

### Não existe usuário para entrar

Execute:

```bash
python cadastrar_usuario.py
```

O novo funcionário já pode entrar, sem reiniciar o servidor.

### A tela diz "Seu acesso não está liberado"

A conta existe no Firebase, mas não está ativa na tabela `usuarios` do Neon. Rode `python cadastrar_usuario.py` e escolha liberar o acesso, ou ative a linha com `UPDATE usuarios SET ativo = TRUE WHERE email = '...'`.

### A tela diz que o login não está configurado

O motivo exato aparece no terminal onde o `app.py` está rodando. Rode também `python verificar_configuracao.py`. A tabela de problemas do [GUIA_CONFIGURACAO.md](GUIA_CONFIGURACAO.md) explica cada mensagem.

### A senha não aparece ao digitar no terminal

Esse comportamento é esperado. O cadastro utiliza `getpass`.

Digite a senha e pressione Enter normalmente.

### O e-mail de recuperação não chegou

Confira:

1. Se o endereço está cadastrado e ativo no Neon.
2. Se o e-mail caiu no spam.
3. Se o terminal registrou `Não foi possível enviar o e-mail de recuperação`.
4. Se o login por e-mail/senha está ativado no Firebase.

Aguarde pelo menos um minuto antes de solicitar novamente.

### O link do e-mail deu erro

O link vale por tempo limitado e só pode ser usado uma vez. Solicite um novo.

### A sessão deixou de funcionar

Entre novamente. Isso pode ocorrer após uma troca de senha, bloqueio do funcionário ou mudança da chave da aplicação.

Se a mensagem solicitar atualização da página, recarregue para receber o token correspondente à sessão.

### As fontes ficaram diferentes ou a tela mostra aviso de conexão

As fontes vêm do Google Fonts e exigem internet. Sem ela, o sistema usa fontes do computador e continua funcionando.

A faixa vermelha "Sem conexão com o servidor" indica que o `app.py` não está respondendo. Confira se o servidor está em execução.

### Os pedidos desapareceram ao reiniciar

Pedidos, vendas e estoque continuam em memória. Esse é o comportamento atual do projeto.

Os usuários permanecem no Neon.

### Aparece erro de módulo não encontrado

Instale as dependências no mesmo ambiente usado para executar o projeto:

```bash
python -m pip install -r requirements.txt
```

## Limitações atuais

- Mesas, pedidos, vendas e estoque ficam em um único texto JSON no Neon. É simples e funciona bem para um restaurante, mas o ideal em produção seria uma tabela para cada coisa (pedidos, itens, pagamentos).
- Se duas pessoas gravarem no mesmo instante, a segunda recebe um aviso e precisa repetir a ação.
- Os limites de tentativas por IP valem por instância do servidor e podem ser contornados em uma hospedagem com várias instâncias.
- Os perfis são fixos (administrador, gerente, caixa, garçom e cozinha).
- Não existe cadastro público de usuários. O primeiro administrador nasce na tela de instalação e os demais são cadastrados dentro do sistema.
- Os ícones dos pratos são emojis, que mudam de aparência conforme o sistema do aparelho.
- Na recuperação por e-mail, a nova senha é escolhida na página padrão do Firebase. Na recuperação por SMS, é escolhida na tela do sistema.
- O código de 4 números é simples de digitar, mas tem só 10 mil combinações. O limite de 5 tentativas por código e os limites por conta e por IP é que o protegem.
- A recuperação por SMS depende de um provedor externo, que costuma cobrar por mensagem e tem regras próprias (remetente aprovado, conta de teste).
- Quem controla o celular registrado consegue trocar a senha daquela conta.
- O telefone é cadastrado pelo terminal, não por uma tela do sistema.
- O Pix, o Google Pay, o Apple Pay e a avaliação do Google são simulações. Não existe integração com pagamentos bancários nem com o Google.
- A página do cliente é pública, mas só abre com o QR Code da mesa (o link tem um código secreto). Quem fotografar o QR Code da mesa consegue pagar a conta dela. Em uma versão real seria preciso também um gateway de pagamento.
- O QR Code não é gerado pelo sistema: só os links das mesas.
- Não existe loja online ligada ao Carrinho.
- Não existe cancelamento parcial por item.
- Não existe controle individual de preparo de cada produto.
- O cardápio é alterado diretamente no Python.
- Reservas existem como comportamento da classe Mesa, sem fluxo na interface.
- O servidor processa uma requisição por vez, usando `threaded=False`.
- A conferência no Firebase e no Neon (no login e a cada 5 minutos por sessão) pode fazer outras requisições aguardarem.
- Os testes usam Neon e Firebase simulados e não confirmam a entrega real do e-mail.
- O limite de tentativas por IP fica em memória e usa o endereço visto pelo servidor; atrás de um proxy, todos podem aparecer com o mesmo IP.
- O front-end não possui testes automatizados; foi verificado manualmente no navegador.
- As fontes da interface vêm do Google Fonts e exigem internet; sem ela, são usadas fontes do sistema.
- A atualização automática faz uma requisição a cada 15 segundos por tela aberta, o que pesa mais com `threaded=False`.
- Histórico de estoque e reserva de mesas não têm tela, pois não existem rotas na API.

A estrutura foi mantida simples para acompanhar a organização acadêmica do repositório. A publicação para uso real exige preparar a hospedagem, HTTPS e armazenamento apropriado.

## Documentação complementar

O arquivo `DOCUMENTACAO.pdf` contém a documentação da versão original do projeto. As funcionalidades acrescentadas estão descritas neste README.