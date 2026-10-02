-- Unidade de Negocio como entidade propria na aba Estrutura, e a ordem das
-- entidades no codigo da filial. Aplicada no Supabase em 01/10/2026.
--
-- NOTA: a TOTVS documenta o codigo corporativo como "EEEUUUFFF (Empresa,
-- Unidade de Negocio e Filial)" - a ordem e fixa, o que varia e o TAMANHO de
-- cada nivel. A coluna `ordem` permite fugir disso a pedido do projeto; a
-- conferencia da aba avisa sempre que a ordem sai do padrao.

alter table cockpit.estrut_config
  add column if not exists usa_unidade boolean not null default false,
  add column if not exists ordem text not null default 'EUF';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'estrut_config_ordem_chk') then
    alter table cockpit.estrut_config
      add constraint estrut_config_ordem_chk
      check (ordem ~ '^[EUF]{3}$'
             and length(replace(replace(replace(ordem,'E',''),'U',''),'F','')) = 0
             and ordem !~ '(.).*\1');
  end if;
end $$;

update cockpit.estrut_config set usa_unidade = true where leiaute = 'EEUUFF';

create table if not exists cockpit.estrut_unidades (
  id         uuid primary key default gen_random_uuid(),
  customer   text not null,
  empresa_id uuid references cockpit.estrut_empresas(id) on delete cascade,
  codigo     text not null,
  nome       text,
  observacao text,
  ordem      integer not null default 0,
  ativo      boolean not null default true,
  created_by text,
  created_at timestamptz not null default now(),
  unique (customer, empresa_id, codigo)
);
create index if not exists ix_estrut_unidades_cli
  on cockpit.estrut_unidades (customer, empresa_id);
alter table cockpit.estrut_unidades enable row level security;

alter table cockpit.estrut_filiais
  add column if not exists unidade_id uuid references cockpit.estrut_unidades(id) on delete set null;
