# Aba Estrutura de Empresas (definição)

*29/09/2026 — pedido para a consultoria e os CPs (Viviani e Cassio), liberação
por cliente. Laboratório: OLIM AGRO CEREAIS (`TFEHXQ00`).*

## O problema

Já existe a aba **Empresas e Compartilhamento** (`monitemp_*`): ela **mede** a
base do cliente — lê a SM0, olha a SX2 de cada empresa e diz onde os dados
caíram. Só que ela só funciona **depois** de existir base.

A decisão que quebra a implantação acontece **antes**: quantos grupos, quantas
empresas, quantas filiais, qual o leiaute do código e qual tabela é exclusiva de
quem. A TDN é dura nisso:

> "A estrutura das tabelas deve ser definida na implantação do sistema (…) Não
> aconselhamos a alteração no compartilhamento das tabelas após a implantação."

Hoje essa decisão vive numa planilha por projeto. Planilha não valida regra, não
guarda quem decidiu e não conversa com a medição que vem depois.

| | Aba **Empresas** | Aba **Estrutura** (esta) |
|---|---|---|
| Pergunta | Onde os dados **caíram**? | Como **combinamos** que seria? |
| Fonte | SM0 + SX2 lidas do banco do cliente | O que a consultoria digitou |
| Quando | Depois da carga | Antes da carga |
| Tabelas | `cockpit.monitemp_*` | `cockpit.estrut_*` |

## O que a aba tem

1. **Leiaute do código** — `FF` (só filial), `EEFF` (empresa + filial) ou
   `EEUUFF` (empresa + unidade de negócio + filial), com o tamanho de cada nível
   e um exemplo montado (`0101`). O exemplo vale mais que a explicação: o
   consultor confere com o cliente em dois segundos.
2. **Grupo · Empresa · Filial** — árvore com código, razão social, CNPJ,
   município/UF e a marcação de **matriz** (uma por empresa; marcar outra
   desmarca a anterior no servidor).
3. **Tabelas e compartilhamento** — por módulo, com `Nome · Descrição ·
   Tipo · Compartilhamento`, editável direto na linha por três `select` E/C.
4. **Inclusão manual** de tabela por módulo (e de módulo novo): tabela
   customizada `Z*` e alias fora do catálogo aparecem em todo projeto.
5. **Conferência** — a lista de inconsistências, que é o que a planilha nunca fez.

## Compartilhamento: TRÊS posições, nesta ordem

**Empresa · Unidade de Negócio · Filial** — a MESMA ordem de
`X2_MODOEMP|X2_MODOUN|X2_MODO` que a aba de medição já mostra. `E` = exclusiva,
`C` = compartilhada. `ECC` = exclusiva por empresa e compartilhada no resto (o
cadastro típico); `ECE` = também exclusiva por filial (o movimento típico);
`CCC` = tudo compartilhado.

Trocar essa ordem entre as duas abas faria o consultor comparar coisas
diferentes achando que são a mesma — por isso ela é igual nas duas.

**O nível que o leiaute não usa fica desabilitado na tela e nasce `C`.** Sem
unidade de negócio no código, "exclusiva por unidade" não significa nada, e
cobrar coerência dessa posição geraria alerta que ninguém consegue resolver.

## A conferência (`_estrut_alertas`)

Três famílias, e a terceira é a que paga a aba:

- **Código** (erro): tamanho diferente do leiaute, ou filial cujo código não
  começa pelo código da empresa dona. É o erro que só aparece na carga.
- **Definição fora da sugestão** (info) e **tabela sem compartilhamento**
  (aviso). Fugir da sugestão não é erro — é decisão; vira linha da ata.
- **Regras da TDN** (erro), em `cockpit.estrut_regras`:
  - `nao_mais` — **movimento não pode ser mais compartilhado que o cadastro**
    (relacionamento 1:n). É a regra central: SE1 mais compartilhada que SA1 abre
    margem para um título ligado a mais de um cliente.
  - `igual` — pares que têm de ter o MESMO compartilhamento: família SE (exceto
    SED e SE8), família FK seguindo a SE5, FKF com os títulos, F7F com SA1,
    MEP com SE1.

**"Mais compartilhada" é comparação por nível, não contagem de C.** `a` só é
mais compartilhada que `b` quando é `>=` em **todos** os níveis que valem e `>`
em algum. Modos cruzados (mais amplo aqui, menos ali) **não são comparáveis** e
não viram alerta — inventar ordem onde não há produz alarme falso, e alarme
falso é como o consultor aprende a ignorar a tela.

## Catálogo semente (`cockpit.estrut_catalogo`)

131 tabelas em 12 módulos: Configurador, Financeiro, Compras, Estoque/Custos,
Faturamento, Fiscal, Contabilidade, Ativo Fixo, PCP, Contratos, **Folha de
Pagamento** e **Ponto Eletrônico**.

- Descrições do backoffice vêm do catálogo já validado em
  `cockpit.monitcad_tabelas` — não foram inventadas aqui.
- **Folha**: nomes conforme `GPE02012 - Tabelas P12 RH` (TDN).
- **Ponto**: as 21 tabelas de `DT Compartilhamento Padrão das Tabelas do
  SIGAPON` (TDN), que desde a **12.1.2310** nascem `E|E|E` em instalação nova.
  Ambiente que já existe **não** teve o compartilhamento alterado — conferir.
- `sugestao` é ponto de partida da consultoria, **nunca** a decisão. Onde a
  fonte é a TDN está marcado; o resto é `TOTVS SC`.
