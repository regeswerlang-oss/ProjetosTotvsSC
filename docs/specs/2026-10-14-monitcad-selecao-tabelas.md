# 2026-10-14 · Cadastros — seleção de tabelas por projeto, catálogo e ajustes do Cássio

Origem: e-mail do Cássio Gularte (GP Digitro), "Ajuste Controle de Cadastros TSC", 14/10/2026.

## O que foi pedido × o que foi feito

| # | Pedido | Causa encontrada | Ajuste |
|---|---|---|---|
| 1 | Script não salva quando alterado | O salvamento funcionava (o script dele de 05/10 estava gravado). O modal **abria sempre no gerado** e o salvo ficava atrás de "Carregar salvo": quem reabria via outro texto e concluía que não tinha gravado. | Havendo script salvo, o modal abre nele. Aviso quando a seleção de tabelas mudou depois do script salvo. |
| 2 | Oracle: tirar o `;` do fim | O gerador fechava sempre com `ORDER BY 1, 2;`. | Oracle sai sem `;` (cadastros e movimentos). O POST do script tira o `;` final quando o dialeto é Oracle, no front e no back. |
| 3 | Tabelas com zero não aparecem | Os zeros estavam no banco; a Situação atual **recolhia os módulos sem carga** (OMS, Systax), escondendo as linhas. | Todos os módulos abrem expandidos. Tabela marcada na seleção e ainda fora da medição aparece como **Aguardando medição**, com faixa de aviso no topo. |
| 4 | Incluir tabelas | — | DA0, DA1, ACO (Faturamento) e SAL (Compras) no catálogo e na seleção da Digitro, mais SA3 (Financeiro, decisão de 23/09). GFE "tabela de frete": aguardando o Cássio confirmar com o consultor. |
| 5 | Tela de checkbox por projeto | — | Botão **☑ Tabelas monitoradas** no rail de Cadastros. |
| 6 | Gestor cadastra tabela nova | — | Formulário "Cadastrar / editar tabela no catálogo" no mesmo modal. |

## Modelo

- `cockpit.monitcad_catalogo` — **global**, uma linha por alias do Protheus (`^[A-Z][A-Z0-9]{2}$`):
  módulo, descrição, filtro padrão, `painel` (cadastro/movimento, mesma lista de `TABELAS_MOVIMENTO`),
  `origem` (padrao/manual). Carga inicial: tudo o que já foi medido em algum cliente (módulo mais
  frequente) + `PADRAO_MONITCAD` + as 4 do Cássio → 162 tabelas.
- `cockpit.monitcad_selecao` — **por projeto** `(customer, tabela)`; `modulo`/`filtro` nulos usam o do
  catálogo, preenchidos valem só ali (ex.: SA3 em Financeiro na Digitro).
- SQL em `docs/sql/2026-10-14-monitcad-catalogo-selecao.sql` (já aplicado no Supabase).

## Regras

- Fonte do script gerado, nesta ordem: **seleção** → última medição → conjunto núcleo.
- Projeto sem seleção: nada muda. Ao abrir o modal pela 1ª vez, já vêm marcadas as da última medição.
- Salvar seleção regrava o conjunto inteiro numa transação. Opção (marcada por padrão) de regravar
  também o script salvo, no dialeto/sufixo dele.
- Tabela só sai do catálogo se for `manual` e nenhum projeto a usar; as demais se desmarcam.
- Filtro aceita só a condição do WHERE (recusa `;`, comentário e comandos).
- Rotas: `GET/POST /api/monitcad/catalogo`, `DELETE /api/monitcad/catalogo/<tabela>`,
  `GET/PUT /api/monitcad/<customer>/selecao`. Escrita: equipe TOTVS, fora do "ver como".

## Digitro (000348D0) após a mudança

Seleção com 47 tabelas (42 da medição de 14/10 + SA3, DA0, DA1, ACO, SAL). Script de cadastros salvo
regravado em Oracle, sufixo 010, sem `;`. A próxima medição precisa rodar esse script para as 5
novas saírem de "Aguardando medição".
