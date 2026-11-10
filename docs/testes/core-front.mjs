// Stub do backend + Chromium para a aba Protótipo Core: abre o projeto da
// Dígitro, entra na aba, confere a fila da ZA3, abre a trilha de uma mensagem,
// expande cada estágio, filtra conceitos, abre o modal de ocorrência (grava no
// stub do Radar), troca de base e testa a busca. Falha se houver erro de console.
//
//   node docs/testes/core-front.mjs        (rodar na raiz do repo)
//
// O stub imita /api/core/* com o MESMO contrato do api/index.py.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const WEB = path.resolve('web');
const CT = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };
const CLI = '000348D0';
const ME = { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'comum', is_admin: true, interno: true, abas: null, abas_catalogo: [] };
const LEG = { ZA3_STG1: { R: 'Recebido', P: 'Processando', L: 'Liberado', E: 'Erro' },
              ZA3_STG2: { N: 'Não liberado', A: 'Aguardando', P: 'Processando', S: 'Sucesso', E: 'Erro' },
              ZA3_STIPA: { N: 'Não disponível', S: 'Sucesso', E: 'Erro' },
              ZA0_STATUS: { 1: 'Em Implantação' }, ZA0_TPPROD: { 1: 'Físico', 2: 'Virtual' }, CN9_SITUAC: { '05': 'Vigente' } };
const EST = [{ id: 'crm', rotulo: 'Proposta no CRM', sub: 'oportunidade · itens · ordens de venda' },
             { id: 'etapa1', rotulo: 'iPaaS → Etapa 1', sub: 'POST /api/v1/CRMIntegracao · ZA3' },
             { id: 'etapa2', rotulo: 'Etapa 2 · Sincronizar', sub: 'U_CRMPROJT' },
             { id: 'painel', rotulo: 'Painel de Projetos', sub: 'ZA0 · ZA1 · SB1 PRJ · CTD · NS' },
             { id: 'contrato', rotulo: 'Contratos', sub: 'CN9 · CNA · CNB' }];
const PROPOSTAS = [
  { msgid: 'msg-001', idcrm: 'opp-aaa', stg1: 'L', stg2: 'S', stipa: 'N', dtinc: '20261109', hrinc: '10:05', contrato: '0001/2026', recno: 1,
    proposta: 'PRP-0001', cliente: 'Cliente Teste', tipo_venda: '001', modalidade: '1', ordens: 2, projetos: 2, contrato_cn9: true, erro: '' },
  { msgid: 'msg-002', idcrm: 'opp-bbb', stg1: 'E', stg2: 'N', stipa: 'N', dtinc: '20261109', hrinc: '10:20', contrato: '', recno: 2,
    proposta: 'PRP-0002', cliente: 'Outro Cliente', tipo_venda: '', modalidade: '', ordens: null, projetos: 0, contrato_cn9: false, erro: 'JSON inválido: tipoVenda ausente' },
  { msgid: 'msg-003', idcrm: 'opp-ccc', stg1: 'L', stg2: 'A', stipa: 'N', dtinc: '20261109', hrinc: '10:31', contrato: '', recno: 3,
    proposta: 'PRP-0003', cliente: 'Terceiro', tipo_venda: '003', modalidade: '3', ordens: 1, projetos: 0, contrato_cn9: false, erro: '' },
];
const JSONFI = { oportunidade: { numeroProposta: 'PRP-0001', tipoVenda: '001', modalidade: '1', unidadeNegocio: 'NVC', cliente: { codigo: '000123', loja: '01', nome: 'Cliente Teste' } },
                 ordensVenda: [{ descricao: 'NGC Corporate', plataforma: '1', tipoProduto: '1', itens: [{ produto: { codigo: 'P001' }, quantidade: 2, valorUnitario: 100 }] },
                               { descricao: 'Nexus', plataforma: '2', tipoProduto: '2', itens: [{ produto: { codigo: 'L001' }, quantidade: 3, valorUnitario: 50 }] }] };