- **Semear de novo não apaga o que já foi decidido** (`do nothing` no conflito).
  Semeadura é ponto de partida, não reset.

Fora do catálogo de propósito: SX6 e SX7. Dicionário não é decisão de
compartilhamento de dado de negócio (mesma razão de
`2026-08-23-remover-sx5-sx6-sx7`).

Também de propósito, as regras `igual` **não** incluem SE4 e SEE, ainda que a
TDN fale da família SE inteira: são cadastros que quase todo cliente deixa
compartilhados, e o alerta apareceria em 100% dos projetos sem nada de errado.

## Acesso

`ABAS` recebe `{"id": "estrutura", "cliente": False}` — **interna**, como
Consumo. Quem é da TOTVS (`admin`, `comum`, `consultoria`, `leitor`) vê nos
clientes que já tem liberados; usuário do cliente não vê a aba nem chamando a
rota na mão (`deny_aba` barra no servidor, `ABAS_CLIENTE_OK` nunca contém
`estrutura`). Toda gravação passa por `require_interno()`.

Por isso os botões do rail **não** levam `data-interno`: a aba inteira já é
interna, e repetir o atributo daria a impressão de que existe uma versão dela
para o cliente.

## Rotas

| Rota | O que faz |
|---|---|
| `GET /api/estrutura/<customer>` | Tudo numa requisição: config, árvore, tabelas, catálogo e alertas |
| `GET /api/estrutura/catalogo/<modulo>` | Tabelas do catálogo daquele módulo |
| `POST /api/estrutura/<customer>/config` | Leiaute e tamanhos |
| `POST /api/estrutura/<customer>/grupo` \| `/empresa` \| `/filial` | Cria, altera e **inativa** (nunca apaga — pode já ser decisão em ata) |
| `POST /api/estrutura/<customer>/semear` | Traz módulos do catálogo |
| `POST /api/estrutura/<customer>/tabela` | Inclusão manual, edição do compartilhamento e remoção |

O GET devolve tudo junto de propósito: em cinco chamadas o consultor veria a
árvore montar em pedaços na frente do cliente.

## Como foi testado

- `testestrutura.py` — 20 asserções sobre `_estrut_mais_compart`,
  `_estrut_niveis` e `_estrut_tam_esperado`, incluindo a tabela SA1 × SE1 da
  própria TDN, os modos cruzados e o nível desligado pelo leiaute.
- `teststub.mjs` — stub HTTP servindo `web/` + Chromium (Playwright): abre o
  projeto, entra na aba, confere KPIs, alertas, árvore, os 12 `select` (4 deles
  desabilitados no `EEFF`), o filtro que **esconde linha em vez de redesenhar**
  (redesenhar a cada tecla joga o cursor para o começo da palavra) e abre e
  fecha os cinco modais. Zero erro de página.

## Pendências

1. Cruzar **definido × medido**: comparar `estrut_tabelas.compart` com o
   `sx2` que a aba Empresas já lê da base. É a pergunta seguinte natural
   ("fizeram o que combinamos?") e só depende de dado que já existe.
2. Exportar a definição no layout que o time usa na reunião (hoje sai pelo
   **⬇ Exportar HTML** global, que já funciona nesta aba).
3. Importar a estrutura de um cliente para outro, como o `?copiar_de=` do
   Protótipo.

## Empresas da base, lado a lado (29/09/2026)

Entre a árvore e a lista de tabelas entrou um bloco **só de leitura** com as
empresas e filiais que a aba Empresas já leu da SM0 do cliente — código, razão
social, leiaute e as filiais de cada empresa, com o ambiente e a data da leitura.

**Nada dali entra na árvore.** A separação entre as duas abas é o que dá valor a
esta: uma é o que a consultoria combinou, a outra é o que o banco tem. No
instante em que o painel começa a copiar uma para a outra, a comparação deixa de
existir — e é a comparação que pega o erro.

Por isso o bloco compara uma coisa só, a que custa caro depois: **o leiaute**. Se
a base está com `FF` e a definição diz `EEFF`, o aviso aparece em cima da tabela.
Um dos dois está errado, e quem paga é o código da filial na carga.

Sem leitura da SM0, o bloco vira uma linha discreta dizendo onde rodar o Script
SM0. A rota `/api/estrutura/<customer>` passou a devolver `sm0` e
`sm0_ambiente`: produção na frente, testes como alternativa — em projeto novo,
que é o caso de uso desta aba, muitas vezes só existe a de testes.

## O escopo sai daqui e a separação cadastro × movimento entra (29/09/2026)

Duas pontas do mesmo laço.

**A aba Empresas passa a medir o que esta aba define.** A rota do monitemp devolve
`escopo` a partir de `cockpit.estrut_tabelas` (ativas) e o gerador dos scripts P0
e P1 usa essa lista no lugar da `LISTA_ESCOPO` fixa. Vale para tabela semeada do
catálogo **e** para tabela incluída na mão: um `Z*` do cliente entra no script
como qualquer outra. Cliente que ainda não definiu nada cai na lista padrão de 34
— medir zero tabelas pareceria painel quebrado, não escopo vazio —, e o modal do
script diz qual das duas está valendo.

**A lista de tabelas ganhou o filtro `Todas · Cadastros · Movimentos`**, com a
contagem de cada um, igual ao da aba de medição. Não é enfeite: é a separação que
a regra central da conferência usa — movimento não pode ser mais compartilhado
que o cadastro. Poder olhar só os movimentos de um módulo é como se confere isso
sem ler linha por linha.

Módulo sem nenhuma tabela do tipo escolhido diz isso em uma linha, em vez de
mostrar tabela vazia.
