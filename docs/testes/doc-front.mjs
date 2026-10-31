// Stub do backend + Chromium para a aba Documentação: visão interna (por
// processo, matriz, dispensa, liberação, visualizador HTML/imagem/texto) e a
// visão do CLIENTE (só o liberado, sem controles internos). Falha se houver
// erro de console.
//
//   node docs/testes/doc-front.mjs                 (rodar na raiz do repo)
//   DOC_MANIFEST=… DOC_PAC=… node docs/testes/doc-front.mjs   (com arquivos reais)
//
// O stub imita /api/docs/* em memória com o MESMO contrato do api/index.py.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const WEB = path.resolve('web');
const SHOTS = process.env.SHOTS || '/tmp';
const CT = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };
const MIME = { html: 'text/html; charset=utf-8', jpeg: 'image/jpeg', png: 'image/png', svg: 'image/svg+xml', pdf: 'application/pdf', md: 'text/markdown; charset=utf-8', txt: 'text/plain; charset=utf-8' };
const CLI = '000348D0';
const P = (id, tipo, grupo, nome, prefixo, ordem) => ({ id, tipo, grupo, nome, prefixo, ordem });
const PROCS = [P(1, 'processo', 'principal', 'CRM', 'CRM', 10), P(2, 'processo', 'principal', 'iPaaS', 'IPA', 20),
  P(3, 'processo', 'principal', 'Painel de Projetos', 'PNL', 30), P(4, 'processo', 'principal', 'Contratos', 'CTR', 40),
  P(7, 'processo', 'complementar', 'Fiscal / NFS-e', 'FIS', 70), P(19, 'processo', 'complementar', 'Cadastros (base)', 'CAD', 105),
  P(11, 'ligacao', 'principal', 'CRM → iPaaS', null, 11), P(12, 'ligacao', 'principal', 'iPaaS → Painel de Projetos', null, 21),
  P(13, 'ligacao', 'principal', 'Painel de Projetos → Contratos', null, 31), P(14, 'ligacao', 'principal', 'CRM → Contratos', null, 32)];
const TIPOS = [['fluxo', 'Fluxo sistêmico', true, 'cliente'], ['explicacao', 'Explicação ao cliente', false, 'cliente'], ['processo', 'Processo consolidado', true, 'cliente'],
  ['especificacao', 'Especificação da customização (MIT044)', true, 'cliente'], ['validacao', 'Termo de validação (MIT010)', true, 'cliente'],
  ['tecnico', 'Desenho / especificação técnica', false, 'consultoria'], ['registro', 'Registro de reunião interno', false, 'consultoria']]
  .map(([codigo, nome, obrigatorio, nivel_max], i) => ({ codigo, nome, obrigatorio, nivel_max, descricao: '', formatos: ['html', 'pdf'], ordem: i }));

// ── dados: manifesto real (opcional) ou sintético ──────────────────────────
const SINT = {
  series: [
    { serie: 'fluxo-comercial', tipo: 'fluxo', titulo: 'Fluxo sistêmico comercial', processos: ['CRM', 'CTR', 'FIS'],
      versoes: [{ arquivo: 'c1.html', versao: 'v1', data: '2026-10-27', vigente: false }, { arquivo: 'c2.html', versao: 'v2', data: '2026-10-30' }, { arquivo: 'c.svg', versao: 'v2' }] },
    { serie: 'fluxo-integracoes', tipo: 'fluxo', titulo: 'Fluxo das integrações <b>CRM</b>', processos: ['CRM', 'IPA', 'PNL', 'CTR', 'CRM → iPaaS'],
      versoes: [{ arquivo: 'i.html', versao: 'v2' }] },
    { serie: 'fluxo-painel', tipo: 'fluxo', titulo: 'Fluxo do Painel', processos: ['PNL'], versoes: [{ arquivo: 'p.html' }] },
    { serie: 'processo-painel', tipo: 'processo', titulo: 'Processo do Painel', processos: ['PNL'], versoes: [{ arquivo: 'p.md' }] },
    { serie: 'mit044', tipo: 'especificacao', titulo: 'MIT044 Painel', processos: ['PNL'], versoes: [{ arquivo: 'm.pdf' }] },
    { serie: 'mit010', tipo: 'validacao', titulo: 'MIT010 Painel', processos: ['PNL'], versoes: [{ arquivo: 'v.pdf' }] },
    { serie: 'desenho', tipo: 'tecnico', titulo: 'Desenho técnico EAI', processos: ['CRM', 'IPA'], versoes: [{ arquivo: 'd.html' }] },
    { serie: 'resumo', tipo: 'registro', titulo: 'Resumo interno', processos: ['CRM'], versoes: [{ arquivo: 'r.txt' }] },
  ] };
