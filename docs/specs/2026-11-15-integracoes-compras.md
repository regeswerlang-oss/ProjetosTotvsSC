# Aba Integrações — grupo Compras × Transmite × Contas a Pagar

*15/11/2026. Piloto: CRESOL (`TFCTQI00`), Base Produção, unidade 010000.*

**Pedido.** Depois da implantação do TOTVS Transmite e do Compras (com o
workflow de aprovação) na Cresol, acompanhar a unidade que entrou em produção:
pedidos de compra ainda em aberto, documentos de entrada que vieram ou não do
Transmite e o contas a pagar que veio ou não do documento de entrada. A carga
é pela REST que já existe (`TSCMONITREST`), no mesmo modelo dos grupos
Transmite, CRM e EAI — sem fonte novo na base do cliente.

## A unidade não é parâmetro

A filial é a unidade que entrou em produção, e isso já está decidido com o
cliente. Fica numa tabela no código, por cliente (`COM_IMPLANTACAO`):

| Cliente | Filial | Início | De onde veio |
|---|---|---|---|
| `TFCTQI00` Cresol | `010000` | 26/10/2026 | Sequência das ondas definida pela Débora (22/10, via Juci): só a 010000 primeiro; depois 900000/900001; depois 020000 e 050000; só então as cooperativas. OS de 26/10 do Murilo: Wizard do COMXCOL configurado para a empresa 010000 na virada. |

Próxima onda = acrescentar a filial na tabela (ex.: `("010000", "900000", "900001")`).
`integ_params.com_filiais`/`com_inicio` sobrepõem a tabela, só para uso interno.

O filtro é por **prefixo** (`F1_FILIAL LIKE '010000%'`): casa com o campo
filial de qualquer tamanho e não usa `RTRIM` na coluna, então o índice vale.
Cliente sem unidade na tabela gera SQL com `1 = 0` e um cartão cinza: o grupo
nunca lê a base inteira por engano.

A **janela** de SF1 e SE2 começa no início da unidade (26/10), limitada a
`COM_JANELA` = 120 dias; o corte da base (⚙ "A partir de") vale se for mais
recente. Pedidos em aberto não têm janela: todo pedido com saldo conta, e os
emitidos antes da virada aparecem destacados no texto do cartão.

## O fluxo que o grupo confere

```
SC7 (pedido) ── C7_CONAPRO B ──► SCR (alçada, CR_STATUS 02) ── aprovador
     │ liberado
     ▼
Transmite → SDS (Monitor) ── DS_STATUS ≠ P ──► XML parado
     │ gerado
     ▼
SF1/SD1 (documento) ── D1_PEDIDO vazio ──► nota sem pedido
     │                 F1_STATUS vazio ──► pré-nota
     │ classificada com F1_DUPL
     ▼
SE2 (título) ── E2_ORIGEM MATA10x + casa com a SF1 ──► título de documento
                 senão ──► lançado no Financeiro
```

Origem **Transmite** = nota com registro na SDS (filial, documento, série,
fornecedor, loja — a mesma chave que o SCHEDUPDTRA usa, Central TOTVS
22989114562839). Na Cresol o Importador XML só recebe do Transmite (substituiu
Flows/ROIT). O retorno "Classificada" ao Transmite continua no grupo Transmite.

## Blocos (`_com_scripts`)

Regras de sempre: só `SELECT`, sem `;`, datas como literal calculadas no
Python, `_integ_vazio`/`_integ_preenchido`, sem concatenação de campo,
agrupamento sobre subconsulta (Oracle não aceita `GROUP BY` por apelido).

