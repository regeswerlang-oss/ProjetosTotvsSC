# Movimentos: de volume para cobertura de cenários

**Data:** 25/08/2026
**Onde encosta:** MONITCAD (job TLPP + HTML semanal) e dashboard de projetos (`ProjetosTotvsSC`, aba Cadastros → sub-aba Movimentos)

## O problema

A medição de movimentos hoje conta linha de tabela: "SD2 = 4.132". Isso responde
"a base tem movimento?" e não responde a pergunta que decide go-live:
**qual cenário ainda não rodou?**

Numa virada, o que dá errado não é o volume — é o cenário que ninguém emitiu.
Venda para contribuinte de outro estado, NCM com ST, baixa com adiantamento,
transferência entre contas. Todos aparecem como "tem movimento" numa contagem
por tabela, e como buraco numa quebra por dimensão.

## A decisão

Movimento passa a ser medido em **combinações de dimensões**, não em total por
tabela. Duas análises na primeira volta:

| Análise | DIM1 | DIM2 | DIM3 | DIM4 |
|---|---|---|---|---|
| `SD2_FISCAL` | UF | CONTRIBUINTE | NCM | CFOP |
| `SE5_BANCARIO` | OPERACAO | SENTIDO | TIPO_DOC | TIPO_TITULO |

As colunas são genéricas (`DIM1..DIM4` + `DIM1_NOME..DIM4_NOME`) de propósito:
incluir `SD1_ENTRADA` ou `SD3_ESTOQUE` depois não muda layout de arquivo, nem
tabela no banco, nem tela.

**Métrica: só quantidade.** `QTDE` (linhas do movimento) e `QTD_DOC`
(documentos/títulos distintos). Valor fica de fora — a pergunta é cobertura, e
valor puxa a conversa para conferência contábil, que é outro assunto.

## As três peças

### 1. `MONITCAD_D5_movimentos_dimensoes_ORACLE.sql`

Roda no console do TCloud e exporta CSV. Mesmo desenho do D4: CTE +
`ALL_TABLES` + `DBMS_XMLGEN`, nenhuma tabela referenciada direto, então cliente
sem SIGALOJA/sem módulo não derruba a query — o bloco só não aparece.

Diferenças em relação ao D4:

- **Parâmetros num lugar só** (`PARAM`): sufixo da empresa e período
  (`DT_INI`/`DT_FIM`, char AAAAMMDD). Acabou o Find/Replace de `010`.
- **Junções de verdade**: SD2 → SA1 (UF `A1_EST` e contribuinte `A1_CONTRIB`)
  → SB1 (NCM `B1_POSIPI`). CFOP vem do próprio item (`D2_CF`).
- `GROUP BY TRIM(coluna)`, nunca a expressão inteira. Oracle só aceita no
  SELECT o que é derivável do agrupamento, e agrupar pela coluna crua deixa
  padding gerar linha duplicada.

Layout de saída:

```
ANALISE ; DESCRICAO ; DIM1_NOME ; DIM1 ; DIM2_NOME ; DIM2 ;
DIM3_NOME ; DIM3 ; DIM4_NOME ; DIM4 ; PERIODO ; DT_LEITURA ; SEMANA ;
QTDE ; QTD_DOC
```

### 2. Classificação bancária que não perde informação

A categoria de operação (`ADIANTAMENTO`, `TRANSFERENCIA ENTRE CONTAS`,
`BAIXA A RECEBER`, `BAIXA A PAGAR`, `COMPENSACAO`, `ENCARGOS / DESCONTOS`,
`TARIFAS`, `APLICACAO / EMPRESTIMO`, `CAIXA / CHEQUE / LOJA`,
`ESTORNO / CANCELAMENTO`) sai de um `CASE` sobre `E5_TIPODOC` + `E5_TIPO` +
`E5_RECPAG` + `E5_SITUACA` + `E5_MOTBX` + `E5_ORIGEM`.

Duas regras merecem nota:

- **Adiantamento antes de baixa.** A baixa de um título RA tem
  `E5_TIPODOC = 'VL'`, igual a qualquer outra baixa a receber. Classificar pelo
  tipo do título (`E5_TIPO IN ('RA','PA')`) antes de olhar o TIPODOC é o que
  faz adiantamento aparecer como adiantamento.
- **Transferência entre contas é o ponto fraco.** `TR` no dicionário é
  *transferência para carteira descontada*, não entre contas. A FINA100 grava o
  tipo escolhido na tela (`TB - Transferência Bancária`), e esse conteúdo varia
  por release e por customização. Por isso há duas regras — `TIPODOC = 'TB'` e,
  como rede, movimento com `E5_ORIGEM` da FINA100 sem tipo de título — e a
  confirmação é feita na primeira medição do cliente.

