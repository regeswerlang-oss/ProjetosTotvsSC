// Stub do backend + Chromium para a aba Radar: abre o projeto da Dígitro, entra
// na aba, aprova (com edição), rejeita, aprova em lote, edita um item, registra
// evidência, cria item manual e passa pelas visões. Falha se houver erro de console.
//
//   node docs/testes/radar-front.mjs        (rodar na raiz do repo)
//
// O stub imita /api/radar/* em memória com o MESMO contrato do api/index.py.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const WEB = path.resolve('web');
const CT = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript',
             '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };
const CLI = '000348D0';
const P = (id, tipo, grupo, nome, prefixo, ordem, o, d) =>
  ({ id, customer: CLI, tipo, grupo, nome, prefixo, ordem, origem_id: o || null, destino_id: d || null, ativo: true });
const PROCS = [P(1, 'processo', 'principal', 'CRM', 'CRM', 10), P(2, 'processo', 'principal', 'iPaaS', 'IPA', 20),
  P(4, 'processo', 'principal', 'Contratos', 'CTR', 40), P(5, 'processo', 'principal', 'Comissões e Metas', 'COM', 50),
  P(6, 'processo', 'principal', 'CNAB', 'CNB', 60), P(10, 'processo', 'complementar', 'Gestão / Cronograma', 'GER', 100),
  P(14, 'ligacao', 'principal', 'CRM → Contratos', null, 32, 1, 4), P(17, 'ligacao', 'principal', 'iPaaS → Comissões e Metas', null, 43, 2, 5)];
const ev = n => [{ fonte: 'transcricao', fonte_ref: 'reuniao-' + n, titulo: 'Anotações do Gemini', ocorrido_em: '2026-10-19T12:00:00-03:00',
                   link: 'https://drive.google.com/x', trecho: 'trecho <b>com html</b>' }];
const prop = (id, payload) => ({ id, customer: CLI, item_id: null, acao: 'criar', payload, evidencias: ev(id),
  justificativa: 'Carga inicial', confianca: 0.7, situacao: 'pendente', created_at: '2026-10-27 13:43:32+00' });
const DB = {
  itens: [], evid: [],
  props: [prop(1, { tipo: 'definicao', titulo: 'NFs de comissão sem duplicidade?', bloqueia: 'Protótipo integrado', dono_lado: 'AMBOS', prioridade: 'alta', processo_id: 5, aberta_em: '2026-10-10' }),
          prop(2, { tipo: 'atividade', titulo: 'Campo participação no iPaaS', dono_lado: 'TOTVS', dono_nome: 'Felipe', prioridade: 'alta', processo_id: 2, ligacao_id: 17, prazo: '2026-11-09', aberta_em: '2026-10-19' }),
          prop(3, { tipo: 'definicao', titulo: 'Regra do tipo de planilha', dono_lado: 'AMBOS', prioridade: 'alta', processo_id: 1, ligacao_id: 14, aberta_em: '2026-10-16' }),
          prop(4, { tipo: 'atividade', titulo: 'Cadastros essenciais até 30/10', dono_lado: 'DIGITRO', prioridade: 'alta', processo_id: 10, aberta_em: '2026-10-14' })],
};
let seq = 100;
const HOJE = '2026-10-27';
const dias = (a, b) => Math.round((new Date(a) - new Date(b)) / 864e5);
const view = () => DB.itens.map(i => {
  const p = PROCS.find(x => x.id === i.processo_id), l = PROCS.find(x => x.id === i.ligacao_id);
  return { ...i, processo_nome: p.nome, processo_grupo: p.grupo, ligacao_nome: l?.nome || null,
    dias_sem_evidencia: dias(HOJE, (i.ultima_evidencia_em || i.aberta_em).slice(0, 10)),
    n_evidencias: DB.evid.filter(e => e.item_id === i.id).length,
    propostas_pendentes: DB.props.filter(x => x.item_id === i.id && x.situacao === 'pendente').length };
});
const codigo = pid => { const pf = PROCS.find(p => p.id === pid).prefixo;
  return pf + '-' + String(DB.itens.filter(i => i.codigo.startsWith(pf + '-')).length + 1).padStart(3, '0'); };
const addEv = (item_id, e) => { DB.evid.push({ id: ++seq, item_id, ...e });
  const it = DB.itens.find(i => i.id === item_id);
  if (!it.ultima_evidencia_em || e.ocorrido_em > it.ultima_evidencia_em) it.ultima_evidencia_em = e.ocorrido_em; };
