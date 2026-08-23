# Remover SX5, SX6 e SX7 do monitoramento de cadastros

**Data:** 23/08/2026
**Origem:** revisão da aba Cadastros — as três linhas apareciam sempre com
"Sem estimativa", 0%, e números na casa das dezenas de milhares.

## Decisão

SX5 (Tabelas Genéricas), SX6 (Parâmetros do Sistema) e SX7 (Gatilhos) **saem da
análise de cadastros**. São tabelas de *configuração* do Protheus: a contagem é
do dicionário/parametrização que já vem com o produto, não de cadastro que o
cliente carrega durante o projeto. Consequências práticas do que estava lá:

- nunca teriam estimativa (não dá para prever "quantos parâmetros o produto tem"),
  então ocupavam três linhas permanentes em cinza no painel;
- os ~40 mil registros somados distorciam qualquer leitura de volume total;
- a variação semanal (ex.: SX6 +4) refletia ajuste técnico, não avanço de carga.

**Continua valendo o SX5 por grupo** (`SX5_S4` = NCM, `SX5_T3` = Cidades, …).
Aquilo é cadastro de verdade, tem estimativa e entra normalmente pelo
`TABELAS_MONITOR.TXT`.

## O que mudou

- `web/index.html` — `PADRAO_MONITCAD`: removidas as três entradas de
  `Configurador`. O módulo fica com SAH e SM2.
- `api/index.py` — nova constante `TABELAS_IGNORADAS = {"SX5","SX6","SX7"}`,
  aplicada na importação (`POST /api/monitcad/<customer>/upload`). Assim um CSV
  gerado por um script antigo não reintroduz as linhas.
- Supabase (`cockpit`):
  - `monitcad_tabelas` — 24 linhas apagadas (000348D0 produção: 6;
    TFEHXQ00 produção: 9; TFEHXQ00 teste: 9). Nenhum agregado guardado em
    `monitcad_medicoes`, então não houve recálculo a fazer.
  - `monitcad_scripts` — script salvo do 000348D0 (tipo `cadastros`) reescrito
    sem as três tabelas nos blocos `LISTA` e `ESTIMATIVA`.
- Projeto MONITCAD: `_entregas/MONITCAD_D4_contagem_estimativa_ORACLE.sql`
  atualizado no mesmo padrão (12 linhas a menos: 6 SELECT + 6 UNION ALL).

## Para reverter

Basta reincluir as três entradas em `PADRAO_MONITCAD`, esvaziar
`TABELAS_IGNORADAS` e subir de novo as medições — o histórico apagado não volta
sozinho.
