# Aba Auditoria de Tabelas — compartilhamento (SX2) e volume, Teste × Produção

*21/10/2026 — pedido do Reges a partir do ticket da Cresol sobre o
compartilhamento das tabelas do Configurador de Tributos (FISA170).*
SQL: `docs/sql/2026-10-21-auditoria-tabelas.sql`.

## O problema

A cliente mandou um De/Para de compartilhamento (perfis em `C C C`, regras em
`E E C` — exclusivo na empresa e na unidade de negócio, compartilhado entre as
filiais da mesma cooperativa). Daí em diante a pergunta passa a ser três:

1. como está a SX2 da base de **Testes**;
2. como está a SX2 da base de **Produção**;
3. quanto cada base ainda falta para chegar no **alvo** — inclusive quantos
   registros vão precisar ter o campo filial convertido junto com a SX2.

Nenhuma aba responde as três juntas:

| Aba | Responde | Não responde |
|---|---|---|
| Estrutura | o alvo (definição da consultoria) | o que a base tem |
| Empresas | uma base por vez, foco na carga da SM0 | Teste × Produção lado a lado |
| Compara | empresas da MESMA base, ao vivo | outra base; volume |
| **Auditoria** | alvo × Teste × Produção + volume por filial | — |

## A decisão

- **O alvo vem da Estrutura** (`cockpit.estrut_tabelas.compart`). Não existe
  segundo lugar para digitar compartilhamento: ter dois seria ter dois alvos.
  Tabela sem `compart` aparece como **Definir**.
- **A coleta guarda** (`cockpit.audtab_coletas` + `audtab_itens`), ao contrário
  da Compara. As duas bases são lidas em momentos diferentes, cada uma pela sua
  REST, e a comparação só existe se a primeira leitura ainda estiver lá quando a
  segunda chegar. Guardar também dá o acompanhamento: o "a converter" tem de cair
  de uma coleta para a outra.
- **Abrir a aba lê o Supabase**; a base só é tocada no **⚡ Coletar**, com
  confirmação dizendo QUAL base. Ler a base errada é o erro caro deste processo.
- **Interna** (`cliente: False`), como Estrutura e Compara. Coletar exige
  `require_interno()`.

## Transporte — duas consultas por base

O mesmo `POST /tscmonit/query` (TSCMONITREST, só leitura):

1. **SX2 + existência**: `X2_CHAVE, X2_NOME, X2_ARQUIVO, X2_MODOEMP, X2_MODOUN,
   X2_MODO` das tabelas do escopo, com a existência física e a do campo filial
   resolvidas no banco por subconsulta escalar (Oracle: `ALL_TABLES` /
   `ALL_TAB_COLUMNS` do `CURRENT_SCHEMA`; SQL Server: `sys.tables` /
   `sys.columns`). Nada de SQL dinâmico — ver as três rodadas de ORA-32031 /
   ORA-00923 em `2026-09-18-aba-empresas-compartilhamento.md`.
2. **Contagem por filial**: um bloco estático por tabela que EXISTE
   (`SELECT 'F22', F22_FILIAL, COUNT(*) … GROUP BY F22_FILIAL`, em `UNION ALL`).
   Tabela ausente nem entra; tabela sem campo filial é contada com filial `*`.
   Citar coluna inexistente derrubaria a consulta inteira (ORA-00904).

Sufixo: o cadastrado no ⚙ Ambiente; sem ele, `empresa + 0` (`01` → `010`).

## Escopo

- Tabelas ativas da Estrutura do cliente (qualquer módulo).
- **Sempre lidas**, mesmo fora do escopo: as estruturais da FISA170 (F2D, F2F,
  F2H–F2M, CJ3 — **não podem mudar**; a aba só vigia se Teste e Produção
  continuam iguais) e os cadastros de referência (SA1, SA2, SB1, SB5, SED, SF4).
- `FOV/FOS/FOT/FOU/FOO` (como vieram no levantamento) são lidas também na
  grafia com zero (`F0V`…). A tela diz qual existe.

Agrupamento: famílias do Configurador de Tributos (`AUD_FAMILIAS`), só rótulo;
tabela fora delas cai no módulo que a Estrutura deu.

## Leitura da tela

Modo sempre em **Empresa · Unidade · Filial**, a ordem da SX2 — igual à
Estrutura e à Empresas.

Situação por base: **No alvo** · **A alterar** · **Fora da SX2** · **Definir**
(sem alvo) · **Referência** · **Estrutural** · **Sem coleta**.

**_FILIAL a converter**: registros cujo conteúdo do campo filial não serve para
o modo ALVO. Tamanho esperado = soma dos níveis até o último exclusivo
(`C C C` → branco; `E C C` → empresa; `E E C` → empresa + unidade; `E E E` →
código inteiro). Mudar o `X2_MODO` sem converter deixa o registro invisível.
O tamanho de empresa/unidade vem da SM0 lida pela aba Empresas; sem ela, da
Estrutura; sem nenhuma, `EEUU` (2+2) — a tela diz qual fonte valeu.

Pontos de atenção calculados na tela:

