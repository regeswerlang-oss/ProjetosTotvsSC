// Stub do backend + Chromium para a aba Plano de Virada: visão interna (janela
// recomendada, linha do tempo, KPIs, filtros, incluir, editar, trocar status,
// excluir, datas do plano) e a visão do CLIENTE (só consulta). Falha se houver
// erro de console.
//
//   node docs/testes/virada-front.mjs        (rodar na raiz do repo)
//
// O stub imita /api/virada/* em memória com o MESMO contrato do api/index.py.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const WEB = path.resolve('web');
const SHOTS = process.env.SHOTS || '/tmp';
const CT = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };
const CLI = '000348D0';
const FIX = JSON.parse(fs.readFileSync(path.resolve('docs/testes/virada-fixture.json'), 'utf8'));
let PLANO = FIX.plano, ITENS = FIX.itens.map(i => ({ ...i }));
let INTERNO = true;
const chamadas = [];

const srv = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x');
  const json = (c, o) => { res.writeHead(c, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
  let corpo = '';
  for await (const ch of req) corpo += ch;
  const b = corpo ? JSON.parse(corpo) : {};
  if (u.pathname === '/api/me') return json(200, { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: INTERNO ? 'comum' : 'cliente', modo: INTERNO ? 'interno' : 'cliente',
    is_admin: INTERNO, interno: INTERNO, abas: INTERNO ? null : { [CLI]: ['virada'] }, abas_catalogo: [] });
  if (u.pathname === '/api/projetos') return json(200, { ok: true, projetos: [], sincronizado_em: '2026-11-04' });
  if (u.pathname === `/api/virada/${CLI}` && req.method === 'GET')
    return json(200, { ok: true, customer: CLI, interno: INTERNO, hoje: '2026-11-04', plano: PLANO, itens: ITENS.filter(i => i.ativo) });
  if (req.method === 'POST' && u.pathname.startsWith('/api/virada')) {
    chamadas.push([u.pathname, b]);
    if (!INTERNO) return json(403, { ok: false, error: 'Ação restrita à equipe TOTVS.' });
    if (u.pathname === `/api/virada/${CLI}/item`) {
      const n = Math.max(...ITENS.map(i => +i.codigo.slice(3))) + 1;
      const it = { ...b, id: ITENS.length + 1, customer: CLI, codigo: `PV-${String(n).padStart(3, '0')}`, origem: 'manual', ativo: true,
                   data_inicio: b.data_inicio || null, data_fim: b.data_fim || null };
      ITENS.push(it); return json(200, { ok: true, item: it });
    }
    if (u.pathname === `/api/virada/${CLI}/plano`) { PLANO = { ...PLANO, ...b }; return json(200, { ok: true, plano: PLANO }); }
    let m = u.pathname.match(/^\/api\/virada\/item\/(\d+)\/excluir$/);
    if (m) { ITENS.find(i => i.id === +m[1]).ativo = false; return json(200, { ok: true }); }
    m = u.pathname.match(/^\/api\/virada\/item\/(\d+)$/);
    if (m) { const it = ITENS.find(i => i.id === +m[1]); Object.assign(it, b); return json(200, { ok: true, item: it }); }
  }
  if (u.pathname.startsWith('/api/')) return json(200, { ok: true });
  const f = path.join(WEB, u.pathname === '/' ? 'index.html' : u.pathname);
  if (fs.existsSync(f) && fs.statSync(f).isFile()) { res.writeHead(200, { 'Content-Type': CT[path.extname(f)] || 'text/plain' }); return res.end(fs.readFileSync(f)); }
  res.writeHead(404); res.end();
});
const PORTA = 5198;
await new Promise(r => srv.listen(PORTA, r));