const ARQ_SINT = {
  'c1.html': '<!DOCTYPE html><meta charset="utf-8"><h1>Comercial v1</h1>', 'c2.html': '<!DOCTYPE html><meta charset="utf-8"><h1 id="t">Comercial v2</h1><script>document.title="ok"</script>',
  'c.svg': '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120"><rect width="400" height="120" fill="#00DBFF"/><text x="20" y="70">fluxo</text></svg>',
  'i.html': '<!DOCTYPE html><meta charset="utf-8"><h1>Integrações</h1>', 'p.html': '<!DOCTYPE html><meta charset="utf-8"><h1>Painel</h1>',
  'p.md': '# Processo do Painel\n\n| Item | Valor |\n|---|---|\n| Cliente | <b>Dígitro</b> |\n\n- **rotina** U_POPROJET\n> regra de leitura',
  'm.pdf': '%PDF-1.4\n%fake', 'v.pdf': '%PDF-1.4\n%fake', 'd.html': '<!DOCTYPE html><h1>Desenho</h1>', 'r.txt': 'Resumo <script>x</script> da reunião',
};
const MAN = process.env.DOC_MANIFEST ? JSON.parse(fs.readFileSync(process.env.DOC_MANIFEST, 'utf8')) : SINT;
const ler = a => process.env.DOC_PAC ? fs.readFileSync(path.join(process.env.DOC_PAC, a)) : Buffer.from(ARQ_SINT[a], 'utf8');
const fmtDe = a => ({ '.html': 'html', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.png': 'png', '.svg': 'svg', '.pdf': 'pdf', '.md': 'md', '.txt': 'txt' })[path.extname(a).toLowerCase()];
const ref = r => PROCS.find(p => p.prefixo === r || p.nome === r || String(p.id) === String(r))?.id;
let seq = 0;
const SERIES = MAN.series.map((s, i) => ({ id: 100 + i, serie: s.serie, tipo: s.tipo, titulo: s.titulo, descricao: s.descricao || null, ordem: s.ordem || i,
  processos: s.processos.map(ref).filter(Boolean),
  versoes: s.versoes.map(v => ({ id: ++seq, formato: fmtDe(v.arquivo), versao: v.versao || null, data_documento: v.data || null, vigente: v.vigente !== false,
    visibilidade: 'consultoria', nome_arquivo: v.nome || v.arquivo, origem: v.origem || null, nota: v.nota || null, url_externa: null,
    tamanho: ler(v.arquivo).length, _arq: v.arquivo, publicado_por: 'reges.werlang@totvs.com.br', publicado_em: '2026-10-30' })) }));
const DISP = [];

function cobertura() {
  const obrig = TIPOS.filter(t => t.obrigatorio).map(t => t.codigo);
  return PROCS.filter(p => p.tipo === 'processo').map(p => {
    const celulas = {}; let ok = 0, exigidos = 0;
    TIPOS.forEach(t => {
      const ss = SERIES.filter(s => s.tipo === t.codigo && s.processos.includes(p.id) && s.versoes.some(v => v.vigente));
      const d = DISP.find(x => x.processo_id === p.id && x.tipo === t.codigo);
      const st = ss.length ? 'ok' : d ? 'dispensado' : obrig.includes(t.codigo) ? 'falta' : null;
      if (obrig.includes(t.codigo) && st !== 'dispensado') { exigidos++; ok += st === 'ok'; }
      if (st) celulas[t.codigo] = { status: st, series: ss.map(s => s.id), cliente: ss.some(s => s.versoes.some(v => v.vigente && v.visibilidade === 'cliente')), motivo: d?.motivo || null };
    });
    return { processo_id: p.id, celulas, ok, exigidos };
  });
}
const limpaV = v => Object.fromEntries(Object.entries(v).filter(([k]) => !k.startsWith('_')));
function payload(interno) {
  if (interno) return { ok: true, interno: true, pode_liberar: true, usuario: 'reges', max_bytes: 3.5e6, max_pacote: 4.4e6, tipos: TIPOS, processos: PROCS,
    series: SERIES.map(s => ({ ...s, versoes: s.versoes.map(limpaV) })), dispensas: DISP, cobertura: cobertura() };
  const pode = TIPOS.filter(t => t.nivel_max === 'cliente').map(t => t.codigo);
  const series = SERIES.filter(s => pode.includes(s.tipo)).map(s => ({ id: s.id, serie: s.serie, tipo: s.tipo, titulo: s.titulo, descricao: s.descricao, ordem: s.ordem, processos: s.processos,
    versoes: s.versoes.filter(v => v.vigente && v.visibilidade === 'cliente').map(v => ({ id: v.id, formato: v.formato, versao: v.versao, data_documento: v.data_documento, tamanho: v.tamanho, nome_arquivo: v.nome_arquivo, url_externa: null })) }))
    .filter(s => s.versoes.length);
  const usados = new Set(series.flatMap(s => s.processos));
  return { ok: true, interno: false, tipos: TIPOS.filter(t => t.nivel_max === 'cliente'), processos: PROCS.filter(p => usados.has(p.id)), series };
}

let MODO = 'interno';
const POSTS = [];
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  const chunks = [];
  req.on('data', c => chunks.push(c));
  req.on('end', () => {
    const raw = Buffer.concat(chunks).toString('utf8');
    const json = (code, o) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
    if (u.pathname === '/api/me') return json(200, MODO === 'interno'
      ? { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'admin', is_admin: true, interno: true, modo: 'interno', abas: null, abas_catalogo: [] }
      : { ok: true, email: 'aline@digitro.com.br', nome: 'Aline', perfil: 'cliente', is_admin: false, interno: false, modo: 'cliente', abas: { [CLI]: ['documentos'] }, abas_catalogo: [] });
    if (u.pathname === '/api/projetos') return json(200, { ok: true, projetos: [], sincronizado_em: '2026-10-30' });
    const m = u.pathname.match(/^\/api\/docs\/([^/]+)(?:\/(\w+)(?:\/(\d+))?)?$/);
    if (m) {
      const [, cli, acao, id] = m;
      if (cli !== CLI) return json(403, { ok: false, error: 'Sem acesso a este cliente.' });
      if (!acao) return json(200, payload(MODO === 'interno'));
      if (acao === 'arquivo') {
        const s = SERIES.find(x => x.versoes.some(v => v.id === +id)), v = s?.versoes.find(x => x.id === +id);
        if (!v || (MODO !== 'interno' && !(v.vigente && v.visibilidade === 'cliente' && TIPOS.find(t => t.codigo === s.tipo).nivel_max === 'cliente')))
          return json(404, { ok: false, error: 'Documento não encontrado.' });
        const h = { 'Content-Type': MIME[v.formato] };
        if (v.formato === 'html' || v.formato === 'svg') h['Content-Security-Policy'] = 'sandbox allow-scripts allow-popups';
        res.writeHead(200, h); return res.end(ler(v._arq));
      }
      if (MODO !== 'interno') return json(403, { ok: false, error: 'Ação restrita à equipe TOTVS.' });
      const b = raw && req.headers['content-type']?.includes('json') ? JSON.parse(raw) : {};
      POSTS.push([acao, id, b]);
      if (acao === 'versao') {
        const s = SERIES.find(x => x.versoes.some(v => v.id === +id)), v = s.versoes.find(x => x.id === +id);
        if (b.visibilidade) { if (b.visibilidade === 'cliente' && TIPOS.find(t => t.codigo === s.tipo).nivel_max !== 'cliente') return json(403, { ok: false, error: 'tipo interno' }); v.visibilidade = b.visibilidade; }
        if (b.vigente) { s.versoes.filter(x => x.formato === v.formato).forEach(x => x.vigente = false); v.vigente = true; }
        return json(200, { ok: true });
      }
      if (acao === 'dispensa') { if (b.remover) DISP.splice(DISP.findIndex(d => d.processo_id === b.processo_id && d.tipo === b.tipo), 1); else DISP.push(b); return json(200, { ok: true }); }
      if (acao === 'serie') { const s = SERIES.find(x => x.id === +id); Object.assign(s, b); return json(200, { ok: true }); }
      return json(200, { ok: true });
    }
    if (u.pathname.startsWith('/api/')) return json(200, { ok: true });
    const f = path.join(WEB, u.pathname === '/' ? 'index.html' : u.pathname.slice(1));
    if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) { res.writeHead(200, { 'Content-Type': CT[path.extname(f)] || 'application/octet-stream' }); return res.end(fs.readFileSync(f)); }
    res.writeHead(404).end('nao encontrado');
  });
});
const PORTA = 5199;
await new Promise(r => srv.listen(PORTA, r));

