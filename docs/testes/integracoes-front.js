// Teste da ABA INTEGRAÇÕES (front), com as rotas /api/* interceptadas.
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/integracoes-front.js
//
// Cobre: barra de estado (sem cadastro, sem coleta, retrato velho, coletando,
// falha), cartões por grupo com status em texto (não só cor), indicador cinza
// de tabela ausente, caixas recolhíveis sem DOM quando fechadas, tabelas de
// detalhe, histórico, troca de base refazendo a leitura, coleta pelo botão do
// topo e pelo rail, modal de scripts e zero erro de JS da aba.
const { chromium } = require('playwright');

const AGORA = new Date().toISOString();
const IND = (chave, grupo, rotulo, valor, nivel, texto) => ({ chave, grupo, rotulo, valor, nivel, texto });
const INDS = [
  IND('quirons_fila', 'quirons', 'Fila Quírons', 12, 'verde', 'Mais antiga de 13/10/2026 (0 dia(s)). Lote do JOB (MV_RHMSGNG) = 100.'),
  IND('quirons_envios', 'quirons', 'Envios Quírons (7 dias)', 49, 'verde', 'Último envio em 13/10/2026 às 09:15.'),
  IND('quirons_erros', 'quirons', 'Erros Quírons (7 dias)', 1, 'vermelho', 'Códigos HTTP: 401. 401 = credencial do Quírons recusada.'),
  IND('ahgora_inconsistencias', 'ahgora', 'Ahgora — inconsistências', 1, 'amarelo', 'A Ahgora recusou.'),
  IND('ahgora_aguardando', 'ahgora', 'Ahgora — retorno perdido', null, 'cinza', 'A tabela RUM010 não existe nesta base.'),
  IND('ahgora_nao_enviados', 'ahgora', 'Ahgora — não enviados', 0, 'verde', '0 com movimento anterior a hoje.'),
  IND('sst_pendentes', 'esocial', 'eSocial SST não transmitidos', 0, 'verde', '30 evento(s), todos transmitidos.'),
  IND('quirons_laudo', 'quirons', 'Laudo Quírons (GPEM926)', '3/3', 'verde', 'Todos os requisitos OK.'),
];
const BLOCOS = {
  config: { ok: true, linhas: [{ PARAMETRO: 'MV_RHNG', FILIAL: '', CONTEUDO: '.T.' }] },
  rjp_fila: { ok: true, linhas: [{ FILIAL: '', TABELA: 'SRA', OPER: 'A', QTD: '12', MAIS_ANTIGO: '20261013' }] },
  rjp_vazao: { ok: true, linhas: [{ DIA: '20261013', QTD: '9', PRIMEIRA: '06:00', ULTIMA: '09:15' }] },
  ru7_erros: { ok: true, linhas: [{ DIA: '20261012', COD_HTTP: '401', QTD: '1' }] },
  rum_resumo: { ok: false, ausente: true, erro: 'A tabela RUM010 não existe nesta base.', linhas: [] },
  rje_sst: { ok: true, linhas: [{ EVENTO: 'S2220', STATUS: '4', QTD: '30', MAIS_ANTIGO: '20260901', MAIS_RECENTE: '20261010' }] },
  rum_pendencias: { ok: true, truncado: true, limite: 300, linhas: [{ FILIAL: '01', MATRICULA: '000123', NOME: 'FULANO <b>X</b>', TIPO: '1', OPER: 'A', STATUS: '3', DT_MOV: '20261010', DT_INTEG: '20261010', HR_INTEG: '08:00' }] },
  rjp_antigos: { ok: true, linhas: [] },
  rje_pendentes: { ok: true, linhas: [] },
};
const ULTIMA = (quando) => ({ id: 2, coletado_em: quando, duracao_ms: 8300, nivel: 'vermelho',
  indicadores: INDS, blocos: BLOCOS, environment: 'RACLI_PROD', disparado_por: 'reges.werlang@totvs.com.br',
  health: { ok: true, url: 'https://x/rest/api/rh/v1/integrationcheck/healthcheck',
            itens: [{ id: 'P1', status: 'ok', mensagem: '' }, { id: 'P2', status: 'aviso', mensagem: '401' }, { id: 'Q3', status: 'ok', mensagem: '' }] } });
const CFG = { url_rest: 'https://x/rest/tscmonit', environment: 'RACLI_PROD', banco: 'oracle', sufixo: '010',
              ativo: true, tem_token: true, tem_senha: true };
