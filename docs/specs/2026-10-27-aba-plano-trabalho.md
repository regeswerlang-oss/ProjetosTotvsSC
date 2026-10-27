# Aba Plano de Trabalho — 27/10/2026

**Pedido:** "Na Açosul a CP Viviani usa uma planilha para determinar e acompanhar
as atividades. O Lucas, CP do cliente, usa a mesma planilha para acompanhar e
atualizar os status. Criar uma área no Dashboard de Projetos onde possamos
controlar essas atividades e os status, com dashboards para a Viviani e o CP do
cliente." A planilha deixa de existir: a atualização do dia a dia passa a ser
no dashboard.

Planilha de origem: `Açosul - Plano de Trabalho Completo - 16102026.xlsx`
(Drive da Viviani) — 8 abas de módulo (Financeiro, Faturamento, Contabilidade,
Ativo Fixo, Compras, Estoque_Custos, PCP, Fiscal) com **89 atividades** e a aba
`Lista de Tarefas_Açosul` com **97 cadastros** (entidades básicas por rotina).

## A pergunta que a aba responde

**"O plano está andando — e o que está travando o próximo marco, na mão de
quem?"** Para a Viviani a resposta é a carteira de atividades do projeto; para o
Lucas é "o que é meu, para quando, e o que vem nas próximas duas semanas".

## Decisões (tomadas com o usuário em 27/10/2026)

1. **Mora no Dashboard de Projetos** (`projetos-vercel`), como aba do detalhe
   do projeto — não no Cockpit Único nem no DashboardIndex.
2. **Substitui a planilha.** Importa uma vez (e reimporta enquanto a
   transição durar); depois Viviani e Lucas atualizam só na tela.
3. **Observações vêm como estão na planilha** e continuam editáveis (texto
   livre). Além delas, toda mudança gera histórico automático (quem, quando,
   de → para) — o diário escrito à mão e o log de auditoria convivem.
4. **Lucas (CP do cliente) edita tudo, igual à Viviani.**
5. **Consultores atualizam o status (e a observação) das próprias
   atividades** — só onde são o responsável.
6. **Os cadastros da Lista de Tarefas ficam dentro do Plano de Trabalho**
   (não na aba Cadastros e Movimentos), como itens do tipo `cadastro`.
7. **Marco oficial de go-live = virada de 04/01/2027** (como no Plano de
   Trabalho). A Lista de Tarefas dizia 17/12/2026 — descartado.

## Onde mora

Aba **`plano`** — rótulo **"Plano de Trabalho"** — logo depois de Cronograma:

`Resumo | Cronograma | Plano de Trabalho | Por Módulo | Por Etapa | …`

Não usar "Tarefas": esse nome já é da aba de tickets do Tasks SC
(`2026-08-26-aba-tarefas.md`).

- Entra em `ABAS` com `"cliente": True` (sem `sensivel`). **Não** entrou em
  `ABAS_PADRAO_CLIENTE`: isso mostraria a aba (vazia) a todo login de cliente
  com `abas` nulo. O CP do cliente recebe `plano` explicitamente na liberação.
- Front: `TABS` (depois de `crono`), `RAIL_ABA.plano = 'pl'`,
  `RELATORIOS.plano` com relatório curado (`relatorioPlanoHTML`).
- **Tela de Acessos** (admin): a aba entra na lista "Abas liberadas" sozinha,
  porque a lista vem do catálogo `ABAS`. Logo abaixo, uma nota
  (`data-acs-nota-plano`) explica que no Plano **quem edita é o papel**: CP
  TOTVS e CP do Cliente editam tudo e importam; Consultor só os itens dele;
  usuário-chave e Leitor só consultam. É ali que se dá `cp_totvs` à Viviani e
  `cp_cliente` + aba `plano` ao Lucas.

> **Armadilha (cockpit-unico-tsc, pré-existente):** salvar os clientes de um
> usuário no `/admin` do Cockpit Único (`salvarLiberacoes`) apaga e regrava as
> linhas de `usuario_clientes` **sem** `abas` e `papel` — o usuário perde as
> abas e o papel em todos os clientes. Gerencie Viviani/Lucas pela tela de
> Acessos deste app.
- Toda rota passa por `deny_aba(customer, "plano")`.
- Trabalha sempre com o cliente do projeto aberto (`state.selected.cli`), como
  Cadastros e Transição. O `codigo_projeto` vai junto: um cliente pode ter dois
  projetos (Açosul tem `TFESR00001` Implantação e `TFESR00002` RH).

