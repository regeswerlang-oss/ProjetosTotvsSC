// Stub do backend + Chromium para a TRILHA de alterações, as PROPOSTAS e o filtro
// de situação da aba Estrutura (01/10/2026). Rodar da raiz do repo:
//   node docs/testes/testestrutura-trilha.mjs
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const WEB = path.resolve('web');
const CT = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript',
             '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };

const CFG = { customer: 'TFEHXQ00', leiaute: 'EEFF', tam_empresa: 2, tam_unidade: 0,
              tam_filial: 2, observacao: 'Definido na reunião de 29/09.',
              definido_por: 'reges.werlang@totvs.com.br' };
const GRUPOS = [{ id: 'g1', codigo: '01', nome: 'Grupo Olim', observacao: null }];
const EMPRESAS = [
  { id: 'e1', grupo_id: 'g1', codigo: '01', nome: 'OLIM AGRO CEREAIS LTDA', cnpj: '00.000.000/0001-00', uf: 'SC' },
  { id: 'e2', grupo_id: null, codigo: '02', nome: 'OLIM TRANSPORTES LTDA', cnpj: null, uf: 'SC' },
];
const FILIAIS = [
  { id: 'f1', empresa_id: 'e1', codigo: '0101', nome: 'Matriz Chapecó', cnpj: '00.000.000/0001-00', uf: 'SC', municipio: 'Chapecó', matriz: true },
  { id: 'f2', empresa_id: 'e1', codigo: '0102', nome: 'Filial Xanxerê', uf: 'SC', municipio: 'Xanxerê', matriz: false },
  { id: 'f3', empresa_id: 'e1', codigo: '013', nome: 'Filial com código curto (erro proposital)', matriz: false },
  { id: 'f4', empresa_id: 'e2', codigo: '0201', nome: 'Matriz Transportes', matriz: false },
];
// SE1 (ECC) mais compartilhada que SA1 (ECE) = o alerta 1:n da TDN.
const TABELAS = [
  { id: 't1', modulo: 'Financeiro', tabela: 'SA1', descricao: 'Clientes', tipo: 'cadastro', compart: 'ECE', sugestao: 'ECC', origem: 'catalogo',
    historico: [{ id: 'h1', compart_antes: 'ECC', compart_depois: 'ECE', origem: 'edicao', alterado_por: 'viviani@totvs.com.br', alterado_em: '2026-09-30T14:10:00-03:00' }],
    propostas: [] },
  { id: 't2', modulo: 'Financeiro', tabela: 'SE1', descricao: 'Contas a Receber', tipo: 'movimento', compart: 'ECC', sugestao: 'ECE', origem: 'catalogo',
    historico: [], propostas: [{ id: 'p1', compart: 'ECE', compart_na_hora: 'ECC', motivo: 'Título é por filial.', autor: 'reges.werlang@totvs.com.br', criado_em: '2026-10-01T09:00:00-03:00', status: 'aberta' }] },
  { id: 't3', modulo: 'Financeiro', tabela: 'SE2', descricao: 'Contas a Pagar', tipo: 'movimento', compart: null, sugestao: 'ECE', origem: 'catalogo' },
  { id: 't4', modulo: 'Financeiro', tabela: 'Z01', descricao: 'Tabela customizada do projeto', tipo: 'cadastro', compart: 'CCC', sugestao: null, origem: 'manual' },
  { id: 't5', modulo: 'Ponto Eletrônico', tabela: 'SP9', descricao: 'Eventos', tipo: 'cadastro', compart: 'EEE', sugestao: 'EEE', origem: 'catalogo' },
];
const ALERTAS = [
  { nivel: 'erro', onde: 'filial', chave: '013', texto: 'Código da filial com 3 caractere(s); o leiaute EEFF espera 4.' },
  { nivel: 'erro', onde: 'regra', chave: 'SE1 x SA1', tabelas: ['SA1', 'SE1'], texto: 'SE1 (ECC) está MAIS compartilhada que SA1 (ECE). Cliente (SA1) x título a receber (SE1): 1:n.', fonte: 'TDN' },
  { nivel: 'aviso', onde: 'tabela', chave: 'SE2', texto: 'Sem compartilhamento definido.' },
  { nivel: 'info', onde: 'tabela', chave: 'SA1', texto: 'Definida como ECE — a sugestão era ECC. Registre o porquê na observação.' },
];

