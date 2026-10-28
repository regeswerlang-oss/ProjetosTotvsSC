// Stub do backend + Chromium para Radar → Estratégico/Diagnóstico e a aba
// Pendências (visão interna e visão do cliente). Falha com erro de console.
//
//   node docs/testes/diag-front.mjs        (rodar na raiz do repo)
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const WEB = path.resolve('web');
const CT = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };
const CLI = 'CLI001';
const PROCS = [{ id: 1, tipo: 'processo', grupo: 'principal', nome: 'Contratos', prefixo: 'CTR', ordem: 40 },
               { id: 2, tipo: 'processo', grupo: 'complementar', nome: 'Contabilidade', prefixo: 'CTB', ordem: 150 }];
const ITENS = [
  { id: 11, codigo: 'CTR-001', tipo: 'definicao', processo_id: 1, processo_prefixo: 'CTR', processo_nome: 'Contratos', titulo: 'Arredondamento <b>contratos</b>', dono_lado: 'AMBOS', status: 'aberta', prioridade: 'alta', bloqueia: 'Protótipo', prazo: '2026-11-09', task_ids: [], dias_sem_evidencia: 12, n_evidencias: 1, aberta_em: '2026-10-16', visivel_cliente: true },
  { id: 12, codigo: 'CTB-001', tipo: 'atividade', processo_id: 2, processo_prefixo: 'CTB', processo_nome: 'Contabilidade', titulo: 'LPs de comissão', dono_lado: 'TOTVS', status: 'aberta', prioridade: 'media', task_ids: [], dias_sem_evidencia: 1, n_evidencias: 0, aberta_em: '2026-10-27' }];
const R = (amb, st, v, t, extra = {}) => ({ [amb]: { status: st, valor: v, total: t, coletado_em: '2026-10-28 20:00:00+00', ...extra } });
const CHECKS = [
  { check_id: 'CTR-F01', processo_prefixo: 'CTR', camada: 'fluxo', titulo: 'Medições sem pedido', pergunta: 'Parou no meio?', tipo: 'sql', impeditivo: true, marco: 'prototipo', responsavel_lado: 'TOTVS', ambientes: ['teste', 'producao'], principal: 'teste',
    resultados: R('teste', 'vermelho', 3, 10, { amostra: '000123', erro: null }), status: 'vermelho', sql: 'SELECT 1 AS VALOR FROM DUAL', regra: { modo: 'zero' }, radar_codigos: ['CTR-001'], mit006_ids: ['36'], visivel_cliente: true },
  { check_id: 'CTB-K02', processo_prefixo: 'CTB', camada: 'contabilizacao', titulo: 'LPs ativos', tipo: 'sql', impeditivo: true, marco: 'prototipo', responsavel_lado: 'TOTVS', ambientes: ['teste', 'producao'], principal: 'teste',
    resultados: R('teste', 'amarelo', 15, 23), status: 'amarelo', sql: 'SELECT 1', regra: {}, radar_codigos: [], mit006_ids: [], visivel_cliente: false },
  { check_id: 'CTB-D01', processo_prefixo: 'CTB', camada: 'contabilizacao', titulo: 'Transitórias do legado', tipo: 'manual', impeditivo: true, marco: 'prototipo', responsavel_lado: 'AMBOS', ambientes: ['producao'], principal: 'producao',
    resultados: { producao: { status: 'cinza' } }, status: 'cinza', radar_codigos: [], mit006_ids: [], visivel_cliente: false, nota: null },
];
const MIT = [{ mit_id: '36', modulo: 'Contratos', pendencia: 'Importações Go Live - Contratos vigentes\n600 contratos', historico: '22/10 revisar', go_nogo: 'NoGo', criticidade: '2 Alta', atribuicao: 'Digitro', status: 'Pendente', processo_prefixo: 'CTR', tasks: ['00013510'], sincronizado_em: '2026-10-28 21:00:00+00' },
             { mit_id: '78', modulo: 'Contabilidade', pendencia: 'Validar contabilizações', go_nogo: 'NoGo', criticidade: '3 Média', atribuicao: 'TOTVS', status: 'Em andamento', processo_prefixo: 'CTB', tasks: [] },
             { mit_id: '35', modulo: 'Cadastros', pendencia: 'Importações OP', go_nogo: 'Go', atribuicao: 'Digitro', status: 'Concluído', tasks: [] }];
