# Design — projetos-vercel (Dashboard de Projetos TOTVS SC na Vercel)

Data: 2026-07-11 · Status: aprovado pelo usuário

## Objetivo

Publicar o dashboard local `totvs-dashboard/Projetos` (index.html + server.py +
pci_client.py) como app na Vercel, com login, recorte por cliente e sem depender
da máquina local.

## Decisões (tomadas com o usuário)

1. **App Vercel separado** (`projetos-vercel`), independente do `gaps-vercel`.
2. **Mesmo Supabase** de todos os apps: `kpimalwnswxalwbidkog`, schema `cockpit`.
3. **Lista de projetos sincronizada** para `cockpit.projetos`; **detalhe**
   (mapa/cronograma) continua **ao vivo** na API PCI.
4. **Atualização sob demanda**: botão "Atualizar" no app (sem cron).
5. **Recorte por cliente** igual ao Gaps: admin vê tudo; usuário comum só os
   clientes liberados em `cockpit.usuario_clientes`.

## Arquitetura

Mesmo padrão do `gaps-vercel`:

- Backend único Flask/WSGI em `api/index.py`, servido como função serverless.
- `vercel.json` faz rewrite `/(.*) -> /api/index`; os HTMLs ficam em **`web/`**
  (nunca em `public/`, que a Vercel serviria estático **antes** da função e
  furaria a porta de login). `includeFiles: web/**`.
- Login reusa `cockpit.usuarios_login` (scrypt **salt UTF-8 estilo Node**
  `scryptSync(pw, salt, 64)`) + cookie de sessão HMAC. Senha é a mesma dos
  outros apps.
- Acesso por cliente: `allowed_customers()` / `deny_customer()` (skill
  `controle-acesso-por-cliente`).

## Fonte de dados

A API PCI usa o **mesmo OAuth do Tasks SC** (`api.tscst.com.br/restAPI`).

| o quê | endpoint |
|---|---|
| lista (paginada) | `GET /custom/tscst/pci/api/v1/projetos?page&pageSize` -> `{items, hasNext}` |
| mapa do projeto | `GET /PCITConectaProjetos/mapa?CLIENTE&CODIGO&VERSAO&LOJA` |
| cronograma | `GET /PCITConectaProjetos/cronograma?CLIENTE&CODIGO&VERSAO&LOJA` |

**Armadilhas a preservar no porte** (já resolvidas no `pci_client.py`):
- **Encoding mentiroso**: a API diz `utf-8` mas manda **cp1252**. Se aparecer
  caractere de substituição no decode UTF-8, re-decodar em cp1252.
- **Instabilidade**: 401 (token vencido) e 5xx (inclusive **500**) são
  transitórios -> retry com backoff; persistindo, erro limpo (503 com
  `api_indisponivel: true`), nunca traceback.

O `CLIENTE` da API PCI é o **mesmo código de customer** do cockpit
(ex.: `000348D0`), então o recorte por cliente casa direto com
`cockpit.usuario_clientes.customer`.

## Banco — nova tabela `cockpit.projetos`

Guarda a **lista** (não o detalhe): codigo_projeto, codigo_cliente_projeto,
nome_cliente_projeto, descricao_projeto, nome_coordenador_projeto,
status_projeto, tipo_projeto, versao, loja, raw jsonb, synced_at.

## Endpoints do app

```
GET  /login  ·  POST /api/login  ·  GET /api/me      (igual ao Gaps)
GET  /api/health                                     -> env + db
GET  /api/clientes                                   -> cockpit.clientes (filtrado)
GET  /api/projetos                                   -> cockpit.projetos (filtrado por cliente)
POST /api/sync?page=N                                -> puxa 1 página da API PCI -> upsert
GET  /api/projeto/<cli>/<cod>/<ver>/<loja>/mapa      -> ao vivo (cache curto)
GET  /api/projeto/<cli>/<cod>/<ver>/<loja>/cronograma-> ao vivo (cache curto)
```

**Sync paginado pelo front**: o botão "Atualizar" chama `/api/sync?page=1`,
`?page=2`... enquanto `hasNext`, com barra de progresso. Evita o timeout de 60s
da função serverless ao puxar os ~1735 projetos (~9 páginas).

## Front

Porte de `Projetos/index.html` + `assets/` para `web/`, ajustando a base da API
para a mesma origem (sem `localhost`). Mantém a UX: lista agrupada por cliente,
filtros de status/tipo, busca, e o detalhe (mapa + cronograma com agendas,
apontamentos e horas). Adiciona `login.html` e o botão "Atualizar".

O `?all=1` do server local perde o sentido: quem governa o que aparece é o
controle de acesso por cliente (admin já vê tudo).

## Env vars (Vercel)

`DATABASE_URL` (pooler 6543), `TASKS_USERNAME` (uma barra), `TASKS_PASSWORD`,
`TASKS_SC_BASE_URL`, `SESSION_SECRET`.

## Escopo v1

Paridade da tela atual (lista + detalhe) + login + recorte por cliente + sync
sob demanda. Sem cron, sem escrita na API PCI (read-only).

## Riscos e mitigação

- **Timeout no sync** -> paginação conduzida pelo front (1 página por request).
- **API PCI instável** -> retry + 503 limpo; a lista continua servível do
  Supabase mesmo com a API fora do ar (vantagem do modelo sincronizado).
- **Encoding** -> tratar cp1252 no porte, senão acentos quebram.
