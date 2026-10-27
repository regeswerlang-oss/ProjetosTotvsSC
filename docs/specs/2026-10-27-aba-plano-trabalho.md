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

- Entra em `ABAS` com `"cliente": True` (sem `sensivel`) e em
  `ABAS_PADRAO_CLIENTE` — o login do cliente que tem papel `cp_cliente` abre
  direto nela.
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
`modulo`, `ordem`, `status`, `responsavel_lado` (`totvs`|`cliente`),
`responsavel_nome` (texto da planilha), `responsavel_email` (login resolvido),
`observacoes`, `ativo`, `origem_chave` (para reimportar sem duplicar),
`created_*`/`updated_*`.

Só de **atividade**: `sequencia`, `etapa`, `tipo_agenda`
(`Individual`|`Coletiva`), `atividade`, `data_de`, `data_ate`, `horas`,
`produto` (MIT entregue), `motivo_restricao`, `qtd_reagendamentos`.

Só de **cadastro**: `rotina` (ex.: `MATA030`), `entidade` (ex.: `Clientes`),
`ambiente`, `base_liberada_em`, `tabela` (alias Protheus, opcional — ver fase 2).
Os prazos (treinamento/protótipo/go-live) **não** ficam na linha: vêm de
`plano_marcos` — eram iguais nas 97 linhas da planilha e foi assim que o go-live
divergiu entre as abas.

## Status

| Tipo | Status gravados | Derivado na leitura |
|---|---|---|
| atividade | `agendado`, `em_andamento`, `finalizado`, `finalizado_restricoes`, `cancelado` | **`atrasada`** = `data_ate < hoje` e não finalizada/cancelada |
| cadastro | `nao_iniciado`, `em_cadastro`, `entregue`, `validado`, `nao_aplicavel` | **`atrasado`** = prazo do marco passou e não `entregue`/`validado`/`nao_aplicavel` |

De-para da planilha (normalizado como `_norm_col`): `AGENDADO` → `agendado`;
`FINALIZADO` → `finalizado`; `FINALIZADOCOMRESTRICOES` → `finalizado_restricoes`;
vazio → `agendado` (atividade) / `nao_iniciado` (cadastro).

`hoje` = UTC‑3 (`_cp_hoje()` — a função roda em UTC na Vercel).

### Regras de gravação (backend — a tela só reflete)

1. **Não finaliza atividade futura**: `finalizado`/`finalizado_restricoes`
   exige `data_de <= hoje`. Erro 422 com a data.
2. **`finalizado_restricoes` exige `motivo_restricao`** não vazio; o item fica
   em "Restrições em aberto" até virar `finalizado`.
3. **Reagendamento conta**: mudar `data_de`/`data_ate` de item não finalizado
   soma 1 em `qtd_reagendamentos` e grava o par de datas no histórico.
4. **Todo update gera uma linha por campo alterado em `plano_itens_hist`**,
   na mesma transação.

## Permissões

Os dois eixos de sempre (`perfil` no sistema × `papel` no cliente — ver
`papel_no_cliente`/`eh_cp_totvs`):

| Quem | Lê | Edita |
|---|---|---|
| `eh_cp_totvs(customer)` (Viviani; admin) | tudo | **tudo**: campos, novo item, inativar, marcos, importar |
| `papel_no_cliente == "cp_cliente"` (Lucas) | tudo | **tudo**, igual à Viviani (decisão 4) — inclusive marcos e importar |
| `papel_no_cliente == "consultor"` | tudo | **só `status`, `observacoes` e `motivo_restricao`** dos itens com `responsavel_email` = ele |
| demais com a aba liberada (`usuario_chave`, leitor…) | tudo | nada |

Helper novo `pode_editar_plano(customer, item=None)` devolve
`"tudo" | "proprio" | None`; o payload de leitura manda o resultado para a
tela esconder o que não pode (o backend confere de novo em cada gravação).

> **Atenção:** `cp_cliente` editar tudo é diferente do Protótipo, onde o CP do
> cliente atribui mas não importa nem libera acesso. Aqui a importação também
> fica liberada para ele, porque a planilha deixa de existir e os dois mantêm o
> plano.

### Resolução do responsável (nome → login)

