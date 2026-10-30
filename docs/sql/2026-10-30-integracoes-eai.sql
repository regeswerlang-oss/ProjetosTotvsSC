-- Aba Integrações — grupo EAI Protheus × Schedule (30/10/2026).
--
-- O grupo lê, pela mesma REST TSCMONITREST (só leitura):
--   XX4<suf> → adapters da Mensagem Única       XX3<suf> → fila do EAI (status, canal, tentativas)
--   XXF      → de-para gravado no retorno        XXD      → de-para de empresa/filial
--   XX1/XX2  → agendamentos do Schedule          SCHDTSK  → tarefas geradas    XX0 → agents
--   SX6      → MV_EAI* (MV_EAIPASS só como "(preenchido)")
-- Nunca lê XX3_URL (a URL do iPaaS leva a api-key) nem XX3_TRANS (a mensagem).
-- Spec: docs/specs/2026-10-30-integracoes-eai-schedule.md
--
-- Nenhuma tabela nova: a coleta grava em cockpit.integ_medicoes. Só a lista de
-- grupos aceitos muda. Inclui o 'crm' (PR #5) para as duas migrações poderem
-- rodar em qualquer ordem.

alter table cockpit.protheus_ambientes drop constraint if exists protheus_ambientes_integ_grupos_check;
alter table cockpit.protheus_ambientes add constraint protheus_ambientes_integ_grupos_check
  check (integ_grupos is null
         or (cardinality(integ_grupos) > 0 and integ_grupos <@ array['rh','transmite','crm','eai']::text[]));
comment on column cockpit.protheus_ambientes.integ_grupos is
  'Aba Integracoes: grupos coletados nesta base (rh, transmite, crm, eai). Nulo = so rh.';

-- Dígitro (000348D0): liga o EAI nas DUAS bases, mantendo o que cada uma já
-- monitora. Base sem grupo (nulo) passa a monitorar só o EAI.
update cockpit.protheus_ambientes
   set integ_grupos = case when integ_grupos is null then array['eai']
                           else array_append(integ_grupos, 'eai') end,
       updated_at = now()
 where customer = '000348D0'
   and (integ_grupos is null or not ('eai' = any(integ_grupos)));
