# Minha conta — credenciais próprias do usuário (15/10/2026)

## Por quê
O painel de GAPs (próximo passo) vai gravar no Tasks SC: % concluído, datas,
status, responsável, histórico. Regra do Reges: **toda escrita no Tasks SC sai
em nome do usuário logado**, nunca da conta de serviço (`TASKS_USERNAME` fica só
para leitura e sync). E os rascunhos de e-mail saem da caixa de cada um.

## O que entrou
- Botão **👤 Minha conta** no topo (só interno). Ponto âmbar enquanto faltar
  alguma das duas credenciais.
- Modal com dois cards, cada um com "Salvar e testar" e "Remover":
  - **Tasks SC** — domínio (padrão `actvs`), usuário, senha. O backend faz o
    login OAuth de verdade antes de gravar; só entra o que autentica.
    Aceita `actvs\usuario` colado no campo usuário.
  - **E-mail (rascunhos)** — e-mail + **senha de app** do Google. Reaproveita
    `/api/gmail/cred` (já existia; antes só aparecia num modal ao criar rascunho).
- **Acessos** (admin): resumo "🔑 Credenciais próprias: Tasks SC x/y · E-mail x/y"
  e a lista por pessoa (✅/⚠️/▫️ e ✉️). Só o indicador — nunca a senha.

## Rotas
| Rota | O que faz |
|---|---|
| `GET /api/conta` | status das duas credenciais do logado (sem senha) + `chave_ok` |
| `POST /api/conta/tasks` | `{ad_domain, ad_username, senha}` → testa OAuth → grava |
| `DELETE /api/conta/tasks` | remove a credencial do logado |
| `GET/POST/DELETE /api/gmail/cred` | (já existia) senha de app do Gmail |

## Para usar nas próximas escritas
`token_tasks_usuario()` devolve o token OAuth **do usuário logado** (cache em
memória, margem de 120 s). Sem credencial válida levanta `SemCredencialTasks`,
que o Flask devolve como **HTTP 428** `{precisa_credencial: "tasks"}` — o front
deve abrir `abreMinhaConta('tasks')` em vez de tentar outra conta. Senha
recusada (400/401) marca `status='invalida'` na linha.

## Armazenamento — compartilhado com o cockpit-unico-tsc
- `cockpit.credenciais_tasks` (email PK em minúsculas, ad_domain, ad_username,
  senha_enc, status, validada_em, criada_em, atualizada_em).
- `senha_enc` = base64(iv[12] ‖ tag[16] ‖ ct), AES-256-GCM, **AAD = e-mail em
  minúsculas**, chave **`TASKS_CRED_KEY`** — idêntico a
  `src/lib/tasks-sc/crypto.ts` do cockpit (testado: Python cifra, Node decifra).
- **Configuração obrigatória:** `TASKS_CRED_KEY` na Vercel do ProjetosTotvsSC com
  o **mesmo valor** da Vercel do cockpit-unico-tsc. Se o cockpit não tiver,
  gere uma (`openssl rand -base64 32`) e coloque **nos dois**. Sem a chave, o
  card mostra o aviso e o salvar devolve erro 500 explicando.
- E-mail continua em `cockpit.gmail_credenciais` (Fernet derivado do
  `SESSION_SECRET` deste app; o cockpit lê com `GMAIL_CRED_SECRET`).

## Decisão registrada
Não guardamos a senha corporativa do e-mail nem "token da API do Gmail":
o Gmail recusa a senha normal por IMAP e o token colável expira em ~1 h.
Senha de app resolve o rascunho hoje; API do Gmail com OAuth fica para quando
houver necessidade além do rascunho.