A planilha traz só o primeiro nome (`Elayne`, `Maurício`, `Lucas`) ou nome e
sobrenome (`Maurício Vitto`, `Fabrício Andrade`, `Murilo Mota`). Na importação,
`_plano_resolve_email()` casa com os logins **liberados no cliente**
(`usuario_clientes`), pelo mesmo critério do Painel CP: todo token do nome da
planilha tem de estar em `usuarios_login.nome` (ou na parte local do e-mail),
sem acento e sem caixa. **Dois candidatos = não adivinha**: fica sem e-mail e
entra na lista "responsáveis sem login" do resumo da importação, para o CP
escolher na tela. Lado: `Responsável = Totvs` → `totvs`; nome do cliente →
`cliente`.

## Importação do xlsx

`POST /api/plano/<customer>/<projeto>/importar` (multipart, `.xlsx`).

1. **Abas de módulo** = toda aba cujo cabeçalho tenha `Etapa`, `Atividade` e
   `Status` (o nome da aba vira `modulo`; `Estoque_Custos` → `Estoque/Custos`).
   Cabeçalho tolerante a acento/caixa (`Produto da Atividade` e `Produto` são o
   mesmo campo — as duas grafias existem no arquivo da Açosul).
2. **Aba de cadastros** = a que tiver `Cadastro/Entidade Básica`. A linha 1
   traz as empresas (Açosul, Cortesul, Perfilados) sobre a coluna de
   responsável; **só a coluna da empresa do projeto é lida** (o escopo da Açosul
   é só Açosul desde 01/07/2026). `MATA030 - Clientes` → `rotina` + `entidade`.
   As datas da linha alimentam `plano_marcos` **apenas se o marco ainda não
   existir** — o go-live da planilha (17/12) não sobrescreve o oficial.
3. **Linhas sem `Atividade`/`Cadastro` são ignoradas** (as abas têm linha de
   total e linhas vazias até a 1000).
4. **Idempotente**: `origem_chave` = `modulo|sequencia` (atividade) ou
   `modulo|rotina` (cadastro). Reimportar atualiza o que veio e **não apaga** o
   que foi criado na tela; item que sumiu da planilha só é listado no resumo
   ("presentes no dashboard e ausentes na planilha"), nunca inativado sozinho.
5. **Importa como está, mas aponta inconsistência.** As regras de status
   **não barram a importação** (a decisão foi trazer o histórico fiel); o que
   as violaria vira `inconsistencias[]` no resumo e um selo ⚠ na linha. No
   arquivo de 16/10 já existe uma: *Faturamento — "Treinamento de processos e
   movimentos" 25–26/11/2026 marcado Finalizado*.
6. Cada importação grava `plano_importacoes` e uma linha de histórico
   `origem = importacao` por item criado/alterado.

## Tela — três subabas (`SUBABAS.plano`)

### Grade (padrão para interno)

- Um `<details>` por módulo, na ordem da planilha, com `x/y finalizadas` e
  horas no cabeçalho; dentro, atividades agrupadas por etapa e, ao final, o
  bloco **Cadastros** do módulo.
- Edição na linha (status, datas, responsável, observações) conforme
  `pode_editar_plano`; salvar por linha, sem botão global.
- Filtros: etapa, status (com "atrasadas"), lado (TOTVS/cliente),
  responsável, período, tipo (atividade/cadastro), busca.
- Selos: atrasada, ⚠ inconsistência, `↻ N` reagendamentos, restrição.
- Clique na linha → drawer com observações e **histórico** (`/hist`).
- Botões: ＋ Atividade, ＋ Cadastro, Importar xlsx, Exportar.
- Blocos recolhidos **não geram DOM** (corpo como função, como em Compara e
  Painel CP) — 186 linhas abertas de uma vez travam a aba.

### Painel (visão da Viviani)

- **KPIs**: atividades, finalizadas (%), atrasadas, restrições em aberto,
  próximas 7 dias, cadastros validados/total, horas planejadas.
- **Marcos**: contagem regressiva para protótipo e go-live, com quantos itens
  ainda precisam fechar antes de cada um.
