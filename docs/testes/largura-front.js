// Teste da LARGURA DA TELA (botão ⇔ no topo, vale para todas as abas).
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/largura-front.js
//
// Cobre: padrão "Ampla" (1760 px), ciclo Ampla → Tela cheia → Normal (1280) →
// Ampla, header e <main> com a mesma largura, escolha guardada no navegador e
// aplicada antes do primeiro desenho, zero erro de JS.
const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 2400, height: 1200 } });
  const erros = [];
  pg.on('pageerror', e => { if (!/tailwind|lucide|Chart/i.test(e.message)) erros.push(e.message); });
  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: { ok: true, email: 'x@totvs.com.br', perfil: 'admin', is_admin: true, interno: true } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [] } }));
  await pg.goto('http://127.0.0.1:8731/index.html');
  await pg.waitForTimeout(400);
  const ok = [], bad = [];
  const t = (n, c, x) => (c ? ok : bad).push(n + (x !== undefined ? ` [${x}]` : ''));
  const larg = (sel) => pg.$eval(sel, n => Math.round(n.getBoundingClientRect().width));
  const rot = () => pg.$eval('#btn-largura-txt', n => n.textContent);
  const clica = async () => { await pg.click('#btn-largura'); await pg.waitForTimeout(80); };

  t('padrão: Ampla 1760', (await larg('main')) === 1760 && (await rot()) === 'Ampla', await larg('main'));
  t('header acompanha o main', (await larg('header .app-wrap')) === (await larg('main')));
  await clica();
  t('Tela cheia ocupa a janela', (await rot()) === 'Tela cheia' && (await larg('main')) === 2400, await larg('main'));
  await clica();
  t('Normal = 1280 (como antes)', (await rot()) === 'Normal' && (await larg('main')) === 1280, await larg('main'));
  await pg.reload(); await pg.waitForTimeout(300);
  t('guardada no navegador', (await rot()) === 'Normal' && (await larg('main')) === 1280);
  t('aplicada antes do primeiro desenho', await pg.evaluate(() => document.documentElement.dataset.largura) === 'normal');
  await clica();
  t('volta para Ampla', (await rot()) === 'Ampla' && (await larg('main')) === 1760);
  await pg.evaluate(() => localStorage.setItem('gp-largura', 'xpto'));
  await pg.reload(); await pg.waitForTimeout(300);
  t('valor inválido cai em Ampla', (await rot()) === 'Ampla' && (await larg('main')) === 1760);
  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  await b.close();
  console.log(`${ok.length} OK, ${bad.length} falha(s)`);
  bad.forEach(x => console.log('FALHOU:', x));
  process.exit(bad.length ? 1 : 0);
})();
