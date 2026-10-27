-- Aba Plano de Trabalho (detalhe do projeto) — 27/10/2026
-- Substitui a planilha de atividades do CP (ex.: Açosul - Plano de Trabalho
-- Completo). Atividades E cadastros na mesma tabela (coluna tipo).
-- Spec: docs/specs/2026-10-27-aba-plano-trabalho.md
-- RLS ligado sem policy: só o backend (DATABASE_URL) lê e grava.

create table if not exists cockpit.plano_itens (
  id                  uuid primary key default gen_random_uuid(),
  customer            text not null references cockpit.clientes(customer),
  codigo_projeto      text not null,
  tipo                text not null check (tipo in ('atividade','cadastro')),
  modulo              text not null,
  ordem               integer not null default 0,
  status              text not null,
  responsavel_lado    text check (responsavel_lado in ('totvs','cliente')),
  responsavel_nome    text,                 -- como veio da planilha
  responsavel_email   text,                 -- login resolvido (null = sem login)
  consultor_nome      text,                 -- cadastro: consultor TOTVS que valida
  consultor_email     text,
  observacoes         text,                 -- texto livre, importado como está
  -- atividade
  sequencia           integer,
  etapa               text,
  tipo_agenda         text,                 -- Individual | Coletiva
  atividade           text,
  data_de             date,
  data_ate            date,
  horas               numeric(8,2),
  produto             text,                 -- MIT entregue
  motivo_restricao    text,
  qtd_reagendamentos  integer not null default 0,
  -- cadastro
  -- cadastro: data_de = base liberada, data_ate = limite (antes do treinamento)
  rotina              text,                 -- ex.: MATA030
  entidade            text,                 -- ex.: Clientes
  ambiente            text,
  tabela              text,                 -- alias Protheus (fase 2: liga ao monitcad)
  -- controle
  inconsistencia      text,                 -- apontada na importação, não barra
  origem_chave        text,                 -- modulo|sequencia ou modulo|rotina
  ativo               boolean not null default true,
  created_by          text,
  created_at          timestamptz not null default now(),
  updated_by          text,
  updated_at          timestamptz not null default now(),
  check (
    (tipo = 'atividade' and status in
       ('agendado','em_andamento','finalizado','finalizado_restricoes','cancelado'))
    or
    (tipo = 'cadastro' and status in
       ('nao_iniciado','em_cadastro','entregue','validado','nao_aplicavel'))
  ),
  check (tipo <> 'atividade' or atividade is not null),
  check (tipo <> 'cadastro'  or rotina is not null or entidade is not null),
  check (data_ate is null or data_de is null or data_ate >= data_de)
);
create index if not exists plano_itens_proj
  on cockpit.plano_itens(customer, codigo_projeto, tipo, modulo, ordem);
create index if not exists plano_itens_resp
  on cockpit.plano_itens(lower(responsavel_email));
create index if not exists plano_itens_cons
  on cockpit.plano_itens(lower(consultor_email));
create unique index if not exists plano_itens_origem
  on cockpit.plano_itens(customer, codigo_projeto, origem_chave)
  where origem_chave is not null;

-- Insert-only: uma linha por campo alterado (tela) ou por item tocado (importação)
create table if not exists cockpit.plano_itens_hist (
  id          bigserial primary key,
  item_id     uuid not null references cockpit.plano_itens(id),
  campo       text not null,
  de          text,
  para        text,
  por         text,
  origem      text not null default 'tela' check (origem in ('tela','importacao')),
  em          timestamptz not null default now()
);
create index if not exists plano_itens_hist_item
  on cockpit.plano_itens_hist(item_id, em desc);

-- Uma data por marco e projeto. O go-live oficial da Açosul é a virada 04/01/2027.
create table if not exists cockpit.plano_marcos (
  customer        text not null references cockpit.clientes(customer),
  codigo_projeto  text not null,
  marco           text not null check (marco in
                    ('base_liberada','treinamentos','prototipo','go_live')),
  data            date not null,
  observacao      text,
  updated_by      text,
  updated_at      timestamptz not null default now(),
  primary key (customer, codigo_projeto, marco)
);

create table if not exists cockpit.plano_importacoes (
  id              bigserial primary key,
  customer        text not null,
  codigo_projeto  text not null,
  arquivo         text,
  por             text,
  em              timestamptz not null default now(),
  criados         integer not null default 0,
  alterados       integer not null default 0,
  ignorados       integer not null default 0,
  resumo          jsonb                   -- inconsistências, responsáveis sem login, ausentes
);
create index if not exists plano_importacoes_proj
  on cockpit.plano_importacoes(customer, codigo_projeto, em desc);

alter table cockpit.plano_itens        enable row level security;
alter table cockpit.plano_itens_hist   enable row level security;
alter table cockpit.plano_marcos       enable row level security;
alter table cockpit.plano_importacoes  enable row level security
