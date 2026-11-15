// Teste do GRUPO Compras × Transmite × Contas a Pagar da aba Integrações (front),
// com /api/* interceptado. Dados SIMULADOS da unidade 010000 da Cresol.
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/integracoes-compras-front.js        (SHOT=/tmp/compras.png tira o print)
//
// Cobre: checkbox do grupo, cartões, caixa com a unidade e o início vindos do
// _meta, aprovação com rótulo, alçada com aprovador e dias, situação do item
// (entrega vencida), motivo de o documento estar fora do fluxo, XML lançado
// por fora, classes do contas a pagar, clique no cartão abre o detalhe,
// texto escapado e zero erro de JS.
const { chromium } = require('playwright');

const AGORA = new Date().toISOString();
const IND = (chave, rotulo, valor, nivel, texto) => ({ chave, grupo: 'compras', rotulo, valor, nivel, texto });
const INDS = [
  IND('com_pc_aprovacao', 'Pedidos aguardando aprovação', 4, 'vermelho', 'R$ 18.500,40 em aprovação. 2 pedido(s) emitido(s) há mais de 5 dias.'),
  IND('com_pc_abertos', 'Pedidos em aberto', 22, 'info', 'R$ 138.800,40 a receber.'),
  IND('com_pc_entrega', 'Itens com entrega vencida', 5, 'amarelo', 'Itens de pedido liberado com a data de entrega vencida.'),
  IND('com_doc_transmite', 'Entradas pelo Transmite', '45/51', 'amarelo', '6 nota(s) normal(is) lançada(s) sem passar pelo Monitor.'),
  IND('com_doc_sem_pc', 'Notas sem pedido de compra', 9, 'amarelo', '3 veio(ram) pelo Transmite sem amarração.'),
  IND('com_doc_prenota', 'Pré-notas sem classificar', 2, 'amarelo', 'A mais antiga foi digitada em 06/11/2026 (9 dia(s)).'),
  IND('com_doc_sem_titulo', 'Classificadas sem título', 1, 'vermelho', 'Nota classificada com duplicata e nenhum título na SE2.'),
  IND('com_monitor', 'XML no Monitor sem documento', 6, 'vermelho', '2 com ocorrência (E).'),
  IND('com_cp_origem', 'Títulos por origem', 66, 'info', 'Documento · Transmite 44.'),
  IND('com_cp_vencidos', 'Vencidos em aberto', 3, 'amarelo', 'R$ 3.600,00 vencido(s) e não baixado(s).'),
];
const BLOCOS = {
  com_pc_resumo: { ok: true, linhas: [
    { APROVACAO: 'B', ITENS: '9', PEDIDOS: '4', SALDO: '18500.40', MAIS_ANTIGO: '20261103', PEDIDOS_ANTIGOS: '2', ENTREGA_VENCIDA: '3', PARCIAIS: '0', EM_PRENOTA: '0' },
    { APROVACAO: 'L', ITENS: '30', PEDIDOS: '17', SALDO: '120000', MAIS_ANTIGO: '20261027', PEDIDOS_ANTIGOS: '12', ENTREGA_VENCIDA: '5', PARCIAIS: '4', EM_PRENOTA: '2' }] },
  com_pc_aprov: { ok: true, linhas: [
    { FILIAL: '010000', PEDIDO: '000100', TIPO: 'PC', NIVEL: '01', APROVADOR: '000010', NOME: 'GESTOR EXEMPLO', EMISSAO: '20261101', VALOR: '250' }] },
  com_pc_lista: { ok: true, linhas: [
    { FILIAL: '010000', PEDIDO: '000101', ITEM: '0001', EMISSAO: '20261027', ENTREGA: '20261110', FORNECEDOR: '000214', LOJA: '01',
      NOME: 'TI SERVICOS EXEMPLO', PRODUTO: 'SV0102', DESCRICAO: 'SUPORTE', QUANT: '5', QUJE: '2', EM_PRENOTA: '1', SALDO: '300', APROVACAO: 'L', SC: '', CC: '4001' },
    { FILIAL: '010000', PEDIDO: '000100', ITEM: '0001', EMISSAO: '20261101', ENTREGA: '20261105', FORNECEDOR: '000101', LOJA: '01',
      NOME: 'PAPELARIA <b>X</b>', PRODUTO: 'MC0001', DESCRICAO: 'PAPEL A4', QUANT: '10', QUJE: '0', EM_PRENOTA: '0', SALDO: '250', APROVACAO: 'B', SC: '000050', CC: '4001' }] },
  com_doc_resumo: { ok: true, linhas: [
    { ORIGEM: 'T', TIPO: 'N', PC: 'COM', STATUS: 'A', QTD: '40', VALOR: '200000', MAIS_ANTIGA: '20261026', SEM_TITULO: '1' },
    { ORIGEM: 'M', TIPO: 'N', PC: 'SEM', STATUS: 'A', QTD: '5', VALOR: '4200.5', MAIS_ANTIGA: '20261028', SEM_TITULO: '0' }] },
  com_doc_lista: { ok: true, linhas: [
    { FILIAL: '010000', DOC: '000000003', SERIE: '1  ', FORNECEDOR: '000101', LOJA: '01', NOME: 'PAPELARIA EXEMPLO', ESPECIE: 'SPED',
      TIPO: 'N', EMISSAO: '20261105', DIGIT: '20261105', VALOR: '80', ORIGEM: 'M', PC: 'PARCIAL', STATUS: 'P', SEM_TITULO: '0', PEDIDO: '000101' },
    { FILIAL: '010000', DOC: '000000002', SERIE: '1  ', FORNECEDOR: '000214', LOJA: '01', NOME: 'TI SERVICOS EXEMPLO', ESPECIE: 'NFS',
      TIPO: 'N', EMISSAO: '20261029', DIGIT: '20261029', VALOR: '500', ORIGEM: 'T', PC: 'SEM', STATUS: 'A', SEM_TITULO: '1', PEDIDO: '' }] },
  com_mon_resumo: { ok: true, linhas: [{ STATUS: 'E', QTD: '2', JA_SF1: '0' }] },
  com_mon_lista: { ok: true, variante: 0, linhas: [
    { FILIAL: '010000', DOC: '000000009', SERIE: '1', FORNECEDOR: '000214', LOJA: '01', TIPO: 'N', STATUS: 'E', EMISSAO: '20261110', JA_SF1: '0', NOME: 'TI' },
    { FILIAL: '010000', DOC: '000000003', SERIE: '1', FORNECEDOR: '000101', LOJA: '01', TIPO: 'N', STATUS: '-', EMISSAO: '20261105', JA_SF1: '1', NOME: 'PAPELARIA' }] },
  com_cp_resumo: { ok: true, linhas: [
    { CLASSE: 'DOC_TRANSMITE', ORIGEM: 'MATA100', QTD: '44', VALOR: '205000', SALDO: '90000', VENCIDOS: '2', SALDO_VENCIDO: '3100' },
    { CLASSE: 'FINANCEIRO', ORIGEM: 'FINA050', QTD: '7', VALOR: '10464.28', SALDO: '4153.34', VENCIDOS: '1', SALDO_VENCIDO: '500' }] },
  com_cp_lista: { ok: true, linhas: [
    { FILIAL: '010000', PREFIXO: 'FIN', NUMERO: '000000900', PARCELA: '', TIPO: 'DP', FORNECEDOR: '000214', LOJA: '01', NOME: 'TI',
      CONTABIL: '20261101', VENCIMENTO: '20261201', VALOR: '300', SALDO: '300', ORIGEM: 'FINA050', NATUREZA: '20199', CLASSE: 'FINANCEIRO', VENCIDO: '0' },
    { FILIAL: '010000', PREFIXO: '1', NUMERO: '000000001', PARCELA: '', TIPO: 'NF', FORNECEDOR: '000101', LOJA: '01', NOME: 'PAPELARIA',
      CONTABIL: '20261028', VENCIMENTO: '20261110', VALOR: '250', SALDO: '250', ORIGEM: 'MATA100', NATUREZA: '20101', CLASSE: 'DOC_TRANSMITE', VENCIDO: '1' }] },
};
const ULTIMA = { id: 11, coletado_em: AGORA, duracao_ms: 6200, nivel: 'vermelho', indicadores: INDS,
  blocos: Object.assign({ _meta: { desde: null, grupos: ['transmite', 'compras'], com_filiais: ['010000'], com_inicio: '2026-10-26' } }, BLOCOS),
  environment: 'producao', disparado_por: 'reges.werlang@totvs.com.br', health: { ok: false } };
