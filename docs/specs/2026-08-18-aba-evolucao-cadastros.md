# Evolução dos cadastros e o CSV que entrava zerado — 18/08/2026

## O que quebrou antes de qualquer tela nova

A medição de 18/08 da Olim (`TFEHXQ00`, base de **teste**) entrou com as **112
tabelas** e `realizado = 0` em todas. Não foi o banco nem o upload: o CSV vinha
do script SQL que a própria aba gera, com as colunas `QTD_REAL` e
`QTD_ESTIMADA`, e `CSV_COLS` não conhecia esses nomes. Coluna não reconhecida
não dá erro — some. O resultado é uma medição válida, completa e zerada, que na
tela parece "não importou nada" e no gráfico parece base esvaziada.

Duas mudanças em `_csv_para_body`:

1. Os aliases entraram (`QTD_REAL`, `QTD`, `QTD_ESTIMADA`, `CONTAGEM`,
   `PREVISTO`…). `PERC_ADERENCIA` e `SITUACAO` continuam ignorados de propósito:
   o dashboard recalcula os dois, e `percentual` vazio quebraria o insert.
2. **CSV sem nenhuma coluna de quantidade agora é erro 400**, com o cabeçalho
   recebido na mensagem. Falhar na importação custa um minuto; descobrir uma
   semana depois que a série está zerada custa a reunião de status.

## A aba Evolução

Não virou uma quinta sub-aba. Virou um par de botões — **Situação atual /
Evolução** — dentro da sub-aba de cadastros, porque cliente e ambiente já estão
escolhidos ali. A visão escolhida é preservada ao pular de Produção para Testes:
quem está acompanhando evolução quer continuar nela.

`GET /api/monitcad/<customer>/evolucao?ambiente=` devolve o retrato bruto: o eixo
de medições e a matriz `tabela → {data: realizado}`. Ranking, consolidação
semanal e deltas são derivados no front (`calcEvolucao`) — uma consulta só, e a
troca de filtro não vai ao servidor.

### Três decisões que mudam o número na tela

**Chave ausente ≠ zero.** `serie` só tem chave nas datas em que a tabela foi
medida. Em 10/08 a Olim tinha 41 tabelas no escopo, em 14/08 já eram 63. Célula
sem chave é `—`, não gera delta, e a tabela entra no ranking como *nova no
escopo* em vez de virar o maior "avanço" da semana.

**Na semana vale a última medição, não a soma.** Cada medição é um retrato do
acumulado; somar as duas medições da S33 dobraria a base. O SQL marca
`fim_semana` com `row_number()` por semana ISO, e a tela avisa quando a semana
teve mais de uma medição, senão o total não bate com o que o usuário lembra.

**Queda é vermelho e ganha bloco próprio.** Em base de projeto, cadastro que
diminui é carga desfeita ou `D_E_L_E_T_` marcado — quase nunca ruído.

E, fechando o círculo com o bug de cima: medição com linhas e `Σ realizado = 0`
rende um alerta no topo da aba, para o próximo import quebrado ser lido como
import quebrado.

### Limite consciente

A matriz mostra as **6 medições mais recentes** e diz quantas ficaram de fora
("Mostrando as 6 medições mais recentes de 8"). A tendência (sparkline SVG
inline, sem biblioteca) considera a série inteira.

## Testado com

Playwright sobre `web/index.html` com a API mockada: fixture de 5 medições em 4
semanas ISO (uma semana com 2 medições, uma tabela que entra no meio, uma que
cai, uma medição zerada) e outra de 8 medições para o corte de colunas. Confere
KPIs, série semanal, ranking, filtros, foco preservado na busca e ida e volta
entre as duas visões — mais o console limpo. As duas SQLs foram rodadas contra o
Supabase real antes de virarem código.
