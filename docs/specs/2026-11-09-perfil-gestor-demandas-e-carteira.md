# Perfil Gestor de Demandas e Carteira de demandas — 09/11/2026

## Contexto

A gestora de demandas sai de licença. Dois consultores (Mauricio Vitto e Daniel
Da Silva) assumem a gestão, **cada um com uma parte dos clientes**. No Cockpit
Único e na Triagem, cada um deve ver **só** os clientes que lhe foram
atribuídos.

## O que entrou

1. **Perfil `gestor`** ("Gestor de Demandas") em `cockpit.usuarios_login.perfil`.
   É interno (`PERFIS_INTERNOS`) e tem o poder de `comum`. Continua podendo
   ter papel de consultor nos projetos.
2. **`cockpit.carteira_demandas (customer PK, email, …)`**: **um gestor por
   cliente**. Migration `0015_gestor_demandas.sql` do repo `cockpit-unico-tsc`.
3. **Tela 👥 Acessos → aba "🗂 Carteira de demandas"**:
   - chips por gestor (com contagem) e "sem gestor" — funcionam como filtro;
   - **Promover** um login interno a Gestor de Demandas (`POST /api/acessos/perfil`)
     e **✕** para voltar a Consultoria;
   - tabela de clientes com o select do gestor (grava na hora) e **atribuição em
     lote** dos marcados (`POST /api/acessos/carteira`).
   - Na aba Liberações, o select de perfil ganhou "Gestor de Demandas".

## Recorte — diferente nos dois apps, de propósito

| App | Gestor vê |
|---|---|
| cockpit-unico-tsc (Cockpit, Triagem, Operacional, …) | **só a carteira** |
| ProjetosTotvsSC | liberações (projetos em que é consultor) **∪** carteira |

Por que tabela própria e não `usuario_clientes`: ali ficam os projetos em que a
pessoa é **consultor** (papel, abas, módulos). Misturar faria o Cockpit mostrar os
projetos dele como consultor junto com a carteira — o contrário do pedido.

## Regras e armadilhas

- `POST /api/acessos/carteira` só aceita login **ativo com perfil gestor**;
  `email: null` tira o gestor dos clientes.
- Quem deixa de ser gestor: as linhas dele ficam **inertes** (o recorte só vale
  para o perfil gestor) e aparecem com ⚠ na tela até serem repassadas.
- `POST /api/acessos/perfil` não concede nem tira `admin` e não altera o próprio
  login.
- Raio X (maturidade): `gestor` vê só a própria linha, igual a `consultoria`
  (`RX_SO_EU`) — gere demandas, não a avaliação dos colegas.
- Banco sem a 0015: `GET /api/acessos` devolve `carteira_ok: false` e a aba mostra
  o aviso. As rotas respondem 503 com a instrução. `allowed_customers()` trata a
  carteira como vazia.
- Perfil novo = **três lugares no mesmo dia**: CHECK do banco, `PERFIS` daqui e
  `perfis.ts` do cockpit-unico-tsc. Senão `perfilDe()` lá degrada para `leitor`.
- No cockpit-unico-tsc, `salvarLiberacoes` (/admin) passou a gravar por
  **diferença**. O "apaga tudo e reinsere" zerava `papel` e `abas` gravados aqui.

Teste: `/tmp/vt/test-carteira.mjs` (Playwright com stub de `/api/me`, `/api/acessos`,
`/api/acessos/carteira`, `/api/acessos/perfil`). Cobre a opção do perfil, o ⚠ do
dono que não é mais gestor, promover, a troca 1-a-1, o lote, o filtro "sem
gestor" e a volta à aba Liberações.