const ROTAS = {
  '/api/me': { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'comum',
               is_admin: true, interno: true, abas: null, abas_catalogo: [] },
  '/api/projetos': { ok: true, projetos: [], sincronizado_em: '2026-09-29' },
  '/api/estrutura/TFEHXQ00': {
    ok: true, customer: 'TFEHXQ00', config: CFG,
    leiautes: [{ id: 'FF', label: 'FF · só filial', ajuda: 'Uma empresa só.' },
               { id: 'EEFF', label: 'EEFF · empresa + filial', ajuda: 'O código da filial começa pelo código da empresa (ex.: 01 + 01 = 0101).' },
               { id: 'EEUUFF', label: 'EEUUFF · empresa + unidade + filial', ajuda: 'Empresa + unidade + filial.' }],
    niveis: [0, 2], niveis_label: ['Empresa', 'Unidade de Negócio', 'Filial'],
    grupos: GRUPOS, empresas: EMPRESAS, filiais: FILIAIS, tabelas: TABELAS,
    catalogo: [{ modulo: 'Financeiro', n: 16 }, { modulo: 'Ponto Eletrônico', n: 23 }],
    alertas: ALERTAS, interno: true,
  },
};

const POSTS = [];
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  if (ROTAS[u.pathname]) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(ROTAS[u.pathname]));
  }
  if (u.pathname.startsWith('/api/')) {
    if (req.method === 'POST') {
      let corpo = '';
      req.on('data', c => (corpo += c));
      req.on('end', () => { POSTS.push({ rota: u.pathname, corpo: JSON.parse(corpo || '{}') });
        res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('{"ok":true}'); });
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ ok: true }));
  }
  const rel = u.pathname === '/' ? 'index.html' : u.pathname.slice(1);
  const f = path.join(WEB, rel);
  if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) {
    res.writeHead(200, { 'Content-Type': CT[path.extname(f)] || 'application/octet-stream' });
    return res.end(fs.readFileSync(f));
  }
  res.writeHead(404).end('nao encontrado');
});

const PORTA = 5199;
await new Promise(r => srv.listen(PORTA, r));

const { default: pw } = await import('/home/claude/.npm-global/lib/node_modules/playwright/index.js');
const navegador = await pw.chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--no-sandbox'],
});
const pag = await navegador.newPage({ viewport: { width: 1440, height: 1180 } });
const erros = [];
pag.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
pag.on('pageerror', e => erros.push('pageerror: ' + e.message));

