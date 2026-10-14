# Aba Integrações — filas Quírons, Ahgora e eSocial SST da base do cliente

*13/10/2026 — piloto: RACLI LIMPEZA (`TFEHM600`), base de Produção.*

**Pedido:** coletar de forma automática, como já fazemos com Cadastros e
Movimentos, os dados de monitoramento das integrações de RH do cliente, numa aba
nova do dashboard, por botão, com um painel para acompanhar falhas, tempo e erros.

Base técnica: a proposta de monitoramento enviada à Racli em 12/10/2026
(`Racli_Monitoramento_Integracoes.html`), seções 4 (indicadores) e 5 (SQL).

## A pergunta que a aba responde

**"As integrações estão rodando, quanto atrasaram e o que falhou?"** Cada
integração guarda a fila numa tabela do Protheus, com data e status. O erro de
cada uma aparece num lugar diferente (GPEM924, GPEM929, Monitor do Middleware,
Integrador 2.0), e é por isso que ninguém vê a falha a tempo. A aba junta as filas
numa tela só.

| Grupo | Fila | O que a coleta lê |
|---|---|---|
| Quírons (NG) | `RJP` (fila do JOB GPEM923), `RU7` (histórico de envio) | pendentes por tabela (`RJP_DTIN` vazio), envios por dia nos últimos 7 dias (`RJP_DTIN`/`RJP_HORAIN`), erros por dia e código HTTP (`RU7_SUCESS = 'N'`), as 100 pendências mais antigas |
| Ahgora PontoWeb | `RUM` (JOB GPEM943 / tela GPEM929) | resumo por tipo × operação × status com a contagem de atrasados; até 300 registros para agir (status 3, status 4 integrado antes de hoje, status 0 com movimento antes de hoje), com o nome da `SRA` |
| eSocial SST | `RJE` (Middleware) | S-2210, S-2220 e S-2240 por status; até 100 não transmitidos (`RJE_STATUS <> '4'`) |
| Configuração | `SX6` | `MV_RHNG`, `MV_HISTQUI`, `MV_RHMSGNG`, `MV_URIQR`, `MV_GPEURLP`, `MV_RHAHGOR`, `MV_INTEGPW`, `MV_FINAPW`. **Nunca** `MV_EMAILQR`, `MV_SENHAQR`, `MV_AHGORA1/2`: são credenciais |
| Laudo Quírons | healthcheck REST | `GET <raiz REST>/api/rh/v1/integrationcheck/healthcheck` (laudo P1–P7 / Q1–Q3 do Verificador GPEM926) |

Fora do alcance da coleta: o que o **Quírons lê direto** das APIs do Protheus
(afastamentos, abonos, estabilidade) e os **Resultados Apurados** que o Integrador
2.0 do PontoWeb grava na `RGB`. Isso não passa por fila no Protheus, e a falha só
aparece no Quírons ou nos Logs do Integrador.

## Transporte

O mesmo `POST /tscmonit/query` da coleta de Cadastros (fonte `TSCMONITREST`, só
leitura), com o cadastro do **⚙ Ambiente** (`cockpit.protheus_ambientes`). Não há
script salvo por cliente: os SQL são gerados em `_integ_scripts()` com o
**sufixo** do ambiente e as datas como literal.

Decisões que custam caro se desfeitas:

1. **Um bloco por chamada, não um UNION.** Base sem Ahgora não tem `RUM`. Num
   UNION, o `ORA-00942` derrubaria a coleta inteira; separado, só aquele
   indicador fica cinza ("A tabela RUM010 não existe nesta base"). `_integ_motivo()`
   classifica tabela inexistente (cinza, informação) e campo inexistente
   (dicionário anterior à expedição que criou o campo).
2. **Datas calculadas no Python** (`_cp_hoje()`, fuso de Florianópolis), não
   `SYSDATE`/`GETDATE()`. O mesmo SQL roda em Oracle, SQL Server e Postgres.
3. **Campo vazio = `(RTRIM(c) IS NULL OR RTRIM(c) = '')`.** O DBAccess grava
   espaços; `= ' '` contra um VARCHAR2 de 8 posições nunca casa no Oracle, e
   `RTRIM` de brancos é `NULL` no Oracle e `''` no SQL Server.
4. **Separador fixo `;`** no parser (`_integ_csv`). O Sniffer chegou a escolher
   `:` por causa da URL do `MV_URIQR`.