## Banco

SQL: `docs/sql/2026-10-27-plano-trabalho.sql`. RLS ligado sem policy: só o
backend (`DATABASE_URL`) lê e grava.

| Tabela | Papel |
|---|---|
| `cockpit.plano_itens` | uma linha por atividade **ou** cadastro (`tipo`) |
| `cockpit.plano_itens_hist` | insert-only: campo, de, para, por, em, origem (`importacao`/`tela`) |
| `cockpit.plano_marcos` | marcos do projeto (base liberada, treinamentos, protótipo, go-live…) — uma data por marco |
| `cockpit.plano_importacoes` | cada importação do xlsx: arquivo, quem, quando, contagens, inconsistências |

### `plano_itens` — campos

Comuns: `customer`, `codigo_projeto`, `tipo` (`atividade`|`cadastro`),
`modulo`, `ordem`, `status`, `data_de`, `data_ate`, `responsavel_lado`
(`totvs`|`cliente`), `responsavel_nome` (texto da planilha),
`responsavel_email` (login resolvido), `observacoes`, `inconsistencia`,
`ativo`, `origem_chave` (para reimportar sem duplicar), `created_*`/`updated_*`.

Só de **atividade**: `sequencia`, `etapa`, `tipo_agenda`
(`Individual`|`Coletiva`), `atividade`, `horas`, `produto` (MIT entregue),
`motivo_restricao`, `qtd_reagendamentos`.

Só de **cadastro**: `rotina` (ex.: `MATA030`), `entidade` (ex.: `Clientes`),
`consultor_nome`/`consultor_email` (o consultor TOTVS que valida — o
responsável é a pessoa do cliente que cadastra), `ambiente`, `tabela` (alias
Protheus, opcional — fase 2). No cadastro, `data_de` = **base liberada** e
`data_ate` = **data limite** (antes do treinamento do módulo).

> **Por que o prazo do cadastro fica na linha.** Na Lista de Tarefas da Açosul a
> base liberada e o limite de treinamento **variam por módulo** (Compras,
> Estoque, PCP e Fiscal vencem em 29/10; Ativo Fixo e Contabilidade em 12/11;
> Faturamento e Financeiro em 20/11). Só protótipo e go-live são iguais em todas
> as linhas — esses viram marco. Regra do parser: **coluna com uma data só vira
> marco; coluna que varia fica no período de cada cadastro.**

## Status

| Tipo | Status gravados | Derivado na leitura |
|---|---|---|
| atividade | `agendado`, `em_andamento`, `finalizado`, `finalizado_restricoes`, `cancelado` | **`atrasada`** = `data_ate < hoje` e não finalizada/cancelada |
| cadastro | `nao_iniciado`, `em_cadastro`, `entregue`, `validado`, `nao_aplicavel` | **`atrasado`** = `data_ate` (ou, sem ela, o marco do protótipo) passou e ainda `nao_iniciado`/`em_cadastro` |

De-para da planilha (normalizado como `_norm_col`): `AGENDADO` → `agendado`;
`FINALIZADO` → `finalizado`; `FINALIZADOCOMRESTRICOES` → `finalizado_restricoes`;
vazio → `agendado` (atividade) / `nao_iniciado` (cadastro).

`hoje` = UTC‑3 (`_cp_hoje()` — a função roda em UTC na Vercel).

### Regras de gravação (backend — a tela só reflete)

1. **Não finaliza atividade futura**: `finalizado`/`finalizado_restricoes`
   exige `data_de <= hoje`. Erro 422 com a data. As regras só valem para o que
   **mudou** no pedido: um item que veio inconsistente da planilha aceita editar
   a observação sem ser barrado.
2. **`finalizado_restricoes` exige `motivo_restricao`** não vazio; o item fica
   em "Restrições em aberto" até virar `finalizado`.
3. **Reagendamento conta**: mudar `data_de`/`data_ate` de item não finalizado
   soma 1 em `qtd_reagendamentos` e grava o par de datas no histórico.
4. **Todo update gera uma linha por campo alterado em `plano_itens_hist`**,
   na mesma transação. Gravar pela tela passando nas regras limpa a
   `inconsistencia` vinda da importação.
