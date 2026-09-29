-- Aba Estrutura de Empresas (definição) — DDL + regras da TDN.
-- Aplicado no Supabase kpimalwnswxalwbidkog em 29/09/2026 como as migrations
--   estrutura_empresas_definicao · estrutura_catalogo_semente · estrutura_regras_tdn
-- Spec: docs/specs/2026-09-29-aba-estrutura-empresas.md
--
-- O SEED DO CATÁLOGO (131 tabelas em 12 módulos) NÃO está aqui de propósito:
-- ele é DADO, não esquema, e o time edita direto no banco. Para reexportá-lo:
--   select format('(%L,%L,%L,%L,%L,%L,%s),', modulo, tabela, descricao, tipo,
--                 sugestao, fonte, ordem)
--     from cockpit.estrut_catalogo order by ordem, modulo, tabela
--
-- Compartilhamento sempre em 3 posições: Empresa · Unidade de Negócio · Filial,
-- na mesma ordem de X2_MODOEMP|X2_MODOUN|X2_MODO da aba de medição.

create table if not exists cockpit.estrut_config (
  customer      text primary key,
  leiaute       text not null default 'EEFF' check (leiaute in ('FF','EEFF','EEUUFF')),
  tam_empresa   smallint not null default 2,
  tam_unidade   smallint not null default 0,
  tam_filial    smallint not null default 2,
  observacao    text,
  definido_por  text,
  definido_em   timestamptz not null default now()
);

create table if not exists cockpit.estrut_grupos (
  id uuid primary key default gen_random_uuid(),
  customer text not null, codigo text not null, nome text not null,
  observacao text, ordem int not null default 0, ativo boolean not null default true,
  created_by text, created_at timestamptz not null default now(),
  unique (customer, codigo)
);

create table if not exists cockpit.estrut_empresas (
  id uuid primary key default gen_random_uuid(),
  customer text not null,
  grupo_id uuid references cockpit.estrut_grupos(id) on delete set null,
  codigo text not null, nome text not null, cnpj text, uf text,
  observacao text, ordem int not null default 0, ativo boolean not null default true,
  created_by text, created_at timestamptz not null default now(),
  unique (customer, codigo)
);

create table if not exists cockpit.estrut_filiais (
  id uuid primary key default gen_random_uuid(),
  customer text not null,
  empresa_id uuid not null references cockpit.estrut_empresas(id) on delete cascade,
  codigo text not null, unidade text, nome text not null,
  cnpj text, uf text, municipio text, matriz boolean not null default false,
  observacao text, ordem int not null default 0, ativo boolean not null default true,
  created_by text, created_at timestamptz not null default now(),
  unique (customer, codigo)
);

create table if not exists cockpit.estrut_catalogo (
  modulo text not null, tabela text not null, descricao text not null,
  tipo text not null default 'cadastro' check (tipo in ('cadastro','movimento')),
  sugestao text, fonte text, ordem int not null default 0,
  primary key (modulo, tabela)
);

create table if not exists cockpit.estrut_tabelas (
  id uuid primary key default gen_random_uuid(),
  customer text not null, modulo text not null, tabela text not null, descricao text,
  tipo text not null default 'cadastro' check (tipo in ('cadastro','movimento')),
  compart text check (compart ~ '^[EC]{3}$'),
  sugestao text,
  origem text not null default 'catalogo' check (origem in ('catalogo','manual')),
  observacao text, ativo boolean not null default true,
  definido_por text, definido_em timestamptz,
  created_at timestamptz not null default now(),
  unique (customer, modulo, tabela)
);

-- 'nao_mais': tab_b (movimento) não pode ser MAIS compartilhada que tab_a
-- (cadastro) — relacionamento 1:n. 'igual': as duas têm de ser idênticas.
create table if not exists cockpit.estrut_regras (
  id bigserial primary key,
  tipo text not null check (tipo in ('igual','nao_mais')),
  tab_a text not null, tab_b text not null, motivo text not null, fonte text,
  unique (tipo, tab_a, tab_b)
);

create index if not exists estrut_tabelas_cust  on cockpit.estrut_tabelas  (customer, modulo);
create index if not exists estrut_filiais_cust  on cockpit.estrut_filiais  (customer);
create index if not exists estrut_empresas_cust on cockpit.estrut_empresas (customer);

alter table cockpit.estrut_config   enable row level security;
alter table cockpit.estrut_grupos   enable row level security;
alter table cockpit.estrut_empresas enable row level security;
alter table cockpit.estrut_filiais  enable row level security;
alter table cockpit.estrut_tabelas  enable row level security;
alter table cockpit.estrut_catalogo enable row level security;
alter table cockpit.estrut_regras   enable row level security;

