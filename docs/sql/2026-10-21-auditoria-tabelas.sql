-- Aba "Auditoria de Tabelas" - 21/10/2026
-- Compartilhamento (SX2) e volume por filial, Teste x Producao, contra o alvo
-- da aba Estrutura. Aditiva: nada existente muda de comportamento.

-- 1) Uma linha por coleta (cliente, base, momento). Guarda historico: a
--    comparacao Teste x Producao so existe se a leitura da primeira base
--    ainda estiver la quando a segunda chegar.
create table if not exists cockpit.audtab_coletas (
  id               bigint generated always as identity primary key,
  customer         text not null references cockpit.clientes(customer) on delete cascade,
  ambiente         text not null check (ambiente in ('producao','teste')),
  lido_em          timestamptz not null default now(),
  environment      text,
  sufixo           text,
  banco            text,
  leiaute          text,           -- de onde veio o tamanho empresa/unidade (SM0, Estrutura, padrao)
  duracao_ms       integer,
  tabelas_lidas    integer,
  total_registros  numeric,
  fora_padrao      numeric,        -- registros com _FILIAL fora do padrao do ALVO
  disparado_por    text
);
create index if not exists audtab_coletas_cli_idx
  on cockpit.audtab_coletas (customer, ambiente, lido_em desc);

-- 2) Itens: tabela x conteudo do campo filial (filial null = tabela sem registro).
create table if not exists cockpit.audtab_itens (
  id          bigint generated always as identity primary key,
  coleta_id   bigint not null references cockpit.audtab_coletas(id) on delete cascade,
  customer    text not null,
  ambiente    text not null,
  tabela      text not null,
  nome        text,
  arquivo     text,
  sx2         text,               -- X2_MODOEMP || X2_MODOUN || X2_MODO (ex.: EEC)
  existe      boolean not null default false,
  tem_filial  boolean not null default false,
  filial      text,
  qtde        numeric not null default 0
);
create index if not exists audtab_itens_coleta_idx on cockpit.audtab_itens (coleta_id);

-- Mesmo padrao das demais cockpit.monit*/estrut_*: RLS ligada, sem policy
-- (o app acessa pelo DATABASE_URL do servidor; anon/authenticated nao leem).
alter table cockpit.audtab_coletas enable row level security;
alter table cockpit.audtab_itens   enable row level security;

-- 3) Log de coleta passa a aceitar o tipo novo.
alter table cockpit.protheus_coletas drop constraint if exists protheus_coletas_tipo_check;
alter table cockpit.protheus_coletas add constraint protheus_coletas_tipo_check
  check (tipo = any (array['cadastros','movimentos','ping','sm0','empresas','integracoes','auditoria']));

-- 4) Regras do Configurador de Tributos na conferencia da aba Estrutura.
--    Fonte: TDN CFGTRIB - Compartilhamento de Tabelas e orientacao da
--    consultoria fiscal TOTVS SC (30/09/2026):
--    - o cabecalho de perfis (F20) tem o MESMO nivel de todos os perfis filhos;
--    - base, aliquota, regra tributaria e escrituracao usam a MESMA tabela de
--      formulas (CIN), entao andam no mesmo nivel dela.
insert into cockpit.estrut_regras (tipo, tab_a, tab_b, motivo, fonte) values
  ('igual','F20','F21','Cabeçalho de perfis (F20) no mesmo nível do perfil Origem x Destino','TDN CFGTRIB / TOTVS SC'),
  ('igual','F20','F22','Cabeçalho de perfis (F20) no mesmo nível do perfil de participante','TDN CFGTRIB / TOTVS SC'),
  ('igual','F20','F23','Cabeçalho de perfis (F20) no mesmo nível do perfil de operação','TDN CFGTRIB / TOTVS SC'),
  ('igual','F20','F24','Cabeçalho de perfis (F20) no mesmo nível do perfil de produto','TDN CFGTRIB / TOTVS SC'),
  ('igual','F20','F25','Cabeçalho de perfis (F20) no mesmo nível de produto x origem','TDN CFGTRIB / TOTVS SC'),
  ('igual','F20','F26','Cabeçalho de perfis (F20) no mesmo nível do tipo de operação','TDN CFGTRIB / TOTVS SC'),
  ('igual','F20','CIO','Cabeçalho de perfis (F20) no mesmo nível do cód. ISS do perfil de operação','TDN CFGTRIB / TOTVS SC'),
  ('igual','CIN','F27','Fórmula (CIN) é única para todas as regras: base de cálculo no mesmo nível','TDN CFGTRIB / TOTVS SC'),
  ('igual','CIN','F28','Fórmula (CIN) é única para todas as regras: alíquota no mesmo nível','TDN CFGTRIB / TOTVS SC'),
  ('igual','CIN','F2B','Fórmula (CIN) é única para todas as regras: regra tributária no mesmo nível','TDN CFGTRIB / TOTVS SC'),
  ('igual','CIN','CJ2','Fórmula (CIN) é única para todas as regras: escrituração no mesmo nível','TDN CFGTRIB / TOTVS SC')
on conflict (tipo, tab_a, tab_b) do nothing;