const pw = createRequire(import.meta.url)('playwright');
const navegador = await pw.chromium.launch();
const TW = process.env.TW_JS || '/home/claude/w/tw.js';
async function novaPagina() {
  const pag = await navegador.newPage({ viewport: { width: 1440, height: 1000 } });
  pag.erros = [];
  pag.on('console', m => { if (m.type() === 'error' && !/Failed to load resource.*(404|tailwind)|net::ERR_/.test(m.text())) pag.erros.push(m.text()); });
  pag.on('pageerror', e => pag.erros.push('pageerror: ' + e.message));
  pag.on('dialog', d => d.type() === 'prompt' ? d.accept('Sem customização neste processo') : d.type() === 'confirm' ? d.accept() : (pag.erros.push('dialog: ' + d.message()), d.dismiss()));
  await pag.route('**/cdn.tailwindcss.com*', r => fs.existsSync(TW)
    ? r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(TW, 'utf8') })
    : r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
  await pag.route('**/fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
  await pag.goto(`http://127.0.0.1:${PORTA}/`, { waitUntil: 'networkidle' });
  await pag.evaluate(cli => abrirDetalhe({ cli, cod: '000348D025', ver: '12', loja: 'D0',
    projeto: { nome_cliente_projeto: 'DIGITRO TECNOLOGIA LTDA', descricao_projeto: 'Servicos de Implantacao' } }), CLI);
  await pag.waitForTimeout(400);
  return pag;
}

