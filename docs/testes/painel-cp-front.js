// Teste do PAINEL CP (bloco de lançamento + bloco de aceite).
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/painel-cp-front.js
//
// Serve por HTTP e NAO por file:// — o fetch do navegador recusa o esquema
// file: e o painel cairia em "Failed to fetch" sem nunca renderizar.
// As rotas /api/* sao interceptadas: o Playwright casa na ordem INVERSA do
// registro, por isso a generica entra primeiro e as especificas depois.
const { chromium } = require('playwright');

const CTX = {
  ok: true,
  eu: { email: 'reges.werlang@totvs.com.br', nome: 'Reges Werlang' },
  palpite: 'REGES PAULO WERLANG',
  hoje: '2026-10-05',
  coordenadores: [
    { chave: 'REGES PAULO WERLANG', nome: 'Reges Paulo Werlang', ativos: 211, projetos: 526, clientes: 188, codigos: ['TSC623'] },
    { chave: 'TIAGO NARDI', nome: 'Tiago Nardi', ativos: 20, projetos: 141, clientes: 53, codigos: ['TSCA92'] },
  ],
};

const L = (o) => Object.assign({
  id: 1, data: '2026-09-20', dias: 15, faixa: '11-15',
  consultor_cod: 'TEC180', consultor: 'Geane Narloch', consultor_email: 'geane.narloch@totvs.com.br',
  owner: 'TSC623', owner_nome: 'Reges Paulo Werlang',
  cliente: '10028400', cliente_nome: 'TTS RS', regiao: '301',
  projeto: '1002840017', projeto_nome: 'REFORMA TRIBUTARIA TIMAC',
  titulo: 'Tts Rs', modulo: 'Atividades Diversas', atividade: 'Atividades Diversas',
  hora_inicio: '08:00', hora_fim: '12:00', horas: 4, realizada: 0,
  local: 'REMOTO', observacao: 'reforma timac e rexnord',
  status: 'C', status_label: 'Confirmado', por: ['owner', 'coord'],
}, o);

const LANC = {
  ok: true, coord: 'REGES PAULO WERLANG', de: '2026-08-06', ate: '2026-10-05',
  hoje: '2026-10-05', dias: 60, total: 4, horas: 21,
  diag: { rota: '/PCITConectaResourceSchedule', paginas: 2, recursos: 114, truncado: false },
  lido_em_ts: 1791230000,
  pendentes: [
    L({ id: 1, dias: 30, faixa: '16+', horas: 8 }),
    L({ id: 2, dias: 4, faixa: '4-5', horas: 4, consultor: 'Felipe Limas', consultor_cod: 'TSCD99',
        consultor_email: 'felipe.jlimas@totvs.com.br', por: ['coord'], owner_nome: 'Tiago Nardi', owner: 'TSCA92',
        cliente_nome: 'OLIM', cliente: 'TFEGN200', projeto: 'TFEGN20001', projeto_nome: 'IMPLANTACAO OLIM' }),
    L({ id: 3, dias: 2, faixa: '0-3', horas: 5, consultor: 'Geane Narloch', por: ['owner'] }),
    L({ id: 4, dias: 1, faixa: '0-3', horas: 4, consultor: 'Geane Narloch', por: ['owner'], realizada: 2 }),
  ],
};

const A = (o) => Object.assign({
  zo2recno: 1, numero_os: 'TSC262TFESR0000109260800-01', customer: 'TFESR000',
  cliente_nome: 'Acosul Comercio E Industria de Ferro E Aco Ltda', tipo_cliente: 'A',
  consultor_cod: 'TSC262', consultor_nome: 'Viviani Carolina Ramos',
  consultor_email: 'viviani.ramos@totvs.com.br',
  coord_nome: 'Reges Paulo Werlang', coord_email: 'reges.werlang@totvs.com.br',
  resp_nome: 'Lucas Kuerten Esser', resp_email: 'lucas@cortesul.com.br',
  resp_cargo: 'Gerente de TI', resp_setor: 'TI',
  data_os: '2026-09-01', hora_inicio: '08:00', hora_fim: '18:00', hora_total: '09:00',
  horas: 9, competencia: '2026-09-01', projeto: 'TFESR00001', projeto_nome: 'Servico de Implantacao',
  servico: 'Gerenciamento / Coordenacao', modulo: 'Monit. Contr. Gerenciamento',
  atividade: '', historico: '', contestada: false, zo2_status: 'PENDENTE',
  dias: 34, faixa: '16+', por: ['coord_os', 'coord'],
}, o);