5. **"Ver como" não grava** (409), como no resto do app.

## Permissões

Os dois eixos de sempre (`perfil` no sistema × `papel` no cliente — ver
`papel_no_cliente`/`eh_cp_totvs`):

| Quem | Lê | Edita |
|---|---|---|
| `eh_cp_totvs(customer)` (Viviani; admin) | tudo | **tudo**: campos, novo item, inativar, marcos, importar |
| `papel_no_cliente == "cp_cliente"` (Lucas) | tudo | **tudo**, igual à Viviani (decisão 4) — inclusive marcos e importar |
| `papel_no_cliente == "consultor"` (perfil interno) | tudo | **só `status`, `observacoes` e `motivo_restricao`** dos itens em que é `responsavel_email` **ou** `consultor_email` |
| perfil `leitor` (mesmo com papel de CP) | tudo | nada |
| demais com a aba liberada (`usuario_chave`…) | tudo | nada |

Helper `plano_permissao(customer)` devolve
`"tudo" | "proprio" | None`; o payload de leitura manda o resultado para a
tela esconder o que não pode (o backend confere de novo em cada gravação).

> **Atenção:** `cp_cliente` editar tudo é diferente do Protótipo, onde o CP do
> cliente atribui mas não importa nem libera acesso. Aqui a importação também
> fica liberada para ele, porque a planilha deixa de existir e os dois mantêm o
> plano.

### Resolução do responsável (nome → login)

A planilha traz só o primeiro nome (`Elayne`, `Maurício`, `Lucas`) ou nome e
sobrenome (`Maurício Vitto`, `Fabrício Andrade`, `Murilo Mota`). Na importação,
`_plano_resolve()` casa com os logins **liberados no cliente**
(`usuario_clientes`): todo token do nome da planilha tem de **estar contido** no
nome do login ou na parte local do e-mail, sem acento e sem caixa — contido, e
não igual, porque o login da Açosul é `fabricio.sandrade` e a planilha diz
"Fabrício Andrade". **Dois candidatos = não adivinha** (`ambiguos` no resumo);
nenhum = `sem_login`. O CP escolhe o login na gaveta do item. Lado:
`Responsável = Totvs` → `totvs`; qualquer outro texto → `cliente`.

Na tela, pessoas são agrupadas **pelo login** (`plQuem()`): "Maurício" e
"Maurício Vitto" são a mesma linha na carga semanal e no filtro.

## Importação do xlsx

`POST /api/plano/<customer>/<projeto>/importar` (multipart, `.xlsx`).

1. **Abas de módulo** = toda aba cujo cabeçalho tenha `Etapa`, `Atividade` e
   `Status` (o nome da aba vira `modulo`; `Estoque_Custos` → `Estoque/Custos`).
   O módulo do cadastro ("Estoque") é casado com o da aba ("Estoque/Custos")
   quando há **um** candidato que começa com ele.
   Cabeçalho tolerante a acento/caixa (`Produto da Atividade` e `Produto` são o
   mesmo campo — as duas grafias existem no arquivo da Açosul).
2. **Aba de cadastros** = a que tiver `Cadastro/Entidade Básica`. A linha 1
   traz as empresas (Açosul, Cortesul, Perfilados) sobre a coluna de
   responsável; **só a coluna da empresa do projeto é lida** (o escopo da Açosul
   é só Açosul desde 01/07/2026). `MATA030 - Clientes` → `rotina` + `entidade`.
   Colunas de data **uniformes** alimentam `plano_marcos` **apenas se o marco
   ainda não existir** — o go-live da planilha (17/12) não sobrescreve o
   oficial (virada 04/01/2027). Por isso: **grave os marcos antes de importar.**
3. **Linhas sem `Atividade`/`Cadastro` são ignoradas** (as abas têm linha de
   total e linhas vazias até a 1000).
4. **Idempotente**: `origem_chave` = `A|modulo|sequencia` (atividade) ou
   `C|modulo|rotina|entidade` (cadastro — a mesma rotina aparece em várias
   linhas: FISA170 tem cinco). Reimportar atualiza o que veio e **não apaga** o
   que foi criado na tela; item que sumiu da planilha só é listado no resumo
   ("presentes no dashboard e ausentes na planilha"), nunca inativado sozinho.
