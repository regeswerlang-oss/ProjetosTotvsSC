// Stub do backend + Chromium: abre o projeto, entra na aba Estrutura e confere
// que a tela monta sem erro de console. É o teste que a aba Protótipo já usava.
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
  { id: 't1', modulo: 'Financeiro', tabela: 'SA1', descricao: 'Clientes', tipo: 'cadastro', compart: 'ECE', sugestao: 'ECC', origem: 'catalogo' },
  { id: 't2', modulo: 'Financeiro', tabela: 'SE1', descricao: 'Contas a Receber', tipo: 'movimento', compart: 'ECC', sugestao: 'ECE', origem: 'catalogo' },
  { id: 't3', modulo: 'Financeiro', tabela: 'SE2', descricao: 'Contas a Pagar', tipo: 'movimento', compart: null, sugestao: 'ECE', origem: 'catalogo' },
  { id: 't4', modulo: 'Financeiro', tabela: 'Z01', descricao: 'Tabela customizada do projeto', tipo: 'cadastro', compart: 'CCC', sugestao: null, origem: 'manual' },
  { id: 't5', modulo: 'Ponto Eletrônico', tabela: 'SP9', descricao: 'Eventos', tipo: 'cadastro', compart: 'EEE', sugestao: 'EEE', origem: 'catalogo' },
];
const ALERTAS = [
  { nivel: 'erro', onde: 'filial', chave: '013', texto: 'Código da filial com 3 caractere(s); o leiaute EEFF espera 4.' },
  { nivel: 'erro', onde: 'regra', chave: 'SE1 x SA1', texto: 'SE1 (ECC) está MAIS compartilhada que SA1 (ECE). Cliente (SA1) x título a receber (SE1): 1:n.', fonte: 'TDN' },
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

const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  if (ROTAS[u.pathname]) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(ROTAS[u.pathname]));
  }
  if (u.pathname.startsWith('/api/')) {
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

const visto = await pag.evaluate(() => ({
  selo: document.querySelector('#est-leiaute-selo')?.textContent,
  cliente: document.querySelector('#est-cliente-nome')?.textContent,
  kpis: [...document.querySelectorAll('#est-conteudo .rounded-lg.px-4.py-3')].map(e => e.innerText.replace('\n', ' = ')),
  alertas: document.querySelectorAll('#est-conteudo details div.flex').length,
  filiais: document.querySelectorAll('#est-conteudo tbody tr').length,
  modulos: [...document.querySelectorAll('#est-modulo option')].map(o => o.textContent.trim()),
  selects: document.querySelectorAll('[data-est-mode]').length,
  desabilitados: document.querySelectorAll('[data-est-mode][disabled]').length,
  railVisivel: !document.querySelector('[data-rail="est"]').classList.contains('hidden'),
  botoesRail: [...document.querySelectorAll('[data-rail="est"] button')].map(b => b.id),
}));

// Filtro de busca: esconde linha, não redesenha (o cursor tem que ficar onde está).
await pag.fill('#est-busca', 'receber');
await pag.waitForTimeout(150);
const aposFiltro = await pag.evaluate(() =>
  [...document.querySelectorAll('#est-conteudo tbody tr[data-est-linha]')]
    .filter(t => !t.classList.contains('hidden')).length);

await pag.fill('#est-busca', '');
await pag.screenshot({ path: '/home/claude/w/estrutura.png', fullPage: true });

// Modais: abrem e fecham sem erro?
for (const b of ['est-leiaute', 'est-empresa-nova', 'est-filial-nova', 'est-semear', 'est-tabela-nova']) {
  await pag.click('#' + b);
  await pag.waitForTimeout(120);
  const titulo = await pag.evaluate(() => document.querySelector('.fixed.inset-0 h3')?.textContent?.trim());
  if (!titulo) erros.push(`modal ${b} não abriu`);
  await pag.evaluate(() => document.querySelector('.fixed.inset-0 [data-fechar]')?.click());
  await pag.waitForTimeout(80);
}

console.log(JSON.stringify({ visto, aposFiltro, erros }, null, 2));
await navegador.close();
srv.close();
process.exit(erros.length ? 1 : 0);