- tabela do alvo fora da SX2 (alias errado ou tabela não criada);
- perfil mais exclusivo que o cadastro que ele referencia (`F22 × SA1/SA2`,
  `F24 × SB1`) — o fornecedor que não gravou em Testes na Cresol (08/10/2026);
- perfis (F20 e filhos) em níveis diferentes; regras que usam a fórmula CIN
  (F27, F28, F2B, CJ2) em níveis diferentes;
- estrutural com compartilhamento diferente entre Teste e Produção;
- tabelas sem alvo e tabelas com **proposta aberta** na Estrutura (💬).

Clique na linha: volume **por cooperativa** (prefixo empresa + unidade do campo
filial) e **por filial**, nas duas bases. Abaixo da grade, o volume por
cooperativa somado.

## Regras novas na conferência da Estrutura

`cockpit.estrut_regras` ganhou pares `igual` do Configurador (TDN CFGTRIB +
orientação da consultoria fiscal): F20 com cada perfil filho (F21–F26, CIO) e
CIN com F27, F28, F2B e CJ2. Valem para qualquer cliente que definir essas
tabelas — regra sobre tabela que o projeto não usa é ignorada.

## Rotas

| Rota | O que faz |
|---|---|
| `GET /api/auditoria/<customer>` | escopo, última coleta de cada base, propostas abertas, leiaute por base |
| `POST /api/auditoria/<customer>/coletar?ambiente=teste\|producao` | as duas consultas, grava coleta + itens na mesma transação, devolve o GET |

Log em `cockpit.protheus_coletas` com `tipo = 'auditoria'`.

## Como foi testado

- `docs/testes/auditoria-e2e.py` — Flask de verdade + Postgres local + stub do
  TSCMONITREST com duas bases plantadas (F22 `E C C` × `C C C`, F0V com zero,
  SB1 sem tabela física, F2D estrutural divergente, filiais com 2, 4 e 8
  posições). Confere escopo, gravação, `fora_padrao` (62 em Teste, 4 em
  Produção), log e o 404 sem ambiente. O stub aplica um porte do `SqlSeguro`
  com a mesma lista do `aProib` do fonte: os quatro SELECTs passam.
- `docs/testes/auditoria-front.js` — Chromium com o payload REAL do teste
  acima: estado sem coleta, coletar pelo topo (POST na base certa), KPIs,
  alertas, linha F22, detalhe por cooperativa, filtro de situação, celular
  (tabela rola dentro da caixa) e zero erro de JS.
- `teststub.mjs`, `integracoes-front.js` e `testestrutura.py` continuam passando.

## Dicionário entre as bases: SX3 e SX6 (21/10/2026, segunda entrega)

Pedido do Reges no mesmo dia: a comparação Teste × Produção passa a incluir o
dicionário. SQL: `docs/sql/2026-10-21-auditoria-dicionario.sql`.

- **SX3 — só as tabelas da auditoria** (escopo + estruturais + referência).
  Campo que existe numa base só, ou com tipo/tamanho/decimal diferente. O SX3
  inteiro passa de 90 mil linhas — não cabe nos 50s da função nem faz sentido
  aqui: a pergunta é "estas tabelas estão iguais nas duas bases?".
- **SX6 — inteiro**. Parâmetro não tem escopo: o que muda o cálculo fiscal pode
  estar em qualquer `MV_`. Três sabores, como na Compara: **só numa base**,
  **filiais diferentes** (o conjunto de `X6_FIL` muda — em branco vale para todas)
  e **conteúdo diferente** (comparado sem espaços nas pontas, até 200 caracteres).
- **Por que não é a aba Compara**: a Compara compara empresas da MESMA base e
  agrega no banco. Entre bases não há banco em comum — cada uma tem sua REST —,
  então a diferença é calculada aqui, no `GET`, e volta só o que diverge.
- **Coleta**: são quatro consultas por base (SX2, volume, SX3, SX6). SX3 e SX6
  **não são fatais**: estouro de limite, timeout ou recusa viram
  `erro_dic` na coleta, a SX2/volume grava igual e a tela diz qual leitura faltou.
  Comparação só com as duas bases tendo lido aquele dicionário.
- **CSV com separador `;` fixo e sem aspas** (`_aud_csv`): o Sniffer do
  `_proto_linhas_csv` adivinha o separador pelas primeiras linhas, e conteúdo de
  parâmetro cheio de vírgula pode enganá-lo. A REST já troca `;` e quebra de
  linha por espaço; aspas o SQL troca.
- **Retenção**: o SX6 inteiro por coleta pesa. Só as **3 últimas coletas** de
  cada base guardam SX3/SX6 (`AUD_DIC_MANTER`); SX2 e volume ficam sempre.
- **Tela**: dois blocos recolhíveis abaixo da grade — SX3 aberto, SX6 recolhido
  (pode passar de mil linhas; fechado nem gera DOM) —, cada um com filtro por
  tipo de divergência e busca, limitados a 500 linhas visíveis. Os pontos de
  atenção resumem os dois.