const novoItem = o => { const it = { id: ++seq, customer: CLI, status: 'aberta', tipo: 'definicao', prioridade: 'media',
  task_ids: [], aberta_em: HOJE, ligacao_id: null, updated_at: '2026-10-27 15:00:00+00', ...o };
  it.codigo = codigo(it.processo_id); DB.itens.push(it); return it; };
const limpa = b => Object.fromEntries(Object.entries(b).filter(([, v]) => v !== '' && v != null)
  .map(([k, v]) => [k, k === 'task_ids' && typeof v === 'string' ? v.split(/[,;\s]+/).filter(Boolean) : v]));

function radar(metodo, partes, corpo) {
  const [, , , cli, a, id, b] = partes;           // /api/radar/<cli>/<a>/<id>/<b>
  if (cli !== CLI) return [403, { ok: false, error: 'Sem acesso a este cliente.' }];
  if (!a) return [200, { ok: true, processos: PROCS, itens: view(), propostas: DB.props.filter(p => p.situacao === 'pendente'),
                          execucao: { finalizada_em: '2026-10-27 13:43:32+00' }, usuario: 'reges.werlang@totvs.com.br' }];
  if (a === 'item' && !id) { if (!corpo.titulo) return [400, { ok: false, error: 'O título é obrigatório.' }];
    const it = novoItem(limpa(corpo)); return [200, { ok: true, id: it.id, codigo: it.codigo }]; }
  if (a === 'item' && b === 'evidencias') return [200, { ok: true, evidencias: DB.evid.filter(e => e.item_id === +id) }];
  if (a === 'item' && b === 'evidencia') { addEv(+id, { fonte: 'manual', fonte_ref: 'm' + seq, titulo: 'Registro manual', ocorrido_em: '2026-10-27T15:00:00-03:00', trecho: corpo.trecho, link: corpo.link || null }); return [200, { ok: true }]; }
  if (a === 'item' && !b) { const it = DB.itens.find(i => i.id === +id); Object.assign(it, limpa(corpo));
    if (it.status === 'decidida' && !it.decidida_em) it.decidida_em = HOJE; return [200, { ok: true }]; }
  const p = DB.props.find(x => x.id === +id);
  if (a === 'proposta' && b === 'rejeitar') { p.situacao = 'rejeitada'; p.motivo = corpo.motivo; return [200, { ok: true }]; }
  if (a === 'proposta' && b === 'aprovar') { if (corpo.payload) p.payload = { ...p.payload, ...limpa(corpo.payload) };
    const it = novoItem(p.payload); p.evidencias.forEach(e => addEv(it.id, e)); p.situacao = 'aplicada'; return [200, { ok: true, item_id: it.id }]; }
  return [404, { ok: false, error: 'rota radar desconhecida' }];
}

const ME = { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'comum', is_admin: true, interno: true, abas: null, abas_catalogo: [] };
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  let raw = '';
  req.on('data', c => raw += c);
  req.on('end', () => {
    const json = (code, o) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
    if (u.pathname === '/api/me') return json(200, ME);
    if (u.pathname === '/api/projetos') return json(200, { ok: true, projetos: [], sincronizado_em: HOJE });
    if (u.pathname.startsWith('/api/radar/')) { const [c, o] = radar(req.method, u.pathname.split('/'), raw ? JSON.parse(raw) : {}); return json(c, o); }
    if (u.pathname.startsWith('/api/')) return json(200, { ok: true });
    const f = path.join(WEB, u.pathname === '/' ? 'index.html' : u.pathname.slice(1));
    if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) {
      res.writeHead(200, { 'Content-Type': CT[path.extname(f)] || 'application/octet-stream' }); return res.end(fs.readFileSync(f));
    }
    res.writeHead(404).end('nao encontrado');
  });
});
const PORTA = 5198;
await new Promise(r => srv.listen(PORTA, r));

const pw = createRequire(import.meta.url)('playwright');
const navegador = await pw.chromium.launch();
const pag = await navegador.newPage({ viewport: { width: 1440, height: 1100 } });
const erros = [];
pag.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
pag.on('pageerror', e => erros.push('pageerror: ' + e.message));
pag.on('dialog', d => { erros.push('dialog: ' + d.message()); d.dismiss(); });
const TW = process.env.TW_JS || '/home/claude/w/tw.js';
await pag.route('**/cdn.tailwindcss.com*', r => fs.existsSync(TW)
  ? r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(TW, 'utf8') })
  : r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