| id | tipo | o que lê | variantes |
|---|---|---|---|
| `com_pc_resumo` | resumo | SC7 em aberto por `C7_CONAPRO`: pedidos, itens, saldo, há +5 dias, entrega vencida, parciais, em pré-nota, emitidos antes da virada | sem `C7_QTDACLA` |
| `com_doc_resumo` | resumo | SF1 da janela por origem × tipo × pedido × status, com valor e "classificada sem título" | `E2_FILORIG` → `E2_FILIAL` |
| `com_mon_resumo` | resumo | SDS com `DS_STATUS` ≠ P por status, e quantas já estão na SF1 | — |
| `com_cp_resumo` | resumo | SE2 da janela (sem abatimentos) por classe × `E2_ORIGEM`, com saldo e vencidos | `E2_FILORIG` → `E2_FILIAL` |
| `com_pc_lista` | detalhe (500) | itens em aberto, dos mais antigos, com fornecedor | sem `C7_QTDACLA` |
| `com_pc_aprov` | detalhe (300) | SCR `PC`/`IP` com `CR_STATUS = 02`, com o nome do aprovador (SAK) | sem SAK |
| `com_doc_lista` | detalhe (600) | notas fora do fluxo: manual, sem pedido ou em parte, pré-nota, sem título | `E2_FILORIG` → `E2_FILIAL` |
| `com_mon_lista` | detalhe (300) | XML parado no Monitor, um a um | com e sem `DS_EMISSA` |
| `com_cp_lista` | detalhe (600) | títulos lançados no Financeiro e vencidos em aberto | `E2_FILORIG` → `E2_FILIAL` |

## Indicadores (`_com_indicadores`, grupo `compras`)

| chave | valor | nível |
|---|---|---|
| `com_pc_aprovacao` | pedidos com `C7_CONAPRO = B` | verde 0 · amarelo · **vermelho** se algum emitido há mais de `COM_APROV_DIAS` (5) |
| `com_pc_abertos` | pedidos em aberto | informativo (saldo, parciais, pré-nota, rejeitados, antes da virada) |
| `com_pc_entrega` | itens liberados com `C7_DATPRF` vencida | amarelo se houver |
| `com_doc_transmite` | notas normais pelo Transmite `n/total` | amarelo se houver nota lançada fora do Monitor |
| `com_doc_sem_pc` | notas normais sem pedido ou com pedido em parte | amarelo se houver (texto separa Transmite × manual) |
| `com_doc_prenota` | pré-notas | amarelo se a mais antiga passar de `COM_PRENOTA_DIAS` (3) |
| `com_doc_sem_titulo` | classificada com `F1_DUPL` e sem SE2 | vermelho se houver |
| `com_monitor` | XML no Monitor sem documento | vermelho com ocorrência (E) · amarelo com revisão (B) ou pendente |
| `com_cp_origem` | títulos da janela | informativo, com a divisão por classe e o alerta de título do Financeiro |
| `com_cp_vencidos` | títulos vencidos em aberto | amarelo se houver |

Só notas de tipo normal (`F1_TIPO` N) entram nas contas de origem e de pedido:
devolução e complemento não têm pedido nem passam pelo Transmite.

## Tela

Checkbox **Compras × CP** na barra da aba. A caixa mostra a unidade e o início
lidos do `_meta` da coleta (`com_filiais`, `com_inicio`), em três partes —
Compras, Documento de entrada, Contas a pagar. Situação e motivo sempre em
texto ("Entrega vencida", "Fora do Monitor", "Sem título"), nunca só cor. Cada
cartão abre o detalhe correspondente.

## A validar na base da Cresol

- `E2_ORIGEM` dos títulos do documento (esperado MATA100): a coluna aparece crua
  no resumo do contas a pagar; se vier outro valor, ajustar `COM_ORIGEM_DOC`.
- `CR_STATUS = 02` como "aguardando o aprovador": conferir no X3_CBOX do campo.
- Leiaute da filial: o prefixo `010000` cobre o código exato e, se o campo for
  maior, as filiais que começam por ele.

## Para ligar na Cresol

1. Rodar `docs/sql/2026-11-15-integracoes-compras.sql` no Supabase (aplicada em 15/11/2026).
2. Cadastrar o ⚙ Ambiente da Produção `TFCTQI00` (URL `…/rest/tscmonit`, token
   `MV_TSCTOKN`, banco, sufixo). Hoje não há linha da Cresol em `protheus_ambientes`.
3. Marcar ☑ TOTVS Transmite e ☑ Compras × CP na barra e clicar ⚡ Coletar agora.