const MARCOS = [{ marco: 'prototipo', nome: 'Protótipo integrado', data: '2026-11-09' }, { marco: 'virada', nome: 'Virada', data: null }];
const salvos = [], coletas = [];
let ME = { ok: true, email: 'reges@totvs', nome: 'Reges', perfil: 'comum', is_admin: true, interno: true, abas: null, abas_catalogo: [] };

const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'); let raw = '';
  req.on('data', c => raw += c);
  req.on('end', () => {
    const json = (code, o) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
    const p = u.pathname;
    if (p === '/api/me') return json(200, ME);
    if (p === '/api/projetos') return json(200, { ok: true, projetos: [] });
    if (p === `/api/radar/${CLI}`) return json(200, { ok: true, processos: PROCS, itens: ITENS, propostas: [], execucao: null });
    if (p === `/api/diag/${CLI}`) return json(200, { ok: true, processos: PROCS, marcos: MARCOS, checks: CHECKS, execucoes: [{ ambiente: 'teste', ok: 2, falhas: 0, finalizada_em: '2026-10-28 20:00:00+00' }],
      legado: [{ familia: 'APB', nome: 'Contas a Pagar', partidas: 10185, lancamentos: 288, debitos: 160774278, processo_prefixo: 'FIN', protheus: 'LP 510', decisao: 'Transitória?', top_contas: [['21020101', 'FORNECEDORES', 1361]], fonte: 'ECD 2025' }],
      mit006: MIT, tickets: [{ id: '00012228', titulo: 'Etiquetas', status_tasks: 'Em Andamento (Cliente)', aging_dias: 105 }], admin: true });
    if (p.startsWith(`/api/diag/${CLI}/coletar`)) { coletas.push(u.searchParams.get('ambiente')); return json(200, { ok: true, verificacoes: 2, falhas: 0 }); }
    if (p.startsWith(`/api/diag/${CLI}/check/`)) { salvos.push({ id: decodeURIComponent(p.split('/').pop()), ...JSON.parse(raw || '{}') }); return json(200, { ok: true }); }
    if (p === `/api/pendencias/${CLI}`) return json(200, { ok: true, marcos: MARCOS, processos: PROCS, mit006: MIT,
      itens: ITENS.filter(i => i.visivel_cliente).map(i => ({ codigo: i.codigo, tipo: i.tipo, titulo: i.titulo, processo_nome: i.processo_nome, dono_lado: i.dono_lado, status: i.status, prioridade: i.prioridade, bloqueia: i.bloqueia, prazo: i.prazo, retorno_cliente: 'Enviar regra até 05/11', task_ids: [] })),
      checks: CHECKS.filter(c => c.visivel_cliente).map(({ sql, regra, nota, ...c }) => c) });
    if (p.startsWith('/api/')) return json(200, { ok: true });
    const f = path.join(WEB, p === '/' ? 'index.html' : p.slice(1));
    if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) { res.writeHead(200, { 'Content-Type': CT[path.extname(f)] || 'application/octet-stream' }); return res.end(fs.readFileSync(f)); }
    res.writeHead(404).end('nao encontrado');
  });
});
const PORTA = 5199;
await new Promise(r => srv.listen(PORTA, r));
const pw = createRequire(import.meta.url)('playwright');
const nav = await pw.chromium.launch();
const erros = [];
async function pagina() {
  const pag = await nav.newPage({ viewport: { width: 1440, height: 1100 } });
  pag.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
  pag.on('pageerror', e => erros.push('pageerror: ' + e.message));
  pag.on('dialog', d => { erros.push('dialog: ' + d.message()); d.dismiss(); });
  const TW = process.env.TW_JS || '/home/claude/w/tw.js';
  await pag.route('**/cdn.tailwindcss.com*', r => r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.existsSync(TW) ? fs.readFileSync(TW, 'utf8') : '' }));
  await pag.route('**/fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
  await pag.goto(`http://127.0.0.1:${PORTA}/`, { waitUntil: 'networkidle' });
  await pag.evaluate(cli => abrirDetalhe({ cli, cod: 'CLI00125', ver: '1', loja: '01', projeto: { nome_cliente_projeto: 'CLIENTE TESTE', descricao_projeto: 'Implantação' } }), CLI);
  await pag.waitForTimeout(400);
  return pag;
}

