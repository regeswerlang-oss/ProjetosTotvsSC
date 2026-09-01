# Coleta automática pela REST do Protheus (cadastros e movimentos)

*01/09/2026 — piloto: OLIM AGRO (`TFEHXQ00`), base de testes.*

## O problema

A medição de cadastros e de movimentos sempre teve o mesmo gargalo: **um humano
no meio do transporte**. O fluxo era abrir o modal *🗄 Script SQL*, copiar,
colar no console TCloud, exportar o CSV, voltar ao dashboard e arrastar o
arquivo. Funciona — e foi assim que o Olim e a Dígitro entraram —, mas custa uma
janela de atenção por medição, só acontece quando alguém lembra, e a série
histórica fica com a cara da agenda do consultor, não da evolução do projeto.

O que faltava não era o dado nem a regra de leitura: era **um transporte que
dispensasse o consultor**.

## A decisão

Publicar na base do cliente uma REST mínima que executa **o script que já está
salvo** e devolve **o CSV que já era exportado**. Assim a automação entra pelo
mesmo importador — `_gravar_cadastros()` / `_gravar_movimentos()` —, e as regras
que decidem o que entra (`TABELAS_IGNORADAS`) e em que painel entra
(`_painel_da_tabela`) continuam existindo **uma vez só**. Uma segunda cópia
dessas regras é exatamente como uma tabela de movimento reaparece em Cadastros.

```
Dashboard (Vercel)                          Base do cliente (Protheus)
────────────────────                        ──────────────────────────
cockpit.monitcad_scripts  ──┐
cockpit.protheus_ambientes ─┤ POST /tscmonit/query  ──►  TSCMONITREST.tlpp
                            │  {token, tipo, sql}         · valida: só SELECT/WITH
                            │                             · TCGenQry + FieldGet
   _csv_para_body()  ◄──────┘  {ok, linhas, csv}      ◄──  · CSV ';' em UTF-8
   _gravar_cadastros()  ──►  cockpit.monitcad_medicoes / _tabelas
```

## Contrato da REST (fonte `TSCMONITREST.tlpp`)

| Rota | Uso |
|---|---|
| `GET /tscmonit/ping` | identidade do ambiente: `environment`, `banco`, empresa/filial, `token_ok` |
| `POST /tscmonit/query` | `{token, tipo, sql, limite}` → `{ok, colunas, linhas, truncado, tempo_ms, csv}` |

O fonte **só executa leitura**: a consulta precisa começar em `SELECT`/`WITH`,
não pode ter um segundo comando e não pode conter `INSERT/UPDATE/DELETE/MERGE/
DROP/CREATE/ALTER/TRUNCATE/GRANT/REVOKE/EXEC/CALL/INTO/DBMS_/UTL_/XP_/SP_`. A
checagem roda sobre uma cópia **sem comentários e sem literais** — de propósito:
os scripts reais são cheios de comentário em português, e um `-- delete` numa
explicação não pode derrubar uma consulta boa, assim como um `DROP` escondido
num comentário não pode passar. A comparação é por palavra inteira, senão
`D_E_L_E_T_` — que aparece em toda consulta do Protheus — bloquearia tudo.

Autenticação em duas camadas: **token** (`X-TSC-Token`, comparado com o
parâmetro `MV_TSCTOKN` da base) e, opcionalmente, o **Basic** do usuário
Protheus, se o `[HTTPURI]` estiver com segurança ligada. Sem `MV_TSCTOKN`
preenchido a rota fica **fechada** — uma REST que executa SQL não pode nascer
aberta porque alguém esqueceu de configurar.

## Parâmetros por cliente e ambiente

`cockpit.protheus_ambientes` — **uma linha por (customer, ambiente)**, porque
produção e teste são bases diferentes, com URL, environment, sufixo e às vezes
banco distintos. Campos: `url_rest`, `environment`, `empresa`, `filial`,
`usuario`, `senha_enc`, `token_enc`, `banco`, `sufixo`, `timeout_s`,
`limite_linhas`, `ativo` e o resultado do último teste.

Segredos em **AES-256-GCM**, formato `base64(iv||tag||ct)` com
`AAD = "<customer>|<ambiente>"` — o mesmo formato do cockpit
(`src/lib/tasks-sc/crypto.ts`), então os dois apps leem a mesma linha. A AAD
amarra o segredo à linha: um blob copiado para outro cliente **não decifra**.
Chave mestra em `PROTHEUS_CRED_KEY` (32 bytes em base64), só no servidor.

`cockpit.protheus_coletas` registra cada disparo (ping ou coleta) com duração,
status HTTP, linhas, medições e erro. Sem esse log, "não atualizou" vira caça ao
log da Vercel — e o cliente não tem como saber quando a leitura foi feita.

## Rotas do dashboard

| Rota | O que faz |
|---|---|
| `GET /api/protheus/<customer>` | parâmetros dos dois ambientes (**sem** segredo: só `tem_senha`/`tem_token`) e as últimas coletas |
| `POST /api/protheus/<customer>/<ambiente>` | salva; senha e token só são regravados quando vêm preenchidos |
| `DELETE /api/protheus/<customer>/<ambiente>` | remove o cadastro |
| `POST /api/protheus/<customer>/<ambiente>/testar` | `/ping` + confere environment e banco contra o cadastrado |
| `POST /api/protheus/<customer>/<ambiente>/coletar?tipo=` | roda o script salvo e grava a medição |

Mesma régua de acesso do resto da aba: `require_auth` + `deny_customer`, e
escrita bloqueada durante o "ver como".

## A tela

Dois botões novos nas sub-abas Cadastros e Movimentos, ao lado do *Script SQL*:

- **⚙ Ambiente** — abre o cadastro da base **da sub-aba aberta** (o título
  carrega o selo *Base Produção* / *Base de Testes*). Tem "Salvar e testar
  conexão", que grava e chama o `/ping`: testar sem salvar mentiria, porque o
  teste roda com o que está gravado.
- **⚡ Coletar agora** — confirma a base, executa e recarrega a sub-aba.

**Divergência de environment ou banco é aviso, não erro.** Quem decide se a URL
aponta para a base certa é o consultor — mas coletar de teste achando que é
produção é o erro caro deste processo: o número chega bonito, plausível, e vem
do lugar errado.

## Limites que valem lembrar

- A função da Vercel morre em **60s** (`vercel.json`). O `timeout_s` do ambiente
  é limitado a 50s no código. Base lenta → o certo é reduzir a janela do script,
  não aumentar o timeout.
- `limite_linhas` (padrão 50.000, teto 200.000 no fonte) protege a resposta. Se
  vier `truncado: true`, a tela avisa — medição truncada é medição errada.
- Idempotência inalterada: regravar a mesma data no mesmo ambiente **substitui**
  a medição, não duplica.
- `origem` passou a distinguir `upload` (arquivo) de `coleta` (REST).

## Como foi testado

Stub HTTP respondendo como o `TSCMONITREST` (`ping` + CSV de 4 tabelas do Olim),
com o banco fingido, cobrindo: cifra/decifra no formato do cockpit (inclusive a
recusa de um blob com AAD de outro cliente), teste de conexão, aviso de
environment divergente, coleta completa (SX5 filtrada, SD2 gravada como
`painel=movimento`) e token errado devolvendo mensagem clara. A tela foi aberta
no Chromium com as rotas `/api/*` interceptadas, conferindo o preenchimento dos
campos e os dois modais.
