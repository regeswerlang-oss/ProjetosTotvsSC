# Abas globais + Cadastros (MONITCAD) + Transição — 11/08/2026

Agrupa no app **Projetos TOTVS SC** (`projetos-vercel`) três visões que antes
viviam em arquivos soltos, e sobe a barra de abas do detalhe do projeto.

## 1. Navegação global

`<nav id="app-tabs">` logo abaixo do header, sticky colado nele (a altura real do
header vai para a CSS var `--hdr`, medida por `ResizeObserver` — o header cresce
quando entra a faixa amarela do "ver como").

| Aba | View | Conteúdo |
|---|---|---|
| Projetos | `#view-lista` / `#view-detalhe` | comportamento anterior, intacto |
| Cadastros | `#view-cadastros` | status de carga dos cadastros (MONITCAD) |
| Transição | `#view-transicao` | painel de status entregue ao cliente |

`setApp(nome)` troca a view; ao voltar para "Projetos" o app volta para onde
estava (lista ou detalhe), sem perder o projeto aberto.

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
- `POST /api/monitcad/<customer>/upload` → carga manual do
  `historico-semanal.json` (o mesmo do projeto *Monitoramento Cadastros*).
  Idempotente: regrava a medição inteira quando a data já existe. Bloqueado
  durante simulação ("ver como") e exige o `customer` em `cockpit.clientes` (FK).

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
  `pode_subir` (admin).
- `GET /painel/<customer>/<slug>` — serve o HTML no iframe; exige sessão **e**
  passa por `deny_customer()`. Por isso não pode morar em `web/` (estático livre).
- `POST /api/paineis/<customer>/<slug>?titulo=…` — publica/atualiza o HTML. Admin.

`static_assets()` passou a exigir sessão para **qualquer** `.html` (antes só
`index.html`), fechando a porta para painéis futuros colocados em `web/`.

## Como publicar o painel do Olim

1. Entrar como admin → aba **Transição** → "⬆ Publicar painel (.html)".
2. Informar `TFEHXQ00/transicao` e escolher o `Olim_Status_Atividades.html`.
3. O painel passa a abrir para todo usuário com o cliente `TFEHXQ00` liberado.
