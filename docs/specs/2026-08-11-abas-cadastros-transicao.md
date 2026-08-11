# Abas globais + Cadastros (MONITCAD) + Transição — 11/08/2026

Agrupa no app **Projetos TOTVS SC** (`projetos-vercel`) três visões que antes
viviam em arquivos soltos, e sobe a barra de abas do detalhe do projeto.

## 1. Uma barra de abas só, no contexto do projeto

Não há navegação global. Cadastros e Transição vivem **na mesma barra** das abas
do projeto, depois de um divisor:

`Resumo | Cronograma | Por Módulo | Por Etapa ┊ Cadastros | Transição`

A consequência é o ponto central do desenho: **as duas abas sempre trabalham com
o cliente do projeto aberto** (`state.selected.cli`, que é o
`codigo_cliente_projeto` = `customer`). Não existe seletor de cliente nem risco de
olhar o cadastro de um cliente enquanto o cabeçalho mostra o projeto de outro.

`setTab(nome)` (lista `TABS`) troca o painel, carrega Cadastros/Transição sob
demanda e esconde o "Expandir/Recolher" fora das abas com árvore. As duas abas
guardam o `customer` já carregado e só refazem a busca quando o projeto aberto é
de outro cliente.

## 2. Abas do detalhe subiram

A barra `Resumo | Cronograma | Por Módulo | Por Etapa` passou para **logo abaixo
do card do projeto**. Os 4 KPIs e o "Apontamentos por tipo" viraram o conteúdo da
nova aba **Resumo** — antes ficavam acima das abas e empurravam o cronograma para
fora da primeira dobra. `abrirDetalhe()` sempre abre em Resumo (`setTab('resumo')`).
"Expandir/Recolher" (`#tab-acoes`) só aparece nas abas com árvore.

## 3. Aba Cadastros — MONITCAD

Fonte canônica = `cockpit.monitcad_projetos` / `_medicoes` / `_tabelas`.

- `GET /api/monitcad/<customer>` → projeto, **última medição** (tabela, descrição,
  **módulo**, realizado, estimativa, %, etapa, responsável, previsão, status),
  **quebra por módulo** e **série histórica**. `tem_estimativa: false` quando
  nenhuma tabela tem estimativa cadastrada — aí a tela troca para contagem
  absoluta (registros carregados, tabelas com carga, módulos) e avisa que sem
  estimativa não há % nem semáforo. Sem medição → `vazio: true`.
- **"Tabelas monitoradas por módulo"** é um accordion: um `<details>` por módulo,
  com barra proporcional, total de registros e `com carga/total` no cabeçalho.
  Módulos com carga nascem abertos, os zerados recolhidos; os botões
  **Expandir/Recolher** (`data-act="cad-expandir|cad-recolher"`) agem em todos.
  A ordem dos grupos vem do `modulos` do backend (registros desc).
- `POST /api/monitcad/<customer>/upload` → carga manual em **dois formatos**:
  o `historico-semanal.json` (projeto *Monitoramento Cadastros*) e o **CSV de
  status de cadastros** exportado do Protheus. Idempotente: regrava a medição
  inteira quando a data já existe. Bloqueado durante simulação ("ver como") e
  exige o `customer` em `cockpit.clientes` (FK).

  O formato é detectado pela extensão, pelo `Content-Type` ou pelo primeiro
  caractere do conteúdo — não há duas rotas. O CSV vira o mesmo dicionário do
  JSON (`_csv_para_body`) e segue pelo mesmo caminho de gravação.

  **CSV aceito** — cabeçalho `MODULO, TABELA, DESCRICAO, DT_LEITURA, SEMANA,
  QTDE`. Tolerâncias que já existem porque o arquivo vem do Protheus:
  delimitador `,` `;` `TAB` ou `|` (detectado por `csv.Sniffer`); encoding
  `utf-8`/`utf-8-sig`/**`cp1252`**/`latin-1`; cabeçalho com ou sem acento e em
  qualquer caixa; `DT_LEITURA` em `dd/mm/aaaa hh:mm`, ISO ou `AAAAMMDD`;
  `SEMANA` no formato `2026-W33` (só o número entra em `medicoes.semana`).
  Sinônimos de coluna: `QTDE|QUANTIDADE|REALIZADO|REGISTROS`,
  `ESTIMATIVA|META`, `DATA_PREV|PREVISAO`, `DT_LEITURA|DATA|DATA_MEDICAO`.
  Uma medição por data distinta encontrada no arquivo. Colunas opcionais
  (`ESTIMATIVA`, `ETAPA`, `RESPONSAVEL`, `STATUS`, `FILTRO`, `DATA_PREV`), quando
  presentes, ligam de volta o modo com % e semáforo.

### Exportar HTML e rascunho no Gmail