5. **Ordem dos blocos = prioridade:** resumos → healthcheck → detalhes. Se o
   orçamento de tempo (o `timeout_s` do ambiente, no máximo 50 s) acabar, falta a
   lista, não o número. Bloco sem tempo fica "Não lido".
6. **Resumo truncado é descartado; detalhe truncado é mostrado** com o aviso "as N
   primeiras linhas".
7. **Base fora do ar no primeiro bloco = 502 e nada gravado.** Depois de o
   primeiro bloco responder, falha de rede só marca aquele bloco.
8. O healthcheck usa o **Basic** do ⚙ Ambiente e **não leva o `X-TSC-Token`**,
   que é segredo da nossa rota. A raiz do REST sai da URL do TSCMONITREST
   (`…/rest/tscmonit` → `…/rest`). Respostas: 404 = expedição RH anterior ao
   GPEM926; 401/403 = credencial recusada. O formato exato do laudo não está na
   TDN, então `_integ_health_itens()` procura objetos com identificador e status
   em qualquer nível. **P2 em aviso/401 não pesa**: a TDN diz que, nesse modo, é
   prova de vida do REST.

## Corte por data (13/10/2026)

A primeira coleta real da Racli mostrou o problema: 23 alterações de
funcionário paradas desde 01/12/2025 e 79 inclusões com inconsistência desde
janeiro. Isso é sobra da implantação e já virou outro assunto. Sem um corte, esse
passado deixa o painel vermelho para sempre e esconde o que quebrou ontem.

- **Um corte por base:** `cockpit.protheus_ambientes.integ_desde` (nulo = todo o
  histórico). Na Racli, produção, está com **01/10/2026**.
- **Onde entra:** `RJP_DTGER` (fila e pendências Quírons), `RUM_DATMOV` (resumo e
  detalhe Ahgora) e `RJE_DTG` (eSocial SST). A janela de 7 dias de envios e erros
  encurta quando o corte é mais recente. Os parâmetros SX6 e o laudo não mudam.
- **Na tela:** campo **"A partir de"** no cabeçalho da aba
  (`POST /api/integracoes/<customer>/corte?ambiente=` com `{"desde": "AAAA-MM-DD" | null}`).
  Gravar o corte **não coleta**; a próxima coleta é que passa a usá-lo.
- **O corte usado vai junto com a coleta** (`blocos._meta.desde`). A barra
  mostra "movimentos a partir de dd/mm/aaaa" e, se o corte da base mudou depois
  da última coleta, avisa em âmbar ("Corte alterado… colete de novo"). Um número
  antigo não pode parecer medido com a régua nova.
- O que ficou antes do corte **continua na base**, só não entra no painel. Para
  o histórico inteiro, basta limpar o campo e coletar.

## Motivo da inconsistência (14/10/2026)

**Pedido:** "detalhar que tipo de inconsistência é: cadastro, campo,
indisponibilidade de licença ou integração".

**De onde vem.** A Ahgora devolve texto livre no `/process`, e o Protheus grava
esse texto no memo **`RUM_STAMSN`**, com os erros separados por `|`. É a mesma
mensagem da tela GPEM929 › Status. O lado Protheus também grava ali falha de
chamada (401, 500, licença).

**Como lê o memo pela REST.** No Oracle o DBAccess guarda memo como BLOB:
`UTL_RAW.CAST_TO_VARCHAR2(DBMS_LOB.SUBSTR(RUM_STAMSN, 400, 1))`. A trava do
TSCMONITREST contra `DBMS_`/`UTL_` compara a **palavra inteira**, então
`DBMS_LOB.SUBSTR` passa sem recompilar o fonte. Como o tipo do memo pode variar,
o bloco tem **variantes** (`sqls`), tentadas em ordem: BLOB → CLOB
(`DBMS_LOB.SUBSTR` puro) → sem a mensagem. A primeira que a base aceitar vale
(`variante` e `aviso_variante` ficam no bloco). Tabela inexistente não tenta a
próxima. SQL Server usa `CONVERT(VARBINARY)`. Postgres fica sem mensagem.

**Classificação** (`_integ_classifica`, servidor; `intClassifica`, tela, com a
mesma regra), sobre o texto sem acento e em minúsculas, nesta ordem:

