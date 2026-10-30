-- Perfil de coleta de movimentos por cliente (30/10/2026)
-- Spec: docs/specs/2026-10-30-perfil-coleta-movimentos.md
--
-- monitmov_perfil  — uma linha por cliente: usa o script salvo?, janela, agenda.
-- monitmov_blocos  — blocos de coleta além do script salvo (catálogo ou próprios).
-- monitmov_lotes   — cada coleta (tela ou cron): o plano, o resultado de cada
--                    bloco (CSV enquanto o lote está aberto) e o resumo.
-- Acesso só pelo backend (service role): RLS ligada sem policy, como os demais
-- monit*.

create table if not exists cockpit.monitmov_perfil (
  customer          text primary key,
  usar_script_salvo boolean not null default true,
  janela_dias       integer not null default 0 check (janela_dias between 0 and 3650),
  agenda            text not null default 'off' check (agenda in ('off','diaria','semanal')),
  agenda_ambientes  text not null default '*' check (agenda_ambientes in ('*','producao','teste')),
  updated_by        text,
  updated_at        timestamptz not null default now()
);

create table if not exists cockpit.monitmov_blocos (
  id         bigserial primary key,
  customer   text not null,
  nome       text not null,
  origem     text not null default 'custom' check (origem in ('catalogo','custom')),
  catalogo   text,
  ambientes  text not null default '*' check (ambientes in ('*','producao','teste')),
  dialeto    text check (dialeto in ('oracle','mssql','postgres')),
  sql        text not null,
  analises   text[] not null default '{}',
  ativo      boolean not null default true,
  ordem      integer not null default 100,
  updated_by text,
  updated_at timestamptz not null default now(),
  unique (customer, nome)
);
create index if not exists monitmov_blocos_customer on cockpit.monitmov_blocos (customer, ordem);

create table if not exists cockpit.monitmov_lotes (
  id            bigserial primary key,
  customer      text not null,
  ambiente      text not null check (ambiente in ('producao','teste')),
  iniciado_em   timestamptz not null default now(),
  fechado_em    timestamptz,
  status        text not null default 'aberto'
                check (status in ('aberto','gravado','recusado','falhou','abandonado')),
  disparado_por text,
  janela        text,
  blocos        jsonb not null default '[]'::jsonb,
  resultados    jsonb not null default '{}'::jsonb,
  resumo        jsonb
);
create index if not exists monitmov_lotes_cli on cockpit.monitmov_lotes (customer, ambiente, iniciado_em desc);
create index if not exists monitmov_lotes_abertos on cockpit.monitmov_lotes (status) where status = 'aberto';

alter table cockpit.monitmov_perfil enable row level security;
alter table cockpit.monitmov_blocos enable row level security;
alter table cockpit.monitmov_lotes  enable row level security;

comment on table cockpit.monitmov_perfil is 'Perfil de coleta de MOVIMENTOS por cliente: script salvo, janela (dias) e agenda do cron. So o backend le.';
comment on table cockpit.monitmov_blocos is 'Blocos de coleta de movimentos alem do script salvo (catalogo SD2_FISCAL/SE5_BANCARIO ou proprios). Placeholders {{SUFIXO}} {{DT_INI}} {{DT_FIM}} {{PERIODO}} {{EMPRESA}} {{FILIAL}} trocados por base.';
comment on table cockpit.monitmov_lotes is 'Cada coleta de movimentos por perfil (tela ou cron): plano, resultado por bloco e resumo. CSV so enquanto aberto.';