**A dimensão guarda o código, o rótulo fica na descrição.** `DIM3` traz `VL`, não
`VL Baixa de título`. O texto legível vai para `DESCRICAO` (no SQL) e para um mapa
no front. Se o rótulo morasse na dimensão, corrigir uma palavra do texto
transformaria cenário coberto em faltante.

O que sustenta isso: **as dimensões cruas saem no arquivo**. TIPODOC, tipo do
título, motivo da baixa e rotina de origem estão em `DIM3`, `DIM4` e
`DESCRICAO`. Rótulo errado se conserta no de-para, sem rodar a query de novo.
E o balde `(A CLASSIFICAR)` é proposital: é a fila de trabalho do consultor na
primeira medição, não um erro.

### 3. Esperado x observado

A query só sabe o que **aconteceu**. O que **deveria** acontecer é combinado com
o cliente e mora em dois lugares equivalentes:

- `\system\CENARIOS_MONITOR.TXT` — lido pelo job TLPP, mesma lógica do
  `TABELAS_MONITOR.TXT` (config por cliente, fonte genérico).
- `cockpit.monitmov_cenarios` — editável no painel.

Layout do TXT, com `*` como coringa:

```
ANALISE;DIM1;DIM2;DIM3;DIM4;DESCRICAO;ESPERADO;ETAPA;RESPONSAVEL
SD2_FISCAL;SC;SIM;*;*;Venda para contribuinte em SC;S;REALIZACAO;Fiscal
SD2_FISCAL;SP;NAO;*;*;Venda consumidor final SP;S;REALIZACAO;Fiscal
SE5_BANCARIO;ADIANTAMENTO;RECEBIMENTO;*;*;Adiantamento de cliente;S;REALIZACAO;Financeiro
SE5_BANCARIO;TRANSFERENCIA ENTRE CONTAS;*;*;*;Transferência entre contas;S;REALIZACAO;Financeiro
```

Status de cada cenário esperado:

| Status | Regra |
|---|---|
| `COBERTO` | tem linha observada que casa e `QTDE > 0` |
| `FALTANTE` | esperado (`ESPERADO = S`) e sem movimento |
| `OPCIONAL` | `ESPERADO = N` e sem movimento — documenta, não cobra |
| `NAO PREVISTO` | observado sem cenário esperado que case |

Não há status de atraso: o TXT tem `ETAPA`, não data. Prazo por cenário só faria
sentido com uma data por etapa, e essa data hoje não existe em lugar nenhum —
inventar uma seria transformar a etapa num prazo que ninguém combinou.

`NAO PREVISTO` não é erro: numa base de produção é o normal no começo. Vira
sinal quando o cliente já fechou a lista de cenários — aí é operação fora do
combinado.

## Por que não medir valor

Foi decidido conscientemente: a análise responde *cobertura*, e valor
convidaria a comparar com o razão contábil — outra pergunta, outra periodicidade,
outro público. `QTD_DOC` já separa "50 itens de uma nota só" de "50 notas".

## O que muda em cada entregável

- **SQL D5** — arquivo novo em `_entregas/`.
- **Dashboard** — `cockpit.monitmov_dimensoes` e `cockpit.monitmov_cenarios`;
  importação do CSV do D5; sub-aba Movimentos com cobertura, faltantes e a fila
  `(A CLASSIFICAR)`; o botão "🗄 Script SQL · movimentos" passa a gerar o D5.
- **HTML semanal** — seção "Cobertura de cenários" no `dashboard.template.html`
  (placeholder `{{BLOCO_MOVIMENTOS}}`), alimentada pelo job, no e-mail de segunda.
- **Job TLPP** — `LoadCenarios` / `MedirMovimentos` / `CobreCenarios` /
  `HtmlMovimentos` em `MONITCAD.tlpp`. O bloco inteiro é **opcional**: sem
  `\system\CENARIOS_MONITOR.TXT` o job roda exatamente como antes, e falha na
  medição de movimento não derruba o e-mail de cadastros. Janela em
  `MOV_PERIODO_DIAS` no `.env` (0 = base inteira).

O SQL do job é portável de propósito — nada de `NVL` nem de concatenação com
`||`/`+`, que mudam entre Oracle e SQL Server. "Campo vazio" é testado com
`IS NULL OR = ''`: no Oracle pega o primeiro, no SQL Server o segundo.

## Ordem de adoção

1. Roda o D5 no cliente e olha o resultado **antes** de combinar cenário nenhum:
   a lista observada é a melhor pauta para a reunião.
2. Ajusta o de-para bancário com o que caiu em `(A CLASSIFICAR)`.
3. Escreve o `CENARIOS_MONITOR.TXT` com o cliente, cenário a cenário.
4. Só então liga a cobrança semanal — antes disso o painel mostraria faltante
   de cenário que ninguém combinou.