const pw = createRequire(import.meta.url)('playwright');
const navegador = await pw.chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const TW = process.env.TW_JS || '/tmp/twb/package/dist/index.global.js';
async function novaPagina() {
  const pag = await navegador.newPage({ viewport: { width: 1440, height: 1000 } });
  pag.erros = [];
  pag.on('console', m => { if (m.type() === 'error' && !/Failed to load resource|net::ERR_/.test(m.text())) pag.erros.push(m.text()); });
  pag.on('pageerror', e => pag.erros.push('pageerror: ' + e.message));
  pag.on('dialog', d => d.type() === 'confirm' ? d.accept() : (pag.erros.push('dialog: ' + d.message()), d.dismiss()));
  await pag.route('**/cdn.tailwindcss.com*', r => r.fulfill({ status: 200, contentType: 'application/javascript',
    body: fs.existsSync(TW) ? fs.readFileSync(TW, 'utf8') : '' }));
  await pag.route('**/fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
  await pag.goto(`http://127.0.0.1:${PORTA}/`, { waitUntil: 'networkidle' });
  await pag.evaluate(cli => abrirDetalhe({ cli, cod: '000348D025', ver: '12', loja: 'D0',
    projeto: { nome_cliente_projeto: 'DIGITRO TECNOLOGIA SA', descricao_projeto: 'Servicos de Implantacao' } }), CLI);
  await pag.waitForTimeout(400);
  return pag;
}

let ok = 0, falhou = 0;
const confere = (nome, cond) => { if (cond) ok++; else { falhou++; console.log('FALHOU:', nome); } };

// ── 1. Visão interna ────────────────────────────────────────────────────────
const pag = await novaPagina();
confere('botão da aba existe', await pag.isVisible('[data-tab="virada"]'));
await pag.click('[data-tab="virada"]');
await pag.waitForSelector('#vir-conteudo table', { timeout: 5000 });
await pag.screenshot({ path: `${SHOTS}/virada-interno.png`, fullPage: true });
const linhas = () => pag.$$eval('#vir-conteudo [data-viredit]', e => e.length);
confere('55 linhas', await linhas() === 55);
const txt = await pag.textContent('#vir-conteudo');
confere('janela recomendada', txt.includes('Melhor período') && txt.includes('04/01/2027'));
confere('dias até a virada', /faltam 61 dias corridos/.test(txt));
confere('janelas avaliadas', txt.includes('Plano B') && txt.includes('Evitar'));
confere('linha do tempo com Dia D', txt.includes('Linha do tempo') && txt.includes('Dia D'));
confere('D-61 na coluna', txt.includes('D-61') || txt.includes('D-55'));

// filtros
await pag.check('#vir-f-go'); await pag.waitForTimeout(100);
confere('filtro Go/No-Go', await linhas() === 32);
await pag.uncheck('#vir-f-go');
await pag.fill('#vir-q', 'cnab'); await pag.waitForTimeout(100);
const nCnab = await linhas();
confere('busca cnab', nCnab >= 2 && nCnab < 10);
await pag.fill('#vir-q', ''); await pag.selectOption('#vir-f-fase', 'corte'); await pag.waitForTimeout(100);
confere('filtro fase corte', await linhas() === 4);
await pag.selectOption('#vir-f-fase', '');

// incluir
await pag.click('#vir-novo');
await pag.waitForSelector('#vi-atividade');
await pag.selectOption('#vi-fase', 'carga');
await pag.fill('#vi-frente', 'Ativo Fixo');
await pag.fill('#vi-atividade', 'Carga do imobilizado com <b>plaqueta</b>');
await pag.fill('#vi-ini', '2027-01-02'); await pag.fill('#vi-fim', '2027-01-01');
await pag.click('[data-ok]'); await pag.waitForTimeout(150);
confere('valida fim antes do início', (await pag.textContent('[data-erro]')).includes('antes do início'));
await pag.fill('#vi-fim', '2027-01-03');
await pag.check('#vi-go');
await pag.click('[data-ok]'); await pag.waitForTimeout(400);
confere('incluiu PV-056', ITENS.some(i => i.codigo === 'PV-056' && i.criterio_go === true && i.fase === 'carga'));
confere('56 linhas', await linhas() === 56);
confere('html escapado', !(await pag.$('#vir-conteudo td b:text("plaqueta")')) && (await pag.content()).includes('&lt;b&gt;plaqueta'));

// editar
const id56 = ITENS.find(i => i.codigo === 'PV-056').id;
await pag.click(`[data-viredit="${id56}"]`);
await pag.waitForSelector('#vi-atividade');
confere('modal traz valores', await pag.inputValue('#vi-frente') === 'Ativo Fixo');
await pag.fill('#vi-resp', 'Fabrício');
await pag.fill('#vi-obs', 'Plaqueta obrigatória');
await pag.click('[data-ok]'); await pag.waitForTimeout(400);
confere('editou', ITENS.find(i => i.id === id56).resp_nome === 'Fabrício');
confere('observação aparece', (await pag.textContent('#vir-conteudo')).includes('Plaqueta obrigatória'));

// status na linha
await pag.selectOption('[data-virst="1"]', 'concluido'); await pag.waitForTimeout(300);
confere('status pela linha', ITENS.find(i => i.id === 1).status === 'concluido');

// excluir
await pag.click(`[data-virdel="${id56}"]`); await pag.waitForTimeout(400);
confere('excluiu', ITENS.find(i => i.id === id56).ativo === false && await linhas() === 55);

// datas do plano
await pag.click('#vir-datas'); await pag.waitForSelector('#vd-virada');
await pag.fill('#vd-virada', '2027-02-01');
await pag.click('[data-ok]'); await pag.waitForTimeout(300);
confere('gravou data da virada', PLANO.data_virada === '2027-02-01');
confere('cartão reflete nova data', (await pag.textContent('#vir-conteudo')).includes('01/02/2027'));
PLANO.data_virada = '2027-01-04';

// export
const rel = await pag.evaluate(() => typeof RELATORIOS !== 'undefined' && RELATORIOS.virada && RELATORIOS.virada.alvo);
confere('relatório registrado', rel === '#vir-conteudo');
confere('interno sem erro de console', pag.erros.length === 0);
if (pag.erros.length) console.log(pag.erros);

// ── 2. Visão do cliente ─────────────────────────────────────────────────────
INTERNO = false;
const pc = await novaPagina();
await pc.waitForTimeout(200);
await pc.click('[data-tab="virada"]').catch(() => {});
await pc.waitForSelector('#vir-conteudo table', { timeout: 5000 });
await pc.screenshot({ path: `${SHOTS}/virada-cliente.png`, fullPage: true });
confere('cliente sem incluir', !(await pc.isVisible('#vir-novo')));
confere('cliente sem editar/excluir', (await pc.$$('[data-viredit],[data-virdel],[data-virst]')).length === 0);
confere('cliente vê a janela', (await pc.textContent('#vir-conteudo')).includes('Melhor período'));
confere('cliente sem erro de console', pc.erros.length === 0);
if (pc.erros.length) console.log(pc.erros);

await navegador.close(); srv.close();
console.log(`virada-front: ${ok} ok, ${falhou} falhou`);
process.exit(falhou ? 1 : 0);