-- ── Regras da TDN ──────────────────────────────────────────────────────────
-- Fontes: "Compartilhamento de tabelas de cadastro x movimento (1:n)" e
--         "Compartilhamento de tabelas do módulo Financeiro".
delete from cockpit.estrut_regras;
insert into cockpit.estrut_regras (tipo, tab_a, tab_b, motivo, fonte) values
('nao_mais','SA1','SE1','Cliente (SA1) x título a receber (SE1): 1:n. Título mais compartilhado que o cliente quebra a integridade referencial.','TDN'),
('nao_mais','SA2','SE2','Fornecedor (SA2) x título a pagar (SE2): 1:n.','TDN'),
('nao_mais','SA3','SE1','Vendedor (SA3) x título a receber (SE1): 1:n.','TDN'),
('nao_mais','SA3','SE3','Vendedor (SA3) x comissão (SE3): recálculo de comissões (FINA440) não admite cadastro exclusivo com movimento compartilhado.','TDN'),
('nao_mais','SEH','SE1','Impostos (SEH) x título a receber (SE1): 1:n.','TDN'),
('nao_mais','SEH','SE2','Impostos (SEH) x título a pagar (SE2): 1:n.','TDN'),
('nao_mais','SA6','FK5','Banco (SA6) x rateio do movimento bancário (FK5): 1:n.','TDN'),
('nao_mais','SA6','SEA','Banco (SA6) x itens do borderô (SEA): 1:n.','TDN'),
('nao_mais','SA6','SE8','Banco (SA6) x saldos bancários (SE8): 1:n.','TDN'),
('nao_mais','SA6','SE5','Banco (SA6) x movimentação bancária (SE5): 1:n; afeta o reprocessamento de saldos (FINA210) e o extrato (FINR470).','TDN'),
('nao_mais','SA1','SE5','Refaz Cli/For (FINA410): não é permitido cadastro (SA1) exclusivo com movimento (SE5) compartilhado.','TDN'),
('nao_mais','SA2','SE5','Refaz Cli/For (FINA410): não é permitido cadastro (SA2) exclusivo com movimento (SE5) compartilhado.','TDN'),
('nao_mais','SB1','SB2','Produto (SB1) x saldo em estoque (SB2): 1:n.','TOTVS SC'),
('nao_mais','SB1','SD1','Produto (SB1) x itens da NF de entrada (SD1): 1:n.','TOTVS SC'),
('nao_mais','SB1','SD2','Produto (SB1) x itens da NF de saída (SD2): 1:n.','TOTVS SC'),
('nao_mais','SB1','SD3','Produto (SB1) x movimentos internos (SD3): 1:n.','TOTVS SC'),
('nao_mais','SA1','SC5','Cliente (SA1) x pedido de venda (SC5): 1:n.','TOTVS SC'),
('nao_mais','SA1','SF2','Cliente (SA1) x NF de saída (SF2): 1:n.','TOTVS SC'),
('nao_mais','SA2','SC7','Fornecedor (SA2) x pedido de compra (SC7): 1:n.','TOTVS SC'),
('nao_mais','SA2','SF1','Fornecedor (SA2) x NF de entrada (SF1): 1:n.','TOTVS SC'),
('nao_mais','CT1','CT2','Plano de contas (CT1) x lançamento contábil (CT2): 1:n.','TOTVS SC'),
('nao_mais','CTT','CT2','Centro de custo (CTT) x lançamento contábil (CT2): 1:n.','TOTVS SC'),
('nao_mais','SRA','SRC','Funcionário (SRA) x movimento do período (SRC): 1:n.','TOTVS SC'),
('nao_mais','SRA','SRD','Funcionário (SRA) x histórico de movimentos (SRD): 1:n.','TOTVS SC'),
('nao_mais','SRA','SRH','Funcionário (SRA) x férias (SRH): 1:n.','TOTVS SC'),
('nao_mais','SRA','SRG','Funcionário (SRA) x rescisões (SRG): 1:n.','TOTVS SC'),
('nao_mais','SRV','SRC','Verba (SRV) x movimento do período (SRC): 1:n.','TOTVS SC'),
('nao_mais','SRA','SP0','Funcionário (SRA) x marcações do ponto (SP0): 1:n.','TOTVS SC'),
('nao_mais','SN1','SN3','Bem (SN1) x saldos do ativo (SN3): 1:n.','TOTVS SC'),
('nao_mais','SN1','SN4','Bem (SN1) x movimentos do ativo (SN4): 1:n.','TOTVS SC');

insert into cockpit.estrut_regras (tipo, tab_a, tab_b, motivo, fonte) values
('igual','SE1','SE2','Família SE: todas com o mesmo compartilhamento, exceto SED e SE8.','TDN'),
('igual','SE1','SE3','Família SE: todas com o mesmo compartilhamento, exceto SED e SE8.','TDN'),
('igual','SE1','SE5','Família SE: todas com o mesmo compartilhamento, exceto SED e SE8.','TDN'),
('igual','SE1','SEA','Família SE: todas com o mesmo compartilhamento, exceto SED e SE8.','TDN'),
('igual','SE1','SEB','Família SE: todas com o mesmo compartilhamento, exceto SED e SE8.','TDN'),
('igual','SE5','FK5','Família FK (reestruturação da SE5): mesmo compartilhamento da SE5.','TDN'),
('igual','SE1','FKF','Complemento de título: FKF e FKG seguem o compartilhamento dos títulos (SE1/SE2).','TDN'),
('igual','SA1','F7F','Análise de crédito financeiro (FINAPP001): F7F e SA1 idênticas.','TDN'),
('igual','SE1','MEP','Conciliador pagamentos e vendas (FINA918): SE1 e MEP idênticas.','TDN');
