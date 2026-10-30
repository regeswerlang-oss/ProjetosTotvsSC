// Teste do GRUPO EAI × Schedule da aba Integrações (front), com /api/* interceptado.
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/integracoes-eai-front.js            (SHOT=/tmp/eai.png tira o print)
//
// Cobre: checkbox do grupo, botão "Produção + Teste" também para o EAI,
// cartões do grupo, caminho da mensagem (fila → falha → entregue → de-para)
// com alerta em texto, status da XX3 com código + rótulo, agendamento que
// nunca executou em texto, recorrência e tarefas por agendamento, XXF vazia
// explicada, coleta nas duas bases ligando o grupo EAI na outra e zero erro.
const { chromium } = require('playwright');

const AGORA = new Date().toISOString();
const IND = (chave, rotulo, valor, nivel, texto) => ({ chave, grupo: 'eai', rotulo, valor, nivel, texto });
const INDS = [
  IND('eai_sem_retorno', 'Entregues sem retorno', 969, 'vermelho', 'A mais antiga espera há 1 d 18 h.'),
  IND('eai_falhas', 'Mensagens com falha', 12, 'vermelho', '12 com 4 tentativas ou mais.'),
  IND('eai_aguardando', 'Aguardando envio', 0, 'verde', 'Nada parado antes do envio.'),
  IND('eai_canal', 'Canal diferente do adapter', 6, 'amarelo', 'SELLER 6 no canal ESB (TOTVS ESB).'),
  IND('eai_depara', 'De-para (XXF)', 0, 'vermelho', 'XXF vazia com 8 mensagem(ns) de cadastro enviada(s).'),
  IND('eai_cobertura', 'Cadastros sem envio', 1, 'vermelho', 'PRICELISTHEADERITEM (DA0: 7 registro(s), 0 mensagem).'),
  IND('eai_jobs', 'Jobs do EAI no Schedule', '0/2', 'vermelho', 'FWEAIRECE agendado (000003) e nunca executou.'),
  IND('eai_agendamentos', 'Agendamentos parados', 2, 'vermelho', '2 de 4 agendamento(s) com início no passado e nenhuma execução.'),
  IND('eai_params', 'Parâmetros do EAI', '3/13', 'amarelo', 'MV_EAIPORT = WS_ERPProtheusToGFE sem adapter de envio no canal ESB.'),
];
const BLOCOS = {
  eai_status: { ok: true, linhas: [
    { MENSAGEM: 'CUSTOMERVENDOR', STATUS: '7', CANAL: '3', TPTRAN: '1', QTD: '821', ESGOTADAS: '0', COM_DESTINO: '821', MAIS_ANTIGA: '20261029', MAIS_RECENTE: '20261029' },
    { MENSAGEM: 'SELLER', STATUS: '5', CANAL: '1', TPTRAN: '1', QTD: '6', ESGOTADAS: '6', COM_DESTINO: '0', MAIS_ANTIGA: '20261030', MAIS_RECENTE: '20261030' },
    { MENSAGEM: 'SELLER', STATUS: '7', CANAL: '3', TPTRAN: '1', QTD: '11', ESGOTADAS: '0', COM_DESTINO: '11', MAIS_ANTIGA: '20261030', MAIS_RECENTE: '20261030' },
    { MENSAGEM: 'ITEM', STATUS: '2', CANAL: '3', TPTRAN: '1', QTD: '4', ESGOTADAS: '0', COM_DESTINO: '4', MAIS_ANTIGA: '20261030', MAIS_RECENTE: '20261030' }] },
  eai_pendentes_lista: { ok: true, variante: 0, linhas: [
    { MENSAGEM: 'CUSTOMERVENDOR', STATUS: '7', CANAL: '3', TENTATIVAS: '0', DIA: '20261029', HORA: '16:00:47', EVENTO: 'upsert', WEBSERVICE: '', COM_DESTINO: 'S', RETORNO: '' },
    { MENSAGEM: 'SELLER<b>x</b>', STATUS: '5', CANAL: '1', TENTATIVAS: '4', DIA: '20261030', HORA: '07:56:23', EVENTO: 'upsert', WEBSERVICE: 'WS_ERPProtheusToGFE', COM_DESTINO: 'N', RETORNO: 'Erro de comunicação' }] },
  eai_adapters: { ok: true, linhas: [
    { ROTINA: 'OMSA010', MENSAGEM: 'PRICELISTHEADERITEM', DESCRICAO: 'TABELA DE PRECO', ENVIA: '1', RECEBE: '2', METODO: '2', CANAL: '3', VERSAO: '2.001', CONDICAO: '' },
    { ROTINA: 'MATA010', MENSAGEM: 'ITEM', DESCRICAO: 'PRODUTO', ENVIA: '1', RECEBE: '1', METODO: '2', CANAL: '3', VERSAO: '4.013', CONDICAO: "b1_grupo = '0009'" }] },
  eai_depara: { ok: true, linhas: [] },
  eai_cadastros: { ok: true, linhas: [{ ALIAS: 'SA1', QTD: '820' }, { ALIAS: 'DA0', QTD: '7' }] },
  eai_agendamentos: { ok: true, variante: 0, linhas: [
    { CODIGO: '000001', ROTINA: "FINA711('01')", STATUS: '0', AMBIENTE: 'PRODUCAO', INICIO: '20260625', HORA: '00:00', ULTDIA: '20261030', ULTHOR: '10:00', EAI: 'N', RECORR: 'D(Each(.T.) Day(1) EveryDay(.T.) ) Execs(0096) Interval(00:15)' },
    { CODIGO: '000003', ROTINA: 'FWEAIRECE', STATUS: '0', AMBIENTE: 'PRODUCAO', INICIO: '20261021', HORA: '09:58', ULTDIA: '', ULTHOR: '', EAI: 'S', RECORR: 'Smart A' }] },
  eai_agend_empfil: { ok: true, linhas: [{ CODIGO: '000001', EMPFIL: '01/01' }, { CODIGO: '000003', EMPFIL: '01/01' }] },
  eai_tarefas: { ok: true, linhas: [{ CODIGO: '000001', STATUS: '2', QTD: '521' }, { CODIGO: '000003', STATUS: '4', QTD: '1' }] },
  eai_agents: { ok: true, linhas: [{ CODIGO: '01', DESCRICAO: 'AGENT 01', IP: '127.0.0.1', PORTA: '6001', AMBIENTE: 'PRODUCAO', THREADS: '2', STATUS: '0', ULTDIA: '20260625', ULTHOR: '14:40' }] },
  eai_config: { ok: true, linhas: [{ PARAMETRO: 'MV_EAIPASS', FILIAL: '', CONTEUDO: '(preenchido)' }] },
  eai_empresa: { ok: true, linhas: [{ REFERENCIA: 'CRM-COMPANY', EMPRESA_EXT: '01', FILIAL_EXT: '', EMPRESA: '01', FILIAL: '01' }] },
};
const ULTIMA = { id: 9, coletado_em: AGORA, duracao_ms: 7100, nivel: 'vermelho', indicadores: INDS,
  blocos: Object.assign({ _meta: { desde: null, grupos: ['eai'] } }, BLOCOS), environment: 'producao',
  disparado_por: 'reges.werlang@totvs.com.br', health: { ok: false } };