// ── 1. Visão interna ────────────────────────────────────────────────────────
const pag = await novaPagina();
const abaVisivel = await pag.isVisible('[data-tab="documentos"]');
await pag.click('[data-tab="documentos"]');
await pag.waitForSelector('[data-docserie]', { timeout: 5000 });
await pag.screenshot({ path: `${SHOTS}/doc-interno-todos.png`, fullPage: true });
const nTodos = await pag.$$eval('#doc-conteudo [data-docserie]', e => e.length);
const htmlCru = (await pag.content()).includes('Fluxo das integrações <b>CRM</b>');
await pag.click('nav [data-docproc="3"]'); await pag.waitForTimeout(150);
const painel = await pag.evaluate(() => ({ n: document.querySelectorAll('#doc-conteudo [data-docserie]').length, faltas: document.querySelectorAll('[data-docdisp]').length,
  cab: document.querySelector('#doc-conteudo h3')?.textContent }));
await pag.screenshot({ path: `${SHOTS}/doc-interno-painel.png`, fullPage: true });
await pag.click('nav [data-docproc="1"]'); await pag.waitForTimeout(150);
const faltasCRM = await pag.$$eval('[data-docdisp]', e => e.map(x => x.dataset.docdisp));
await pag.click('[data-docdisp="especificacao"]'); await pag.waitForTimeout(300);
const aposDisp = { disp: DISP.map(d => `${d.processo_id}:${d.tipo}:${d.motivo}`), reativar: await pag.$$eval('[data-docreativa]', e => e.length) };
// visualizador: HTML
const sCom = SERIES[1].id === undefined ? null : SERIES.find(s => s.serie.startsWith('fluxo-comercial'));
const vHtml = sCom.versoes.find(v => v.vigente && v.formato === 'html');
await pag.click(`[data-docabre="${vHtml.id}"]`); await pag.waitForSelector('#doc-viewer iframe');
const iframe = await pag.$eval('#doc-viewer iframe', f => ({ src: f.getAttribute('src'), sandbox: f.getAttribute('sandbox') }));
await pag.waitForTimeout(400);
await pag.screenshot({ path: `${SHOTS}/doc-viewer-html.png` });
await pag.keyboard.press('Escape'); await pag.waitForTimeout(100);
const fechou = !(await pag.$('#doc-viewer'));
// visualizador: imagem
const vImg = SERIES.flatMap(s => s.versoes).find(v => v.vigente && ['jpeg', 'png', 'svg'].includes(v.formato));
await pag.click('nav [data-docproc="todos"]'); await pag.waitForTimeout(100);
await pag.click(`[data-docabre="${vImg.id}"]`); await pag.waitForSelector('#doc-viewer img');
await pag.waitForTimeout(500);
const img = await pag.$eval('#doc-viewer img', i => ({ ok: i.complete && i.naturalWidth > 0, src: i.getAttribute('src') }));
await pag.screenshot({ path: `${SHOTS}/doc-viewer-img.png` });
await pag.click('#doc-viewer [data-fechar]');
// visualizador: texto/markdown
const vTxt = SERIES.flatMap(s => s.versoes).find(v => v.vigente && ['md', 'txt'].includes(v.formato));
let leitura = null;
if (vTxt) {
  await pag.click(`[data-docabre="${vTxt.id}"]`); await pag.waitForSelector('#doc-viewer article', { timeout: 4000 });
  leitura = await pag.$eval('#doc-viewer article', a => ({ temScript: !!a.querySelector('script'), temB: !!a.querySelector('td b'), txt: a.textContent.slice(0, 40) }));
  await pag.click('#doc-viewer [data-fechar]');
}
// liberar ao cliente: fluxo comercial (html)
await pag.click(`[data-docserie="${sCom.id}"] details summary`);
await pag.selectOption(`[data-docvis="${vHtml.id}"]`, 'cliente'); await pag.waitForTimeout(350);
const sInt = SERIES.find(s => s.tipo === 'tecnico' || s.tipo === 'registro');
await pag.click(`[data-docserie="${sInt.id}"] details summary`);
const travaInterno = await pag.$eval(`[data-docvis="${sInt.versoes[0].id}"] option[value="cliente"]`, o => o.disabled);
// matriz
await pag.click('[data-docv="matriz"]'); await pag.waitForTimeout(150);
const matriz = await pag.evaluate(() => ({ ok: document.querySelectorAll('#doc-conteudo td button.bg-emerald-100').length,
  falta: document.querySelectorAll('#doc-conteudo [data-docdisp]').length, disp: document.querySelectorAll('#doc-conteudo [data-docreativa]').length,
  olho: [...document.querySelectorAll('#doc-conteudo td button')].some(b => b.textContent.includes('👁')) }));