const TRILHA = {
  ok: true, ambiente: 'producao', lido_em: '2026-11-09T10:40:00-03:00', dicionario: 'sx3', memo_variante: 0, avisos: [], ms: 1234,
  za3: { ZA3_MSGID: 'msg-001', ZA3_IDCRM: 'opp-aaa', ZA3_STG1: 'L', ZA3_STG2: 'S', ZA3_STIPA: 'N', ZA3_CONTRA: '0001/2026', ZA3_DTINC: '20261109', ZA3_HRINC: '10:05',
         ZA3_DTFIM: '20261109', ZA3_HRFIM: '10:06', ZA3_PROJET: '["000010 2026","000011 2026"]', ZA3_JSONFI: JSON.stringify(JSONFI), RECNO: 1 },
  irmas: [{ ZA3_MSGID: 'msg-001', ZA3_STG1: 'L', ZA3_STG2: 'S', ZA3_STIPA: 'N', ZA3_DTINC: '20261109', ZA3_HRINC: '10:05', ZA3_CONTRA: '0001/2026' }],
  json: JSONFI,
  resumo: { numeroProposta: 'PRP-0001', opportunityId: 'opp-aaa', cliente: '000123', clienteLoja: '01', clienteNome: 'Cliente Teste', tipoVenda: '001', modalidade: '1',
            unidadeNegocio: 'NVC', tabelaPreco: '08', condicaoPagamento: 'C12', vendedor: '000045', memorialCalculo: 'desconto 10%', valorTotal: 350, ordensVenda: JSONFI.ordensVenda },
  ordens: [{ id: '', descricao: 'NGC Corporate', plataforma: '1', tipoProduto: '1', natureza: '1', instrucaoTecnica: 'instalar', itens: [{ codigo: 'P001', descricao: 'Produto 1', quantidade: 2, valorUnitario: 100, valorTotal: null }], valorTotal: 200 },
           { id: '', descricao: 'Nexus', plataforma: '2', tipoProduto: '2', natureza: '', itens: [{ codigo: 'L001', descricao: 'Licença', quantidade: 3, valorUnitario: 50, valorTotal: null }], valorTotal: 150 }],
  projetos: [{ _COD: '000010 2026', ZA0_CODIGO: '000010 2026', ZA0_NOME: 'NGC', ZA0_TPPROD: '1', ZA0_STATUS: '1', ZA0_CONTRA: '0001/2026', ZA0_PROPOS: 'PRP-0001', ZA0_IT: 'instalar', RECNO: 1 },
             { _COD: '000011 2026', ZA0_CODIGO: '000011 2026', ZA0_NOME: 'Nexus', ZA0_TPPROD: '2', ZA0_STATUS: '1', ZA0_CONTRA: '0001/2026', ZA0_NUMSER: 'V00000000012', RECNO: 2 }],
  itens: [{ _PRJ: '000010 2026', _PRODUTO: 'P001', ZA1_ITEM: '001', ZA1_DESCRI: 'Produto 1', ZA1_QUANT: '2', ZA1_CRM: 'S', ZA1_AUTO: '' },
          { _PRJ: '000010 2026', _PRODUTO: 'PRJ0000102026', ZA1_ITEM: '002', ZA1_DESCRI: 'NGC - Cliente', ZA1_QUANT: '1', ZA1_CRM: '', ZA1_AUTO: 'S' },
          { _PRJ: '000011 2026', _PRODUTO: 'L001', ZA1_ITEM: '001', ZA1_DESCRI: 'Licença', ZA1_QUANT: '3', ZA1_CRM: 'S', ZA1_AUTO: '' }],
  sb1: [{ B1_COD: 'PRJ0000102026', B1_DESC: 'NGC Corporate - Cliente: Cliente Teste', B1_TIPO: 'PA', B1_PRV1: '200' }],
  ctd: [{ CTD_ITEM: '0000102026', CTD_DESC01: 'NGC' }, { CTD_ITEM: '0000112026', CTD_DESC01: 'Nexus' }], ns: [],
  cn9: [{ CN9_NUMERO: '0001/2026', CN9_REVISA: '001', CN9_SITUAC: '05', CN9_TPCTO: '001', CN9_VIGE: '12', CN9_UNVIGE: 'M', CN9_ZMEMOR: 'desconto 10%', CN9_XOPORT: 'PRP-00' }],
  cna: [{ _PRJ: '000010 2026', CNA_NUMERO: '001', CNA_ZPLATA: '1', CNA_VLTOT: '200' }, { _PRJ: '000011 2026', CNA_NUMERO: '002', CNA_ZPLATA: '2', CNA_VLTOT: '150' }],
  cnb: [{ CNB_NUMERO: '001', CNB_ITEM: '001', CNB_PRODUT: 'PRJ0000102026', CNB_QUANT: '1', CNB_VLUNIT: '200', CNB_VLTOT: '200', CNB_ITEMCTA: '0000102026' },
        { CNB_NUMERO: '002', CNB_ITEM: '001', CNB_PRODUT: 'L001', CNB_QUANT: '3', CNB_VLUNIT: '50', CNB_VLTOT: '150', CNB_ITEMCTA: '0000112026' }],
  estagios: EST.map((e, i) => ({ ...e, nivel: 'ok', kpis: [['Teste', 'x']], resumo: ['linha de resumo'] })),
  conceitos: [{ cod: 'C23', titulo: 'Nº da proposta', regra: 'regra', nivel: 'alerta', esperado: 'PRP-0001', observado: 'CN9_XOPORT PRP-00', dica: 'truncado', estagio: 'contrato' },
              { cod: 'C19', titulo: 'Venda de físico · 000010 2026', regra: 'VENDA: PRJ na CNB', nivel: 'ok', esperado: '1 item PRJ', observado: '1 item PRJ', dica: '', estagio: 'contrato' },
              { cod: 'C07', titulo: 'Físico · 000010 2026', regra: 'PRJ no SB1', nivel: 'ok', esperado: '1', observado: '1', dica: '', estagio: 'painel' },
              { cod: 'C18', titulo: 'Itens com valor zero', regra: 'zero só no projeto', nivel: 'erro', esperado: 'fora da CNB', observado: '1 na CNB', dica: '', estagio: 'contrato' }],
  titulos: { ZA3: { ZA3_MSGID: 'Message ID', ZA3_STG1: 'Etapa 1' }, ZA0: { ZA0_NOME: 'Nome do Projeto' }, CN9: { CN9_NUMERO: 'Contrato' } },
  legendas: LEG,
};
const PROCS = [{ id: 1, customer: CLI, tipo: 'processo', grupo: 'principal', nome: 'CRM', prefixo: 'CRM', ordem: 10, ativo: true },
               { id: 2, customer: CLI, tipo: 'processo', grupo: 'principal', nome: 'Integração CRM × Painel', prefixo: 'INT', ordem: 20, ativo: true }];