const CFG = { url_rest: 'https://x/rest/tscmonit', environment: 'producao', banco: 'oracle', sufixo: '010',
              ativo: true, tem_token: true, tem_senha: true, integ_desde: null, integ_grupos: ['eai'] };
const OUTRA = { ambiente: 'teste', cadastrada: true, integ_grupos: ['crm'], ultima: { coletado_em: AGORA, nivel: 'verde', indicadores: [
  { chave: 'eai_sem_retorno', grupo: 'eai', rotulo: 'Entregues sem retorno', valor: 3, nivel: 'verde' }] } };
const PAYLOAD = (o = {}) => Object.assign({ ok: true, customer: '000348D0', ambiente: 'producao', hoje: '2026-10-30',
  ambiente_cfg: CFG, ultima: ULTIMA, serie: [], coletas: [], outra: OUTRA }, o);

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

  t('checkbox EAI marcado', await pg.$eval('[data-int-grupo="eai"]', n => n.checked));
  t('CRM desmarcado', !(await pg.$eval('[data-int-grupo="crm"]', n => n.checked)));
  t('botão Produção + Teste visível só com EAI', await pg.$eval('#int-coletar-duas', n => !n.classList.contains('hidden')));
  t('9 cartões do grupo', (await pg.$$('#int-conteudo [data-int-ind]')).length === 9);
  const c = await txt('#int-conteudo');
  t('grupo nomeado', /EAI Protheus × Schedule/.test(c));
  t('cartão crítico com rótulo', /✕ Crítico/.test(await txt('[data-int-ind="eai_sem_retorno"]')));
  t('caixa EAI aberta', /o cadastro saiu e voltou\?/.test(c));
  const f = async (k) => txt(`[data-int-funil="${k}"]`);
  t('caminho: 842 na fila', /Na fila \(XX3\)\s*842/.test(await f('fila')), await f('fila'));
  t('caminho: falhas 6 com alerta em texto', /Com falha\s*6/.test(await f('falha')) && /atenção/.test(await f('falha')), await f('falha'));
  t('caminho: 832 entregues sem retorno', /832/.test(await f('entregue')) && /atenção/.test(await f('entregue')), await f('entregue'));
  t('caminho: 4 finalizadas, sem alerta', /Finalizadas\s*4/.test(await f('finalizada')) && !/atenção/.test(await f('finalizada')));
  t('caminho: de-para 0 com alerta', /De-para gravado\s*0/.test(await f('depara')) && /atenção/.test(await f('depara')), await f('depara'));
  const duas = await txt('[data-int-duas]');
  t('produção × teste do EAI lado a lado', /Base Produção × Base de Testes/.test(duas) && /Entregues sem retorno\s*969\s*✕ Crítico\s*3\s*✓ OK/.test(duas), duas.slice(0, 220));
  t('aviso de grupo desligado não aparece (teste tem dado)', !/não leu o grupo/.test(duas));
  const linhas = await pg.$$eval('#int-conteudo table tr', trs => trs.map(tr => tr.textContent.replace(/\s+/g, ' ').trim()));
  t('status com código e rótulo', linhas.some(l => /CUSTOMERVENDOR\s*7 · Entregue/.test(l)) && linhas.some(l => /5 · Não entregue/.test(l)));
  t('canal com nome', linhas.some(l => /1 · ESB/.test(l)) && linhas.some(l => /3 · EAI · PAD\.APP/.test(l)));
  t('pendente com idade e destino', linhas.some(l => /SELLER/.test(l) && /WS_ERPProtheusToGFE/.test(l) && /Erro de comunicação/.test(l)));
  t('mensagem escapada', /SELLER<b>x<\/b>/.test(c));
  t('adapter com condição em código', linhas.some(l => /MATA010/.test(l) && /b1_grupo = '0009'/.test(l) && /Assíncrono/.test(l)));
  t('XXF vazia explicada', /XXF vazia: nenhum retorno processado/.test(c));
  const lRece = linhas.find(l => /FWEAIRECE/.test(l)) || '';
  t('agendamento nunca executou em texto', /✕ nunca executou/.test(lRece) && /EAI/.test(lRece) && /Smart A/.test(lRece) && /1 · status 4/.test(lRece), lRece);
  const lFina = linhas.find(l => /FINA711/.test(l)) || '';
  t('agendamento com última execução e tarefas', /30\/10\/2026 10:00/.test(lFina) && /521 · status 2/.test(lFina) && /01\/01/.test(lFina), lFina);
  t('agent com último sinal', linhas.some(l => /AGENT 01/.test(l) && /127\.0\.0\.1:6001/.test(l)));
  t('senha do ESB mascarada', /\(preenchido\)/.test(c));
  t('rodapé diz que URL do iPaaS não é lida', /api-key\) e o conteúdo da mensagem não são lidos/.test(c));

  await pg.click('#int-coletar-duas');
  await pg.waitForTimeout(60);
  t('barra coletando diz Produção + Teste', /Produção \+ Teste/.test(await txt('#int-conteudo')));
  await pg.waitForTimeout(900);
  t('ligou o EAI na base de testes mantendo o CRM', grupos.length === 1 && /ambiente=teste/.test(grupos[0].url)
    && JSON.stringify(grupos[0].body.grupos) === '["crm","eai"]', JSON.stringify(grupos));
  const cols = pedidos.filter(p => p.includes('/coletar'));
  t('coletou produção e depois teste', cols.length === 2 && /producao/.test(cols[0]) && /teste/.test(cols[1]), cols.join(' | '));

  if (process.env.SHOT) {
    await pg.$eval('#int-conteudo', n => n.scrollIntoView());
    await pg.screenshot({ path: process.env.SHOT, fullPage: true });
  }

  await pg.route('**/api/integracoes/000348D0?*', r => r.fulfill({ json: PAYLOAD({ ambiente_cfg: Object.assign({}, CFG, { integ_grupos: ['rh'] }), ultima: null }) }));
  await pg.click('#int-reload'); await pg.waitForTimeout(300);
  t('só RH: botão Produção + Teste some', await pg.$eval('#int-coletar-duas', n => n.classList.contains('hidden')));

  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  await b.close();
  console.log(`${ok.length} OK, ${bad.length} falha(s)`);
  bad.forEach(x => console.log('FALHOU:', x));
  process.exit(bad.length ? 1 : 0);
})();
