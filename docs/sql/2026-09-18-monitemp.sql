-- Aba "Empresas e Compartilhamento" (MONITEMP) - 18/09/2026
-- Aditiva: nada existente muda de comportamento.

-- 1) Leitura da SM0 (P0), por cliente e base. E a fonte das empresas/filiais
--    que o script de Empresas carrega como literais.
create table if not exists cockpit.monitemp_sm0 (
  customer      text not null references cockpit.clientes(customer) on delete cascade,
  ambiente      text not null check (ambiente in ('producao','teste')),
  empresa       text not null,
  filial        text not null,
  nome_empresa  text,
  nome_filial   text,
  cnpj          text,
  leiaute       text,
  sizefil       integer,
  sx2           boolean,
  qtd_tabelas   integer,
  tabelas       text,
  lido_em       text,
  updated_by    text,
  updated_at    timestamptz not null default now(),
  primary key (customer, ambiente, empresa, filial)
);

-- 2) Medicoes: uma por (cliente, base, data), como em monitcad_medicoes.
create table if not exists cockpit.monitemp_medicoes (
  id            bigint generated always as identity primary key,
  customer      text not null references cockpit.clientes(customer) on delete cascade,
  ambiente      text not null check (ambiente in ('producao','teste')),
  data_medicao  date not null,
  hora_medicao  text,
  semana        integer,
  origem        text not null default 'upload',
  created_at    timestamptz not null default now(),
  unique (customer, ambiente, data_medicao)
);

-- 3) Itens: empresa x tabela x conteudo do campo filial.
create table if not exists cockpit.monitemp_itens (
  id            bigint generated always as identity primary key,
  medicao_id    bigint not null references cockpit.monitemp_medicoes(id) on delete cascade,
  customer      text not null,
  ambiente      text not null,
  empresa       text not null,
  nome_empresa  text,
  leiaute       text,
  tipo          text,
  tabela        text not null,
  descricao     text,
  tabela_fisica text,
  situacao      text,
  sx2           text,
  filial        text,
  filial_tipo   text,
  nome_filial   text,
  qtde          numeric not null default 0,
  consistencia  text
);
create index if not exists monitemp_itens_med_idx on cockpit.monitemp_itens (medicao_id);
create index if not exists monitemp_itens_cli_idx on cockpit.monitemp_itens (customer, ambiente, tabela);

-- Mesmo padrao das demais tabelas cockpit.monit*: RLS ligada, sem policy
-- (o app acessa pelo DATABASE_URL do servidor; anon/authenticated nao leem).
alter table cockpit.monitemp_sm0      enable row level security;
alter table cockpit.monitemp_medicoes enable row level security;
alter table cockpit.monitemp_itens    enable row level security;

-- 4) Scripts salvos e log de coleta passam a aceitar os dois tipos novos.
alter table cockpit.monitcad_scripts drop constraint if exists monitcad_scripts_tipo_check;
alter table cockpit.monitcad_scripts add constraint monitcad_scripts_tipo_check
  check (tipo = any (array['cadastros','movimentos','sm0','empresas']));
alter table cockpit.protheus_coletas drop constraint if exists protheus_coletas_tipo_check;
alter table cockpit.protheus_coletas add constraint protheus_coletas_tipo_check
  check (tipo = any (array['cadastros','movimentos','ping','sm0','empresas']));