const CFG = { url_rest: 'https://x/rest/tscmonit', environment: 'producao', banco: 'oracle', sufixo: '010',
              ativo: true, tem_token: true, tem_senha: false, integ_desde: null, integ_grupos: ['transmite', 'compras'] };
const PAYLOAD = (o = {}) => Object.assign({ ok: true, customer: 'TFCTQI00', ambiente: 'producao', hoje: '2026-11-15',
  ambiente_cfg: CFG, ultima: ULTIMA, serie: [], coletas: [], outra: { ambiente: 'teste', cadastrada: false } }, o);

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  const erros = [];
  pg.on('pageerror', e => { if (!/tailwind|lucide|Chart/i.test(e.message)) erros.push('pageerror: ' + e.message); });
  pg.on('dialog', d => d.accept());
  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'admin', is_admin: true, interno: true } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [] } }));
  await pg.route('**/api/integracoes/TFCTQI00?*', r => r.fulfill({ json: PAYLOAD() }));

  await pg.goto('http://127.0.0.1:8731/index.html');
  await pg.waitForTimeout(400);
  const ok = [], bad = [];
  const t = (nome, cond, extra) => (cond ? ok : bad).push(nome + (extra ? ` [${extra}]` : ''));
  const txt = (sel) => pg.$eval(sel, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');

  await pg.evaluate(() => {
    state.selected = { cli: 'TFCTQI00', cod: 'TFCTQI0025', ver: '12', loja: '00',
                       projeto: { nome_cliente_projeto: 'CRESOL CONFEDERACAO' } };
    $('#view-lista').classList.add('hidden');
    $('#view-detalhe').classList.remove('hidden');
    $('#detalhe-conteudo').classList.remove('hidden');
    setTab('integracoes');
  });
  await pg.waitForFunction(() => document.querySelectorAll('#int-conteudo [data-int-ind]').length > 0, null, { timeout: 5000 }).catch(() => {});

  t('checkbox Compras marcado', await pg.$eval('[data-int-grupo="compras"]', n => n.checked));
  t('checkbox Transmite marcado', await pg.$eval('[data-int-grupo="transmite"]', n => n.checked));
  t('RH desmarcado', !(await pg.$eval('[data-int-grupo="rh"]', n => n.checked)));
  t('10 cartões do grupo', (await pg.$$('#int-conteudo [data-int-grupo="compras"][data-int-ind]')).length === 10);
  const c = await txt('#int-conteudo');
  t('grupo nomeado', /Compras × Transmite × Contas a Pagar/.test(c));
  t('unidade e início na caixa', /Unidade 010000 · em produção desde 26\/10\/2026/.test(c), c.slice(0, 400));
  t('cartão crítico com rótulo', /✕ Crítico/.test(await txt('[data-int-ind="com_pc_aprovacao"]')));
  t('cartão informativo', /Informativo/.test(await txt('[data-int-ind="com_pc_abertos"]')));

  // abre todas as subseções
  await pg.$$eval('#int-conteudo details.int-sub', ds => ds.forEach(d => { d.open = true; }));
  const linhas = await pg.$$eval('#int-conteudo table tr', trs => trs.map(tr => tr.textContent.replace(/\s+/g, ' ').trim()));
  t('resumo de aprovação com rótulo', linhas.some(l => /Aguardando aprovação\s*4\s*9/.test(l)), linhas.find(l => /Aguardando/.test(l)));
  t('saldo em reais', linhas.some(l => /R\$\s*18\.500,40/.test(l)));
  t('alçada com aprovador e dias', linhas.some(l => /000100/.test(l) && /GESTOR EXEMPLO \(000010\)/.test(l) && /01\/11\/2026\s*14/.test(l)),
    linhas.find(l => /GESTOR/.test(l)));
  const lVenc = linhas.find(l => /000101\s*0001/.test(l)) || '';
  t('item liberado com entrega vencida, parcial e em pré-nota', /Entrega vencida/.test(lVenc) && /Atendido em parte/.test(lVenc) && /Em pré-nota/.test(lVenc), lVenc);
  const lBloq = linhas.find(l => /000100\s*0001/.test(l)) || '';
  t('item bloqueado sem "entrega vencida"', /Aguardando aprovação/.test(lBloq) && !/Entrega vencida/.test(lBloq), lBloq);
  t('nome escapado', /PAPELARIA <b>X<\/b>/.test(c));
  const lDoc3 = linhas.find(l => /000000003\/1/.test(l) && /Por que|Fora do Monitor/.test(l)) || '';
  t('documento manual em parte e pré-nota', /Fora do Monitor/.test(lDoc3) && /Pedido em parte/.test(lDoc3) && /Pré-nota/.test(lDoc3), lDoc3);
  const lDoc2 = linhas.find(l => /000000002\/1/.test(l)) || '';
  t('documento Transmite sem pedido e sem título', /Sem pedido/.test(lDoc2) && /Sem título/.test(lDoc2) && !/Fora do Monitor/.test(lDoc2), lDoc2);
  t('XML com ocorrência', linhas.some(l => /000000009\/1/.test(l) && /Ocorrência \(E\)/.test(l)));
  t('XML lançado por fora', linhas.some(l => /000000003\/1/.test(l) && /Sim — lançada por fora/.test(l)));
  t('CP por classe', linhas.some(l => /Documento · Transmite\s*MATA100\s*44/.test(l)) && linhas.some(l => /Lançado no Financeiro\s*FINA050\s*7/.test(l)));
  t('título vencido em aberto', linhas.some(l => /000000001/.test(l) && /Vencido em aberto/.test(l)));
  t('rodapé explica a regra', /não é parâmetro de tela/.test(c));

  // clique no cartão leva ao detalhe
  await pg.$$eval('#int-conteudo details.int-sub', ds => ds.forEach(d => { d.open = false; }));
  await pg.click('[data-int-ind="com_doc_sem_titulo"]'); await pg.waitForTimeout(200);
  t('cartão abre "Documentos fora do fluxo"', await pg.$eval('details[data-int-sub="Documentos fora do fluxo"]', n => n.open).catch(() => false));

  if (process.env.SHOT) {
    await pg.$$eval('#int-conteudo details.int-sub', ds => ds.forEach(d => { d.open = true; }));
    await pg.$eval('#int-conteudo', n => n.scrollIntoView());
    await pg.screenshot({ path: process.env.SHOT, fullPage: true });
  }
  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  await b.close();
  console.log(`${ok.length} OK, ${bad.length} falha(s)`);
  bad.forEach(x => console.log('FALHOU:', x));
  process.exit(bad.length ? 1 : 0);
})();