5. **Importa como está, mas aponta inconsistência.** As regras de status
   **não barram a importação** (a decisão foi trazer o histórico fiel); o que
   as violaria vira `inconsistencias[]` no resumo e um selo ⚠ na linha. No
   arquivo de 16/10 já existe uma: *Faturamento — "Treinamento de processos e
   movimentos" 25–26/11/2026 marcado Finalizado*.
6. **A tela vence.** Campo que já foi alterado pela tela (há linha de
   histórico `origem = tela`) **não volta** ao valor da planilha numa
   reimportação — senão reimportar o xlsx antigo desfaria o trabalho do dia sem
   ninguém perceber. Contado em `preservados` no resumo. Campos nunca tocados na
   tela acompanham a planilha.
7. Cada importação grava `plano_importacoes` e o histórico `origem =
   importacao` (uma linha "criado" por item novo; uma por campo alterado).

## Tela — três subabas (`pl.sub`)

### Grade (padrão para interno)

- Um `<details>` por módulo (alfabético), com `x/y atividades finalizadas`,
  horas, `x/y cadastros` e selos de atrasado/a revisar no cabeçalho; dentro,
  atividades agrupadas por etapa na ordem do método e, ao final, o bloco
  **Cadastros** do módulo.
- **Status na linha** (select) para quem pode editar o item; o resto na gaveta.
  Escolher "Finalizado c/ restrições" sem motivo **abre a gaveta** pedindo o
  motivo em vez de gravar e tomar 422.
- Filtros: módulo, etapa, status (em aberto / atrasados / ⚠ a revisar / cada
  status), lado, responsável (pelo login), tipo, busca sem acento.
- Selos: atrasado (barra vermelha à esquerda), ⚠ revisar, `↻ N`, restrição.
- Clique na descrição → **gaveta** com todos os campos (travados conforme a
  permissão), login do responsável/consultor, observações e **histórico**.
- Rail: ⬆ Importar planilha, ＋ Atividade, ＋ Cadastro — só para `tudo`
  (atributo `data-pl-tudo`, **não** `data-interno`: o CP do cliente usa).
- Blocos recolhidos **não geram DOM** (corpo como função, como em Compara e
  Painel CP) — 186 linhas abertas de uma vez travam a aba.

### Painel (visão da Viviani)

- **Marcos** (faixa comum às três subabas): data e contagem regressiva;
  ✎ marcos para quem edita tudo.
- **KPIs**: atividades (+ horas), finalizadas %, atrasados (quantos do lado do
  cliente), restrições abertas, próximos 7 dias, cadastros entregues/total, a
  revisar.
- **Matriz módulo × etapa**: finalizadas/total por célula; vermelho se tem
  atrasado. **Clique na célula filtra a Grade.**
- **Carga semanal por responsável**: horas em aberto distribuídas nos dias
  úteis do período, por semana; vermelho acima de 40 h.
- **Atrasados** (mais antigo primeiro) e **restrições em aberto** com o motivo.

### Pendências (padrão para `cp_cliente`, perfil cliente e consultor)

Rótulo "Minhas pendências" para o CP do cliente e o consultor; "Pendências
<cliente>" para o CP TOTVS. Para o consultor (`proprio`) a lista é **dos itens
dele**; para os demais, do lado do cliente.

- **O que está com o cliente**: atividades em aberto ordenadas (atrasadas
  primeiro, depois prazo) e **cadastros a entregar** por módulo, com o limite
  e o selo "vence em Nd" a 7 dias ou menos.
- **Próximas agendas (14 dias)**: para mobilizar os usuários-chave.
- **Aguardando aprovação**: itens com `produto` (MIT) e status
  `finalizado_restricoes` ou observação contendo "aguardando aprovação"
  (heurística da fase 1 — fase 2 vira campo próprio).
- **Marcos** (mesmo bloco do Painel).

## Exportar HTML e e-mail

Mesmo padrão das outras abas (`2026-08-25-exportar-html-e-gmail-em-todas-as-abas.md`):
`RELATORIOS.plano.curado = relatorioPlanoHTML` → HTML one-page com estilo
inline (serve ao Gmail): marcos, KPIs, atrasados, pendências do cliente e
próximas 2 semanas, na moldura padrão (`molduraRelatorio`).

## Rotas

