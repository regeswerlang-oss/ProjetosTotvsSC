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

**Não testado:** Oracle e SQL Server reais (o SQL passou pela trava do
SqlSeguro e pelo stub, não por um banco) e a base da Cresol, que ainda não tem
o TSCMONITREST publicado nem o ⚙ Ambiente cadastrado.
