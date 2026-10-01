-- Aba Estrutura de Empresas — trilha de ALTERAÇÕES e PROPOSTAS de compartilhamento.
-- Aplicado no Supabase kpimalwnswxalwbidkog em 01/10/2026 como a migration
--   estrutura_alteracoes_propostas
-- Spec: docs/specs/2026-10-01-estrutura-alteracoes-e-propostas.md
--
-- Por que existe: dois consultores mexem na mesma definição. Sem trilha, quem
-- chega depois troca o compartilhamento sem saber que outro já tinha decidido
-- — e a decisão some sem discussão. A trilha diz QUEM mudou; a proposta abre a
-- conversa ANTES de mudar.

-- 1) Histórico: uma linha por troca REAL de compartilhamento (antes <> depois).
--    Semear do catálogo NÃO grava aqui: semente é ponto de partida, não decisão.
create table if not exists cockpit.estrut_tabelas_hist (
  id            uuid primary key default gen_random_uuid(),
  tabela_id     uuid not null references cockpit.estrut_tabelas(id) on delete cascade,
  customer      text not null,
  tabela        text not null,
  compart_antes text,
  compart_depois text,
  origem        text not null default 'edicao'
                check (origem in ('edicao','proposta','manual','legado')),
  proposta_id   uuid,
  alterado_por  text,
  alterado_em   timestamptz not null default now()
);
create index if not exists estrut_tabelas_hist_cli
  on cockpit.estrut_tabelas_hist (customer, tabela_id, alterado_em desc);

-- 2) Propostas: o consultor que discorda registra a SUA sugestão sem sobrescrever
--    a definição. Fica aberta até alguém aplicar (vira a definição + histórico)
--    ou descartar (com o porquê).
create table if not exists cockpit.estrut_propostas (
  id            uuid primary key default gen_random_uuid(),
  tabela_id     uuid not null references cockpit.estrut_tabelas(id) on delete cascade,
  customer      text not null,
  tabela        text not null,
  compart       text not null check (compart ~ '^[EC]{3}$'),
  compart_na_hora text,                -- o que estava definido quando foi proposta
  motivo        text not null,
  autor         text,
  criado_em     timestamptz not null default now(),
  status        text not null default 'aberta'
                check (status in ('aberta','aplicada','descartada')),
  resolvido_por text,
  resolvido_em  timestamptz,
  resolucao     text
);
create index if not exists estrut_propostas_cli
  on cockpit.estrut_propostas (customer, tabela_id, criado_em desc);

alter table cockpit.estrut_tabelas_hist enable row level security;
alter table cockpit.estrut_propostas    enable row level security;

-- 3) Legado: definição que já fugia da sugestão antes desta trilha existir vira
--    UMA linha 'legado' com quem gravou por último — melhor que ✓ sem autor.
insert into cockpit.estrut_tabelas_hist
  (tabela_id, customer, tabela, compart_antes, compart_depois, origem,
   alterado_por, alterado_em)
select t.id, t.customer, t.tabela, t.sugestao, t.compart, 'legado',
       t.definido_por, coalesce(t.definido_em, t.created_at)
  from cockpit.estrut_tabelas t
 where t.compart is not null and t.sugestao is not null
   and t.compart <> t.sugestao
   and not exists (select 1 from cockpit.estrut_tabelas_hist h where h.tabela_id = t.id);
