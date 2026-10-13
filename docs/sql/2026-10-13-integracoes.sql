-- Aba Integrações — retrato das filas de integração RH da base do cliente.
--
-- Cada clique em "⚡ Coletar agora" roda, pela REST TSCMONITREST da base, um
-- conjunto de consultas SÓ LEITURA sobre as filas das integrações:
--   RJP / RU7  → Protheus → Quírons (fila de envio e histórico de erros)
--   RUM        → Protheus → Ahgora (funcionários e afastamentos)
--   RJE        → eventos SST do eSocial (S-2210, S-2220, S-2240) no Middleware
--   SX6        → parâmetros que ligam/desligam cada integração
-- e chama o healthcheck da integração Quírons (/api/rh/v1/integrationcheck/healthcheck).
--
-- UMA LINHA POR COLETA. A série histórica sai daqui: é ela que mostra se a fila
-- está crescendo ou zerando — o número de um dia só não diz isso.
-- `indicadores` = lista já calculada (chave, rótulo, valor, nível, texto);
-- `blocos`      = o CSV de cada consulta, já em linhas, para a tela detalhar;
-- `health`      = resposta do healthcheck (ou o motivo de não ter vindo).

create table if not exists cockpit.integ_medicoes (
  id            bigserial primary key,
  customer      text not null references cockpit.clientes(customer) on update cascade,
  ambiente      text not null check (ambiente in ('producao','teste')),
  coletado_em   timestamptz not null default now(),
  duracao_ms    integer,
  nivel         text not null check (nivel in ('verde','amarelo','vermelho','cinza')),
  indicadores   jsonb not null default '[]'::jsonb,
  blocos        jsonb not null default '{}'::jsonb,
  health        jsonb,
  environment   text,
  disparado_por text
);

create index if not exists integ_medicoes_cliente_idx
  on cockpit.integ_medicoes (customer, ambiente, coletado_em desc);

-- Mesmo padrão das outras tabelas do cockpit: RLS ligado sem policy; o Flask
-- acessa pelo DATABASE_URL, a anon key não enxerga nada.
alter table cockpit.integ_medicoes enable row level security;

-- O log de disparos passa a aceitar o tipo novo.
alter table cockpit.protheus_coletas drop constraint if exists protheus_coletas_tipo_check;
alter table cockpit.protheus_coletas add constraint protheus_coletas_tipo_check
  check (tipo = any (array['cadastros','movimentos','ping','sm0','empresas','integracoes']));
