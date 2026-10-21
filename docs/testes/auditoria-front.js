// Teste da ABA AUDITORIA DE TABELAS (front), com /api/* interceptado.
//
// Como rodar, da raiz do repo:
//   python3 docs/testes/auditoria-e2e.py      (gera o payload real do backend)
//   cd web && python3 -m http.server 8732 --bind 127.0.0.1 &
//   node docs/testes/auditoria-front.js
//
// O payload é o GET de verdade do auditoria-e2e.py (Flask + Postgres local +
// stub da REST), não um JSON montado à mão: se o contrato mudar, a tela quebra
// aqui e não no cliente.
const fs = require('fs');
const { chromium } = require(process.env.PW || 'playwright');

const PAYLOAD = JSON.parse(fs.readFileSync(process.env.AUD_JSON || '/home/claude/w/aud.json', 'utf8'));
const VAZIO = Object.assign({}, PAYLOAD, { coletas: { teste: null, producao: null } });

(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || undefined, args: ['--no-sandbox'] });
  const pg = await b.newPage({ viewport: { width: 1440, height: 1000 } });
  const erros = [];
  pg.on('pageerror', e => erros.push('pageerror: ' + e.message));
  pg.on('dialog', d => d.accept());
  if (process.env.TW) {
    await pg.route('**/cdn.tailwindcss.com*', r => r.fulfill({ status: 200, contentType: 'application/javascript',
      body: fs.readFileSync(process.env.TW, 'utf8') }));
  }
  let leitura = VAZIO;
  const pedidos = [];
  pg.on('request', r => { if (r.url().includes('/api/auditoria')) pedidos.push(`${r.method()} ${new URL(r.url()).pathname}${new URL(r.url()).search}`); });
  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'admin', is_admin: true, interno: true } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [] } }));
  await pg.route('**/api/auditoria/TFCTQI00', r => r.fulfill({ json: leitura }));
  const uploads = [];
  await pg.route('**/api/auditoria/TFCTQI00/scripts*', r => r.fulfill({ json: { ok: true, banco: 'oracle', sufixo: '010',
    ambiente_cadastrado: false, contagem_base: null, scripts: [
      { id: 'sx2', n: 1, rotulo: 'Script 1 · SX2', sql: '-- c\nSELECT 1 FROM SX2010' },
      { id: 'contagem', n: 2, rotulo: 'Script 2 · contagem', sql: null, pendente: 'Suba primeiro o resultado do Script 1' },
      { id: 'sx3', n: 3, rotulo: 'Script 3 · SX3', sql: 'SELECT 1 FROM SX3010' },
      { id: 'sx6', n: 4, rotulo: 'Script 4 · SX6', sql: 'SELECT 1 FROM SX6010' }] } }));
  await pg.route('**/api/auditoria/TFCTQI00/upload*', r => {
    uploads.push({ url: r.request().url(), body: JSON.parse(r.request().postData()) });
    r.fulfill({ json: Object.assign({}, PAYLOAD, { upload: { arquivos: { sx2: 's1.csv', sx6: 's4.csv' }, ignorados: [],
      estranhas: [], completou: false, falta_contagem: true } }) });
  });
  await pg.route('**/api/auditoria/TFCTQI00/coletar*', async r => {
    await new Promise(res => setTimeout(res, 250));
    leitura = PAYLOAD;
    r.fulfill({ json: PAYLOAD });
  });

  await pg.goto('http://127.0.0.1:8732/index.html');
  await pg.waitForTimeout(500);
  const ok = [], bad = [];
  const t = (nome, cond, extra) => (cond ? ok : bad).push(nome + (extra ? ` [${extra}]` : ''));
  const txt = sel => pg.$eval(sel, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');

  await pg.evaluate(() => {
    state.selected = { cli: 'TFCTQI00', cod: 'TFCTQI0020', ver: '01', loja: '00',
                       projeto: { nome_cliente_projeto: 'CONF NAC DAS COOP CENTRAL CRESOL CONFEDERACAO' } };
    $('#view-lista').classList.add('hidden');
    $('#view-detalhe').classList.remove('hidden');
    $('#detalhe-conteudo').classList.remove('hidden');
    setTab('auditoria');
  });
  await pg.waitForTimeout(400);
  t('aba na barra', await pg.$('button[data-tab="auditoria"]') !== null);
  t('rail da aba visível', await pg.$eval('[data-rail="aud"]', n => !n.classList.contains('hidden')));
  t('sem coleta avisa as duas bases', (await txt('#aud-conteudo')).includes('Teste: ainda sem coleta')
    && (await txt('#aud-conteudo')).includes('Produção: ainda sem coleta'));

  await pg.click('#aud-coletar-teste');
  await pg.waitForTimeout(80);
  t('coletando aparece', (await txt('#aud-conteudo')).includes('Coletando na Base de Testes'));
  await pg.waitForTimeout(500);
  t('POST na base certa', pedidos.some(p => p === 'POST /api/auditoria/TFCTQI00/coletar?ambiente=teste'), pedidos.join(' | '));

  const corpo = await txt('#aud-conteudo');
  t('KPI no alvo teste', corpo.includes('No alvo · Teste'));
  t('alerta F22 x SA2 em Teste, com descrição', corpo.includes('Teste: F22 · Desc F22 (E C C) está mais exclusiva que SA2 · Tabela SA2 (C C C)'), corpo.slice(0, 400));
  t('variante com zero', corpo.includes('FOV está na SX2 como F0V'));
  t('estrutural divergente', corpo.includes('F2D é estrutural'));
  t('_FILIAL a converter', corpo.includes('_FILIAL a converter para o modo alvo'));
  t('sem alvo CI6 com descrição', corpo.includes('Sem compartilhamento definido na Estrutura: CI6 · Desc CI6'));
  t('proposta CK3 com descrição', corpo.includes('Em discussão na Estrutura (proposta aberta): CK3 · Desc CK3'));
  t('perfis em níveis diferentes', corpo.includes('perfis em níveis diferentes'));

  const linhaF22 = await txt('tr[data-aud-linha="F22"]');
  t('linha F22: teste A alterar, prod No alvo', /E C C.*A alterar.*C C C.*No alvo/.test(linhaF22), linhaF22);
  await pg.click('tr[data-aud-linha="F27"]');
  await pg.waitForTimeout(150);
  const det = await txt('#aud-conteudo');
  const fils = await pg.$$eval('[data-aud-fil]', ns => ns.map(n => n.innerText.replace(/\s+/g, ' ').trim()));
  t('detalhe por variação de filial, Teste x Produção', fils.length >= 4 && fils.some(f => f.startsWith('01260001')) && fils.some(f => f.startsWith('0126 ')), fils.join(' | '));
  t('variação fora do padrão do alvo', fils.some(f => f.startsWith('01260001') && f.includes('tamanho 8, alvo espera 4')), fils.join(' | '));
  t('coluna de variações', (await txt('tr[data-aud-linha="F27"]')).includes('2 / 3'), await txt('tr[data-aud-linha="F27"]'));

  await pg.selectOption('#aud-f-st', 'A alterar');
  await pg.waitForTimeout(150);
  const vis = await pg.$$eval('tr[data-aud-linha]', ns => ns.map(n => n.dataset.audLinha));
  t('filtro situação Teste', vis.length > 0 && !vis.includes('F20'), vis.join(','));
  await pg.selectOption('#aud-f-st', '');
  await pg.screenshot({ path: process.env.SHOT || '/home/claude/w/auditoria.png', fullPage: true });

  // Dicionário: SX3 aberto, SX6 recolhido até o clique.
  const dic = await txt('#aud-conteudo');
  t('SX3 com A2_NOME divergente', dic.includes('A2_NOME') && dic.includes('Tipo/tamanho diferente'));
  t('SX3 campo só em Teste', dic.includes('F22_XCUSTOM'));
  t('SX6 nasce recolhido', !(await pg.$('[data-aud-x6]')));
  t('alerta resume o SX6', dic.includes('SX6: 3 parâmetro(s) divergem'));
  await pg.click('[data-aud-caixa="x6"]');
  await pg.waitForTimeout(120);
  const x6 = await pg.$$eval('[data-aud-x6]', ns => [...new Set(ns.map(n => n.dataset.audX6))]);
  t('SX6 abre com as 3 divergências', x6.length === 3 && x6.includes('MV_CFGTRIB'), x6.join(','));
  await pg.selectOption('[data-aud-dic-sit="x6"]', 'conteudo');
  await pg.waitForTimeout(120);
  const x6f = await pg.$$eval('[data-aud-x6]', ns => [...new Set(ns.map(n => n.dataset.audX6))]);
  t('filtro SX6 por conteúdo', x6f.length === 1 && x6f[0] === 'MV_CFGTRIB', x6f.join(','));
  await pg.fill('[data-aud-dic-txt="x3"]', 'f27');
  await pg.press('[data-aud-dic-txt="x3"]', 'Enter');
  await pg.waitForTimeout(120);
  const x3f = await pg.$$eval('[data-aud-x3]', ns => ns.map(n => n.dataset.audX3));
  t('busca no SX3', x3f.length === 1 && x3f[0] === 'F27.F27_DESC', x3f.join(','));
  await pg.screenshot({ path: (process.env.SHOT || '/home/claude/w/auditoria.png').replace('.png', '-dic.png'), fullPage: true });

  // Base sem REST: modal de scripts e upload de vários CSVs de uma vez.
  await pg.click('#aud-scripts-topo');
  await pg.waitForSelector('[data-aud-sql="sx2"]', { timeout: 3000 }).catch(() => {});
  const modalTxt = await txt('#aud-scr');
  t('modal de scripts com passo 1 e 2', modalTxt.includes('Passo 1') && modalTxt.includes('aguardando o Script 1'));
  t('scripts 1, 3 e 4 com SQL', (await pg.$$('[data-aud-sql]')).length === 3);
  t('pediu os scripts da base certa', pedidos.some(p => p.startsWith('GET /api/auditoria/TFCTQI00/scripts?ambiente=')), pedidos.join(' | '));
  await pg.evaluate(() => document.querySelector('.fixed.inset-0 [data-fechar]').click());
  const dialogos = [];
  pg.removeAllListeners('dialog');
  pg.on('dialog', d => { dialogos.push(d.message()); d.accept(); });
  await pg.setInputFiles('#aud-file', [
    { name: 's1.csv', mimeType: 'text/csv', buffer: Buffer.from('CHAVE;NOME;ARQ;MODOEMP;MODOUN;MODO;EXISTE;TEMFIL\nF22;x;F22010;E;C;C;1;1') },
    { name: 's4.csv', mimeType: 'text/csv', buffer: Buffer.from('PARAM;FIL;TIPO;CONTEUDO;DESCR\nMV_X;;C;1;d') }]);
  await pg.waitForTimeout(200);
  await pg.click('.fixed.inset-0 input[value="teste"]');
  await pg.click('.fixed.inset-0 [data-ok]');
  await pg.waitForTimeout(500);
  const up = uploads[0];
  t('upload manda os dois arquivos para a base escolhida', up && up.url.includes('ambiente=teste') && up.body.arquivos.length === 2, up && up.url);
  t('aviso de que falta o Script 2', dialogos.some(m => m.includes('Falta o Script 2')), dialogos.join(' | '));

  await pg.setViewportSize({ width: 390, height: 900 });
  await pg.waitForTimeout(150);
  const larg = await pg.evaluate(() => document.querySelector('#tab-auditoria').scrollWidth);
  t('tabela rola dentro da caixa no celular', larg <= 420, String(larg));

  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  console.log(JSON.stringify({ ok: ok.length, falhas: bad }, null, 2));
  await b.close();
  process.exit(bad.length ? 1 : 0);
})();
