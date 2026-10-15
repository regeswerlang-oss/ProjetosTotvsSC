# Gestão de GAPs — 🧭 Interno → GAPs (15/10/2026)

Painel de administração dos GAPs (tickets com a tag `GAP`) de **um cliente**:
fase, % concluído, datas, dependências, Gantt e edição da Task no padrão
"Ações 1-a-1" do Console de Triagem.

## Duas origens — não misturar
| Dado | Onde vive | Grava em |
|---|---|---|
| % concluído (`progress`), início, vencimento, fim | **Task** (Tasks SC) | Task (credencial do usuário) **e** cópia em `cockpit.gap_plano` |
| Status, responsável interno, estimativa | Task | Task |
| Ocorrência (Externo/Interno) | Task | Task (`POST /tickets/history`) |
| Fase + observação | Supabase | `cockpit.gap_plano` + `cockpit.gap_fase_hist` |
| Dependências | Supabase | `cockpit.gap_dependencias` |

Toda escrita na Task usa `token_tasks_usuario()` (ver
`2026-10-15-minha-conta-credenciais.md`). Sem credencial → HTTP 428 e o front
abre **👤 Minha conta**. Gravação direta, **sem fila**; cada escrita entra em
`cockpit.action_queue` como `aplicado` ou `erro` (tipos novos: `progresso`, `datas`).

Escrita = GET → merge → PUT do ticket **inteiro** (`put_ticket_usuario`, port de
`buildPayload` do cockpit `src/lib/tasks-sc/mutations.ts` — mexeu num, mexa no outro).
Mesmo comportamento do cockpit: `observer` vai vazio no PUT.

## Leitura
`GET /api/gestao-gaps/<customer>` — `cockpit.tickets` + tag GAP, campos da Task do
espelho `totvs.tickets.payload` (sync 15 min; fallback `tickets.raw`). Logo após
gravar, o espelho ainda está velho: se `gap_plano.updated_at` > `totvs.tickets.synced_at`,
vale a cópia do painel.

## Rotas
| Rota | |
|---|---|
| `GET /api/gestao-gaps/clientes` | clientes com GAP (contagem) |
| `GET /api/gestao-gaps/<customer>` | GAPs + fases + status + usuários |
| `POST /api/gestao-gaps/<uuid>/task` | `progress`, `start_date`, `due_date`, `end_date`, `status`, `user_assigned`, `time_estimate` |
| `POST /api/gestao-gaps/<uuid>/ocorrencia` | `{texto, tipo: "1"|"2"}` |
| `GET /api/gestao-gaps/<uuid>/ocorrencias` | espelho `cockpit.ocorrencias` |
| `POST /api/gestao-gaps/<uuid>/fase` | `{fase_id, observacao}` + histórico |
| `GET /api/gestao-gaps/<uuid>/historico-fase` | trocas de fase |
| `POST /api/gestao-gaps/<uuid>/dependencias` | `{depende_de: [uuid…]}` — substitui; recusa ciclo e GAP de outro cliente |

Todas `require_interno`; o customer sempre vem do banco (`_guarda_gap`), nunca do front.

## Tela
- Filtros: cliente (lembrado no navegador), busca, fase, mostrar cancelados.
- KPIs: GAPs/horas, % concluído ponderado pelas horas, atrasados (vencimento < hoje e < 100%),
  sem vencimento, conflito de dependência (começa antes da dependência vencer, ou já tem %
  com dependência < 100%).
- **Tabela** (ordem por vencimento), **Gantt** (barras início→vencimento, preenchimento = %,
  linha de hoje, contorno âmbar = conflito, vermelho = atrasado) e **Funil** por fase.
- Modal: Ações 1-a-1 (Fase · % e datas · Dependências · Status/Responsável/Estimativa ·
  Ocorrência), Detalhes, Histórico (trocas de fase + ocorrências). Selo **● TASK** = grava no
  Tasks SC; **● PAINEL** = só Supabase. Trocar a fase sugere o `pct_padrao` dela no campo de %.

## Fases (cockpit.gap_fases, editável por SQL)
Levantamento 10% · Desenvolvimento 40% · Validação Consultoria 70% · Homologação 85% · Produção 100%.
SQL: `docs/sql/2026-10-15-gestao-gaps.sql` (já aplicado).

## Fica para depois
Tags (add/remove), descrição, responsável do cliente, setas desenhadas no Gantt, cadastro
de fases pela tela.

## Botões ⓘ (15/10/2026)
Cada KPI tem um ⓘ com a regra do número (popover único, fecha com clique fora/Esc),
o campo **% concluído** do modal tem ⓘ explicando que é o `progress` da Task e que a
fase só sugere o %, e a barra tem **ⓘ Critérios** (quais GAPs aparecem). Textos no
objeto `INFO` dentro do módulo da Gestão de GAPs — mudou a regra, mude o texto.
