-- Aba Integrações — grupo CRM × iPaaS × Painel de Projetos (30/10/2026).
--
-- O grupo novo lê, pela mesma REST TSCMONITREST (só leitura), o caminho da
-- proposta ganha no TOTVS CRM até o contrato e a medição no Protheus:
--   ZA3      → registro da integração (Etapa 1 STG1, Etapa 2 STG2, retorno STIPA, ZA3_ERRO)
--   ZA0      → projetos gerados (1 por Ordem de Venda), ligados por ZA0_CONTRA
--   CN9/CND  → contrato gerado (1 por oportunidade) e as medições dele
--   SB1/DA0/DA1 → prontidão dos cadastros que sobem ao CRM (produto com preço vigente)
--   SX6      → MV_ZCRMMOD, MV_ZMAILPP... (tokens só como "(preenchido)")
-- Spec: docs/specs/2026-10-30-integracoes-crm-ipaas.md
--
-- Nenhuma tabela nova: a coleta grava em cockpit.integ_medicoes, como os
-- outros grupos. Só a lista de grupos aceitos muda.

alter table cockpit.protheus_ambientes drop constraint if exists protheus_ambientes_integ_grupos_check;
alter table cockpit.protheus_ambientes add constraint protheus_ambientes_integ_grupos_check
  check (integ_grupos is null
         or (cardinality(integ_grupos) > 0 and integ_grupos <@ array['rh','transmite','crm']::text[]));
comment on column cockpit.protheus_ambientes.integ_grupos is
  'Aba Integracoes: grupos coletados nesta base (rh, transmite, crm). Nulo = so rh.';

-- Dígitro (000348D0): só CRM, nas DUAS bases (Produção e Testes). Só mexe em
-- base que ainda não escolheu grupo (nulo); quem já escolheu fica como está.
update cockpit.protheus_ambientes set integ_grupos = array['crm']
 where customer = '000348D0' and integ_grupos is null;
