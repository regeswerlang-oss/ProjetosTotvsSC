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

Aplique a Production + Preview e faça **Redeploy** (variáveis só valem em deploy novo).

## 4. Primeiro uso

1. Abra a URL → cai em `/login`. Entre com o mesmo e-mail/senha dos outros apps
   (a base `cockpit.usuarios_login` é compartilhada).
2. Clique em **⟳ Sincronizar API** — ele puxa os ~1735 projetos da API PCI,
   página a página, e grava em `cockpit.projetos`. Só precisa na 1ª vez e quando
   quiser atualizar.
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
