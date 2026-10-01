-- Comparador de conteudo entre empresas (MONITEMP C0/C1).
-- Aplicada no Supabase em 01/10/2026.
--
-- C0 le o dicionario da base (SIX indice 1 + SX3) das tabelas marcadas; C1 le o
-- conteudo usando os campos que o C0 trouxe. Dois passos porque o release Oracle
-- do cliente recusa SQL dinamico (ORA-32031 / ORA-00923).

-- Marca a tabela para comparacao. Nao e todo o escopo de proposito: puxar o
-- conteudo da SRA ou da SD2 estoura o teto de linhas da REST sem servir a nada.
alter table cockpit.estrut_tabelas
  add column if not exists comparar boolean not null default false;

-- C0: o dicionario lido da base, por empresa.
create table if not exists cockpit.monitemp_dicionario (
  id          uuid primary key default gen_random_uuid(),
  customer    text not null,
  ambiente    text not null,
  empresa     text not null,
  tabela      text not null,
  registro    text not null check (registro in ('CHAVE', 'CAMPO')),
  seq         text not null default '00',
  campo       text not null default '',
  conteudo    text,
  tipo_dado   text,
  tamanho     integer,
  lido_em     text,
  updated_by  text,
  updated_at  timestamptz not null default now(),
  unique (customer, ambiente, empresa, tabela, registro, campo)
);
create index if not exists ix_monitemp_dicionario_cli
  on cockpit.monitemp_dicionario (customer, ambiente, tabela);
alter table cockpit.monitemp_dicionario enable row level security;

-- C1: cabecalho de cada coleta de conteudo.
create table if not exists cockpit.monitemp_comparacoes (
  id           uuid primary key default gen_random_uuid(),
  customer     text not null,
  ambiente     text not null,
  data_medicao date not null,
  hora_medicao text,
  semana       text,
  origem       text,
  created_at   timestamptz not null default now(),
  unique (customer, ambiente, data_medicao)
);
alter table cockpit.monitemp_comparacoes enable row level security;

-- C1: uma linha por tabela x empresa x chave. VALOR e a concatenacao legivel
-- dos campos comparaveis - campo de controle e de auditoria ficam de fora, se
-- nao divergem sempre e o alerta vira ruido que se aprende a ignorar.
create table if not exists cockpit.monitemp_conteudo (
  id            bigserial primary key,
  comparacao_id uuid not null references cockpit.monitemp_comparacoes(id) on delete cascade,
  customer      text not null,
  ambiente      text not null,
  tabela        text not null,
  empresa       text not null,
  chave         text not null,
  filial        text,
  valor         text
);
create index if not exists ix_monitemp_conteudo_med
  on cockpit.monitemp_conteudo (comparacao_id, tabela, chave);
alter table cockpit.monitemp_conteudo enable row level security;
