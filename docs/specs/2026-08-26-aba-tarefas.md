# Aba Tarefas — 26/08/2026

Décima aba do detalhe do projeto, ao lado de GAPs. Mesma leitura, **sem a tag
GAP obrigatória**: entra todo ticket do cliente e o recorte é o que o usuário
marcar no filtro de tags.

## Por que é uma cópia, e não um componente compartilhado

Decisão do usuário, com o custo na mesa. A aba GAPs é onde se decide escopo com
o cliente e não pode regredir por causa de um ajuste feito aqui. Em troca,
**melhoria numa não chega sozinha na outra** — ordenação, coluna nova ou correção
precisam ser aplicadas duas vezes. Quem mexer numa das duas: olhe a outra.

O que **é** compartilhado, de propósito: `DECISAO`, `GAP_STATUS`, `chipsTags`,
`selosGap`, `semAcento` e o **drawer** (`abreGap`). A rota de detalhe
`/api/gaps/ticket/<uuid>` autoriza pelo cliente **dono** do ticket e nunca
exigiu a tag GAP — então serve para qualquer tarefa, sem rota nova.

## Três diferenças de comportamento

1. **Sem o `join ... raw_tag = 'GAP'`** (`SQL_TAREFAS`): entra todo ticket.
2. **A tag `GAP` aparece** na coluna e no filtro. Na aba GAPs ela é removida do
   array — lá toda linha tem a tag por definição, então só ocuparia espaço. Aqui
   ela é o que separa "o que já virou GAP" do resto, e precisa ser marcável.
   `eh_gap` vem no payload para o KPI, evitando uma segunda consulta.
3. **Filtro de tags é OU por padrão**, com botão para E. Numa tela de garimpo o
   normal é juntar assuntos ("INTEGRACAO ou PRIORIDADE"); cruzar é a exceção. Na
   aba GAPs continua sendo só E, e isso não mudou.

O contador no botão mostra o modo junto com a quantidade — `(2 E)` / `(2 OU)`.
Sem essa dica, duas telas com o mesmo par de tags marcado e resultados diferentes
pareceriam bug.

## KPIs

Tarefas no filtro · horas estimadas · em aberto (o que não está Resolvido nem
Cancelado) · marcadas como GAP.

## Volume

Dígitro 268 tickets (78 GAP, 190 não-GAP, 29 sem tag nenhuma), 71 tags distintas;
2.100 tickets na base inteira. Carrega tudo de uma vez, sem paginação — é o mesmo
que a aba GAPs já faz e o maior cliente tem poucas centenas.

## Cuidado ao mexer

- **`data-gap` é o atributo da linha nas DUAS abas.** É o que faz o drawer
  funcionar sem alteração. Renomear aqui quebra o clique.
- O botão E/OU vive dentro de um `<details>`: sem `preventDefault()` o clique
  fecha o dropdown antes de aplicar o filtro.
- Tag que some do cliente é retirada do filtro no reload (`tar.tags.delete`) —
  senão a tela ficaria filtrando por algo que não existe mais e mostrando zero.

## Como conferir

`/tmp/tarefas_check.py`: aba presente, 20 itens sem filtro (12 GAP + 8 comuns),
`GAP` entre as tags do filtro, união **cresce** e interseção **encolhe** ao marcar
a segunda tag, ordenação inverte, kanban monta as colunas, drawer abre e o export
da aba sai com conteúdo.
