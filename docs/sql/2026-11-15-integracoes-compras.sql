-- Aba Integrações — grupo Compras × Transmite × Contas a Pagar (15/11/2026).
--
-- Monitor pós-implantação da unidade que entrou em produção (Cresol: 010000,
-- virada em 26/10/2026). Lê, pela mesma REST TSCMONITREST (só leitura):
--   SC7<suf> → pedidos em aberto e aprovação (C7_CONAPRO)
--   SCR<suf> → alçadas aguardando o aprovador (CR_STATUS 02) · SAK<suf> → nome do aprovador
--   SF1/SD1<suf> → documentos de entrada e pedido por item (D1_PEDIDO)
--   SDS<suf> → Monitor do Importador XML (origem Transmite × manual)
--   SE2<suf> → títulos a pagar por origem (documento × Financeiro)
-- A filial NÃO é parâmetro: fica em COM_IMPLANTACAO (api/index.py), por cliente.
-- Spec: docs/specs/2026-11-15-integracoes-compras.md
--
-- Nenhuma tabela nova: a coleta grava em cockpit.integ_medicoes. Só a lista de
-- grupos aceitos muda.

alter table cockpit.protheus_ambientes drop constraint if exists protheus_ambientes_integ_grupos_check;
alter table cockpit.protheus_ambientes add constraint protheus_ambientes_integ_grupos_check
  check (integ_grupos is null
         or (cardinality(integ_grupos) > 0
             and integ_grupos <@ array['rh','transmite','crm','eai','compras']::text[]));
comment on column cockpit.protheus_ambientes.integ_grupos is
  'Aba Integracoes: grupos coletados nesta base (rh, transmite, crm, eai, compras). Nulo = so rh.';

-- Cresol (TFCTQI00): Transmite + Compras na Produção. Só tem efeito depois que
-- o ⚙ Ambiente da Produção for cadastrado (URL .../rest/tscmonit, token
-- MV_TSCTOKN, sufixo); até lá o update não acha linha e não faz nada. Pode
-- ser ligado também pela tela (☑ TOTVS Transmite ☑ Compras × CP na barra).
update cockpit.protheus_ambientes
   set integ_grupos = array['transmite','compras'], updated_at = now()
 where customer = 'TFCTQI00' and ambiente = 'producao' and integ_grupos is null;