const DB = { itens: [], chamadas: [] };

const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  let raw = '';
  req.on('data', c => raw += c);
  req.on('end', () => {
    const json = (c, o) => { res.writeHead(c, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
    if (u.pathname === '/api/me') return json(200, ME);
    if (u.pathname === '/api/projetos') return json(200, { ok: true, projetos: [], sincronizado_em: '2026-11-09' });
    if (u.pathname === `/api/core/${CLI}/propostas`) {
      DB.chamadas.push('propostas:' + u.searchParams.get('ambiente'));
      const amb = u.searchParams.get('ambiente');
      return json(200, { ok: true, ambiente: amb, lido_em: '2026-11-09T10:40:00-03:00', dicionario: 'sx3', memo_variante: 0, ms: 800,
                         propostas: amb === 'teste' ? PROPOSTAS.slice(0, 1) : PROPOSTAS, estagios: EST, legendas: LEG });
    }
    if (u.pathname === `/api/core/${CLI}/trilha`) {
      DB.chamadas.push('trilha:' + u.searchParams.get('msgid'));
      if (u.searchParams.get('msgid') === 'msg-002') return json(200, { ...TRILHA, za3: { ...TRILHA.za3, ZA3_MSGID: 'msg-002', ZA3_STG1: 'E', ZA3_STG2: 'N', ZA3_CONTRA: '', ZA3_ERRO: 'JSON inválido', ZA3_JSONFI: '' },
        json: null, resumo: {}, ordens: [], projetos: [], itens: [], sb1: [], ctd: [], cn9: [], cna: [], cnb: [],
        estagios: EST.map((e, i) => ({ ...e, nivel: i === 1 ? 'erro' : i === 0 ? 'alerta' : 'na', kpis: [], resumo: i === 1 ? ['JSON inválido'] : [] })),
        conceitos: [] });
      return json(200, TRILHA);
    }
    if (u.pathname === `/api/radar/${CLI}`) return json(200, { ok: true, processos: PROCS, itens: [], propostas: [] });
    if (u.pathname === `/api/radar/${CLI}/item` && req.method === 'POST') { const b = JSON.parse(raw || '{}'); DB.itens.push(b); return json(200, { ok: true, id: 9, codigo: 'INT-001' }); }
    if (u.pathname.startsWith('/api/')) return json(200, { ok: true });
    const rel = u.pathname === '/' ? 'index.html' : u.pathname.slice(1);
    const f = path.join(WEB, rel);
    if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) {
      res.writeHead(200, { 'Content-Type': CT[path.extname(f)] || 'application/octet-stream' });
      return res.end(fs.readFileSync(f));
    }
    res.writeHead(404).end('nao encontrado');
  });
});
const PORTA = 5207;
await new Promise(r => srv.listen(PORTA, r));

