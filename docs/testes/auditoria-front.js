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
  t('alerta F22 x SA2 em Teste', corpo.includes('Teste: F22 (E C C) está mais exclusiva que SA2 (C C C)'));
  t('variante com zero', corpo.includes('FOV está na SX2 como F0V'));
  t('estrutural divergente', corpo.includes('F2D é estrutural'));
  t('_FILIAL a converter', corpo.includes('_FILIAL a converter para o modo alvo'));
  t('sem alvo CI6', corpo.includes('Sem compartilhamento definido na Estrutura: CI6'));
  t('proposta CK3', corpo.includes('Em discussão na Estrutura (proposta aberta): CK3'));
  t('perfis em níveis diferentes', corpo.includes('perfis em níveis diferentes'));

  const linhaF22 = await txt('tr[data-aud-linha="F22"]');
  t('linha F22: teste A alterar, prod No alvo', /E C C.*A alterar.*C C C.*No alvo/.test(linhaF22), linhaF22);
  await pg.click('tr[data-aud-linha="F27"]');
  await pg.waitForTimeout(150);
  const det = await txt('#aud-conteudo');
  t('detalhe por cooperativa', det.includes('Por cooperativa') && det.includes('0126'));

  await pg.selectOption('#aud-f-st', 'A alterar');
  await pg.waitForTimeout(150);
  const vis = await pg.$$eval('tr[data-aud-linha]', ns => ns.map(n => n.dataset.audLinha));
  t('filtro situação Teste', vis.length > 0 && !vis.includes('F20'), vis.join(','));
  await pg.selectOption('#aud-f-st', '');
  await pg.screenshot({ path: process.env.SHOT || '/home/claude/w/auditoria.png', fullPage: true });

  await pg.setViewportSize({ width: 390, height: 900 });
  await pg.waitForTimeout(150);
  const larg = await pg.evaluate(() => document.querySelector('#tab-auditoria').scrollWidth);
  t('tabela rola dentro da caixa no celular', larg <= 420, String(larg));

  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  console.log(JSON.stringify({ ok: ok.length, falhas: bad }, null, 2));
  await b.close();
  process.exit(bad.length ? 1 : 0);
})();
