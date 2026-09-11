# Perfil Consultoria e módulos na tela de Acessos — 11/09/2026

## O que mudou

1. **Perfil `consultoria`** em `cockpit.usuarios_login.perfil`, para separar o
   consultor que trabalha no projeto de quem é do time fixo. **Poder idêntico ao
   `comum`** — entra em `PERFIS_INTERNOS`, então cadastra e opera normalmente.
   Só o rótulo é próprio.
2. **Papel e módulos saem da tela de Acessos**, junto com cliente e abas. Antes
   só existiam no modal *Equipe do protótipo*, e sobrava consultor liberado no
   cliente sem módulo nenhum — ele descobria ao ser barrado na validação.
3. **Catálogo de módulos unificado**: `modulos_do_cliente()` / `modulos_por_cliente()`
   unem as três fontes que guardam módulo — itens do roteiro do protótipo,
   `monitcad_tabelas` (Cadastros) e `monitmov_itens` (Movimentos).

## Banco

```sql
alter table cockpit.usuarios_login drop constraint usuarios_login_perfil_chk;
alter table cockpit.usuarios_login add constraint usuarios_login_perfil_chk
  check (perfil = any (array['admin','comum','consultoria','dev','cliente','leitor']));
```

Migration aplicada como `perfil_consultoria` (Supabase `kpimalwnswxalwbidkog`).

## ARMADILHA — a tabela de login é compartilhada

`cockpit.usuarios_login` também serve o **cockpit-unico-tsc**, e lá
`perfilDe()` (`src/lib/auth/perfis.ts`) degrada perfil desconhecido para
`leitor`, fail-closed. Sem o mesmo perfil declarado nos dois apps, o consultor
entra no Cockpit como somente-leitura e ninguém entende por quê. O perfil novo
precisa de TRÊS passos no mesmo dia: CHECK do banco, `PERFIS`/`PERFIS_INTERNOS`
do `api/index.py` e `PERFIS`/`PERFIL_LABEL`/`PERFIL_HINT` do `perfis.ts`.

## ARMADILHA — a lista de módulos vinha só do roteiro

A consulta antiga era `proto_itens` × `proto_roteiros ativo`. Cliente sem MIT045
importado abria o modal *Equipe* com `* todos` e mais nada — parecia recurso
quebrado. Módulo também mora em Cadastros e Movimentos, que existem desde o
primeiro dia do projeto. `'(sem módulo)'` é RÓTULO de tela que já entrou no
dado: filtrado em `_MODULO_VALIDO`, senão viraria opção de liberação.

## Regras da gravação (POST /api/acessos)

- `papel` só de `PROTO_PAPEIS`; papel da TOTVS (`cp_totvs`, `consultor`) exige
  perfil interno — conferido **depois** de criar o login e aplicar o perfil,
  senão recusaria o consultor criado na mesma chamada.
- `modulos` exige `papel_modulo` (`executa` | `valida`) e **substitui** o
  conjunto daquele papel nos pares marcados: o que a tela mostra desmarcado sai.
- Módulo que não existe no cliente não é gravado (liberação fantasma) e volta em
  `modulos_ignorados` — a lista da tela é a UNIÃO dos clientes marcados, então
  um módulo válido para um pode não valer para o outro.

## Front

- `acs.emails` guarda o que foi colado: `pintaAcessos()` reescreve o innerHTML
  inteiro e, sem isso, filtrar um cliente apagava a lista de e-mails.
- O bloco de módulos repinta sozinho (`renderModulosAcessos`) quando muda o
  cliente marcado — repintar a tela toda perderia o que já foi digitado.
- Perfil `cliente` não oferece papel da TOTVS; trocar o perfil para cliente
  limpa um papel TOTVS já escolhido (senão a tela mentiria até o Liberar).
- Padrão do `papel_modulo`: `cp_totvs`/`consultor` → **valida**;
  `cp_cliente`/`usuario_chave` → **executa**.

## Teste

`/tmp/v/test-acessos.mjs` (Playwright, stub de `/api/me` + `/api/acessos`):
opção Consultoria no select, papéis filtrados por perfil, módulos por cliente
marcado, união de dois clientes, e-mails sobrevivendo ao filtro, payload do POST
e o "editar" recarregando papel + módulos do par.