const PW = process.env.PW_PATH || '/home/claude/.npm-global/lib/node_modules/playwright/index.js';
const { default: pw } = await import(fs.existsSync(PW) ? PW : '/opt/npm-tools/node_modules/playwright/index.js');
const navegador = await pw.chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] } : {});
const pag = await navegador.newPage({ viewport: { width: 1440, height: 1100 } });
const erros = [];
pag.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
pag.on('pageerror', e => erros.push('pageerror: ' + e.message));
const dialogos = [];
pag.on('dialog', d => { dialogos.push(d.message()); d.dismiss(); });
const TW = process.env.TW_JS || '/home/claude/w/tw.js';
await pag.route('**/cdn.tailwindcss.com*', r => fs.existsSync(TW)
  ? r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(TW, 'utf8') })
  : r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
await pag.route('**/fonts.googleapis.com/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
await pag.route('**/rsms.me/**', r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));

await pag.goto(`http://127.0.0.1:${PORTA}/`, { waitUntil: 'networkidle' });
await pag.evaluate(cli => abrirDetalhe({ cli, cod: '000348D025', ver: '12', loja: 'D0',
  projeto: { nome_cliente_projeto: 'DIGITRO TECNOLOGIA LTDA', descricao_projeto: 'Servicos de Implantacao' } }), CLI);
await pag.waitForTimeout(400);
const abaVisivel = await pag.isVisible('[data-tab="core"]');
await pag.click('[data-tab="core"]');
await pag.waitForSelector('.core-item', { timeout: 5000 });
const fila = await pag.evaluate(() => ({
  itens: document.querySelectorAll('.core-item').length,
  kpis: [...document.querySelectorAll('.core-kpi')].map(k => k.innerText.replace(/\n/g, ' ')),
  vazio: !!document.querySelector('.core-vazio'),
  cliente: document.querySelector('#core-cliente-nome').textContent,
}));