## Testes

- `python3 docs/testes/integracoes-compras-back.py` — unidade fixa, SQL dos
  blocos e níveis dos cartões com retrato simulado.
- `node docs/testes/integracoes-compras-front.js` — cartões, caixa, tabelas,
  motivos e clique no cartão.
- Os SQL também foram executados num Postgres local com tabelas no formato do
  Protheus (campos preenchidos com espaço), cobrindo as variantes.

## Scripts SQL sem a base cadastrada (15/11/2026)

O modal **🗄 Scripts SQL** passou a ter, no topo, os grupos e o banco
(Oracle, SQL Server, Postgres). Marcar ali só muda os scripts mostrados — não
grava nada no ⚙ Ambiente. Sem o ⚙ Ambiente cadastrado, cliente com unidade em
`COM_IMPLANTACAO` abre com Transmite + Compras marcados (os outros, com RH,
como antes). Rota: `GET /api/integracoes/<customer>/scripts?grupos=compras&banco=mssql`
(grupo ou banco desconhecido = 400). Serve para rodar no console TCloud
enquanto a REST da Cresol não está cadastrada no painel.

## Script único e importação manual (15/11/2026)

**Script único.** Com o grupo Compras marcado, o modal 🗄 Scripts SQL mostra no
topo o **script único**: os 9 blocos numa consulta só (`UNION ALL`), com a
coluna `BLOCO` e as colunas genéricas `C01…C17`, todas texto
(`CAST(… AS VARCHAR(250))`, igual em Oracle, SQL Server e Postgres). A 1ª linha,
`com_meta`, traz cliente, filiais, o dia em que o script foi gerado e o início
da janela — um agregado sem `GROUP BY` sobre `SX6 … WHERE 1 = 0`, que devolve
sempre uma linha nos três bancos. Cada bloco usa a 1ª variante (dicionário
padrão da 12) e perde o `ORDER BY` (o SQL Server não aceita em tabela
derivada); a importação reordena (`COM_ORDEM`). As datas de "vencido" e
"parado" vão como literal: gerar no dia em que for rodar.

**Importação.** `POST /api/integracoes/<customer>/importar?ambiente=` (multipart
`arquivo`), botão **⬆ Importar arquivo** no menu da aba. Aceita CSV (separador
`;`, `,`, TAB ou `|`, tirado do cabeçalho) e XLSX, até 20 MB, em cp1252 ou UTF-8.
O arquivo volta às colunas de cada bloco (`COM_COLUNAS`), decimal com vírgula
(NLS do Oracle) vira ponto nas colunas numéricas (`COM_NUMERICAS`), listas acima
do limite do bloco ficam truncadas e marcadas. Grava em `cockpit.integ_medicoes`
como uma coleta (`environment = 'arquivo'`, `_meta.origem = 'arquivo'`,
`_meta.arquivo`, `_meta.script_gerado_em`, `_meta.avisos`) e no log de coletas.
Não precisa do ⚙ Ambiente. Recusa: arquivo de outro cliente (pelo `com_meta`),
arquivo sem a coluna `BLOCO`, cliente sem unidade em `COM_IMPLANTACAO` (409).
Sem a linha `com_meta`, bloco ausente vira "Não veio no arquivo" (cinza); com
ela, bloco sem linha é resultado vazio legítimo.

A barra de estado mostra "Importado de arquivo (nome) · script gerado em …" e
os avisos, e não acusa "Grupos alterados" em medição importada.

## Grupos marcáveis antes de cadastrar a base (15/11/2026)

Sem o ⚙ Ambiente não há linha em `protheus_ambientes` para gravar os grupos,
e as caixas de "Monitorar" ficavam travadas. Agora ficam liberadas: sem
cadastro, a escolha é guardada no navegador (`localStorage tsc.integ.grupos`,
por cliente × base), não chama o servidor e vale para a tela e para o modal
🗄 Scripts SQL. Sem escolha, valem os grupos da última medição (ex.: a
importada do arquivo). Com a base cadastrada, volta a gravar no servidor
(`POST /grupos`) como antes.
