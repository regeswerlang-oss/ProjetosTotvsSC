# Área de clientes no dashboard de Projetos — 03/09/2026

## A pergunta que esta entrega responde

Não é "como faço uma tela para o cliente", é **"quem vê o quê, de qual cliente"**.
Por isso a unidade de liberação é o par **(usuário, cliente)** e as abas ficam
**nele**, não no usuário: o mesmo e-mail pode ver só Cadastros no Olim e
Cadastros + GAPs na Dígitro.

## Decisão de fundo: MESMA tela, não uma cópia

Não foi criada uma `cliente.html`. A área de clientes é o **mesmo**
`web/index.html`, com dois recortes:

- `body.modo-cliente` esconde tudo que tem `data-interno`;
- a barra de abas só mostra o que estiver liberado para o cliente do projeto aberto.

Por quê: este repo já paga o preço de duas cópias deliberadas (GAPs × Tarefas —
ver `2026-08-26-aba-tarefas.md`). Uma terceira cópia da tela de Cadastros e
Movimentos significaria corrigir a mesma coisa em dois lugares para sempre, e a
tela do cliente é justamente a que não pode ficar para trás.

## Três eixos — confundi-los abre acesso

| eixo | responde | onde |
|---|---|---|
| `allowed_customers()` | **quais clientes** ele vê | `cockpit.usuario_clientes` |
| `abas_liberadas()` | **que abas** ele vê **naquele cliente** | `usuario_clientes.abas` |
| `perfil` | ele é da **TOTVS** ou é o **cliente** | `cockpit.usuarios_login.perfil` |

Perfis (mesmo vocabulário do cockpit-unico-tsc): `admin`, `comum`, `leitor` =
internos; `cliente` = área de clientes. A tradução `(perfil, is_admin) → perfil`
é a mesma do `src/lib/auth/perfis.ts`: perfil **vazio** cai no `is_admin`
legado; perfil **preenchido e desconhecido** degrada para `leitor`, nunca para
`comum` — a tabela é compartilhada entre os apps e um perfil novo pode chegar
aqui antes do deploy.

## Banco

```sql
alter table cockpit.usuario_clientes add column abas text[];
```

- `NULL` → herda: interno vê tudo; perfil `cliente` recebe `ABAS_PADRAO_CLIENTE`
  (hoje `['cadastros']`, o protótipo).
- `'{}'` → liberado no cliente e **sem nenhuma aba**, de propósito. A tela mostra
  a faixa `#sem-aba` explicando — tela em branco sem explicação vira chamado.

## Esconder ≠ proteger

O `data-interno` some no CSS; quem **barra** é o servidor. Se alguém tirar o
atributo de um botão, o backend continua devolvendo 403.

- `require_interno()` — ações de **operação**: `/api/sync`, `script` (GET/POST/DELETE),
  `upload` de medição e de movimentos, `/api/protheus/*` (via `_guarda_ambiente`),
  `cenarios` (GET/POST/DELETE), `decisao`, `alinhamento`, `gmail/rascunho`.
- `deny_aba(customer, *abas)` — **leituras**: `monitcad`, `monitcad/evolucao`,
  `monitmov`, `monitmov/evolucao`, `gaps`, `tarefas`, `/painel/<c>/<slug>` e o
  detalhe do ticket (`_guarda_ticket`). `monitmov` aceita `cadastros` **ou**
  `cobertura` porque a mesma rota alimenta as duas telas.

O que o cliente **mantém**: `⬇ Exportar HTML`, `↻ Atualizar`, `Situação atual /
Evolução`, as quatro sub-abas (Cadastros/Movimentos × Produção/Testes) e a troca
da própria senha.
O que **sai** (o print de 03/09/2026): `✉ Rascunho no Gmail`, `🗄 Script SQL`,
`⚙ Ambiente`, `⚡ Coletar agora`, `⬆ Subir medição`, `⬆ Importar movimentos`,
`🎯 Cenários`, `⬆ Publicar painel`, `⟳ Sincronizar API`, `👁 Ver como`.

## ARMADILHA (custou um teste): `setTab` reescreve o `className`

```js
b.className = `tab-btn px-4 py-2 ...`;   // apaga o 'hidden' de aplicaAbas()
```

