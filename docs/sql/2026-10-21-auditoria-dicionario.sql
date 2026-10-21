-- Aba "Auditoria de Tabelas" - dicionario (SX3 / SX6) entre as bases - 21/10/2026
-- Aditiva. Complementa 2026-10-21-auditoria-tabelas.sql.

-- Situacao das leituras extras de cada coleta. SX3/SX6 nao sao fatais: a
-- coleta grava SX2 + volume mesmo quando o dicionario falha, e diz o porque.
alter table cockpit.audtab_coletas add column if not exists x3_ok     boolean;
alter table cockpit.audtab_coletas add column if not exists x6_ok     boolean;
alter table cockpit.audtab_coletas add column if not exists x3_linhas integer;
alter table cockpit.audtab_coletas add column if not exists x6_linhas integer;
alter table cockpit.audtab_coletas add column if not exists erro_dic  text;

-- SX3 das tabelas da auditoria (escopo + estruturais + referencia).
create table if not exists cockpit.audtab_sx3 (
  coleta_id  bigint not null references cockpit.audtab_coletas(id) on delete cascade,
  tabela     text not null,
  campo      text not null,
  tipo       text,
  tamanho    integer,
  decimal    integer,
  titulo     text,
  contexto   text
);
create index if not exists audtab_sx3_coleta_idx on cockpit.audtab_sx3 (coleta_id);

-- SX6 inteiro. So as ultimas 3 coletas de cada base guardam (o app apaga o resto).
create table if not exists cockpit.audtab_sx6 (
  coleta_id  bigint not null references cockpit.audtab_coletas(id) on delete cascade,
  param      text not null,
  fil        text,
  tipo       text,
  conteudo   text,
  descricao  text
);
create index if not exists audtab_sx6_coleta_idx on cockpit.audtab_sx6 (coleta_id);

alter table cockpit.audtab_sx3 enable row level security;
alter table cockpit.audtab_sx6 enable row level security;

-- Coleta sem REST (21/10/2026): scripts no console TCloud + upload do CSV.
-- 'rest' = TSCMONITREST; 'upload' = resultado subido na aba.
alter table cockpit.audtab_coletas add column if not exists origem text not null default 'rest';