| Categoria | Quem resolve | Exemplos |
|---|---|---|
| 🔑 Licença | TOTVS Cloud / License Server | "Nao existe licenca disponivel no License Server" |
| 🔌 Integração | credencial, rede ou serviço | Unauthorized, 401/403, 5xx, timeout, token, SSL |
| 🗂 Cadastro · duplicidade/conflito | dado conflita do outro lado | "E-mail já cadastrado", "PIS já cadastrado", "afastamento possui intersecção" |
| 🗂 Cadastro · tabela de apoio | cadastro que falta na Ahgora | centro de custo, escala/turno, sindicato, motivo de afastamento, CNPJ, "não encontrado" |
| ✏️ Campo | valor vazio ou inválido no Protheus | "CPF Inválido", "Data de nascimento inválida", obrigatório, formato |
| ❔ Outros | ninguém ainda: vira regra | o texto cru aparece na lista |

"E-mail já cadastrado" é **Cadastro** (duplicidade), não Campo: a ordem das
regras decide. Um registro com `A | B` conta em cada motivo, mas na categoria só
uma vez, na mais grave pela ordem acima.

**Blocos novos/alterados.**
- `rum_motivos`: `TIPO, OPER, MENSAGEM` dos registros com status 3 (respeita o
  corte por data), até 2.000. O servidor resume em `_integ_motivos()` (contagem
  por categoria e lista de motivos com matrícula/CPF mascarados por `…`, para
  agrupar) e grava **só o resumo** na coleta.
- `rum_pendencias` ganhou a coluna `MENSAGEM` (400 caracteres).

**Na tela (caixa Ahgora).** Cinco quadros com a contagem por categoria e quem
resolve. Depois, a lista de motivos (texto, categoria e subtipo, se afeta
Funcionário ou Afastamento, ocorrências) e a coluna **Motivo** na lista de
registros para agir, com o selo da categoria e a mensagem. O cartão "Ahgora —
inconsistências" passa a dizer "Por motivo: Cadastro 7 · Campo 2 · Licença 2".

## Indicadores (`_integ_indicadores`, função pura)

| Chave | Verde | Amarelo | Vermelho |
|---|---|---|---|
| `quirons_fila` | ≤ lote (`MV_RHMSGNG`, padrão 100) e de hoje | até 3× o lote, ou mais antiga de ontem | > 3× o lote, ou mais antiga com 2+ dias |
| `quirons_envios` | houve envio hoje (ou fila vazia) | — | fila pendente e nenhum envio hoje (JOB parado?) |
| `quirons_erros` | 0 em 7 dias | erros, pico ≤ 10/dia | qualquer 401 (o JOB aborta o lote) ou pico > 10/dia |
| `quirons_laudo` | todos OK | aviso | erro em qualquer item |
| `ahgora_inconsistencias` | 0 | 1 a 5 | > 5 |
| `ahgora_aguardando` | 0 | — | qualquer status 4 integrado antes de hoje (consulta expirou → Reintegração) |
| `ahgora_nao_enviados` | nenhum status 0 de dia anterior | status 0 de ontem | status 0 com 2+ dias |
| `sst_pendentes` | 0 não transmitidos | pendentes recentes | pendente com 2+ dias |

**Cinza = sem dado** (tabela ausente, `MV_HISTQUI = 0`, healthcheck indisponível,
bloco não lido) e **não piora** a situação geral. A situação geral é o pior nível
entre os não cinzas (`_integ_pior`).

Só o `RJE_STATUS = 4` é tratado como transmitido. Os demais códigos aparecem como
vieram da base: o domínio completo não está confirmado no `X3_CBOX` do cliente.

## Persistência

`cockpit.integ_medicoes` guarda **uma linha por coleta**: nível geral,
indicadores, blocos já em linhas, health, environment, duração e quem disparou. A
série histórica sai daqui, e é ela que mostra se a fila está crescendo.
`cockpit.protheus_coletas` ganhou o tipo `integracoes` (um log por disparo, com as
falhas parciais em `erro`). SQL: `docs/sql/2026-10-13-integracoes.sql`, já
aplicado no Supabase `kpimalwnswxalwbidkog`.

## Rotas

