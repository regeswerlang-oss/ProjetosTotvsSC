// Teste da aba Tributos (Configurador de Tributos, front), com /api/* interceptado.
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/tributos-front.js            (SHOT=/tmp/trib.png tira o print)
//
// O payload é o MESMO retrato do teste do back (tributos-fixture.json,
// regerado com FIXTURE=1 python3 docs/testes/tributos-back.py).
// Cobre: aba no lugar, cartões, migração com dependências, matriz CBS/IBS por
// filial, saúde (referência quebrada, status de teste), quantidades com Δ,
// comparação registro a registro com filtro, coleta faseada nas duas bases
// (repete enquanto houver pendente), botão escondido para o cliente e zero erro.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const FIX = JSON.parse(fs.readFileSync(path.join(__dirname, 'tributos-fixture.json'), 'utf-8'));
const AGORA = new Date().toISOString();
const COL = (amb) => ({ id: amb === 'producao' ? 11 : 12, iniciado_em: AGORA, concluido_em: AGORA, status: 'ok',
  environment: amb === 'producao' ? 'producao' : 'desenvolvimento', disparado_por: 'reges', sufixo: '010', duracao_ms: 60000, chamadas: 2 });
const PAYLOAD = (interno = true) => Object.assign({ ok: true, customer: '000348D0', hoje: '2026-10-30', interno,
  bases: { producao: { cadastrada: true, ativo: true, coleta: COL('producao'), erros: {}, andamento: null },
           teste: { cadastrada: true, ativo: true, coleta: Object.assign(COL('teste'), { status: 'parcial' }),
                    erros: { CIN: 'ORA-00932' }, andamento: null } } }, FIX);

