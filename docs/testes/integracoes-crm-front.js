// Teste do GRUPO CRM × iPaaS da aba Integrações (front), com /api/* interceptado.
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/integracoes-crm-front.js            (SHOT=/tmp/crm.png tira o print)
//
// Cobre: checkbox do grupo, botão "Produção + Teste" só com o grupo ligado,
// cartões do grupo, funil (recebidas → tratadas → projetos → contratos →
// medidos → retorno) com a queda marcada em texto, comparação das duas bases,
// causa do erro com quem resolve, rastreio com contrato ausente da CN9, seção
// de cadastros para o CRM, coleta nas duas bases (liga o grupo na outra) e zero
// erro de JS.
const { chromium } = require('playwright');

const AGORA = new Date().toISOString();
const IND = (chave, rotulo, valor, nivel, texto) => ({ chave, grupo: 'crm', rotulo, valor, nivel, texto });
const INDS = [
  IND('crm_recebidas', 'Propostas recebidas', 5, 'verde', '4 com projetos e contrato gerados (6 mensagem(ns) do iPaaS). Última recebida em 29/10/2026.'),
  IND('crm_erros', 'Propostas com erro', 1, 'vermelho', 'Etapa 1 (recebimento) 0 · Etapa 2 (geração) 1. Mais antiga de 27/10/2026. Por causa: Cliente 1.'),
  IND('crm_fila', 'Paradas na fila', 0, 'verde', 'Fila vazia: tudo o que chegou foi processado.'),
  IND('crm_contratos', 'Contratos gerados', 3, 'vermelho', '3 de 4 contrato(s) gravados na ZA3 existem na CN9; 1 não encontrado(s) — sucesso sem contrato. 7 projeto(s) no Painel.'),
  IND('crm_medicoes', 'Contratos já medidos', '1/3', 'verde', '1 de 3 contrato(s) com medição · 2 medição(ões), 2 encerrada(s).'),
  IND('crm_retorno', 'Retorno ao CRM', null, 'cinza', 'Retorno ao CRM ainda não implementado (P11).'),
  IND('crm_cad_produtos', 'Produtos com preço vigente', '95%', 'verde', '95 de 100 produto(s) ativo(s) têm preço.'),
  IND('crm_cad_tabelas', 'Tabelas de preço vigentes', 1, 'verde', '1 de 2 tabela(s) ativas e vigentes.'),
  IND('crm_params', 'Parâmetros da integração', '3/13', 'verde', 'MV_ZCRMMOD = 2.'),
];
const BLOCOS = {
  crm_totais: { ok: true, linhas: [{ MENSAGENS: '6', PROPOSTAS: '5', LIBERADAS: '5', TRATADAS: '4', CONTRATOS_ZA3: '4', RETORNADAS: '0' }] },
  crm_situacao: { ok: true, linhas: [{ STG1: 'L', STG2: 'S', STIPA: 'N', QTD: '4', PROPOSTAS: '4', MAIS_ANTIGO: '20261001', MAIS_RECENTE: '20261029' },
                                     { STG1: 'L', STG2: 'E', STIPA: 'N', QTD: '2', PROPOSTAS: '1', MAIS_ANTIGO: '20261027', MAIS_RECENTE: '20261027' }] },
  crm_projetos: { ok: true, linhas: [{ TPPROD: '1', STATUS: '1', QTD: '5', CONTRATOS: '3' }, { TPPROD: '2', STATUS: '1', QTD: '2', CONTRATOS: '1' }] },
  crm_contratos: { ok: true, linhas: [{ SITUAC: '02', CONTRATOS: '3', REVISOES: '3', INICIO_MAIS_ANTIGO: '20261001' },
                                      { SITUAC: '10', CONTRATOS: '1', REVISOES: '1', INICIO_MAIS_ANTIGO: '20261001' }] },
  crm_medicoes: { ok: true, linhas: [{ SITUAC: 'E', QTD: '2', CONTRATOS: '1', COM_PEDIDO: '2' }] },
  crm_pendentes_lista: { ok: true, variante: 1, causas: { cliente: 1 }, linhas: [
    { IDCRM: 'OPP-<b>9</b>', STG1: 'L', STG2: 'E', ETAPA: 'VALIDA CABECALHO', DTINC: '20261027', HRINC: '08:00:00', JA_OK: 'N',
      CAUSA: 'cliente', ERRO: 'Cliente 000099/01 não encontrado' },
    { IDCRM: 'OPP-8', STG1: 'L', STG2: 'A', ETAPA: '', DTINC: '20261030', HRINC: '09:00:00', JA_OK: 'N', ERRO: '' }] },
  crm_rastreio_lista: { ok: true, linhas: [
    { IDCRM: 'OPP-1', DTINC: '20261001', HRINC: '09:00:00', DTFIM: '20261001', HRFIM: '09:01:00', CONTRATO: '0001/2026', STIPA: 'N',
      PROPOSTA: 'PROP-1', PROJETOS: '2', SITUAC: '02', MEDICOES: '2' },
    { IDCRM: 'OPP-4', DTINC: '20261020', HRINC: '10:00:00', DTFIM: '20261020', HRFIM: '10:02:00', CONTRATO: '0004/2026', STIPA: 'N',
      PROPOSTA: 'PROP-4', PROJETOS: '1', SITUAC: '', MEDICOES: '0' }] },
  crm_cad_produtos: { ok: true, linhas: [{ TIPO: 'PA', ATIVOS: '80', COM_PRECO: '76', COM_ZFATURA: '80' }] },
  crm_cad_tabelas: { ok: true, linhas: [{ TABELA: '001', DESCRICAO: 'PADRAO', ATIVO: '1', DE: '20260101', ATE: '', ITENS: '90', COM_PRECO: '90' }] },
  crm_sem_preco_lista: { ok: true, linhas: [{ PRODUTO: 'NGC-01', DESCRICAO: 'NGC CORPORATE', TIPO: 'PA', GRUPO: '0001' }] },
  crm_config: { ok: true, linhas: [{ PARAMETRO: 'MV_ZCRMTOK', FILIAL: '', CONTEUDO: '(preenchido)' }] },
};
const ULTIMA = { id: 9, coletado_em: AGORA, duracao_ms: 9100, nivel: 'vermelho', indicadores: INDS,
  blocos: Object.assign({ _meta: { desde: null, grupos: ['crm'] } }, BLOCOS), environment: 'producao',
  disparado_por: 'reges.werlang@totvs.com.br', health: { ok: false } };