const ACE = {
  ok: true, coord: 'REGES PAULO WERLANG', hoje: '2026-10-05', total: 3, horas: 18,
  sincronizado_em: '2026-09-22T03:00:00+00:00', lido_em_ts: 1791230000,
  pendentes: [
    A({ zo2recno: 1 }),
    A({ zo2recno: 2, numero_os: 'TSC262TFESR0000209261300-01', data_os: '2026-09-02', dias: 33, horas: 5, contestada: true }),
    A({ zo2recno: 3, numero_os: 'TSCC01TFDCCB001509261400-01', customer: 'TFDCCB00',
        cliente_nome: 'Sicoob Sc Rs Digital', consultor_nome: 'Gabriel Antonio de Oliveira',
        resp_nome: 'Otavio Adriano Da Conceicao', resp_email: 'otavio.adriano@segurosicoob.com.br',
        resp_cargo: '', data_os: '2026-09-15', dias: 20, horas: 4, faixa: '16+',
        projeto: 'TFDCCB0006', projeto_nome: 'Atendimento Eventual', por: ['coord_os'] }),
  ],
};

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage();
  const erros = [];
  pg.on('pageerror', e => erros.push('pageerror: ' + e.message));
  pg.on('console', m => { if (m.type() === 'error' && !/404 \(File not found\)/.test(m.text())) erros.push('console: ' + m.text()); });

  // ORDEM IMPORTA: o Playwright casa as rotas na ordem INVERSA do registro,
  // então a genérica entra primeiro e as específicas depois.
  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: { ok: true, email: CTX.eu.email, nome: CTX.eu.nome, perfil: 'admin', is_admin: true, interno: true } }));
  await pg.route('**/api/clientes', r => r.fulfill({ json: { ok: true, clientes: [] } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [], sincronizado_em: null } }));
  await pg.route('**/api/cp/contexto', r => r.fulfill({ json: CTX }));
  await pg.route('**/api/cp/lancamento*', r => r.fulfill({ json: LANC }));
  await pg.route('**/api/cp/aceite*', r => r.fulfill({ json: ACE }));

  await pg.goto('http://127.0.0.1:8731/index.html');
  await pg.waitForTimeout(400);

  const ok = [], bad = [];
  const t = (nome, cond, extra) => (cond ? ok : bad).push(nome + (extra ? ` [${extra}]` : ''));

  await pg.evaluate(() => window.abreInterno('cp'));
  await pg.waitForFunction(() => {
    const k = document.querySelector('#cp-kpis');
    return k && k.children.length === 4;
  }, null, { timeout: 5000 }).catch(() => {});

  const leKpis = () => pg.$$eval('#cp-kpis .cp-kpi', ns => ns.map(n => ({
    rotulo: n.querySelector('span').textContent.trim(),
    valor: n.querySelector('b').textContent.trim(),
    txt: Array.from(n.querySelectorAll('em')).map(e => e.textContent.trim()).join(' | ') })));
  const kpis = await leKpis();
  t('4 KPIs', kpis.length === 4, kpis.length);
  t('KPI lançamento = 4', kpis[0] && kpis[0].rotulo === 'Pendentes de lançamento' && kpis[0].valor === '4', JSON.stringify(JSON.stringify(kpis[0])));
  t('KPI horas lançamento 21', (kpis[0] || {}).txt.includes('21 h'), JSON.stringify(kpis[0]));
  t('KPI mais antiga 30 dias', (kpis[0] || {}).txt.includes('30 dias'), JSON.stringify(kpis[0]));
  t('KPI consultores = 2', kpis[1] && kpis[1].rotulo === 'Consultores a cobrar' && kpis[1].valor === '2', JSON.stringify(kpis[1]));
  t('KPI aceite = 3', kpis[2] && kpis[2].rotulo === 'Pendentes de aceite' && kpis[2].valor === '3', JSON.stringify(kpis[2]));
  t('KPI responsáveis = 2', kpis[3] && kpis[3].rotulo === 'Responsáveis a cobrar' && kpis[3].valor === '2', JSON.stringify(kpis[3]));

  const coord = await pg.$eval('#cp-coord', s => s.value);
  t('CP pré-selecionado pelo palpite', coord === 'REGES PAULO WERLANG', coord);

  const contas = await pg.$$eval('#cp-blocos [data-cpcx]', ns => ns.map(n => ({
    id: n.dataset.cpcx, conta: n.lastElementChild.textContent.trim() })));
  t('bloco lanc conta 4', contas.find(c => c.id === 'lanc')?.conta === '4', JSON.stringify(contas));
  t('bloco ace conta 3', contas.find(c => c.id === 'ace')?.conta === '3');

  const grupos = await pg.$$eval('#cp-blocos details summary', ns => ns.map(n => n.textContent.replace(/\s+/g, ' ').trim()));
  t('2 grupos de consultor + 2 de responsável', grupos.length === 4, grupos.length + ': ' + grupos.join(' | '));
  t('grupo Geane com 3 agendas', grupos.some(g => /Geane Narloch.*3 agendas/.test(g)), grupos[0]);
  t('grupo Felipe com 1 agenda', grupos.some(g => /Felipe Limas.*1 agenda\b/.test(g)));
  t('grupo aceite por cliente × responsável', grupos.some(g => /Acosul.*Lucas Kuerten Esser/.test(g)));
  t('pior faixa do grupo em dias', grupos.some(g => /\b30 d\b/.test(g)), grupos.join(' | '));

  const linhas = await pg.$$eval('#cp-blocos tbody tr', ns => ns.length);
  t('7 linhas (4 agendas + 3 OS)', linhas === 7, linhas);
  t('apontamento parcial visível', await pg.$$eval('#cp-blocos td', ns => ns.some(n => /apt 2/.test(n.textContent))));
  t('contestada marcada', await pg.$$eval('#cp-blocos td', ns => ns.some(n => /contestada/.test(n.textContent))));
  t('aviso de sincronismo velho', await pg.$eval('#cp-aviso', n => !n.classList.contains('hidden') && /os_aceites/.test(n.textContent)));
  t('readout com rota/recursos', await pg.$eval('#cp-readout', n => /114 consultores/.test(n.textContent)), await pg.$eval('#cp-readout', n => n.textContent));

  // LENTE: 'Agenda dela' tira a linha que só casou por projeto (Felipe)
  await pg.click('#cp-lente [data-cpl="owner"]');
  await pg.waitForTimeout(150);
  let k = await leKpis();
  t('lente owner: 3 lançamentos', k[0].valor === '3', JSON.stringify(k[0]));
  t('lente owner: 1 consultor', k[1].valor === '1', JSON.stringify(k[1]));
  t('lente owner: aceite cai para 0', k[2].valor === '0', JSON.stringify(k[2]));
  t('lente owner marcada', await pg.$eval('#cp-lente [data-cpl="owner"]', n => n.classList.contains('is-on')));

  // LENTE 'Projeto dela': aceite volta (coord_os/coord) e lançamento fica 2
  await pg.click('#cp-lente [data-cpl="coord"]');
  await pg.waitForTimeout(150);
  k = await leKpis();
  t('lente coord: 2 lançamentos', k[0].valor === '2', JSON.stringify(k[0]));
  t('lente coord: 3 aceites', k[2].valor === '3', JSON.stringify(k[2]));

  await pg.click('#cp-lente [data-cpl="tudo"]');
  await pg.waitForTimeout(150);

  // BUSCA
  await pg.fill('#cp-busca', 'olim');
  await pg.waitForTimeout(300);
  k = await leKpis();
  t('busca olim: 1 lançamento', k[0].valor === '1', JSON.stringify(k[0]));
  t('busca olim: 0 aceite', k[2].valor === '0', JSON.stringify(k[2]));
  await pg.fill('#cp-busca', 'sicoob');
  await pg.waitForTimeout(300);
  k = await leKpis();
  t('busca sicoob: 1 aceite', k[2].valor === '1', JSON.stringify(k[2]));
  await pg.fill('#cp-busca', '');
  await pg.waitForTimeout(300);

  // RECOLHER: bloco fechado não gera DOM
  await pg.click('#cp-blocos [data-cpcx="lanc"]');
  await pg.waitForTimeout(150);
  const aposFechar = await pg.$$eval('#cp-blocos tbody tr', ns => ns.length);
  t('recolhido não gera linhas (3 restantes)', aposFechar === 3, aposFechar);
  await pg.click('#cp-blocos [data-cpcx="lanc"]');
  await pg.waitForTimeout(150);
  t('reabre com as 7 linhas', (await pg.$$eval('#cp-blocos tbody tr', ns => ns.length)) === 7);

  // TROCA DE CP refaz a chamada
  let pedidos = 0;
  pg.on('request', r => { if (r.url().includes('/api/cp/lancamento')) pedidos++; });
  await pg.selectOption('#cp-coord', 'TIAGO NARDI');
  await pg.waitForTimeout(500);
  t('trocar de CP recarrega', pedidos >= 1, pedidos);

  // JANELA
  await pg.selectOption('#cp-dias', '15');
  await pg.waitForTimeout(400);
  t('trocar janela recarrega', pedidos >= 2, pedidos);

  t('sem erros de JS', erros.length === 0, erros.join(' ;; '));

  console.log('\n== OK (' + ok.length + ') ==');
  ok.forEach(s => console.log('  ✓ ' + s));
  if (bad.length) { console.log('\n== FALHOU (' + bad.length + ') =='); bad.forEach(s => console.log('  ✗ ' + s)); }
  await b.close();
  process.exit(bad.length ? 1 : 0);
})();
