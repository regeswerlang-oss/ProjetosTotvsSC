# Diagnóstico de Sobrevivência + Pendências do cliente (28/10/2026)

*Piloto: DIGITRO (`000348D0`). Complementa a aba Radar (spec 2026-10-27-aba-radar.md).*

**Pedido:** um diagnóstico vivo de cadastros, movimentos, fluxos e contabilização,
com duas visões: a **interna** (coordenação), com o que precisamos definir e correr
atrás, e a do **cliente**, com as pendências de definição e de retorno, dentro do
Dashboard de Projetos.

## O que entrou

| Onde | O quê |
|---|---|
| Aba **Radar** → visão **Estratégico** (padrão) | Marcos com o que trava cada um; KPIs; três listas para correr atrás — *Cobrar do cliente*, *Nossa fila (TOTVS)*, *Decisões que travam marcos* — com "Copiar pauta" (texto para e-mail/reunião). Junta Radar, MIT006 (NoGo), verificações críticas do diagnóstico e Tasks paradas com o cliente. |
| Aba **Radar** → visão **Diagnóstico** | Matriz **processo × camada** (cadastro, movimento, contabilização, fluxo) + definições abertas. Célula = pior cor das verificações. Detalhe com valor/total/amostra por base, erro da consulta, SQL e avaliação manual (cor + nota). Botões ⟳ Coletar Produção / Teste. Perfil da contabilização do legado (ECD). |
| Aba nova **Pendências** (`pendencias`, liberável) | Visão do cliente: *Aguardando a empresa*, *Com a TOTVS*, *Prontidão por processo*, *Concluídas*. Fonte: MIT006 espelhada + itens do Radar com `visivel_cliente` (texto para o cliente e retorno esperado) + recorte do diagnóstico (só cor e número). |
| Item do Radar | Campos novos: **Visível ao cliente**, **Texto para o cliente**, **Retorno esperado/recebido**. |

## Decisões que custam caro se desfeitas

1. **Uma consulta por verificação, em paralelo (6).** Campo ausente na base derruba
   só aquela verificação (fica cinza com o erro), não a matriz. Teto de 50 s (Vercel).
2. **Catálogo genérico no repositório, personalização no banco.** O SQL padrão mora em
   `docs/diagnostico/catalogo_padrao.json` (sem dado de cliente — o repo é público).
   O que é do cliente (impeditivo, marco, vínculos Radar/MIT006, lado responsável,
   avaliação manual, metas da regra) fica só em `cockpit.diag_checks`.
   "Atualizar catálogo" (admin) relê o JSON e só troca SQL/camada/processo.
3. **A visão do cliente é recorte do servidor**, não da tela: `/api/pendencias` não
   devolve contexto, SQL, amostra, nota nem verificação marcada como interna.
4. **Sem agendamento automático das consultas por enquanto.** A rota
   `/api/cron/diagnostico` existe (Bearer `CRON_SECRET`), mas o pg_cron só será
   criado com autorização. Hoje a coleta é pelo botão.
5. **MIT006 continua sendo a planilha oficial.** `cockpit.mit006_itens` é espelho de
   leitura, atualizado pela leitura agendada; ninguém edita a MIT006 pelo app.

## Regras de cor (`_diag_status`)

`zero` (problema = 0 é verde; até 10% do total amarelo; `teto: amarelo`),
`minimo` (≥ min verde), `cobertura`/`paridade` (valor ÷ total ou ÷ `meta`),
`info`. Bloco por ambiente na própria regra (`{"producao": {"modo": "info"}}`).
Cor da célula: vermelho > amarelo > cinza > verde; `info` não pinta.

## Dados (SQL em `docs/sql/2026-10-28-diagnostico-pendencias.sql`)

`diag_checks` · `diag_execucoes` · `diag_resultados` (+ `vw_diag_ultimo`) ·
`diag_legado` · `diag_marcos` · `mit006_itens` · colunas novas em `radar_itens`
(+ `vw_radar_itens` e `radar_aplicar_proposta` atualizadas) · fontes novas de
evidência: `os`, `mit006`, `diagnostico`.

## Rotas

| Rota | Portão |
|---|---|
| `GET /api/diag/<c>` | interno |
| `POST /api/diag/<c>/coletar?ambiente=` | interno, fora do "ver como" |
| `POST /api/diag/<c>/check/<id>` | interno (SQL/regra/visibilidade: admin) |
| `POST /api/diag/<c>/catalogo` | admin |
| `GET /api/cron/diagnostico?customer=&ambiente=` | `CRON_SECRET` |
| `GET /api/pendencias/<c>` | `deny_aba(c, "pendencias")` |

## Testes

- `python3 docs/testes/diag-back.py` — regras de cor, sufixo, catálogo aceito pela TSCMONITREST, portões.
- `node docs/testes/diag-front.mjs` — Estratégico, matriz, avaliação manual, coleta, Pendências (interno e cliente).