const CFG = { url_rest: 'https://x/rest/tscmonit', environment: 'producao', banco: 'oracle', sufixo: '010',
              ativo: true, tem_token: true, tem_senha: true, integ_desde: null, integ_grupos: ['crm'] };
const OUTRA = (o = {}) => Object.assign({ ambiente: 'teste', cadastrada: true, integ_grupos: ['rh'],
  ultima: { coletado_em: AGORA, nivel: 'verde', indicadores: [
    { chave: 'crm_recebidas', grupo: 'crm', rotulo: 'Propostas recebidas', valor: 12, nivel: 'verde' }] } }, o);
const PAYLOAD = (o = {}) => Object.assign({ ok: true, customer: '000348D0', ambiente: 'producao', hoje: '2026-10-30',
  ambiente_cfg: CFG, ultima: ULTIMA, serie: [], coletas: [], outra: OUTRA() }, o);

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  const erros = [];
  pg.on('pageerror', e => { if (!/tailwind|lucide|Chart/i.test(e.message)) erros.push('pageerror: ' + e.message); });
  pg.on('dialog', d => d.accept());
  const pedidos = [];
  const grupos = [];
  pg.on('request', r => { if (r.url().includes('/api/integracoes')) pedidos.push(`${r.method()} ${r.url()}`); });

  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'admin', is_admin: true, interno: true } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [] } }));
  await pg.route('**/api/integracoes/000348D0?*', r => r.fulfill({ json: PAYLOAD() }));
  await pg.route('**/api/integracoes/000348D0/coletar*', async r => {
    await new Promise(res => setTimeout(res, 150));
    r.fulfill({ json: PAYLOAD() });
  });
  await pg.route('**/api/integracoes/000348D0/grupos*', r => {
    grupos.push({ url: r.request().url(), body: JSON.parse(r.request().postData() || '{}') });
    r.fulfill({ json: { ok: true } });
  });

  await pg.goto('http://127.0.0.1:8731/index.html');
  await pg.waitForTimeout(400);
  const ok = [], bad = [];
  const t = (nome, cond, extra) => (cond ? ok : bad).push(nome + (extra ? ` [${extra}]` : ''));
  const txt = (sel) => pg.$eval(sel, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');

  await pg.evaluate(() => {
    state.selected = { cli: '000348D0', cod: '000348D025', ver: '12', loja: 'D0',
                       projeto: { nome_cliente_projeto: 'DIGITRO TECNOLOGIA LTDA' } };
    $('#view-lista').classList.add('hidden');
    $('#view-detalhe').classList.remove('hidden');
    $('#detalhe-conteudo').classList.remove('hidden');
    setTab('integracoes');
  });
  await pg.waitForFunction(() => document.querySelectorAll('#int-conteudo [data-int-ind]').length > 0, null, { timeout: 5000 }).catch(() => {});

  t('checkbox CRM marcado', await pg.$eval('[data-int-grupo="crm"]', n => n.checked));
  t('RH desmarcado', !(await pg.$eval('[data-int-grupo="rh"]', n => n.checked)));
  t('botão Produção + Teste visível', await pg.$eval('#int-coletar-duas', n => !n.classList.contains('hidden')));
  t('9 cartões do grupo', (await pg.$$('#int-conteudo [data-int-ind]')).length === 9);
  const c = await txt('#int-conteudo');
  t('grupo nomeado', /CRM × iPaaS · Painel de Projetos/.test(c));
  t('cartão de erro com rótulo', /✕ Crítico/.test(await txt('[data-int-ind="crm_erros"]')));
  t('retorno cinza explicado', /– Sem dado/.test(await txt('[data-int-ind="crm_retorno"]')) && /P11/.test(await txt('[data-int-ind="crm_retorno"]')));
  t('caixa CRM aberta', /da proposta ao contrato e à medição/.test(c));
  const f = async (k) => txt(`[data-int-funil="${k}"]`);
  t('funil: recebidas 5', /Propostas recebidas\s*5/.test(await f('recebidas')), await f('recebidas'));
  t('funil: tratadas 4 com queda em texto', /4/.test(await f('tratadas')) && /1 a menos/.test(await f('tratadas')), await f('tratadas'));
  t('funil: projetos 7 (soma por OV, sem "queda")', /\b7\b/.test(await f('projetos')) && !/a menos/.test(await f('projetos')));
  t('funil: contratos sem revisão antiga = 3, comparado às tratadas', /Contratos gerados\s*3/.test(await f('contratos'))
    && /1 a menos que tratadas/.test(await f('contratos')), await f('contratos'));
  t('funil: medidos pelo rastreio = 1 de 3, sem alerta', /Contratos medidos\s*1/.test(await f('medidos'))
    && /de 3/.test(await f('medidos')) && !/a menos/.test(await f('medidos')), await f('medidos'));
  t('funil: retorno', /Retorno ao CRM\s*0/.test(await f('retorno')));
  const duas = await txt('[data-int-duas]');
  t('produção × teste lado a lado', /Base Produção × Base de Testes/.test(duas) && /Propostas recebidas\s*5\s*✓ OK\s*12\s*✓ OK/.test(duas), duas.slice(0, 200));
  const linhas = await pg.$$eval('#int-conteudo table tr', trs => trs.map(tr => tr.textContent.replace(/\s+/g, ' ').trim()));
  const lErro = linhas.find(l => /VALIDA CABECALHO/.test(l)) || '';
  t('pendente: causa com rótulo', /Cliente/.test(lErro) && /Erro/.test(lErro) && /Cliente 000099\/01/.test(lErro), lErro);
  const lFila = linhas.find(l => /OPP-8/.test(l)) || '';
  t('pendente na fila sem causa', /na fila/.test(lFila) && /Aguardando/.test(lFila), lFila);
  t('ID escapado', await pg.$('#int-conteudo td b:text-is("9")') === null && /OPP-<b>9<\/b>/.test(c));
  const lSem = linhas.find(l => /OPP-4/.test(l)) || '';
  t('rastreio: contrato fora da CN9 em texto', /não está na CN9/.test(lSem), lSem);
  t('rastreio: situação com nome', /02 · Em elaboração/.test(linhas.find(l => /OPP-1/.test(l)) || ''));
  t('projetos por tipo e situação', linhas.some(l => /1 · Físico/.test(l) && /1 · Em Implantação/.test(l)));
  t('revisão antiga nomeada', linhas.some(l => /10 · Revisado/.test(l)));
  t('medição encerrada com pedido', linhas.some(l => /E · Encerrada/.test(l)) && /Com pedido de venda/.test(c));
  t('seção de cadastros explica P1', /Protheus → CRM · produtos e tabelas de preço/.test(c) && /P1/.test(c));
  t('% com preço', linhas.some(l => /^PA\s*80\s*76\s*95%/.test(l)), linhas.find(l => /^PA/.test(l)));
  t('tabela sem fim de vigência', linhas.some(l => /sem fim/.test(l)));
  t('produto sem preço listado', /NGC CORPORATE/.test(c));
  t('token mascarado', /\(preenchido\)/.test(c));

  // ── coleta nas duas bases: liga o grupo na outra e coleta as duas ─────────
  await pg.click('#int-coletar-duas');
  await pg.waitForTimeout(60);
  t('barra coletando diz Produção + Teste', /Produção \+ Teste/.test(await txt('#int-conteudo')));
  await pg.waitForTimeout(900);
  t('ligou o CRM na base de testes mantendo o RH', grupos.length === 1 && /ambiente=teste/.test(grupos[0].url)
    && JSON.stringify(grupos[0].body.grupos) === '["rh","crm"]', JSON.stringify(grupos));
  const cols = pedidos.filter(p => p.includes('/coletar'));
  t('coletou produção e depois teste', cols.length === 2 && /producao/.test(cols[0]) && /teste/.test(cols[1]), cols.join(' | '));
  t('releu ao fim', /GET .*000348D0\?ambiente=producao/.test(pedidos[pedidos.length - 1]));
  t('botão volta a funcionar', !(await pg.$eval('#int-coletar-duas', n => n.disabled)));

  if (process.env.SHOT) {
    await pg.$eval('#int-conteudo', n => n.scrollIntoView());
    await pg.screenshot({ path: process.env.SHOT, fullPage: true });
  }

  // ── grupo desligado: botão some ───────────────────────────────────────────
  await pg.route('**/api/integracoes/000348D0?*', r => r.fulfill({ json: PAYLOAD({ ambiente_cfg: Object.assign({}, CFG, { integ_grupos: ['rh'] }), ultima: null }) }));
  await pg.click('#int-reload'); await pg.waitForTimeout(300);
  t('sem CRM o botão Produção + Teste some', await pg.$eval('#int-coletar-duas', n => n.classList.contains('hidden')));

  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  await b.close();
  console.log(`${ok.length} OK, ${bad.length} falha(s)`);
  bad.forEach(x => console.log('FALHOU:', x));
  process.exit(bad.length ? 1 : 0);
})();