- **Matriz módulo × etapa**: % finalizado por célula, cor por atraso.
- **Carga semanal por consultor**: horas das atividades agendadas por semana
  (sobreposição de datas do mesmo consultor em destaque).
- **Restrições em aberto** e **atrasadas**, ordenadas pela mais antiga.

### Minhas pendências (visão do Lucas — padrão para `cp_cliente`)

- **O que é da Açosul**: itens com `responsavel_lado = cliente` não
  finalizados, ordenados por prazo (inclui os 97 cadastros).
- **Próximas agendas (14 dias)**: para mobilizar os usuários-chave.
- **Aguardando aprovação**: itens com `produto` (MIT) e status
  `finalizado_restricoes` ou observação contendo "aguardando aprovação"
  (heurística da fase 1 — fase 2 vira campo próprio).
- **Marcos** (mesmo bloco do Painel).

## Exportar HTML e e-mail

Mesmo padrão das outras abas (`2026-08-25-exportar-html-e-gmail-em-todas-as-abas.md`):
`EXPORTS.plano` → HTML one-page do status do plano (marcos, KPIs, atrasadas,
pendências do cliente, próximas 2 semanas) no layout TOTVS, e rascunho de e-mail
HTML para o CP do cliente.

## Rotas

| Rota | Faz |
|---|---|
| `GET /api/plano/<customer>/<projeto>` | itens + marcos + KPIs + `permissao` + responsáveis possíveis |
| `POST /api/plano/<customer>/<projeto>/importar` | importa o xlsx (ver acima) e devolve o resumo |
| `POST /api/plano/<customer>/<projeto>/item` | cria item |
| `POST /api/plano/item/<id>` | altera campos (regras + histórico) |
| `POST /api/plano/item/<id>/inativar` | inativa (nunca apaga) |
| `GET /api/plano/item/<id>/hist` | histórico do item |
| `POST /api/plano/<customer>/<projeto>/marcos` | grava marcos |

Rotas de item conferem o `customer` **dono** do item antes de qualquer coisa
(não confiar no customer da URL).

## Antes de liberar para a Açosul (TFESR000)

1. **Viviani sem papel**: em `usuario_clientes` ela está liberada no
   TFESR000 com `papel` vazio — precisa virar `cp_totvs`, senão não importa.
2. **Lucas sem login**: criar login perfil `cliente`, liberar TFESR000 com
   papel `cp_cliente` e abas `plano` (+ as que a Viviani quiser mostrar).
3. **Consultores**: já liberados com papel `consultor` (Elayne, Fabrício,
   Maurício, Murilo) — incluir `plano` nas abas deles.
4. **Protótipo diverge**: a Lista de Tarefas diz 27/11; o Plano de Trabalho
   agenda o 1º protótipo integrado de 02 a 04/12. Confirmar o marco com a
   Viviani antes de importar.

## Fases

1. **Fase 1** — SQL, importação, Grade com edição e histórico, permissões,
   Painel da Viviani, Minhas pendências do Lucas, exportar HTML/e-mail.
2. **Fase 2** — `tabela` do cadastro ligada à última medição do
   `monitcad_tabelas` (registros na base ao lado do status manual); vínculo da
   atividade com a atividade do Cronograma PCI (horas apontadas × planejadas,
   agenda `ZA` sugerindo `finalizado`); campo próprio para aprovação de MIT.

## Testes

- `docs/testes/plano-back.py` — funções puras: de-para de status, cabeçalho
  tolerante (`Produto`/`Produto da Atividade`), linhas de total ignoradas,
  `origem_chave` idempotente, coluna da empresa certa na Lista de Tarefas,
  marco existente não sobrescrito, inconsistência de finalizado futuro
  apontada (e não barrada), resolução nome → login (único, ambíguo, sem login),
  regras 1–3 de gravação, matriz de permissões (cp_totvs, cp_cliente,
  consultor próprio/alheio, usuario_chave) e `hoje` em UTC‑3.
- `docs/testes/plano-front.js` — Playwright com `/api/*` interceptado (padrão
  `**/api/plano/*`): aba aparece e abre na subaba certa por papel, grade monta
  recolhida, filtros, edição na linha respeitando a permissão, drawer de
  histórico, KPIs/marcos do Painel, Minhas pendências, export, zero erro de JS.
