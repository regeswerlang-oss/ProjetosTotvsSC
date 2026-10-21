// SM0 agrupada por EMPRESA + UNIDADE quando o leiaute tem UU (Cresol: EEUUFFFF).
// Monta os dois blocos que listam a SM0 — aba Empresas (empSM0Html) e "Empresas
// da base" na aba Estrutura (estBlocoSM0) — direto pelas funções do painel.
//
//   cd web && python3 -m http.server 8733 --bind 127.0.0.1 &
//   node docs/testes/sm0-unidade-front.js
const { chromium } = require(process.env.PW || 'playwright');

const F = (empresa, filial, nome, leiaute = 'EEUUFFFF') =>
  ({ empresa, filial, nome_empresa: 'CRESOL', nome_filial: nome, cnpj: '', leiaute, sizefil: 8,
     sx2: true, qtd_tabelas: 80, tabelas: 'F20 F22', lido_em: '21/10/2026 14:00', updated_by: 'reges' });
const CRESOL = [F('01', '01260001', 'Sede'), F('01', '01260002', 'Agência A'), F('01', '01260003', 'Agência B'),
  F('01', '01010001', 'Central'), F('01', '01010002', 'Central 2')];
for (let i = 4; i <= 20; i++) CRESOL.push(F('01', '0126' + String(i).padStart(4, '0'), 'Ag ' + i));
const SEM_UN = [F('01', '0101', 'Matriz', 'EEFF'), F('01', '0102', 'Filial', 'EEFF'), F('02', '0201', 'Outra', 'EEFF')];

(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || undefined, args: ['--no-sandbox'] });
  const pg = await b.newPage();
  const erros = [];
  pg.on('pageerror', e => erros.push(e.message));
  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.goto('http://127.0.0.1:8733/index.html');
  await pg.waitForTimeout(400);
  const r = await pg.evaluate(([cresol, semUn]) => {
    const doc = html => { const d = document.createElement('div'); d.innerHTML = html; return d; };
    const linhas = d => [...d.querySelectorAll('[data-sm0-grupo]')].map(t => t.dataset.sm0Grupo);
    const e1 = doc(empSM0Html(cresol)), e2 = doc(estBlocoSM0({ sm0: cresol, sm0_ambiente: 'teste' }, { leiaute: 'EEUUFFFF' }));
    const e3 = doc(empSM0Html(semUn));
    return {
      emp: linhas(e1), est: linhas(e2), semUn: linhas(e3),
      cabEmp: [...e1.querySelectorAll('th')].map(t => t.textContent.trim()),
      cabSem: [...e3.querySelectorAll('th')].map(t => t.textContent.trim()),
      resumo: e1.querySelector('h3').parentElement.textContent.replace(/\s+/g, ' '),
      recolhe: !!e1.querySelector('[data-sm0-grupo="01|0126"] details'),
      rowspan: e1.querySelectorAll('td[rowspan="2"]').length,
    };
  }, [CRESOL, SEM_UN]);
  const ok = [], bad = [];
  const t = (n, c, x) => (c ? ok : bad).push(n + (x ? ` [${x}]` : ''));
  t('Empresas: uma linha por empresa + unidade', JSON.stringify(r.emp) === JSON.stringify(['01|0101', '01|0126']), r.emp.join(','));
  t('Estrutura: mesmo agrupamento', JSON.stringify(r.est) === JSON.stringify(['01|0101', '01|0126']), r.est.join(','));
  t('coluna Empresa + unidade', r.cabEmp.includes('Empresa + unidade'), r.cabEmp.join(','));
  t('resumo conta as unidades', r.resumo.includes('2 empresa+unidade(s)') && r.resumo.includes('22 filial(is)'), r.resumo);
  t('unidade com muitas filiais recolhe', r.recolhe);
  t('dicionário/tabelas em rowspan por empresa', r.rowspan === 2, String(r.rowspan));
  t('sem UU: uma linha por empresa, sem a coluna', JSON.stringify(r.semUn) === JSON.stringify(['01|', '02|']) && !r.cabSem.includes('Empresa + unidade'), r.semUn.join(','));
  t('zero erro de JS', !erros.length, erros.join(' | '));
  console.log(JSON.stringify({ ok: ok.length, falhas: bad }, null, 2));
  await b.close();
  process.exit(bad.length ? 1 : 0);
})();
