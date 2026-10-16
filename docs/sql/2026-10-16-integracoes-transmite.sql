-- Aba Integrações — grupo TOTVS Transmite e grupos por base (16/10/2026).
--
-- Até aqui a aba só lia as filas de RH (Quírons, Ahgora, eSocial SST). O grupo
-- novo lê o caminho do XML de entrada do TOTVS Transmite no Protheus:
--   CKOCOL → XML importados (SCHEDIMPTRA/COMXCOL) e CKO_STRAN (4 = Classificada)
--   SDS    → Importador XML / Monitor (DS_STATUS B = revisão cadastral)
--   SF1    → nota classificada, com F1_DTDIGIT/F1_HORA que vão no evento
--   SX6    → parâmetros do Importador (MV_IMPXML, MV_DTINITR, ...)
--
-- Cada base escolhe o que monitora. Nulo = só RH, que é o comportamento de
-- antes: nenhuma base em produção muda sem alguém ligar o grupo.

alter table cockpit.protheus_ambientes add column if not exists integ_grupos text[];
comment on column cockpit.protheus_ambientes.integ_grupos is
  'Aba Integracoes: grupos coletados nesta base (rh, transmite). Nulo = so rh.';

alter table cockpit.protheus_ambientes drop constraint if exists protheus_ambientes_integ_grupos_check;
alter table cockpit.protheus_ambientes add constraint protheus_ambientes_integ_grupos_check
  check (integ_grupos is null
         or (cardinality(integ_grupos) > 0 and integ_grupos <@ array['rh','transmite']::text[]));

-- Rio Deserto (TFDPHR00): só Transmite. Só tem efeito depois que o ⚙ Ambiente
-- da base for cadastrado (URL .../rest/tscmonit, token MV_TSCTOKN, sufixo 010);
-- até lá o update não acha linha e não faz nada. Pode ser ligado também pela
-- própria tela (☑ TOTVS Transmite na barra da aba).
update cockpit.protheus_ambientes set integ_grupos = array['transmite']
 where customer = 'TFDPHR00' and integ_grupos is null;