// abre a trilha da 1ª mensagem
await pag.click('.core-item');
await pag.waitForSelector('.core-card', { timeout: 5000 });
const document_has_retorno = await pag.evaluate(() => !!document.querySelector('[data-core-est="retorno"]') || document.querySelectorAll('.core-dot').length / document.querySelectorAll('.core-item').length > 2);
const trilha = await pag.evaluate(() => ({
  cards: document.querySelectorAll('.core-card').length,
  badges: [...document.querySelectorAll('.core-card .core-badge')].map(b => b.textContent),
  cab: document.querySelector('.core-cab .text-lg').textContent,
  conceitos: document.querySelectorAll('.core-conc').length,
  detalheAberto: !!document.querySelector('.core-detalhe'),
}));
await pag.screenshot({ path: '/home/claude/w/core-trilha.png', fullPage: true }).catch(() => {});

// expande cada estágio
const detalhes = {};
for (const id of ['crm', 'etapa1', 'etapa2', 'painel', 'contrato']) {
  // o CRM já abre expandido na primeira carga (a proposta é o que se quer ver primeiro)
  const jaAberto = await pag.evaluate(i => document.querySelector(`.core-card.is-aberto[data-core-est="${i}"]`) != null, id);
  if (!jaAberto) await pag.click(`.core-card[data-core-est="${id}"]`);
  await pag.waitForTimeout(120);
  detalhes[id] = await pag.evaluate(() => {
    const d = document.querySelector('.core-detalhe');
    return d ? { campos: d.querySelectorAll('.core-campo').length, tabelas: d.querySelectorAll('table').length, ovs: d.querySelectorAll('details.core-ov').length, texto: d.innerText.length } : null;
  });
}
// recolhe pelo botão do detalhe
await pag.click('.core-detalhe [data-core-est]');
await pag.waitForTimeout(100);
const recolhido = await pag.evaluate(() => !document.querySelector('.core-detalhe'));

// conceitos: filtro e expansão
await pag.click('[data-core-fc="problemas"]'); await pag.waitForTimeout(100);
const soProblemas = await pag.evaluate(() => document.querySelectorAll('.core-conc').length);
await pag.click('.core-conc'); await pag.waitForTimeout(100);
const concAberto = await pag.evaluate(() => ({ mais: !!document.querySelector('.core-conc-mais'), botao: !!document.querySelector('[data-core-ocorr]') }));

// registrar ocorrência → modal → grava no stub do radar
await pag.click('[data-core-ocorr]');
await pag.waitForSelector('.fixed.inset-0 h3', { timeout: 4000 });
const modalInfo = await pag.evaluate(() => ({ titulo: document.querySelector('.fixed.inset-0 h3').textContent, campo: document.querySelector('#oc-titulo').value,
  procs: [...document.querySelectorAll('#oc-proc option')].map(o => o.textContent), procSel: document.querySelector('#oc-proc').value, prio: document.querySelector('#oc-prio').value }));
await pag.click('.fixed.inset-0 [data-ok]'); await pag.waitForTimeout(300);
const gravado = DB.itens[0];

// troca de base recarrega a fila (1 item na base de testes)
await pag.selectOption('#core-ambiente-sel', 'teste'); await pag.waitForSelector('.core-item'); await pag.waitForTimeout(200);
const emTeste = await pag.evaluate(() => ({ itens: document.querySelectorAll('.core-item').length, selo: document.querySelector('#core-conteudo .rounded-full').textContent, vazio: !!document.querySelector('.core-vazio') }));
await pag.selectOption('#core-ambiente-sel', 'producao'); await pag.waitForSelector('.core-item'); await pag.waitForTimeout(200);

// busca filtra sem perder o foco
await pag.fill('#core-busca', 'outro'); await pag.waitForTimeout(150);
const busca = await pag.evaluate(() => ({ itens: document.querySelectorAll('.core-item').length, foco: document.activeElement?.id }));
await pag.fill('#core-busca', '');
await pag.click('#core-sofalhas'); await pag.waitForTimeout(150);
const soFalhas = await pag.evaluate(() => document.querySelectorAll('.core-item').length);
await pag.click('#core-sofalhas');

