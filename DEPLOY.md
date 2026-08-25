# Deploy — projetos-vercel

Dashboard de Projetos TOTVS SC na Vercel. Design: `docs/specs/2026-07-11-projetos-vercel-design.md`.

## 1. Subir para o GitHub

```bash
cd projetos-vercel
git init && git add . && git commit -m "Projetos TOTVS SC — app Vercel"
git branch -M main
git remote add origin https://github.com/regeswerlang-oss/projetos-vercel.git
git push -u origin main
```
(Crie antes o repo vazio `projetos-vercel` na org `regeswerlang-oss`.)

## 2. Importar na Vercel

Add New → Project → importe o repo. Framework: **Other** (o `vercel.json` cuida
do resto). Sem build command.

## 3. Variáveis de ambiente (Settings → Environment Variables)

| Nome | Valor |
|---|---|
| `DATABASE_URL` | pooler do Supabase, porta **6543** (`postgres.kpimalwnswxalwbidkog@aws-1-us-east-2.pooler...`) |
| `TASKS_USERNAME` | `actvs\reges.werlang` (uma barra) |
| `TASKS_PASSWORD` | senha do AD |
| `TASKS_SC_BASE_URL` | `https://api.tscst.com.br/restAPI` |
| `SESSION_SECRET` | `python3 -c "import secrets;print(secrets.token_hex(32))"` |
| `CRON_SECRET` | segredo do `Authorization: Bearer` do `/api/cron/sync` (pg_cron jobid 7) |
| `SYNC_REGIOES` | regiões do recorte — default `201,202,211`; **vazio desliga o filtro** |
| `SYNC_PURGE` | `1` (default) apaga da base o que sai do recorte; `0` só para de gravar |

Aplique a Production + Preview e faça **Redeploy** (variáveis só valem em deploy novo).

## 4. Primeiro uso

1. Abra a URL → cai em `/login`. Entre com o mesmo e-mail/senha dos outros apps
   (a base `cockpit.usuarios_login` é compartilhada).
2. A base se atualiza sozinha **de hora em hora** (pg_cron do Supabase, jobid 7
   `projetos-sync` → `GET /api/cron/sync` com o `CRON_SECRET`). O botão
   **⟳ Sincronizar API** é só para forçar na hora.
   Só entram projetos da regional ou da carteira — ver
   `docs/specs/2026-08-25-recorte-regional-e-cron-horario.md`.
3. **↻ Atualizar** recarrega a lista do Supabase (rápido, sem bater na API).

## Diagnóstico

`GET /api/health` mostra as env vars, se o banco respondeu, quantos projetos há
na base e o último sync.

## Notas

- Cada login só vê os projetos dos **clientes liberados** em
  `cockpit.usuario_clientes` (admin vê todos) — mesmo controle do Gaps.
- O detalhe (mapa/cronograma) é **ao vivo** na API PCI, com cache curto. Se a
  API der soluço, o app serve o cache anterior marcado como `_stale`.
- Os HTMLs ficam em `web/` (nunca em `public/`, que a Vercel serviria antes da
  função e furaria o login).

## Roteamento na Vercel — o contrato `?__path=`

Com `destination: "/api/index"` (seco), a Vercel entrega à função o caminho de
**destino**: o Flask recebe `PATH_INFO=/api/index` em **toda** request, nenhuma
rota casa e tudo cai no catch-all `/<path:asset>`, que responde
`404 {"ok": false, "error": "Rota de API desconhecida."}` — o site inteiro morre,
inclusive `/` e `/api/health`.

Por isso o `vercel.json` usa:

```json
"rewrites": [ { "source": "/(.*)", "destination": "/api/index?__path=/$1" } ]
```

e o `api/index.py` embrulha o WSGI no middleware `_VercelRewritePath`, que
devolve o `__path` ao `PATH_INFO`, remove o `__path` da query e preserva o resto
(fallback: header `x-vercel-original-path`). Ele só age quando o `PATH_INFO` é o
caminho da função, então fica inerte no `python api/index.py` local.

**Os dois andam em par: mexeu no `destination`, mexa no `FUNC_PATHS`/contrato
`__path`.** Mesmo bug e mesmo fix do projeto Gaps · Tomada de Decisão (30/07/2026).

Diagnóstico rápido: se `/api/health` — rota que existe — devolver "Rota de API
desconhecida.", o problema é o `PATH_INFO`, não rota faltando nem deploy velho.