// ── Interno: Radar abre no Estratégico ──
let pag = await pagina();
await pag.click('[data-tab="radar"]');
await pag.waitForSelector('[data-dgcopia]', { timeout: 5000 });
const est = await pag.evaluate(() => ({ visao: rad.view, kpis: [...document.querySelectorAll('[data-dgk]')].map(b => b.innerText.replace(/\n/g, ' ')),
  cliente: document.querySelectorAll('[data-dgcopia="cliente"]')[0].closest('div.bg-white').querySelectorAll('.border-t').length,
  marcos: document.querySelector('#rad-conteudo').innerText.includes('Protótipo integrado') }));
await pag.screenshot({ path: '/home/claude/w/diag-estrategico.png', fullPage: true });
await pag.click('[data-radv="diagnostico"]');
await pag.waitForSelector('[data-dgcel]');
const celulas = await pag.$$eval('[data-dgcel]', e => e.map(x => x.dataset.dgcel + ':' + x.innerText.split('\n')[0]));
await pag.click('[data-dgcel="CTB|contabilizacao"]'); await pag.waitForTimeout(150);
const det = await pag.$$eval('[data-dgchk]', e => e.map(x => x.dataset.dgchk));
await pag.click('[data-dgchk="CTB-D01"] summary');
await pag.selectOption('[data-dgchk="CTB-D01"] [data-dgst]', 'vermelho');
await pag.fill('[data-dgchk="CTB-D01"] [data-dgnota]', 'sem decisão');
await pag.click('[data-dgchk="CTB-D01"] [data-dgsalva]'); await pag.waitForTimeout(300);
await pag.click('[data-dgcol="teste"]'); await pag.waitForTimeout(300);
await pag.selectOption('#dg-amb', 'pior'); await pag.waitForTimeout(150);
await pag.screenshot({ path: '/home/claude/w/diag-matriz.png', fullPage: true });
const legado = await pag.evaluate(() => document.querySelector('#rad-conteudo').innerText.includes('Contas a Pagar'));
await pag.click('[data-tab="pendencias"]'); await pag.waitForSelector('#pen-kpis [data-penk]');
const penInt = await pag.evaluate(() => ({ nota: document.querySelector('#pen-conteudo').innerText.includes('visão do cliente'), kpis: [...document.querySelectorAll('#pen-kpis button')].map(b => b.innerText.replace(/\n/g, ' ')) }));
await pag.close();

// ── Cliente: só Pendências liberada ──
ME = { ok: true, email: 'aline@cliente', nome: 'Aline', perfil: 'cliente', is_admin: false, interno: false, abas: { [CLI]: ['pendencias'] }, abas_catalogo: [] };
pag = await pagina();
await pag.waitForTimeout(300);
const visiveis = await pag.$$eval('.tab-btn', e => e.filter(b => !b.classList.contains('hidden') && b.offsetParent).map(b => b.dataset.tab));
await pag.evaluate(() => setTab('pendencias')); await pag.waitForSelector('#pen-kpis [data-penk]');
const lista = await pag.$$eval('#pen-conteudo .font-mono', e => e.map(x => x.textContent));
const retorno = await pag.evaluate(() => document.querySelector('#pen-conteudo').innerText.includes('Enviar regra'));
await pag.click('[data-penv="totvs"]'); const totvs = await pag.$$eval('#pen-conteudo .font-mono', e => e.map(x => x.textContent));
await pag.click('[data-penv="prontidao"]'); await pag.waitForTimeout(150);
const pront = await pag.evaluate(() => document.querySelector('#pen-conteudo').innerText);
await pag.screenshot({ path: '/home/claude/w/pendencias-cliente.png', fullPage: true });
const htmlCru = (await pag.content()).includes('<b>contratos</b>');
await pag.close();

const r = { est, celulas, det, salvos, coletas, legado, penInt, visiveis, lista, retorno, totvs, prontidao: pront.slice(0, 200), htmlCru, erros };
console.log(JSON.stringify(r, null, 2));
const ok = est.visao === 'estrategico' && est.marcos && est.cliente >= 3 && celulas.includes('CTR|fluxo:Crítico') && det.length === 2
  && salvos[0]?.id === 'CTB-D01' && salvos[0].status_manual === 'vermelho' && coletas.join() === 'teste' && legado
  && penInt.nota && visiveis.join() === 'pendencias' && [...lista].sort().join() === '#36,CTR-001' && retorno && totvs.join() === '#78'
  && pront.includes('Contratos') && !pront.includes('LPs ativos') && !htmlCru && !erros.length;
console.log(ok ? 'DIAG FRONT: OK' : 'DIAG FRONT: FALHOU');
await nav.close(); srv.close();
process.exit(ok ? 0 : 1);