| Rota | O que faz |
|---|---|
| `GET /api/integracoes/<customer>?ambiente=&n=` | última coleta, série (`n` últimas, padrão 60), últimos 10 disparos e o cadastro do ambiente **sem segredo** (só `tem_token`/`tem_senha`). Não toca a base |
| `POST /api/integracoes/<customer>/coletar?ambiente=` | roda os blocos, chama o healthcheck, grava e devolve o mesmo payload do GET |
| `GET /api/integracoes/<customer>/scripts?ambiente=` | os SQL como a coleta manda, sem `;`, para o console TCloud |

Acesso: `require_interno` + `deny_customer` + `deny_aba('integracoes')`. A coleta
passa por `_guarda_ambiente(escrita=True)` e é bloqueada no "ver como". A aba é
**interna** (`cliente: False`) porque o detalhe traz matrícula e nome de
funcionário.

## A tela

- **Cabeçalho:** base (Produção/Testes), **⚡ Coletar agora** e **↻ Atualizar**.
  O rail repete Coletar e traz **🗄 Scripts SQL** e **⚙ Ambiente** (o mesmo modal
  de Cadastros; a aba relê a coleta quando ele fecha).
- **Barra de estado** (`intEstado`, um só lugar decide): coletando; falha da
  coleta (mantém e avisa o retrato anterior); base não cadastrada, sem sufixo ou
  sem senha; nenhuma coleta; **retrato com mais de 24 h** em âmbar.
- **Cartões por grupo:** valor, status sempre com ícone e rótulo (nunca só a
  cor), texto que diz o que fazer e uma linha da evolução, de uma série só e cor
  neutra, com o valor de cada coleta no hover.
- **Caixas recolhíveis:** Quírons, Ahgora e eSocial abertas; Configuração/laudo e
  Histórico fechadas. **Caixa fechada não gera DOM.**
- **Exportar HTML / Rascunho no Gmail** funcionam pelo snapshot da aba
  (`RELATORIOS.integracoes`), com o selo da base.

## Para ligar num cliente

1. Compilar o `TSCMONITREST.tlpp` na base e reiniciar o AppServer do REST
   (`fontes/tlpp/INSTALACAO-TSCMONITREST.md`, no Cockpit Único).
2. No dashboard: Cadastros → **⚙ Ambiente** da base. Informe URL
   (`…/rest/tscmonit`), token (`MV_TSCTOKN`), usuário e senha do Protheus (para o
   healthcheck), banco e **sufixo** (ex.: `010`). Salvar e testar.
3. Aba **Integrações** → **⚡ Coletar agora**.

## Testes

- `docs/testes/integracoes-back.py` — 198 asserções sobre as funções puras: SQL
  (sufixo, datas, sem `;`, sem comando de escrita, sem parâmetro de senha), CSV,
  classificação de erro, itens do laudo e as regras de nível de cada indicador
  (cenário saudável, com problema, base sem Ahgora, histórico desligado).
- `docs/testes/integracoes-rotas.py` — 45 asserções com o Flask de verdade, banco
  em memória e REST fingida: coleta feliz, token só no `/query`, healthcheck na
  raiz do REST com Basic, nada de segredo na resposta, tabela ausente virando
  cinza, healthcheck 404, base fora do ar (502 sem gravar), guardas de sufixo,
  token, ambiente e cadastro, a rota de scripts e o corte por data (gravar, recusar data futura ou inválida, aplicar no SQL, gravar na coleta, limpar).
- `docs/testes/integracoes-front.js` — 55 asserções (Playwright, `/api/*`
  interceptado): abrir não coleta, cartões e rótulos, cinza com motivo,
  sparkline, escape de HTML, caixas sem DOM, coleta pelo topo e pelo rail com a
  barra "coletando", falha mantendo o retrato anterior, troca de base, retrato
  velho, corte por data (campo preenchido, troca grava sem coletar, aviso de corte alterado), modal de scripts, exportação e zero erro de JS.

> O `painel-cp-front.js` tem 7 falhas que **já existiam antes** desta mudança
> (testes do estado "truncado" escritos antes da foto no Supabase, de 06/10).
> Não foram tocados aqui.

## Próximos passos possíveis

- Agendar a coleta diária pelo pg_cron (rota `/api/cron/integracoes` com
  `CRON_SECRET`, no mesmo molde do `cp-lancamento`), para a série não depender de
  alguém clicar.
- Classificar também os erros da Quírons (`RU7_RTN`/`RJP_RTN`) com a mesma régua.
