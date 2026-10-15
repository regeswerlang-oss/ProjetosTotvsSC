-- Gestão de GAPs (menu 🧭 Interno → GAPs) — 15/10/2026
-- Fase e dependências vivem SÓ aqui. % concluído e datas são da Task
-- (Tasks SC) e ficam aqui como CÓPIA do último valor gravado pelo painel.
-- RLS ligado sem policy: só o backend (DATABASE_URL) lê e grava.

create table if not exists cockpit.gap_fases (
  id          smallserial primary key,
  nome        text not null unique,
  ordem       smallint not null,
  pct_padrao  smallint,                -- sugestão de % ao entrar na fase
  cor         text not null default '#94a3b8',
  ativo       boolean not null default true
);

insert into cockpit.gap_fases (nome, ordem, pct_padrao, cor) values
  ('Levantamento',           1, 10,  '#94a3b8'),
  ('Desenvolvimento',        2, 40,  '#3b82f6'),
  ('Validação Consultoria',  3, 70,  '#a855f7'),
  ('Homologação',            4, 85,  '#f59e0b'),
  ('Produção',               5, 100, '#10b981')
on conflict (nome) do nothing;

create table if not exists cockpit.gap_plano (
  uuid_ticket  text primary key,
  customer     text not null,
  fase_id      smallint references cockpit.gap_fases(id),
  progress     numeric,               -- cópia do progress da Task
  start_date   date,                  -- cópias das datas da Task
  due_date     date,
  end_date     date,
  observacao   text,
  updated_by   text,
  updated_at   timestamptz not null default now()
);
create index if not exists gap_plano_customer on cockpit.gap_plano(customer);

create table if not exists cockpit.gap_fase_hist (
  id           bigserial primary key,
  uuid_ticket  text not null,
  fase_de      smallint,
  fase_para    smallint,
  por          text,
  em           timestamptz not null default now()
);
create index if not exists gap_fase_hist_ticket on cockpit.gap_fase_hist(uuid_ticket, em desc);

-- "uuid_ticket só começa depois que depende_de terminar"
create table if not exists cockpit.gap_dependencias (
  uuid_ticket  text not null,
  depende_de   text not null,
  criado_por   text,
  criado_em    timestamptz not null default now(),
  primary key (uuid_ticket, depende_de),
  check (uuid_ticket <> depende_de)
);
create index if not exists gap_dep_depende on cockpit.gap_dependencias(depende_de);

alter table cockpit.gap_fases        enable row level security;
alter table cockpit.gap_plano        enable row level security;
alter table cockpit.gap_fase_hist    enable row level security;
alter table cockpit.gap_dependencias enable row level security;

-- auditoria das escritas na Task feitas pelo painel
alter type cockpit.action_type add value if not exists 'progresso';
alter type cockpit.action_type add value if not exists 'datas';