| Rota | Faz |
|---|---|
| `GET /api/plano/<customer>/<projeto>` | itens (com `atrasado`, `meu`, `editavel`) + marcos + `permissao` + `papel` + candidatos (logins liberados) + última importação |
| `POST /api/plano/<customer>/<projeto>/importar` | importa o xlsx (ver acima) e devolve o resumo |
| `POST /api/plano/<customer>/<projeto>/item` | cria item |
| `POST /api/plano/item/<id>` | altera campos (regras + histórico) |
| `POST /api/plano/item/<id>/inativar` | inativa (nunca apaga) |
| `GET /api/plano/item/<id>/hist` | histórico do item |
| `POST /api/plano/<customer>/<projeto>/marcos` | grava marcos |

Rotas de item conferem o `customer` **dono** do item antes de qualquer coisa
(não confiar no customer da URL).

## Antes de liberar para a Açosul (TFESR000)

0. ~~Aplicar o SQL~~ — **aplicado em 27/10/2026** no Supabase (migration
   `plano_trabalho`; RLS ligado, sem policy).
1. **Viviani sem papel**: em `usuario_clientes` ela está liberada no
   TFESR000 com `papel` vazio — precisa virar `cp_totvs`, senão não importa.
2. **Lucas sem login**: criar login perfil `cliente`, liberar TFESR000 com
   papel `cp_cliente` e abas `plano` (+ as que a Viviani quiser mostrar).
3. **Consultores**: já liberados com papel `consultor` (Elayne, Fabrício,
   Maurício, Murilo) — incluir `plano` nas abas deles.
4. **Gravar os marcos antes de importar** (go-live = 04/01/2027).
   **Protótipo diverge**: a Lista de Tarefas diz 27/11; o Plano de Trabalho
   agenda o 1º protótipo integrado de 02 a 04/12. Confirmar com a Viviani.

Ensaio com o arquivo real (16/10), em banco local: 186 itens (89 atividades +
97 cadastros), 8 linhas ignoradas (totais), 8 módulos, todos os nomes
resolvidos menos "Lucas" (sem login ainda), 2 inconsistências (Financeiro —
restrição sem motivo; Faturamento — finalizado com data futura), 14 atividades
já atrasadas em 27/10 e 52 cadastros com limite em 29/10.

## Fases

1. **Fase 1** — SQL, importação, Grade com edição e histórico, permissões,
   Painel da Viviani, Minhas pendências do Lucas, exportar HTML/e-mail.
2. **Fase 2** — `tabela` do cadastro ligada à última medição do
   `monitcad_tabelas` (registros na base ao lado do status manual); vínculo da
   atividade com a atividade do Cronograma PCI (horas apontadas × planejadas,
   agenda `ZA` sugerindo `finalizado`); campo próprio para aprovação de MIT.

## Testes

- `docs/testes/plano-back.py` — **83 asserções**. Sempre: funções puras com
  planilha **sintética** (repo público — nada de dado de cliente): de-para,
  cabeçalho tolerante, total ignorado, empresa certa, rotina repetida, módulo
  casado, regra do marco uniforme, inconsistências, nome → login (contido,
  ambíguo, sem login), regras 1–3, atraso, UTC‑3. Com
  `PLANO_TEST_DB=<Postgres descartável>`: as rotas pelo test client —
  importação, idempotência, **a tela vence**, permissões (cp_totvs, cp_cliente,
  consultor próprio/alheio, usuário-chave, leitor, sem aba), simulação 409,
  regras na rota, criar/inativar, histórico. **Nunca aponte para o Supabase**:
  o teste recria o schema `cockpit` no banco que recebe.
- `docs/testes/plano-front.js` — **43 asserções**, Playwright com `/api/*`
  interceptado: subaba inicial por papel, grade recolhida sem DOM, selos,
  etapas na ordem, status na linha (payload só com o status), restrição sem
  motivo abrindo a gaveta, histórico, Esc, filtros (atrasados, responsável pelo
  login, busca sem acento), Painel (KPIs, restrição, matriz → filtro, carga
  agrupada pelo login), relatório, visão do cliente (só o lado dele, "vence em
  2d", importar visível), do consultor (só as linhas dele, gaveta travada) e
  a tela de Acessos (aba listada, nota de papéis, liberação existente), zero
  erro de JS.
