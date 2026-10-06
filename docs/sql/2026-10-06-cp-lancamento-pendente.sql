-- Painel CP — foto da fila "pendentes de LANÇAMENTO" (agenda realizada sem OS).
--
-- Até 05/10/2026 a tela lia a agenda da célula AO VIVO na API Totvs SC toda vez
-- que abria. Agora ela lê ESTA tabela; a API só é chamada:
--   (1) pelo pg_cron `projetos-cp-lancamento-2h` (GET /api/cron/cp-lancamento)
--   (2) pelo botão "↻ Atualizar" do painel (GET /api/cp/lancamento?live=1)
-- Cada leitura ao vivo que termina sem truncar REFAZ a foto do escopo que leu
-- (janela de datas + cliente, se houver): o que não voltou da API ganhou OS e sai.

create table if not exists cockpit.cp_lanc_pendente (
  agenda_id   text primary key,          -- id da agenda na API (ou chave composta)
  data        date not null,             -- dia da agenda
  cliente     text,                      -- customer com padding (ex.: 04506 00)
  owner       text,                      -- matrícula de quem marcou a agenda
  owner_nome  text,
  projeto     text,                      -- codigo_projeto (10 chars)
  dados       jsonb not null,            -- linha achatada por _cp_pendentes()
  synced_at   timestamptz not null default now()
);
create index if not exists cp_lanc_pendente_data_idx on cockpit.cp_lanc_pendente (data);
create index if not exists cp_lanc_pendente_cliente_idx on cockpit.cp_lanc_pendente (cliente);

-- Uma linha por leitura ao vivo (cron ou botão): é o que a tela mostra como
-- "foto de HH:MM" e o que diz qual janela a foto automática cobre.
create table if not exists cockpit.cp_lanc_sync (
  id         bigserial primary key,
  origem     text not null,              -- 'cron' | 'botao'
  de         date not null,
  ate        date not null,
  cliente    text not null default '',   -- '' = célula inteira
  total      int  not null default 0,
  removidos  int  not null default 0,
  truncado   boolean not null default false,
  diag       jsonb,
  criado_em  timestamptz not null default now()
);
create index if not exists cp_lanc_sync_criado_idx on cockpit.cp_lanc_sync (criado_em desc);

-- Mesmo padrão das outras tabelas do cockpit: RLS ligado sem policy; o Flask
-- acessa pelo DATABASE_URL (role postgres), a anon key não enxerga nada.
alter table cockpit.cp_lanc_pendente enable row level security;
alter table cockpit.cp_lanc_sync enable row level security;

-- Agendamento (rodar DEPOIS do deploy; secret copiado do job projetos-sync):
-- select cron.schedule('projetos-cp-lancamento-2h', '40 */2 * * *',
--   $$ select net.http_get(
--        url := 'https://projetos-totvs-sc.vercel.app/api/cron/cp-lancamento',
--        headers := jsonb_build_object('Authorization', 'Bearer <CRON_SECRET>'),
--        timeout_milliseconds := 60000) $$)