// mensagem com erro na Etapa 1 (o filtro de conceitos é pegajoso: volta a 'todos' antes)
await pag.click('.core-item[data-core-msg="msg-002"]'); await pag.waitForTimeout(300);
await pag.click('[data-core-fc="todos"]'); await pag.waitForTimeout(100);
const erroE1 = await pag.evaluate(() => ({ badges: [...document.querySelectorAll('.core-card .core-badge')].map(b => b.textContent), conceitos: document.querySelectorAll('.core-conc').length }));

// exportar HTML da aba
const rel = await pag.evaluate(() => { const r = relatorioDaAba(); return r ? { titulo: r.titulo, base: r.base, tam: r.html.length } : null; });
// atualizar agora
await pag.click('#core-reload'); await pag.waitForTimeout(300);

console.log(JSON.stringify({ abaVisivel, fila, trilha, detalhes, recolhido, soProblemas, concAberto, modalInfo, gravado: gravado && { titulo: gravado.titulo, processo_id: gravado.processo_id, prioridade: gravado.prioridade, status: gravado.status, ctx: gravado.contexto.slice(0, 60) },
  emTeste, busca, soFalhas, erroE1, rel, chamadas: DB.chamadas, dialogos, erros }, null, 2));
await navegador.close();
srv.close();

let falhas = 0;
const ok = (n, c) => { if (!c) { falhas++; console.log('FALHOU:', n); } };
ok('aba visível', abaVisivel);
ok('3 mensagens na fila e trilha vazia', fila.itens === 3 && fila.vazio);
ok('KPIs', fila.kpis.length === 4 && fila.kpis[0].startsWith('3'));
ok('5 cards de estágio (sem retorno)', trilha.cards === 5 && !document_has_retorno);
ok('cabeçalho com a proposta', trilha.cab === 'PRP-0001');
ok('4 conceitos', trilha.conceitos === 4);
ok('crm abre expandido com as OVs', trilha.detalheAberto && detalhes.crm?.ovs === 2 && detalhes.crm.tabelas >= 2);
ok('detalhe etapa1 com campos', detalhes.etapa1?.campos > 3);
ok('detalhe painel com 2 projetos', detalhes.painel?.ovs === 2 && detalhes.painel.tabelas >= 4);
ok('detalhe contrato com CNA/CNB', detalhes.contrato?.tabelas === 2 && detalhes.contrato.campos > 3);
ok('sem card de retorno', !('retorno' in detalhes));
ok('recolhe', recolhido);
ok('filtro divergências = 2', soProblemas === 2);
ok('conceito expande com botão', concAberto.mais && concAberto.botao);
ok('modal com processo sugerido (integração)', modalInfo.procSel === '2' && modalInfo.campo.startsWith('[Protótipo Core]'));
ok('gravou no radar', gravado && gravado.status === 'aberta' && gravado.processo_id === 2 && gravado.contexto.includes('Esperado'));
ok('base de testes recarrega', emTeste.itens === 1 && /TESTES/i.test(emTeste.selo) && emTeste.vazio);
ok('busca filtra e mantém foco', busca.itens === 1 && busca.foco === 'core-busca');
ok('só problemas = 2', soFalhas === 2);
ok('erro etapa1 no card', erroE1.badges[1] === 'Divergente' && erroE1.conceitos === 0);
ok('relatório exporta com base', rel && rel.base === 'producao' && rel.tam > 1000);
ok('sem erro de console', erros.length === 0);
ok('alert da ocorrência', dialogos.some(d => /INT-001/.test(d)));
console.log(falhas ? `${falhas} falha(s)` : 'tudo ok');
process.exit(falhas ? 1 : 0);
