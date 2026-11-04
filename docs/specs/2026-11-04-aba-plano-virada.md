# Aba Plano de Virada — 04/11/2026

*Piloto: DIGITRO (`000348D0`), projeto 000348D025 — Serviços de Implantação.*

**Pedido:** "Desenvolver uma aba no Dashboard de Projetos chamada Plano de Virada
e listar os itens e planos com base no histórico da Dígitro que precisam constar
no plano de virada, melhor período. Botão para inclusão manual, editar a linha e
excluir."

## A pergunta que a aba responde

**"Quando viramos, o que precisa estar pronto até lá, na mão de quem — e o que
ainda impede o Go?"**

## Decisões

1. **Um plano por cliente** (`virada_planos`): data da virada, Go/No-Go,
   congelamento, corte do legado, fim da operação assistida, texto da
   recomendação e as **janelas avaliadas** (jsonb: período, avaliação
   `recomendado | alternativa | evitar`, prós, contras).
2. **Atividades por fase** (`virada_itens`), em nove fases fixas:
   `preparacao → testes → go_nogo → congelamento → corte → carga → dia_d →
   assistida → fechamento`. Cada item tem frente, responsável (lado TOTVS /
   CLIENTE / AMBOS + nomes), início/fim, status, criticidade, **critério de
   Go/No-Go**, referência (Radar, Task, MIT006) e dependência.
3. **Código fixo** `PV-nnn` gerado no servidor (lock por cliente). Excluir é
   lógico (`ativo=false`); o código não é reutilizado.
4. **Liberável ao cliente para consulta** (`"cliente": True`). Incluir, editar,
   trocar status, excluir e mudar as datas do plano: só a equipe TOTVS
   (`require_interno` + `deny_customer`). Os botões têm `data-interno`.
5. **Carga inicial da Dígitro** (`origem='historico'`): 55 itens, 32 critérios
   de Go/No-Go, tirados do comitê de 14/10, reuniões de 01–23/10, inventário de
   e-mails do CP (28/10), Radar (30/10), dossiê de transição (03/11) e
   respostas devidas (04/11). Itens novos pela tela entram como `manual`.
6. **Melhor período (Dígitro): 04/01/2027**, corte em 31/12 e carga de 01 a
   03/01. Justificativa gravada no plano: começa com o exercício contábil e com
   a CBS plena (PIS/COFINS extintos em 01/01/2027), corte em dias sem operação.
   Plano B 01/02/2027; dezembro/2026 e março/2027+ marcados "evitar".

## Dados (schema `cockpit`, SQL em `docs/sql/2026-11-04-plano-virada.sql`)

| Objeto | Papel |
|---|---|
| `virada_planos` | 1 linha por cliente: datas-marco, recomendação, janelas |
| `virada_itens` | atividades do plano por fase |

RLS ligado sem policy (o Flask é o único caminho).

## Rotas

| Rota | O quê |
|---|---|
| `GET /api/virada/<customer>` | plano + itens ativos + `interno` + `hoje` (aba `virada`) |
| `POST /api/virada/<customer>/item` | inclui item (interno) |
| `POST /api/virada/item/<id>` | edita a linha, inclusive só o status (interno) |
| `POST /api/virada/item/<id>/excluir` | exclusão lógica (interno) |
| `POST /api/virada/<customer>/plano` | datas-marco e recomendação, upsert (interno) |

## Tela

Cartão **Melhor período** (data, dias corridos/úteis até o Dia D, marcos com
D−n, recomendação e tabela das janelas) · **linha do tempo por fase** com
marcas de hoje e Dia D · KPIs clicáveis (concluídos, Go/No-Go pendentes,
atrasados, bloqueados, com o cliente) · filtros (busca, fase, frente, lado,
status, só Go/No-Go) · tabela agrupada por fase com status editável na linha,
✎ editar e 🗑 excluir. Exportar HTML/Gmail do rail: `RELATORIOS.virada`.

## Testes

- `python3 docs/testes/virada-back.py` — validação dos campos, aba no catálogo, portão nas 5 rotas.
- `CHROME=/usr/bin/google-chrome node docs/testes/virada-front.mjs` — stub + Chromium com a carga real
  (`virada-fixture.json`): janela, filtros, incluir (validação de datas, HTML escapado), editar,
  status na linha, excluir, datas do plano, visão do cliente sem controles, sem erro de console.
