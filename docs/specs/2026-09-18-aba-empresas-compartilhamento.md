# Aba Empresas e Compartilhamento (MONITEMP)

*18/09/2026 — laboratório: AÇOSUL COMERCIO (`TFESR000`). Escopo inicial: RH.*

## O problema

Cadastros responde **quanto** foi carregado. Numa carga vinda de sistema legado a
pergunta que quebra o go-live é outra: **onde** foi carregado. Três erros típicos:

- tudo entrou na empresa 01 (`SRA010`) e a `SRA030` nem existe — ou existe vazia;
- o campo filial ficou em branco numa tabela **exclusiva**, ou preenchido numa
  tabela **compartilhada**;
- o código de filial é de outra empresa, ou não está na SM0 (`0301` dentro da
  `SRD010`, `9999`).

Contagem por tabela não enxerga nenhum dos três.

## A decisão: dois passos, e o primeiro é manual

| Passo | Script | Sobe por | Grava em |
|---|---|---|---|
| **P0** leitura da SM0 | `scriptSM0()` — SYS_COMPANY + existência das tabelas do escopo e da SX2 por empresa | ⬆ Subir SM0 / ⚡ Coletar SM0 | `cockpit.monitemp_sm0` (substitui a leitura anterior daquela base) |
| **P1** medição | `scriptEmpresas()` — empresa × tabela × conteúdo do campo filial, SX2 ao lado | ⬆ Subir medição / ⚡ Coletar agora | `cockpit.monitemp_medicoes` + `_itens` |

O P1 é **montado a partir do P0**: empresas e filiais viram literais do script.
É de propósito: a estrutura de empresas precisa ser lida e conferida com o cliente
antes de o monitoramento existir. Sem isso o script mede a estrutura errada e o
número chega bonito.

Gerador único: `web/assets/js/monitemp-sql.js` (navegador e node). O modal da aba e
os arquivos de `_entregas` saem do mesmo código.

## Layout de saída (idêntico em Oracle e SQL Server)

P0: `EMPRESA; FILIAL; NOME_EMPRESA; NOME_FILIAL; CNPJ; LEIAUTE; SIZEFIL; SX2;
QTD_TABELAS; TABELAS_EXISTENTES; DT_LEITURA; SEMANA`

P1: `EMPRESA; NOME_EMPRESA; LEIAUTE; TIPO; TABELA; DESCRICAO; TABELA_FISICA;
SITUACAO; SX2; FILIAL; FILIAL_TIPO; NOME_FILIAL; QTDE; DT_LEITURA; SEMANA`

- `SITUACAO`: `NAO EXISTE` (não há tabela física) · `VAZIA` (existe, 0 ativos) ·
  `COM DADOS` · `SEM CAMPO FILIAL`.
- `SX2`: `X2_MODOEMP|X2_MODOUN|X2_MODO` da SX2 **da própria empresa** (`E|E|C`), ou
  `SEM SX2` / `SEM REGISTRO NA SX2`.
- `FILIAL`: o conteúdo real agrupado (`(branco)`, `0301`, `03`...).
- `FILIAL_TIPO`: `BRANCO` · `FILIAL` (código da SM0) · `PARCIAL` (prefixo — nível
  empresa/unidade) · `FILIAL DE OUTRA EMPRESA` · `NAO CADASTRADA NA SM0`.

## Consistência (servidor, `_consistencia()`)

Tamanho esperado do conteúdo = soma dos níveis do leiaute até o último nível
**exclusivo**: `X2_MODO=E` → código inteiro; `X2_MODOUN=E` → empresa+unidade;
`X2_MODOEMP=E` → só empresa; tudo `C` → branco. Resultados: `OK`,
`PREENCHIDA EM TABELA COMPARTILHADA`, `BRANCO EM TABELA EXCLUSIVA`,
`TAMANHO n - ESPERADO m`, `FILIAL DE OUTRA EMPRESA`, `NAO CADASTRADA NA SM0`.
Calculada na gravação, com o leiaute que veio na própria linha — o script fica
simples e a regra muda num lugar só.

## Dialetos

- **Oracle**: nada é referenciado direto. Dono/existência por `ALL_TABLES`, coluna
  filial e `X2_MODOEMP/X2_MODOUN` por `ALL_TAB_COLUMNS`, leitura por
  `DBMS_XMLGEN` (`XMLTABLE` para a distribuição, `XMLQUERY` para a SX2). Metadado
  em `META`, SQL montado em `SQLS` (lição do console TCloud). Tabela inexistente
  recebe uma consulta vazia em `DUAL` — nunca depende da ordem de avaliação.
- **SQL Server**: não há SQL dinâmico dentro de um SELECT. A existência fica
  **congelada no P0**: tabela que não existia sai como `NAO EXISTE` sem ser lida.
  Criou tabela nova → refazer o P0 e gerar o P1 de novo.
- Ambos: só SELECT, uma consulta, sem `;` no fim, ASCII puro. Passam pelo
  `SqlSeguro()` do TSCMONITREST (`DBMS_XMLGEN` não casa com a palavra `DBMS_`).

## Como foi testado

Laboratório com **Oracle Free 23** e **SQL Server 2022** reais (docker), SYS_COMPANY
com 3 empresas/5 filiais, SX2010/SX2030 (sem SX2020) e casos plantados: SRA010 com
filial completa, parcial (`01`), branco e deletado; SRA020 vazia; SRA030 inexistente;
SRD010 com filial de outra empresa e `9999`; CTT010 compartilhada em branco;
SRJ010 sem campo filial (Oracle). P0 → P1 rodados nos dois bancos; depois o fluxo
inteiro pelo app (Flask + Postgres local + stub do TSCMONITREST executando o SQL no
banco): salvar script, coletar SM0, gerar P1 a partir da SM0 gravada, coletar,
ler a aba. Tela conferida no Chromium.

Dois bugs pegos só executando: `ISNULL` do SQL Server truncava
`SEM REGISTRO NA SX2` em `SEM R` (tamanho do 1º argumento → `COALESCE`); e o
`sx2=false` vindo do JSON do painel era lido como "tem SX2", gerando leitura de
`SX2020` inexistente.

## ORA-32031 no release do cliente (22/09/2026)

O P0 rodou aqui em Oracle Free 23 e falhou na base da Açosul com **ORA-32031 —
*illegal reference of a query name in WITH clause***. O suspeito é o bloco `WITH`
chamado `SX2` convivendo com a coluna `SX2` da saída: alguns releases recusam,
o 23 aceita. Correção: **todo bloco do `WITH` passou a ter prefixo `Q_`**
(`Q_LISTA`, `Q_SM0`, `Q_SX2`…), nos dois scripts e nos dois dialetos. Nenhum nome
de bloco pode mais esbarrar em nome de coluna, alias ou literal. Saída e layout
inalterados — conferido rodando P0 e P1 de novo em Oracle e SQL Server.

**Não testado:** a base real da Açosul (nome das colunas da SYS_COMPANY na release
do cliente, owner, volume da SRD dentro dos 50s da coleta REST) e o console TCloud
com `XMLTABLE`.

## Migração

`docs/sql/2026-09-18-monitemp.sql` (aplicada no Supabase em 18/09/2026): três
tabelas novas com RLS sem policy, e os CHECKs de `monitcad_scripts.tipo` e
`protheus_coletas.tipo` passam a aceitar `sm0` e `empresas`.