async function abre(pg, interno) {
  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: interno
    ? { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'admin', is_admin: true, interno: true }
    : { ok: true, email: 'fiscal@digitro.com.br', nome: 'Fiscal', perfil: 'cliente', modo: 'cliente', is_admin: false, interno: false,
        abas: { '000348D0': ['tributos'] }, abas_catalogo: [] } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [] } }));
  await pg.route('**/api/tributos/000348D0', r => r.fulfill({ json: PAYLOAD(interno) }));
  await pg.goto('http://127.0.0.1:8731/index.html');
  await pg.waitForTimeout(400);
  await pg.evaluate(() => {
    state.selected = { cli: '000348D0', cod: '000348D025', ver: '12', loja: 'D0',
                       projeto: { nome_cliente_projeto: 'DIGITRO TECNOLOGIA LTDA' } };
    $('#view-lista').classList.add('hidden');
    $('#view-detalhe').classList.remove('hidden');
    $('#detalhe-conteudo').classList.remove('hidden');
    setTab('tributos');
  });
  await pg.waitForFunction(() => /O que falta subir/.test(document.querySelector('#trb-conteudo')?.textContent || ''), null, { timeout: 5000 }).catch(() => {});
}

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1500, height: 1000 } });
  const erros = [];
  pg.on('pageerror', e => { if (!/tailwind|lucide|Chart/i.test(e.message)) erros.push('pageerror: ' + e.message); });
  pg.on('dialog', d => d.accept());
  const ok = [], bad = [];
  const t = (nome, cond, extra) => (cond ? ok : bad).push(nome + (extra ? ` [${extra}]` : ''));
  const txt = (sel) => pg.$eval(sel, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');

  await abre(pg, true);
  // coleta: produção com 2 voltas (1 pendente), teste com 1
  const coletas = [];
  await pg.route('**/api/tributos/000348D0/coletar*', async r => {
    const u = r.request().url(); const body = JSON.parse(r.request().postData() || '{}');
    coletas.push(`${/producao/.test(u) ? 'P' : 'T'}:${body.coleta_id || '-'}`);
    await new Promise(res => setTimeout(res, 60));
    const prod = /producao/.test(u);
    if (prod && !body.coleta_id) return r.fulfill({ json: { ok: true, coleta_id: 11, pendentes: ['CIN'], lidas: ['F2B'], status: 'coletando' } });
    r.fulfill({ json: { ok: true, coleta_id: prod ? 11 : 12, pendentes: [], lidas: ['CIN'], status: 'ok' } });
  });

  t('botão da aba Tributos', await pg.$('button.tab-btn[data-tab="tributos"]') !== null);
  const c = await txt('#trb-conteudo');
  t('estado das duas bases', /Base Produção coletada em/.test(c) && /Base de Testes coletada em/.test(c));
  t('base parcial avisada', /parcial \(1 leitura\(s\) com falha\)/.test(c), c.slice(0, 300));
  const cards = await pg.$$eval('#trb-conteudo .grid > div', ns => ns.map(n => n.textContent.replace(/\s+/g, ' ').trim()));
  t('cartões', cards.length >= 6, cards.length);
  t('cartão só em Teste = 4', cards.some(x => /Regras só em Teste\s*! Atenção\s*4/.test(x)), cards[0]);
  t('cartão ref Produção crítico', cards.some(x => /Referências quebradas \(Produção\)\s*✕ Crítico\s*1/.test(x)));
  t('migração com dependências', /TR0010/.test(c) && /Regra de alíquota TA0004/.test(c) && /Perfil de produto TPP009/.test(c));
  t('migração: par de mesmo conteúdo', /mesmo conteúdo na Produção com o código 01 \/ TR0007/.test(c));
  t('migração: campo diferente com título', /Raliq \(F2B_RALIQ\)/.test(c));
  t('reforma por filial', /CBSFED/.test(c) && /02 · Filial SP/.test(c));
  const celula = await pg.$$eval('#trb-conteudo td[title]', ns => ns.map(n => `${n.title}|${n.textContent.trim()}`));
  t('célula só em Teste amarela/rotulada', celula.some(x => /só em Teste — falta subir\|P 0 · T 1/.test(x)), celula.join(' ; ').slice(0, 300));
  t('saúde: ref quebrada PROD01 → TA0099', /PROD01/.test(c) && /TA0099/.test(c) && /não existe \(F28\)/.test(c));
  t('saúde: outra filial no Teste', /existe em outra filial \(F20\)/.test(c));
  t('saúde: status de teste na Produção', /1 regra\(s\) vigente\(s\) com status de teste/.test(c));
  t('quantidades: F2B 5 × 7, Δ +2', /F2B\s*Regra de Cálculo — Documentos Fiscais.*?5\s*7\s*\+2/.test(c));
  t('quantidades: tabela inexistente', /não existe/.test(c));
  t('quantidades: movimento F2D', /F2D/.test(c) && /1\.500/.test(c));
  t('compartilhamento', /EEE/.test(c));

  // comparação registro a registro (F2B fechada → abre)
  await pg.click('[data-trb-caixa="cmp_F2B"]'); await pg.waitForTimeout(80);
  let f2b = await txt('#trb-conteudo');
  t('F2B aberta: diferença Produção → Teste', /TA0002\s*→\s*TA0003/.test(f2b), '');
  t('F2B: chave mostrada', /chave: F2B_FILIAL \+ F2B_REGRA \+ F2B_VIGINI/.test(f2b));
  t('F2B: ID ignorado', /ignora: F2B_ID/.test(f2b));
  t('F2B: status decodificado', /2 - Aprovado/.test(f2b));
  await pg.selectOption('[data-trb-filtro="F2B"]', 'iguais'); await pg.waitForTimeout(80);
  const iguais = await pg.$$eval('[data-trb-filtro="F2B"] ~ span', ns => ns.map(n => n.textContent));
  t('filtro iguais = 2', /2 registro/.test(iguais[0] || ''), iguais[0]);
  await pg.click('[data-trb-caixa="cmp_F21"]'); await pg.waitForTimeout(80);
  t('F21 por conteúdo', /sem chave estável: comparado pelo conteúdo/.test(await txt('#trb-conteudo')));
  if (process.env.SHOT) await pg.screenshot({ path: process.env.SHOT, fullPage: true });

  // coleta faseada
  await pg.click('#trb-coletar');
  await pg.waitForTimeout(40);
  t('barra coletando', /Coletando…/.test(await txt('#trb-conteudo')));
  await pg.waitForTimeout(800);
  t('coleta: P nova, P continua 11, T nova', coletas.join(',') === 'P:-,P:11,T:-', coletas.join(','));
  t('voltou ao normal', /O que falta subir/.test(await txt('#trb-conteudo')));
  t('zero erro de JS (interno)', erros.length === 0, erros.join(' | '));

  // cliente: vê a aba, sem botão de coleta
  const pg2 = await b.newPage({ viewport: { width: 1400, height: 900 } });
  pg2.on('pageerror', e => { if (!/tailwind|lucide|Chart/i.test(e.message)) erros.push('cliente: ' + e.message); });
  await abre(pg2, false);
  const vis = await pg2.$eval('#trb-coletar', n => getComputedStyle(n).display !== 'none').catch(() => true);
  t('cliente não vê o ⚡ Coletar', !vis);
  t('cliente vê a comparação', /O que falta subir/.test(await pg2.$eval('#trb-conteudo', n => n.textContent)));
  t('zero erro de JS (cliente)', erros.length === 0, erros.join(' | '));

  await b.close();
  console.log(`${ok.length} ok, ${bad.length} falhou`);
  bad.forEach(x => console.log('FALHOU:', x));
  process.exit(bad.length ? 1 : 0);
})();
