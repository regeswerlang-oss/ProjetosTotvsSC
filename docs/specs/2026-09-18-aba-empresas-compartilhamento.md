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

## ORA-32031, segunda rodada: XMLTABLE não aceita coluna de CTE (25/09/2026)

Trocar os nomes dos blocos não bastou — a base da Açosul repetiu o ORA-32031. A
causa não era colisão de nome: naquele release o Oracle recusa um `XMLTABLE`
cujo `PASSING` recebe **coluna vinda de um bloco do `WITH`**. O Oracle Free 23 do
laboratório aceita, e foi por isso que passou nos testes.

- **P0**: o texto da consulta à SYS_COMPANY passou a ser montado por **uma
  subconsulta escalar fechada em si mesma** (subqueries aninhadas no `FROM`),
  sem nenhum bloco do `WITH` no caminho do `XMLTABLE`. Os blocos `Q_DONO`,
  `Q_COLS`, `Q_META` e `Q_SQLS` deixaram de existir.
- **P1**: `Q_MODO` e `Q_DIST` passaram a ler de `(SELECT ... FROM Q_SQLS) S` —
  envolver o bloco numa inline view tira a referência direta ao query name, que
  é o que o erro reclama.

Saída e layout inalterados: P0 e P1 reexecutados em Oracle 23 e SQL Server 2022,
resultado linha a linha igual ao da rodada anterior.

**Não testado:** a base real da Açosul (nome das colunas da SYS_COMPANY na release
do cliente, owner, volume da SRD dentro dos 50s da coleta REST) e o console TCloud
com `XMLTABLE`.

## ORA-00923: fim do SQL dinâmico nos dois scripts (25/09/2026)

Envolver o `XMLTABLE` em subconsulta escalar também não passou: a base da Açosul
respondeu **ORA-00923 — *FROM keyword not found where expected***, ou seja, erro
de parse, não de execução. Aquele release simplesmente não digere a subconsulta
dentro do `PASSING`. Em vez de tentar uma quarta variante da mesma técnica,
**o SQL dinâmico saiu dos dois scripts**:

- **P0 Oracle** passou a ler `SYS_COMPANY` direto, sem `DBMS_XMLGEN`/`XMLTABLE`.
  O cabeçalho traz as duas saídas manuais caso a base fuja do padrão: se der
  `ORA-00942`, qualificar com o owner (`"OWNER"."SYS_COMPANY"`); se der
  `ORA-00904` em `M0_LEIAUTE` ou `M0_SIZEFIL`, trocar a coluna por `NULL`.
- **P1** (os dois dialetos) passou a gerar **blocos estáticos por empresa ×
  tabela**, montados no painel a partir da existência já congelada pelo P0.
  Um `UNION ALL` por bloco, nenhum texto de SQL montado dentro do banco.

### Tabela existe mas não tem o campo de filial

Sem SQL dinâmico surgiu um efeito que o dinâmico escondia: citar uma coluna
inexistente derruba a consulta inteira com `ORA-00904`, não só aquele bloco.
Peguei isso no laboratório com a `SRJ010`, que existe sem `RJ_FILIAL`.

- **P0** passou a marcar essas tabelas com `*` colado no nome dentro de
  `TABELAS_EXISTENTES` (ex.: `SRA SRB SRJ*`). Oracle descobre pelo
  `ALL_TAB_COLUMNS`, SQL Server pelo `sys.columns` dentro do `FOR XML PATH`.
- O painel separa isso ao ler o CSV: `tabelas` (nomes limpos) e `semFilial`.
- **P1** gera para elas um bloco de terceiro formato —
  `SELECT '*' AS F, COUNT(*) AS C ... HAVING COUNT(*) > 0` — e a coluna `FILIAL`
  sai como `(sem campo)`, com `SITUACAO = SEM CAMPO FILIAL`.

Laboratório refeito do zero em Oracle Free 23 e SQL Server 2022 com o mesmo
fixture (3 empresas, 5 filiais, `SRA010` com filial cheia/parcial/branca/deletada,
`SRA020` vazia, `SRA030` ausente, `SRD010` com filial de outra empresa e `9999`,
`CTT010` compartilhada em branco, `SRJ010` sem o campo, `SX2010`/`SX2030`
presentes e `SX2020` ausente). Resultado linha a linha igual nos dois bancos,
incluindo `SRJ010 | SEM CAMPO FILIAL | (sem campo) | 2`.

**O que ficou mais simples de quebra:** os dois scripts agora são SQL estático
puro, então rodam igual no console do TCloud, no SQL Developer e pela coleta REST,
sem depender de privilégio em `DBMS_XMLGEN`.

## Escopo cresce: Cadastros Gerais, Financeiro e Contabilidade (28/09/2026)

A aba nasceu só com RH (carga do legado). Entraram mais 9 tabelas, levando o
escopo a **34**:

| Módulo | Tabelas |
|---|---|
| Cadastros Gerais | SA1 Clientes, SA2 Fornecedores, SB1 Produtos |
| Financeiro | SEB Ocorrências CNAB, SEJ Ocorrências de Extrato |
| Contabilidade | CT1 Plano de Contas, CTD Itens Contábeis, CTH Classes de Valor, CT5 Lançamentos Padrão |

SEB e SEJ conferidas na TDN (`FIN0037_CNAB_Carga_de_Dados_Tab_SEB_SEJ`): são a
parametrização do CNAB — ocorrências de retorno e ocorrências de extrato —
carregadas pela própria carga de dados do banco, não digitadas uma a uma. Valem
para este monitoramento justamente por isso: base nova sem elas trava conciliação
e retorno bancário, e ninguém percebe na contagem de cadastro comum.