await pag.route('**/fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));

await pag.goto(`http://127.0.0.1:${PORTA}/`, { waitUntil: 'networkidle' });
await pag.evaluate(cli => abrirDetalhe({ cli, cod: '000348D025', ver: '12', loja: 'D0',
  projeto: { nome_cliente_projeto: 'DIGITRO TECNOLOGIA LTDA', descricao_projeto: 'Servicos de Implantacao' } }), CLI);
await pag.waitForTimeout(400);
const abaVisivel = await pag.isVisible('[data-tab="radar"]');
await pag.click('[data-tab="radar"]');
await pag.waitForSelector('[data-radp]', { timeout: 5000 });
const inicio = await pag.evaluate(() => ({ visao: rad.view, pill: document.querySelector('#rad-pill').textContent,
  filtrosOcultos: document.querySelector('#rad-filtros').classList.contains('hidden') }));
await pag.screenshot({ path: '/home/claude/w/radar-propostas.png', fullPage: true });

await pag.selectOption('[data-radform="3"] [data-f="dono_lado"]', 'DIGITRO');      // corrige antes de aprovar
await pag.click('[data-radapr="3"]'); await pag.waitForTimeout(250);
await pag.fill('[data-radmot="4"]', 'duplicado'); await pag.click('[data-radrej="4"]'); await pag.waitForTimeout(250);
await pag.click('#rad-apr-todas'); await pag.waitForTimeout(500);
const aposAprov = { itens: DB.itens.map(i => `${i.codigo}:${i.dono_lado}`), situacoes: DB.props.map(p => p.situacao), motivo: DB.props[3].motivo };

await pag.click('[data-radv="processo"]'); await pag.waitForTimeout(200);
await pag.screenshot({ path: '/home/claude/w/radar-processo.png', fullPage: true });
await pag.click('[data-radi]'); await pag.waitForSelector('#rad-g-form');
await pag.selectOption('#rad-g-form [data-f="status"]', 'decidida');
await pag.fill('#rad-g-form [data-f="decisao"]', 'Decidido em reunião');
await pag.fill('#rad-g-form [data-f="task_ids"]', '00017713, 00012345');
await pag.click('#rad-g-salvar'); await pag.waitForTimeout(350);
await pag.fill('#rad-g-etxt', 'Confirmado por e-mail'); await pag.click('#rad-g-eadd'); await pag.waitForTimeout(350);
await pag.screenshot({ path: '/home/claude/w/radar-gaveta.png' });
const evNaGaveta = await pag.evaluate(() => document.querySelectorAll('#rad-g-ev > div').length);
await pag.keyboard.press('Escape');

await pag.click('[data-radv="ligacao"]'); await pag.waitForTimeout(200);
await pag.screenshot({ path: '/home/claude/w/radar-ligacao.png', fullPage: true });
await pag.click('[data-radv="processo"]');
await pag.click('#rad-novo'); await pag.waitForSelector('#rad-g-form');
await pag.fill('#rad-g-form [data-f="titulo"]', 'Item manual do teste');
await pag.selectOption('#rad-g-form [data-f="processo_id"]', '6');
await pag.click('#rad-g-criar'); await pag.waitForTimeout(350);
await pag.keyboard.press('Escape');
await pag.fill('#rad-q', 'manual'); await pag.waitForTimeout(150);
const busca = await pag.$$eval('#rad-conteudo [data-radi] .font-mono', e => e.map(x => x.textContent));
await pag.fill('#rad-q', ''); await pag.check('#rad-fech'); await pag.waitForTimeout(150);
const kpis = await pag.$$eval('#rad-kpis [data-radk]', e => e.map(x => x.innerText.replace(/\n/g, ' ')));
const exportavel = await pag.evaluate(() => !!relatorioDaAba());
const htmlCru = (await pag.content()).includes('<b>com html</b>');

const item1 = DB.itens.find(i => i.status === 'decidida');
const r = { abaVisivel, inicio, aposAprov, item1: item1 && { codigo: item1.codigo, decidida_em: item1.decidida_em, tasks: item1.task_ids, evid: DB.evid.filter(e => e.item_id === item1.id).length },
  evNaGaveta, busca, kpis, exportavel, htmlCru, erros };
console.log(JSON.stringify(r, null, 2));
const ok = abaVisivel && inicio.visao === 'propostas' && aposAprov.itens.length === 3 && aposAprov.itens.includes('CRM-001:DIGITRO')
  && aposAprov.situacoes.join() === 'aplicada,aplicada,aplicada,rejeitada' && item1 && item1.task_ids.length === 2
  && evNaGaveta === 2 && busca.join() === 'CNB-001' && exportavel && !htmlCru && !erros.length;
console.log(ok ? 'RADAR FRONT: OK' : 'RADAR FRONT: FALHOU');
await navegador.close(); srv.close();
process.exit(ok ? 0 : 1);