const SERIE = [
  { id: 1, coletado_em: '2026-10-12T12:00:00Z', nivel: 'amarelo', indicadores: [{ chave: 'quirons_fila', valor: 40, nivel: 'amarelo' }] },
  { id: 2, coletado_em: AGORA, nivel: 'vermelho', indicadores: [{ chave: 'quirons_fila', valor: 12, nivel: 'verde' }] },
];
const PAYLOAD = (o = {}) => Object.assign({ ok: true, customer: 'TFEHM600', ambiente: 'producao', hoje: '2026-10-13',
  ambiente_cfg: CFG, ultima: ULTIMA(AGORA), serie: SERIE,
  coletas: [{ iniciado_em: AGORA, duracao_ms: 8300, ok: true, linhas: 20, itens: 8, erro: 'rum_resumo: tabela não existe', disparado_por: 'reges' }] }, o);

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage();
  const erros = [];
  // Tailwind/fontes vêm de CDN, que o laboratório não alcança: erro de rede não é da aba.
  pg.on('pageerror', e => { if (!/tailwind|lucide|Chart/i.test(e.message)) erros.push('pageerror: ' + e.message); });
  pg.on('dialog', d => d.accept());

  let modo = { leitura: PAYLOAD(), coleta: { status: 200, json: PAYLOAD() } };
  const pedidos = [];
  pg.on('request', r => { if (r.url().includes('/api/integracoes')) pedidos.push(`${r.method()} ${r.url()}`); });

  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'admin', is_admin: true, interno: true } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [] } }));
  await pg.route('**/api/integracoes/TFEHM600?*', r => r.fulfill({ json: modo.leitura }));
  await pg.route('**/api/integracoes/TFEHM600/coletar*', async r => {
    await new Promise(res => setTimeout(res, 300));
    r.fulfill({ status: modo.coleta.status, json: modo.coleta.json });
  });
  await pg.route('**/api/integracoes/TFEHM600/scripts*', r => r.fulfill({ json: { ok: true, sufixo: '010', sufixo_usado: '010',
    scripts: [{ id: 'config', rotulo: 'Parâmetros (SX6)', tabela: 'SX6010', sql: "SELECT X6_VAR FROM SX6010 WHERE D_E_L_E_T_ = ' '" },
              { id: 'rjp_fila', rotulo: 'Fila RJP', tabela: 'RJP010', sql: 'SELECT 1 FROM RJP010' }] } }));

  await pg.goto('http://127.0.0.1:8731/index.html');
  await pg.waitForTimeout(400);

  const ok = [], bad = [];
  const t = (nome, cond, extra) => (cond ? ok : bad).push(nome + (extra ? ` [${extra}]` : ''));
  const txt = (sel) => pg.$eval(sel, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');

  await pg.evaluate(() => {
    state.selected = { cli: 'TFEHM600', cod: 'TFEHM60001', ver: '01', loja: '00',
                       projeto: { nome_cliente_projeto: 'RACLI LIMPEZA' } };
    $('#view-lista').classList.add('hidden');
    $('#view-detalhe').classList.remove('hidden');
    $('#detalhe-conteudo').classList.remove('hidden');
    setTab('integracoes');
  });
  await pg.waitForFunction(() => document.querySelectorAll('#int-conteudo [data-int-ind]').length > 0, null, { timeout: 5000 }).catch(() => {});

  t('aba listada na barra', await pg.$('button[data-tab="integracoes"]') !== null);
  t('painel visível', await pg.$eval('#tab-integracoes', n => !n.classList.contains('hidden')));
  t('rail das integrações visível', await pg.$eval('[data-rail="int"]', n => !n.classList.contains('hidden')));
  t('nome do cliente', (await txt('#int-cliente-nome')) === 'RACLI LIMPEZA');
  t('leu a produção ao abrir', pedidos.some(p => /GET .*\/api\/integracoes\/TFEHM600\?ambiente=producao/.test(p)), pedidos.join(' | '));
  t('abrir NÃO coleta', !pedidos.some(p => p.includes('/coletar')));
  t('8 cartões', (await pg.$$('#int-conteudo [data-int-ind]')).length === 8);
  const conteudo = await txt('#int-conteudo');
  t('barra com data da coleta e environment', /Coleta de .*RACLI_PROD.*8\.3 s/.test(conteudo), conteudo.slice(0, 160));
  t('situação geral em texto', /Situação geral\s*✕ Crítico/.test(conteudo));
  t('grupos nomeados', /Quírons \(NG\)/.test(conteudo) && /Ahgora PontoWeb/.test(conteudo) && /eSocial SST/.test(conteudo));
  const erroCard = await txt('[data-int-ind="quirons_erros"]');
  t('status com rótulo, não só cor', /✕ Crítico/.test(erroCard) && /401/.test(erroCard), erroCard);
  const cinza = await txt('[data-int-ind="ahgora_aguardando"]');
  t('tabela ausente vira "Sem dado" com motivo', /– Sem dado/.test(cinza) && /RUM010/.test(cinza) && /—/.test(cinza), cinza);
  t('sparkline com 2 pontos', await pg.$('[data-int-ind="quirons_fila"] svg polyline') !== null);
  t('sem sparkline para valor não numérico', await pg.$('[data-int-ind="quirons_laudo"] svg') === null);
  t('quirons aberta: fila por tabela', /Fila pendente por tabela/.test(conteudo) && /SRA/.test(conteudo));
  t('bloco ausente explicado', /ℹ A tabela RUM010 não existe/.test(conteudo));
  t('lista truncada avisada', /300 primeiras linhas/.test(conteudo));
  t('nome escapado (sem HTML injetado)', await pg.$('#int-conteudo b:has-text("X")') === null && /FULANO <b>X<\/b>/.test(conteudo));
  t('config fechada não gera DOM', !/Laudo do healthcheck/.test(conteudo));
  t('histórico fechado não gera DOM', !/Últimos disparos/.test(conteudo));

  await pg.click('[data-int-caixa="config"]');
  const cfg = await txt('#int-conteudo');
  t('abre config com laudo', /Laudo do healthcheck/.test(cfg) && /P2/.test(cfg) && /MV_RHNG/.test(cfg));
  await pg.click('[data-int-caixa="historico"]');
  const hist = await txt('#int-conteudo');
  t('histórico com coletas e disparos', /Últimos disparos/.test(hist) && /2 coleta\(s\)/.test(hist) && /40/.test(hist));
  await pg.click('[data-int-caixa="quirons"]');
  t('recolher remove DOM', !/Fila pendente por tabela/.test(await txt('#int-conteudo')));

  // ── coleta pelo botão do topo: barra "coletando" durante a chamada ────────
  modo.coleta = { status: 200, json: PAYLOAD({ ultima: Object.assign(ULTIMA(AGORA), { nivel: 'verde' }) }) };
  await pg.click('#int-coletar-topo');
  await pg.waitForTimeout(80);
  t('barra coletando', /Coletando na base/.test(await txt('#int-conteudo')));
  t('botão desabilitado durante a coleta', await pg.$eval('#int-coletar-topo', n => n.disabled));
  await pg.waitForTimeout(500);
  t('POST na base escolhida', pedidos.some(p => /POST .*\/coletar\?ambiente=producao/.test(p)));
  t('resultado novo pintado', /Situação geral\s*✓ OK/.test(await txt('#int-conteudo')));

  // ── coleta com falha: mantém o retrato anterior e diz isso ────────────────
  modo.coleta = { status: 502, json: { ok: false, error: 'Falha ao chamar a base: ConnectTimeout' } };
  await pg.click('#int-coletar');
  await pg.waitForTimeout(600);
  const falha = await txt('#int-conteudo');
  t('falha explicada', /A coleta falhou: Falha ao chamar a base/.test(falha), falha.slice(0, 200));
  t('retrato anterior mantido e avisado', /coleta anterior/.test(falha) && (await pg.$$('[data-int-ind]')).length === 8);

  // ── troca de base relê, sem coletar ───────────────────────────────────────
  modo.leitura = PAYLOAD({ ambiente: 'teste', ambiente_cfg: null, ultima: null, serie: [], coletas: [] });
  const nAntes = pedidos.length;
  await pg.selectOption('#int-ambiente-sel', 'teste');
  await pg.waitForTimeout(300);
  t('troca de base relê', pedidos.slice(nAntes).some(p => /GET .*ambiente=teste/.test(p)));
  const vazio = await txt('#int-conteudo');
  t('sem cadastro pede ⚙ Ambiente', /Base de Testes ainda não cadastrada/.test(vazio) && /⚙ Ambiente/.test(vazio));
  t('sem coleta orienta o botão', /Nenhuma coleta ainda/.test(vazio));
  t('sem cartões sem coleta', (await pg.$$('[data-int-ind]')).length === 0);

  // ── retrato velho ─────────────────────────────────────────────────────────
  modo.leitura = PAYLOAD({ ultima: ULTIMA('2026-10-01T10:00:00Z') });
  await pg.selectOption('#int-ambiente-sel', 'producao');
  await pg.waitForTimeout(300);
  t('retrato > 24 h avisado', /mais de 24 h/.test(await txt('#int-conteudo')));

  // ── modal de scripts ──────────────────────────────────────────────────────
  await pg.click('#int-scripts');
  await pg.waitForTimeout(200);
  const modalTxt = await pg.$eval('.fixed.inset-0', n => n.textContent.replace(/\s+/g, ' ')).catch(() => '');
  t('modal de scripts', /Scripts SQL da coleta/.test(modalTxt) && /sufixo 010/.test(modalTxt) && /Fila RJP/.test(modalTxt), modalTxt.slice(0, 160));
  t('modal largo', await pg.$('.fixed.inset-0 .max-w-3xl') !== null);
  const sqls = await pg.$$eval('.fixed.inset-0 textarea', ns => ns.map(n => n.value));
  t('SQL sem ;', sqls.length === 2 && sqls.every(s => !s.trim().endsWith(';')));
  await pg.click('.fixed.inset-0 [data-fechar]');

  // ── exportar: a aba entra no relatório ────────────────────────────────────
  const rel = await pg.evaluate(() => { const r = relatorioDaAba(); return r && { titulo: r.titulo, base: r.base }; });
  t('exportar reconhece a aba', rel && rel.titulo === 'Monitoramento de Integrações' && rel.base === 'producao', JSON.stringify(rel));

  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  await b.close();
  console.log(`${ok.length} OK, ${bad.length} falha(s)`);
  bad.forEach(x => console.log('FALHOU:', x));
  process.exit(bad.length ? 1 : 0);
})();