await pag.screenshot({ path: `${SHOTS}/doc-matriz.png`, fullPage: true });
const kpis = await pag.$$eval('#doc-kpis > *', e => e.map(x => x.innerText.replace(/\n/g, ' ')));
const exportavel = await pag.evaluate(() => !!relatorioDaAba());
const errosInt = pag.erros;

// ── 2. Visão do cliente ─────────────────────────────────────────────────────
MODO = 'cliente';
const cli = await novaPagina();
const abasCli = await cli.$$eval('.tab-btn', b => b.filter(x => !x.classList.contains('hidden')).map(x => x.dataset.tab));
await cli.waitForSelector('[data-docserie]', { timeout: 5000 });
const visaoCli = await cli.evaluate(() => ({ series: [...document.querySelectorAll('[data-docserie]')].map(e => e.querySelector('.font-medium').textContent),
  internosVisiveis: [...document.querySelectorAll('[data-interno]')].filter(e => e.offsetParent !== null).length,
  controles: document.querySelectorAll('[data-docvis],[data-docdel],[data-docnova]').length, nav: document.querySelectorAll('nav [data-docproc]').length }));
await cli.screenshot({ path: `${SHOTS}/doc-cliente.png`, fullPage: true });
const r404 = await cli.evaluate(async id => (await fetch(`/api/docs/000348D0/arquivo/${id}`)).status, sInt.versoes[0].id);
const errosCli = cli.erros;

const r = { abaVisivel, nTodos, htmlCru, painel, faltasCRM, aposDisp, iframe, fechou, img, leitura, posts: POSTS.map(p => p.slice(0, 2).join('/')),
  travaInterno, matriz, kpis, exportavel, abasCli, visaoCli, r404, errosInt, errosCli };
console.log(JSON.stringify(r, null, 2));
const ok = abaVisivel && nTodos === SERIES.length && !htmlCru && painel.n >= 4 && painel.faltas === 0 && faltasCRM.includes('especificacao')
  && aposDisp.disp.length === 1 && aposDisp.reativar === 1 && iframe.sandbox && !iframe.sandbox.includes('allow-same-origin') && iframe.src.includes('/arquivo/')
  && fechou && img.ok && (!leitura || !leitura.temScript) && travaInterno && matriz.olho && matriz.disp === 1 && exportavel
  && abasCli.join() === 'documentos' && visaoCli.series.length === 1 && visaoCli.internosVisiveis === 0 && visaoCli.controles === 0 && r404 === 404
  && !errosInt.length && !errosCli.length;
console.log(ok ? 'DOC FRONT: OK' : 'DOC FRONT: FALHOU');
await navegador.close(); srv.close();
process.exit(ok ? 0 : 1);