Sem repor o `hidden` **dentro do mesmo forEach**, o usuário do cliente clicava
numa aba e as dez voltavam. Quem mexer no `setTab` tem que manter a linha
`b.classList.toggle('hidden', !!ok && !ok.has(b.dataset.tab))`.

## ARMADILHA: hash de senha

`hash_scrypt()` gera `scrypt$<saltHex>$<hashHex>` com o salt usado como
**STRING** (o hex em UTF-8), `N=16384 r=8 p=1 dklen=64`, salt de 16 bytes →
168 chars. É o formato do `scryptSync` do Node no cockpit. Conferido: o hash
gerado aqui é validado pelo `crypto.scryptSync(senha, saltHex, 64)` do Node.
Gravar **bcrypt** nessa coluna derruba o login de TODOS os dashboards — eles
leem a mesma `cockpit.usuarios_login` (ver `cockpit-login-scrypt`).

## Tela "👥 Acessos" (só admin)

Botão no header. Cola-se a lista de e-mails **em qualquer formato** (vírgula,
ponto-e-vírgula, quebra de linha, `Nome <email>`) — `emails_do_texto()` extrai —,
marcam-se os clientes e as abas, e um POST grava tudo. Quem não tem login é
criado com **senha provisória**, mostrada **uma única vez** na resposta: não
fica gravada em lugar nenhum nem em log.

Rotas: `GET/POST/DELETE /api/acessos`, `POST /api/acessos/senha`,
`POST /api/acessos/ativo`.

Duas recusas de propósito no POST: perfil `admin` (admin vê todos os clientes,
não se concede numa tela de liberação) e cliente que não existe em
`cockpit.clientes` (liberação que nunca apareceria na tela).
O perfil de quem **já existe** só muda com `aplicar_perfil` marcado.

## FK de `usuario_clientes`

`usuario_clientes.email` referencia `usuarios_login(email)` com **casing exato**.
Inserir o e-mail em minúsculo quando o login foi criado `Fulano@x.com` estoura a
FK — por isso o POST resolve o e-mail canônico no banco antes do insert.

## Como conferir (sem Supabase)

`/tmp/v/test2.mjs` — stub Playwright que serve `web/index.html` com `/api/me`
falso nos dois modos. O CDN da Tailwind é inalcançável do sandbox: trocar por
`@tailwindcss/browser@4` via `page.route` + `window.tailwind={}` e injetar as
cores TOTVS num `<style type="text/tailwindcss">@theme{…}</style>`.
Resultado esperado: modo cliente = 1 aba (`Cadastros`), zero `[data-interno]`
visível, barra de ações só com `Exportar HTML`.

Auditoria dos portões (roda no repo, sem banco):

```
python3 - <<'PY'
import ast,pathlib
src=pathlib.Path("api/index.py").read_text(encoding="utf-8"); t=ast.parse(src); L=src.split("\n")
for n in t.body:
    if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
    rotas=[(d.args[0].value,d.func.attr.upper()) for d in n.decorator_list
           if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.args
           and isinstance(d.args[0],ast.Constant)]
    if not rotas: continue
    c="\n".join(L[n.lineno-1:(n.end_lineno or n.lineno)])
    g=[k.rstrip("()") for k in ("require_admin()","require_interno()","require_auth()",
        "deny_aba(","deny_customer(","_guarda_ambiente(","_guarda_ticket(","_cron_autorizado(") if k in c]
    for r,m in rotas: print(f"{r:46} {m:7} {' + '.join(g) or 'PUBLICA'}")
PY
```

Foi essa auditoria que pegou o bug do patch: `_guarda_ambiente` **retorna tupla**
(`return r, None`), então uma substituição cega de `require_auth` pulou o portão
dele para a rota seguinte e cascateou até `api_tarefas`. Rodar a auditoria depois
de mexer em portão não é opcional.

## Pendências

1. Commit + push + redeploy (git não roda pela ponte — é no Terminal do Mac).
2. Criar o primeiro usuário de cliente real pela tela de Acessos e conferir com
   o `👁 Ver como`, que agora entra em modo cliente de verdade.
3. Decidir se a área de clientes ganha um logo/subtítulo próprio por cliente.
4. Reaproveitar o mesmo `abas` no cockpit-unico-tsc (a coluna é compartilhada).