// O CDN da Tailwind não é alcançável daqui — troca pelo pacote do npm.
await pag.route('**/cdn.tailwindcss.com*', async rota => {
  const js = fs.readFileSync('/home/claude/w/tw.js', 'utf8');
  await rota.fulfill({ status: 200, contentType: 'application/javascript',
                       body: 'window.tailwind=window.tailwind||{};' + js });
});
await pag.route('**/fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));

await pag.goto(`http://127.0.0.1:${PORTA}/`, { waitUntil: 'networkidle' });
await pag.evaluate(() => {
  abrirDetalhe({ cli: 'TFEHXQ00', cod: 'TFEHXQ0001', ver: '06', loja: '00',
                 projeto: { nome_cliente_projeto: 'OLIM AGRO CEREAIS LTDA',
                            descricao_projeto: 'Servico de Implantacao - Backoffice' } });
});
await pag.waitForTimeout(400);
await pag.click('[data-tab="estrutura"]');
await pag.waitForSelector('#est-conteudo table', { timeout: 5000 });
await pag.waitForTimeout(500);

const chips = async () => pag.evaluate(() =>
  Object.fromEntries([...document.querySelectorAll('[data-est-sit]')]
    .map(b => [b.dataset.estSit, +b.querySelector('span').textContent])));
const linhas = async () => pag.evaluate(() =>
  [...document.querySelectorAll('#est-conteudo tbody tr[data-est-linha]')]
    .map(t => t.querySelector('td').childNodes[0].textContent.trim()));
const falha = (c, m) => { if (!c) erros.push(m); };

const contagem = await chips();
falha(contagem.INDEF === 1 && contagem.CONFLITO === 2 && contagem.ALTERADA === 1 && contagem.DISCUSSAO === 1,
      'contagem das situações errada: ' + JSON.stringify(contagem));

await pag.click('[data-est-sit="CONFLITO"]'); await pag.waitForTimeout(120);
const conf = await linhas();
falha(conf.join() === 'SA1,SE1', 'filtro conflito: ' + conf);
await pag.click('[data-est-sit="INDEF"]'); await pag.waitForTimeout(120);
const indef = await linhas();
falha(indef.join() === 'SE2', 'filtro não definidas: ' + indef);
await pag.click('[data-est-sit="TODAS"]'); await pag.waitForTimeout(120);

// Hover no ✓ mostra quem alterou
await pag.hover('[data-est-alt="t1"]'); await pag.waitForTimeout(120);
const tip = await pag.evaluate(() => { const t = document.getElementById('est-tip');
  return t && !t.classList.contains('hidden') ? t.innerText : ''; });
falha(tip.includes('viviani') && tip.includes('ECC → ECE'), 'tooltip sem autor: ' + tip);
await pag.screenshot({ path: '/home/claude/w/trilha-hover.png' });
await pag.mouse.move(5, 5);

// Trocar o que outra pessoa decidiu pede confirmação; cancelar abre a discussão
let dialogo = '';
pag.once('dialog', d => { dialogo = d.message(); d.dismiss(); });
await pag.selectOption('[data-est-mode="t1"][data-pos="2"]', 'C');
await pag.waitForTimeout(250);
falha(dialogo.includes('viviani'), 'não avisou quem alterou: ' + dialogo);
falha(!POSTS.some(p => p.rota.endsWith('/tabela')), 'gravou mesmo cancelando');
const tituloModal = await pag.evaluate(() => document.querySelector('.fixed.inset-0 h3')?.textContent || '');
falha(tituloModal.includes('SA1'), 'cancelar não abriu a discussão');

// Registrar proposta pelo modal
await pag.selectOption('.fixed.inset-0 [data-prop-pos="2"]', 'C');
await pag.fill('#est-prop-motivo', 'Clientes compartilhados entre filiais.');
await pag.screenshot({ path: '/home/claude/w/trilha-modal.png' });
await pag.click('.fixed.inset-0 [data-ok]'); await pag.waitForTimeout(250);
const prop = POSTS.find(p => p.rota.endsWith('/proposta'));
falha(prop && prop.corpo.compart === 'ECC' && prop.corpo.tabela_id === 't1', 'POST da proposta: ' + JSON.stringify(prop));

// Aplicar proposta aberta da SE1
await pag.click('[data-est-disc="t2"]'); await pag.waitForTimeout(150);
pag.once('dialog', d => d.accept());
await pag.click('[data-prop-aplicar="p1"]'); await pag.waitForTimeout(250);
falha(POSTS.some(p => p.corpo.acao === 'aplicar' && p.corpo.id === 'p1'), 'aplicar não postou');

await pag.click('[data-est-sit="CONFLITO"]'); await pag.waitForTimeout(150);
await pag.screenshot({ path: '/home/claude/w/trilha-conflito.png', fullPage: true });

console.log(JSON.stringify({ contagem, conf, indef, tip, dialogo, posts: POSTS, erros }, null, 2));
await navegador.close();
srv.close();
process.exit(erros.length ? 1 : 0);
