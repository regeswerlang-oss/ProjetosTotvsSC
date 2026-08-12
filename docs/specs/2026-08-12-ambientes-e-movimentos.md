# Produção × Teste e a aba Movimentos — 12/08/2026

## O conceito: ambiente é dimensão, não filtro

Cadastros e movimentos podem vir da **base de produção** ou da **base de teste**, e
as duas leituras **nunca se somam nem se sobrescrevem**. O ambiente entrou como
coluna nas tabelas, não como filtro de tela:

- `cockpit.monitcad_medicoes.ambiente` e `monitcad_tabelas.ambiente`
  (`producao` | `teste`, default `producao` — tudo que já existia veio de produção).
- A unicidade virou `(customer, data_medicao, ambiente)`: a mesma data pode ter
  uma medição de produção e outra de teste convivendo.
- `monitcad_projetos.ultima_medicao` só é atualizada por upload de **produção** —
  o marco do projeto é a base real.

## Uma aba no topo, quatro sub-abas dentro

A barra de cima continua enxuta — `… ┊ GAPs | Cadastros | Transição`. As quatro
combinações vivem **dentro** de Cadastros, numa segunda linha de abas:

`Cadastros·Produção | Cadastros·Testes | Movimentos·Produção | Movimentos·Testes`

E existem só **dois sub-painéis** (`#sub-cadastros` e `#sub-movimentos`): o mapa
`SUBABAS` diz qual painel cada sub-aba usa e com qual ambiente. Duplicar o DOM só
para trocar uma palavra na query seria o dobro de manutenção para o mesmo
resultado. A chave de cache de cada painel é o par **cliente + ambiente**.

`state.sub` guarda a sub-aba, então voltar para Cadastros devolve você para onde
estava.

Um selo colorido ao lado do nome do cliente diz em qual base você está —
verde para produção, âmbar para teste.

## A pergunta na importação

Todo upload passa por um modal **"De qual base veio este arquivo?"**, com a base da
aba aberta pré-selecionada. Não é confirmação decorativa: subir um CSV de teste em
cima da série de produção contamina o acompanhamento do projeto e não há como
saber depois qual linha veio de onde.

Se o arquivo for de uma base diferente da sub-aba aberta, a tela **muda para a
sub-aba correspondente** depois de importar — deixar a aba "Produção" exibindo dado de
teste é exatamente a confusão que o modal existe para evitar.

## Botão "🗄 Script SQL"

Gera o script que levanta os números no banco do Protheus, no mesmo padrão do job
MONITCAD (`COUNT(*)` com `D_E_L_E_T_=' '`), já no layout do CSV que a aba importa.
Ajustável na hora: sufixo das tabelas (`SA1` + `010` = `SA1010`), dialeto
(SQL Server ou Oracle) e, em movimentos, o período. Copia ou baixa `.sql`.

O cabeçalho do script avisa em MAIÚSCULAS de qual base ele deve ser rodado —
o script é o ponto onde o erro de ambiente nasce.

Fonte das tabelas: as da última medição daquele cliente/ambiente; se não houver,
um conjunto núcleo embutido (42 tabelas de cadastro, 16 de movimento).

**Movimentos**: o 4º campo do conjunto é a **coluna de data do documento**
(`C5_EMISSAO`, `F2_EMISSAO`…), usada no `BETWEEN` do período. Tabelas sem coluna
de data (SB2, SD4) contam o total e são listadas no cabeçalho do script para você
não achar que o período foi aplicado nelas.

## Armadilha: a UNIQUE antiga

`monitcad_medicoes` tinha uma **constraint** `UNIQUE (customer, data_medicao)`
criada antes do conceito de ambiente — com nome `..._key`, diferente do índice
`..._uk` que a migração dropou. Ela sobreviveu e barrava a primeira importação de
teste numa data que já existia em produção:

```
UniqueViolation: duplicate key value violates unique constraint
"monitcad_medicoes_customer_data_medicao_key"
```

Removida em 12/08/2026. A unicidade válida é só
`monitcad_medicoes_customer_data_amb_uk (customer, data_medicao, ambiente)`.
**Ao mexer em unicidade, conferir constraints E índices** — `\d` da tabela mostra
os dois, mas `drop index` não derruba uma constraint.

## Movimentos: o que existe e o que falta

Existe: as duas abas, a leitura (`GET /api/monitmov/<customer>?ambiente=`), o
script SQL e as tabelas `cockpit.monitmov_medicoes` / `monitmov_itens` — mesmo
desenho dos cadastros, com campos para quantidade, **valor** e período.

Falta: **o layout de importação**. O botão "⬆ Importar movimentos" existe e abre
um modal explicando o que falta, em vez de fingir que funciona. Três perguntas
fecham o layout:

1. Uma linha por tabela (como nos cadastros) ou uma linha por documento?
2. Entra **valor** além da quantidade?
3. O período é fixo (mês) ou vem no arquivo?
