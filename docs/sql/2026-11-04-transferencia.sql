-- Transferência de cadastros entre bases (04/11/2026)
-- Cada lote GRAVADO (não a simulação) entra no log de coletas com tipo
-- 'transferencia', no ambiente DESTINO. Entram também 'tributos' e 'diagnostico',
-- que o backend já gravava e a constraint recusava (o log falhava calado). Spec:
-- docs/specs/2026-11-04-transferencia-cadastros-entre-bases.md
alter table cockpit.protheus_coletas drop constraint if exists protheus_coletas_tipo_check;
alter table cockpit.protheus_coletas add constraint protheus_coletas_tipo_check
  check (tipo = any (array['cadastros','movimentos','ping','sm0','empresas','integracoes',
                           'auditoria','tributos','diagnostico','transferencia']));