### Módulo é rótulo, não coluna

O agrupamento por módulo vive **na lista do gerador** (`LISTA_ESCOPO`, campo
`grupo`), não no CSV nem no Supabase:

- O layout do P0 e do P1 não mudou, o importador não mudou, e nenhuma medição já
  gravada virou inválida.
- O painel deriva o módulo da tabela na hora de montar a matriz
  (`MonitEmp.grupoDaTabela`). Tabela que sair do escopo, ou medição antiga com
  tabela que não está mais na lista, cai em **Outros** em vez de desaparecer.
- A matriz ganhou faixa por módulo e um seletor **Módulo** ao lado do filtro de
  tipo. A faixa mostra o tipo (Cadastros / Movimentos) só no módulo que tem os
  dois — hoje só o RH.

`LISTA_RH` passou a se chamar `LISTA_ESCOPO`. A **CTT** ficou em RH de propósito:
entrou pelo escopo do RH (centro de custo do funcionário), ainda que a tabela
seja da Contabilidade.

### O que o laboratório mostrou das novas

Fixture ampliado e rodado em Oracle Free 23 e SQL Server 2022, com as linhas do
P1 passando pelas **funções reais do backend** (`_niveis_leiaute` e
`_consistencia` importadas de `api/index.py`), não por uma cópia da regra:

- `SA1010` compartilhada com filial em branco → OK. `SA2010` exclusiva com
  `0101`/`0102` → OK. `SB1010` existe e vazia → VAZIA.
- `SA1020` medida sem SX2020 na base → `SEM SX2`, que já acende alerta.
- O padrão contábil (`E|C|C`: exclusiva na empresa, compartilhada na filial) é o
  caso novo que valia testar — o campo deve guardar só a parte da empresa:
  `CT1010` com `01` → **OK**; a mesma tabela com branco → **BRANCO EM TABELA
  EXCLUSIVA**; `CT1030` com `0301` → **TAMANHO 4 - ESPERADO 2**.
- `CTD010` com `9999` → alerta pelo tamanho antes do "não cadastrada na SM0":
  as duas regras pegam, a de tamanho vem primeiro.
- `SEJ` e `CT5` ausentes em todas as empresas → `NAO EXISTE` em todas, sem
  derrubar a consulta.

Resultado linha a linha idêntico nos dois bancos (única diferença por desenho: a
`SRJ010` sem campo de filial existe só no fixture Oracle).

**Não testado:** a base real da Açosul.

## A definição sai desta aba (29/09/2026)

A faixa por módulo e o seletor **Módulo**, que entraram no dia 28, saíram. A aba
volta a separar só **Cadastros** e **Movimentos / histórico**.

O motivo não é estético: definir *como deveria ser* — quais tabelas, de qual
módulo, com qual compartilhamento — é trabalho de consultor, feito uma vez, antes
da carga. Isso agora tem casa própria na aba **Estrutura de Empresas**
(`cockpit.estrut_*`), onde o compartilhamento é digitado nos mesmos três níveis
`Empresa · Unidade · Filial` da SX2 e conferido contra as regras da TDN.

Esta aba faz a outra metade: **mede** o que está no banco, pela conexão. O escopo
continua vindo da `LISTA_ESCOPO` do gerador (34 tabelas), com o campo `grupo`
preservado — ele só não é mais usado para desenhar a matriz aqui.

## O escopo passa a vir da aba Estrutura (29/09/2026)

As tabelas medidas não são mais a lista fixa do gerador: vêm de
`cockpit.estrut_tabelas`, ou seja, do que a consultoria definiu na aba
**Estrutura de Empresas** — sugeridas pelo catálogo ou incluídas na mão, `Z*`
inclusive. `GET /api/monitemp/<customer>` devolve `escopo`, o painel traduz para
o formato do gerador (`modulo → grupo`, `tipo` em maiúsculas) e passa em `lista`
para `scriptSM0` e `scriptEmpresas`.

A `LISTA_ESCOPO` das 34 continua no gerador como **padrão**, para cliente que
ainda não definiu nada: medir zero tabelas pareceria erro, não escopo vazio. O
modal do script diz qual das duas origens está valendo, para ninguém rodar um P0
achando que mede uma coisa e medir outra.

Conferido gerando P0 e P1 com um escopo de quatro tabelas — uma delas manual
(`ZZ1`) e uma de movimento (`SE1`) — e checando que só elas entram no SQL, que o
`TIPO` sai certo nas duas, e que escopo vazio cai nas 34.

### Leitura velha contra escopo novo

"Tabelas do escopo" é **congelada no P0**: ela diz o que aquela leitura procurou e
achou. Com o escopo agora vindo da aba Estrutura, mudar a definição depois deixa o
numerador contando de uma lista e o denominador de outra — `25/131`, como se 106
tabelas não existissem na base, quando o P0 daquele dia só procurou 34.

A rota devolve `escopo_mudou` (o `max(definido_em, created_at)` das tabelas ativas
contra o `updated_at` da SM0 gravada) e a tela avisa em cima da estrutura, com o
caminho: **Coletar SM0** → salvar o **Script Empresas** → **Coletar agora**.
Recalcular o numerador aqui seria pior: daria um número que nenhuma leitura
produziu.

## Migração

`docs/sql/2026-09-18-monitemp.sql` (aplicada no Supabase em 18/09/2026): três
tabelas novas com RLS sem policy, e os CHECKs de `monitcad_scripts.tipo` e
`protheus_coletas.tipo` passam a aceitar `sm0` e `empresas`.