`relatorioCadastrosHTML()` monta um relatório **autocontido** a partir dos dados já
na tela — estilo inline, sem Tailwind e sem `<script>`, porque o mesmo HTML serve
para três destinos: arquivo solto, corpo de e-mail e impressão. Conteúdo: cabeçalho
do cliente/projeto, os 4 KPIs, registros por módulo, evolução por medição e todas
as tabelas agrupadas por módulo.

- **⬇ Exportar HTML** — download via `Blob`, nome
  `status-cadastros-<customer>-<AAAAMMDD>.html`.
- **✉ Rascunho no Gmail** — modal com Para/Cc/Assunto (assunto já preenchido) →
  `POST /api/gmail/rascunho`, que faz **IMAP APPEND** na conta do usuário logado.
  Nada é enviado: o e-mail nasce em Rascunhos.

A App Password fica cifrada (Fernet) em `cockpit.gmail_credenciais`, com a chave
derivada do `SESSION_SECRET` da Vercel — **trocar o `SESSION_SECRET` invalida todas
as credenciais salvas**, e cada usuário salva a sua de novo pela própria tela. A
senha nunca volta para o front. Rotas: `GET/POST/DELETE /api/gmail/cred` (o POST
valida fazendo login IMAP de verdade antes de gravar).

Quando não há credencial, `/api/gmail/rascunho` responde **428** e o front abre o
modal "Conectar o Gmail"; ao salvar, ele reabre o modal de e-mail de onde parou —
por isso o helper `api()` expõe `erro.status`. A pasta de rascunhos é achada pela
flag `\Drafts` do IMAP, não pelo nome (`[Gmail]/Drafts` vs `[Gmail]/Rascunhos`
muda com o idioma da conta). Depende de `cryptography` no `requirements.txt`.

### Migração do schema `monitcad` (11/08/2026)

Os dados reais estavam no schema **`monitcad`** (`clientes`, `medicoes`,
`estimativas`) — 41 medições do Olim importadas em 10/08/2026 — enquanto as
`cockpit.monitcad_*` estavam vazias. Decisão: **`cockpit` é o canônico** e o
schema `monitcad` foi migrado para lá.

- `cockpit.monitcad_tabelas` ganhou a coluna **`modulo`** (o schema legado traz o
  módulo Protheus por tabela).
- Índice único `monitcad_medicoes (customer, data_medicao)` — deixa upload e
  migração idempotentes.
- A ligação é `monitcad.clientes.codigo` (`OLIM`, um slug) →
  `cockpit.monitcad_projetos.slug`, com `customer = TFEHXQ00`. **Não confundir o
  slug com o `customer`.**
- `monitcad.estimativas` está vazia: sem ela não há % nem semáforo, só contagem.
  Popular a partir do `TABELAS_MONITOR.TXT` do cliente resolve.

### Segurança

- As três `cockpit.monitcad_*` estavam com **RLS desabilitado** — corrigido em
  11/08/2026 (RLS ligado, sem policy: só o backend por `DATABASE_URL`).
- `public.monitcad_gravar_medicoes(...)` é `SECURITY DEFINER` e era executável
  por `anon`/`authenticated`, o que furava o RLS. `EXECUTE` revogado. Quem grava
  agora é o backend ou o `POST /api/monitcad/<customer>/upload`. **Se algum script
  de importação usava a chave anon via RPC, ele passa a receber permission
  denied** — o rollback é `grant execute on function
  public.monitcad_gravar_medicoes(text,text,text,jsonb,text) to anon;`.
- As duas RPC de leitura (`monitcad_clientes`, `monitcad_historico`) continuam
  abertas ao `anon` — pendência conhecida.

## 4. Aba Transição — painéis do cliente

O HTML do painel (status por atividades, transição de GP) **não entra no git**:
este repo é público e o arquivo carrega plano de atividades, consultores, horas e
GAPs do cliente. Ele vive em `cockpit.paineis_cliente (customer, slug, html…)`,
RLS habilitado sem policy (só service_role).

- `GET /api/paineis` — painéis dos clientes que o usuário enxerga; devolve
  `pode_subir` (admin). A aba filtra pelo `customer` do projeto aberto: um painel
  só abre direto, vários mostram um seletor, nenhum mostra o estado vazio.
  A publicação também mira sempre esse `customer` — só o slug é perguntado.
- `GET /painel/<customer>/<slug>` — serve o HTML no iframe; exige sessão **e**
  passa por `deny_customer()`. Por isso não pode morar em `web/` (estático livre).
- `POST /api/paineis/<customer>/<slug>?titulo=…` — publica/atualiza o HTML. Admin.

`static_assets()` passou a exigir sessão para **qualquer** `.html` (antes só
`index.html`), fechando a porta para painéis futuros colocados em `web/`.

## Como publicar o painel do Olim

1. Entrar como admin e abrir um projeto do Olim (cliente `TFEHXQ00`).
2. Aba **Transição** → "⬆ Publicar painel (.html)" → slug `transicao` → escolher o
   `Olim_Status_Atividades.html`.
3. O painel passa a abrir para todo usuário com o cliente `TFEHXQ00` liberado.