Testado no `auditoria-e2e.py` (A2_NOME 40 × 60, campo só em uma base, MV com
conteúdo/filial diferente, conteúdo com vírgula, aspas e ponto, SX6 truncado sem
derrubar a coleta, retenção em 3 coletas; oito SELECTs pela trava do SqlSeguro)
e no `auditoria-front.js` (blocos, recolhido, filtros e busca).

## Base sem REST: scripts para o console TCloud + upload (21/10/2026, terceira entrega)

A base de Testes da Cresol não tem o TSCMONITREST publicado. A mesma coleta
passa a poder ser feita à mão — **🗄 Scripts SQL** e **⬆ Subir resultado** no
rail e no topo da aba.

- **Os scripts são os MESMOS SELECTs da REST** (`_aud_sql_sx2`, `_aud_sql_contagem`,
  `_aud_sql_x3`, `_aud_sql_x6`), com um cabeçalho de comentário em ASCII dizendo
  cliente, base, sufixo e banco. Sem `;` no fim.
- **Dois passos, como P0 → P1 da aba Empresas**, e pelo mesmo motivo: a contagem
  só pode citar tabela e coluna que existem (ORA-00942/00904 derrubam a consulta).
  - Passo 1: Scripts **1 (SX2 + existência), 3 (SX3) e 4 (SX6)** — independentes.
  - Passo 2: **Script 2 (contagem por filial)**, montado a partir da última
    coleta daquela base (REST ou upload). Sem coleta, o modal diz que está
    aguardando o Script 1.
- **Banco e sufixo**: os do ⚙ Ambiente quando ele existe (mesmo sem REST, o
  cadastro guarda os dois); sem cadastro, o modal deixa escolher.
- **Upload** (`POST /api/auditoria/<customer>/upload?ambiente=`): um ou vários
  CSVs de uma vez, em JSON `{arquivos:[{nome, texto}]}`. Cada arquivo é
  reconhecido **pelo cabeçalho** (`AUD_TIPOS_CSV`), não pelo nome; separador
  `;` ou `,`, cabeçalho com aspas e BOM aceitos (export do console/SQL Developer).
  - Com o Script 1 no pacote → **coleta nova** (`origem = 'upload'`).
  - Sem ele → **completa a última coleta de upload** daquela base (janela de 7
    dias), regravando o que já tinha e sobrepondo o que chegou. Gravação é a
    mesma `_aud_gravar` da REST; a coleta antiga sai na mesma transação.
  - Script 2 sem Script 1 antes → 409 com o caminho. Contagem de tabela que o
    Script 1 não listou é descartada e listada na resposta.
- **Selo da base** mostra "upload do console" no lugar do environment da REST.
- Conteúdo do SX6 tem aspas trocadas por espaço também no parser: o SQL já
  troca, mas o CSV do console pode trazer o original, e os dois caminhos
  precisam comparar igual.

Testado no `auditoria-e2e.py`: base de Testes sem ambiente cadastrado, scripts
(ASCII, sem `;`, pela trava do SqlSeguro), upload do passo 1 com CSV em vírgula
+ aspas + BOM e um arquivo desconhecido (ignorado), Script 2 montado só com o
que existe, upload do passo 2 completando a coleta sem duplicar, **mesmo
`fora_padrao` (62) da coleta pela REST**, e o 409 do Script 2 sem o 1.
`auditoria-front.js`: modal de scripts e upload de dois arquivos.

### Primeira execução real — base de Testes da Cresol (SQL Server, 21/10/2026)

1. `'SYS_CONTEXT' is not a recognized built-in function name` — o modal gerou o
   dialeto Oracle (padrão sem ⚙ Ambiente). A escolha de banco/sufixo passou a
   ficar lembrada por cliente × base no navegador, e o modal traduz os dois
   erros típicos de dialeto trocado.
2. Erro **468** `Cannot resolve the collation conflict between
   "Latin1_General_BIN" and "Latin1_General_100_CI_AS_KS_WS_SC"` — a SX2 do
   Protheus vem em `Latin1_General_BIN` e o catálogo (`sys.tables`,
   `sys.columns`) na collation do banco. As duas comparações do Script 1 levam
   `COLLATE DATABASE_DEFAULT` nos dois lados. Vale também para a coleta pela REST.

### Detalhamento por filial e descrição nos alertas (21/10/2026)

- Coluna **Variações filial T / P**: quantos conteúdos distintos o campo filial
  tem em cada base. A linha abre (▸) uma tabela **uma linha por variação**, com
  Teste e Produção lado a lado, a cooperativa (prefixo empresa + unidade) e a
  situação daquela variação contra o modo alvo ("tamanho 8, alvo espera 4",
  "preenchida — alvo compartilhado", "em branco — alvo exclusivo"). Contagens
  diferentes entre as bases ficam destacadas.
- **Pontos de atenção levam a descrição da tabela** junto do alias
  (`F22 · Perfil trib. de participantes`): da Estrutura, ou o X2_NOME lido.
- Modo (`C C C`) não quebra mais em duas linhas na grade.

**Não testado:** Oracle e SQL Server reais (o SQL passou pela trava do
SqlSeguro e pelo stub, não por um banco) e a base da Cresol, que ainda não tem
o TSCMONITREST publicado nem o ⚙ Ambiente cadastrado.
