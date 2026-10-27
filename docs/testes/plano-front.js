// Teste da aba PLANO DE TRABALHO (front).
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8732 --bind 127.0.0.1 &
//   node docs/testes/plano-front.js
//
// Serve por HTTP (o fetch recusa file://). Todas as rotas /api/* são
// interceptadas — dados SINTÉTICOS (o repo é público). O Playwright casa na
// ordem INVERSA do registro: a genérica entra primeiro, as específicas depois.
const { chromium } = require('playwright');

const BASE = process.env.PLANO_URL || 'http://127.0.0.1:8732/index.html';
const HOJE = '2026-10-27';
const CLI = 'CLIX0000', PROJ = 'CLIX000001';

const PROJETO = {
  codigo_projeto: PROJ, codigo_cliente_projeto: CLI, nome_cliente_projeto: 'CLIENTE X COMERCIO',
  descricao_projeto: 'SERVICO DE IMPLANTACAO', nome_coordenador_projeto: 'CP TESTE',
  status_projeto: 'Em Execução', tipo_projeto: 'Implantação', versao_projeto: '01', loja: '00',
};

let seq = 0;
const A = (o) => Object.assign({
  id: `00000000-0000-0000-0000-${String(++seq).padStart(12, '0')}`, tipo: 'atividade',
  modulo: 'Financeiro', ordem: seq, sequencia: seq, etapa: 'Parametrização', tipo_agenda: 'Individual',
  atividade: 'Atividade ' + seq, data_de: '2026-11-03', data_ate: '2026-11-04', horas: 8,
  responsavel_lado: 'totvs', responsavel_nome: 'Ana', responsavel_email: 'ana.lima@totvs.com.br',
  consultor_nome: null, consultor_email: null, produto: null, status: 'agendado',
  observacoes: null, motivo_restricao: null, qtd_reagendamentos: 0, inconsistencia: null,
  atrasado: false, meu: false, editavel: true,
}, o);
const C = (o) => A(Object.assign({
  tipo: 'cadastro', atividade: null, etapa: null, tipo_agenda: null, horas: null, sequencia: null,
  rotina: 'MATA070', entidade: 'Bancos', status: 'nao_iniciado', responsavel_lado: 'cliente',
  responsavel_nome: null, responsavel_email: null, consultor_nome: 'Ana Lima',
  consultor_email: 'ana.lima@totvs.com.br', data_de: '2026-10-22', data_ate: '2026-10-29',
}, o));

function plano(perm = 'tudo', papel = 'cp_totvs', eu = 'vivi@totvs.com.br') {
  seq = 0;
  const itens = [
    A({ atividade: 'Re-parametrização da base', data_de: '2026-10-17', data_ate: '2026-10-23', status: 'finalizado' }),
    A({ atividade: 'Treinamento de processos', etapa: 'Treinamento', status: 'finalizado_restricoes',
        data_de: '2026-10-20', data_ate: '2026-10-21', produto: 'MIT037', motivo_restricao: 'Movimento bancário pendente' }),
    A({ atividade: 'Entrega dos cadastros', responsavel_lado: 'cliente', responsavel_nome: 'Lucas',
        responsavel_email: 'lucas@clientex.com.br', data_de: '2026-10-22', data_ate: '2026-11-13' }),
    A({ atividade: 'Reunião vencida', etapa: 'Refinamento', data_de: '2026-10-22', data_ate: '2026-10-22',
        atrasado: true, responsavel_nome: 'Bruno', responsavel_email: 'bruno.souza@totvs.com.br' }),
    A({ modulo: 'Faturamento', atividade: 'Treinamento faturamento', etapa: 'Treinamento', status: 'finalizado',
        data_de: '2026-11-25', data_ate: '2026-11-26', inconsistencia: 'Marcada como finalizada, mas começa em 25/11/2026.' }),
    A({ modulo: 'Faturamento', atividade: 'Primeiro protótipo', etapa: 'Protótipo Integrado', horas: 13.5,
        data_de: '2026-12-02', data_ate: '2026-12-04', responsavel_nome: 'Ana Lima' }),
    C({}),
    C({ modulo: 'Faturamento', rotina: 'MATA030', entidade: 'Clientes', data_ate: '2026-11-20',
        consultor_nome: 'Bruno Souza', consultor_email: 'bruno.souza@totvs.com.br' }),
  ];
  const meu = (i) => [i.responsavel_email, i.consultor_email].includes(eu);
  itens.forEach(i => {
    i.meu = meu(i);
    i.editavel = perm === 'tudo' || (perm === 'proprio' && i.meu);
  });
  return {
    ok: true, hoje: HOJE, itens, eu, papel, permissao: perm,
    marcos: { prototipo: '2026-11-27', go_live: '2027-01-04' },
    candidatos: [
      { email: 'ana.lima@totvs.com.br', nome: 'Ana Lima', papel: 'consultor' },
      { email: 'bruno.souza@totvs.com.br', nome: 'Bruno Souza', papel: 'consultor' },
      { email: 'lucas@clientex.com.br', nome: 'Lucas Cliente', papel: 'cp_cliente' },
    ],
    ultima_importacao: null, marcos_ids: ['base_liberada', 'treinamentos', 'prototipo', 'go_live'],
    status: {
      atividade: ['agendado', 'em_andamento', 'finalizado', 'finalizado_restricoes', 'cancelado'],
      cadastro: ['nao_iniciado', 'em_cadastro', 'entregue', 'validado', 'nao_aplicavel'],
    },
  };
}

let OK = 0;
const ok = (c, m) => { if (!c) throw new Error('FALHOU: ' + m); OK++; };

async function abre(b, { perm, papel, eu, modo = 'interno', abas = null }) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  const erros = [], posts = [];
  p.on('pageerror', e => erros.push(e.message));
  p.on('dialog', d => d.accept());
  const dados = plano(perm, papel, eu);
  await p.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await p.route('**/api/me', r => r.fulfill({ json: {
    ok: true, email: eu, nome: eu, is_admin: false, view_as: null, efetivo: eu,
    perfil: modo === 'cliente' ? 'cliente' : 'comum', interno: modo !== 'cliente', modo,
    abas_catalogo: [], abas: abas ? { [CLI]: abas } : null } }));
  await p.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, projetos: [PROJETO], sincronizado_em: HOJE } }));
  await p.route('**/api/projeto/**/mapa', r => r.fulfill({ json: { IB7_VERSAO: '01' } }));
  await p.route('**/api/projeto/**/cronograma', r => r.fulfill({ status: 503, json: { ok: false, error: 'offline' } }));
  await p.route(`**/api/plano/${CLI}/${PROJ}`, r => r.fulfill({ json: dados }));
  await p.route('**/api/plano/item/*/hist', r => r.fulfill({ json: { ok: true, hist: [
    { campo: 'status', de: 'agendado', para: 'finalizado', por: 'vivi@totvs.com.br', por_nome: 'Viviane CP', origem: 'tela', em: '2026-10-27 10:00:00+00' },
    { campo: 'criado', de: null, para: 'plano.xlsx', por: 'vivi@totvs.com.br', por_nome: 'Viviane CP', origem: 'importacao', em: '2026-10-26 10:00:00+00' },
  ] } }));
  await p.route(/\/api\/plano\/item\/[0-9a-f-]{36}$/, async r => {
    const body = JSON.parse(r.request().postData() || '{}');
    posts.push(body);
    const id = r.request().url().split('/').pop();
    const it = dados.itens.find(i => i.id === id);
    await r.fulfill({ json: { ok: true, item: { ...it, ...body }, reagendou: false } });
  });
  await p.goto(BASE);
  await p.waitForSelector('[data-projeto]');
  await p.click('[data-projeto]');
  await p.waitForSelector('.tab-btn[data-tab="plano"]:not(.hidden)');
  return { p, ctx, erros, posts, dados };
}

(async () => {
  const b = await chromium.launch();

  // ── CP TOTVS ────────────────────────────────────────────────────────────
  let { p, erros, posts } = await abre(b, { perm: 'tudo', papel: 'cp_totvs', eu: 'vivi@totvs.com.br' });
  await p.click('.tab-btn[data-tab="plano"]');
  await p.waitForSelector('#pl-conteudo details.pl-mod');
  ok(await p.$eval('[data-plsub="grade"]', e => e.classList.contains('is-active')), 'CP TOTVS abre na Grade');
  ok(await p.$$eval('details.pl-mod', l => l.length) === 2, 'um bloco por módulo');
  ok(await p.$$eval('details.pl-mod .pl-mod-corpo', l => l.every(c => !c.innerHTML)), 'abre recolhido, sem DOM');
  ok(await p.isVisible('#pl-upload-wrap') && await p.isVisible('#pl-nova-ativ'), 'importar/criar visíveis para quem edita tudo');
  ok((await p.textContent('#pl-marcos')).includes('04/01/2027'), 'marco de go-live');
  ok((await p.textContent('details.pl-mod[data-mod="Financeiro"] summary')).includes('1 atrasado'), 'selo de atraso no módulo');
  ok((await p.textContent('details.pl-mod[data-mod="Faturamento"] summary')).includes('1 a revisar'), 'selo de revisão');
  await p.click('details.pl-mod[data-mod="Financeiro"] > summary');
  await p.waitForSelector('details.pl-mod[data-mod="Financeiro"] tr[data-pl-item]');
  ok(await p.$$eval('details.pl-mod[data-mod="Financeiro"] tr[data-pl-item]', l => l.length) === 5, '4 atividades + 1 cadastro');
  ok(await p.$$eval('details.pl-mod[data-mod="Financeiro"] tr.pl-etapa', l => l.map(x => x.textContent.trim()).join('|'))
     === 'Parametrização|Treinamento|Refinamento', 'etapas na ordem do método');
  ok(await p.$('details.pl-mod[data-mod="Financeiro"] tr.pl-atrasado'), 'linha atrasada marcada');

  // status na linha → POST só com o status
  const sel = 'details.pl-mod[data-mod="Financeiro"] select[data-pl-status]';
  const id3 = await p.$$eval(sel, l => l.find(s => s.value === 'agendado').dataset.plStatus);
  await p.selectOption(`select[data-pl-status="${id3}"]`, 'em_andamento');
  await p.waitForTimeout(300);
  ok(posts.length === 1 && posts[0].status === 'em_andamento' && Object.keys(posts[0]).length === 1, 'grava só o status');

  // finalizar com restrição pela linha → abre a gaveta pedindo o motivo, sem gravar
  await p.selectOption(`select[data-pl-status="${id3}"]`, 'finalizado_restricoes');
  await p.waitForSelector('.pl-gaveta');
  ok(posts.length === 1, 'restrição sem motivo não grava direto');
  ok(await p.isVisible('.pl-gaveta [data-motivo]'), 'gaveta mostra o motivo');
  await p.fill('.pl-gaveta [data-c="motivo_restricao"]', 'Falta conciliação');
  await p.click('.pl-gaveta [data-salva]');
  await p.waitForTimeout(300);
  ok(posts[1] && posts[1].status === 'finalizado_restricoes' && posts[1].motivo_restricao === 'Falta conciliação',
     'gaveta grava status + motivo');

  // gaveta com histórico
  await p.click('details.pl-mod[data-mod="Financeiro"] [data-pl-abre]');
  await p.waitForSelector('.pl-gaveta [data-hist] div');
  const hist = await p.textContent('.pl-gaveta [data-hist]');
  ok(hist.includes('Viviane CP') && hist.includes('planilha') && hist.includes('Finalizado'), 'histórico legível');
  await p.keyboard.press('Escape');
  ok(!(await p.$('.pl-gaveta')), 'Esc fecha a gaveta');

  // filtros
  await p.selectOption('#pl-f-status', '_atrasado');
  await p.waitForTimeout(100);
  ok((await p.textContent('#pl-conteudo')).includes('1 de 8 itens'), 'filtro de atrasados');
  await p.selectOption('#pl-f-status', '');
  await p.selectOption('#pl-f-resp', 'Bruno Souza');
  await p.waitForTimeout(100);
  ok((await p.textContent('#pl-conteudo')).includes('2 de 8 itens'), 'responsável pelo login (Bruno = Bruno Souza)');
  await p.selectOption('#pl-f-resp', '');
  await p.fill('#pl-busca', 'protótipo');
  await p.waitForTimeout(100);
  ok((await p.textContent('#pl-conteudo')).includes('1 de 8 itens'), 'busca sem acento/caixa');
  await p.fill('#pl-busca', '');
  await p.dispatchEvent('#pl-busca', 'input');

  // Painel
  await p.click('[data-plsub="painel"]');
  await p.waitForSelector('#pl-conteudo section');
  const painel = await p.textContent('#pl-conteudo');
  ok(/Atrasados\s*1/.test(painel), 'KPI atrasados');
  ok(painel.includes('Restrições em aberto') && painel.includes('Movimento bancário pendente'), 'restrição com motivo');
  ok(await p.$$eval('[data-pl-celula]', l => l.length) >= 5, 'matriz módulo × etapa');
  ok(painel.includes('Ana Lima') && !/\bAna\b(?! Lima)/.test(await p.textContent('#pl-conteudo section:nth-of-type(2)')),
     'carga agrupa "Ana" e "Ana Lima" pelo login');
  await p.click('[data-pl-celula^="Faturamento|Treinamento"]');
  await p.waitForSelector('[data-plsub="grade"].is-active');
  ok(await p.inputValue('#pl-f-modulo') === 'Faturamento' && await p.inputValue('#pl-f-etapa') === 'Treinamento',
     'clique na célula filtra a Grade');

  // export
  const html = await p.evaluate(() => relatorioPlanoHTML());
  ok(html && html.includes('Plano de Trabalho') && html.includes('Pendências') && html.includes('Próximas 2 semanas'),
     'relatório exportável');
  ok(erros.length === 0, 'zero erro de JS (CP TOTVS): ' + erros.join(' | '));
  await p.context().close();

  // ── CP do cliente ───────────────────────────────────────────────────────
  ({ p, erros } = await abre(b, { perm: 'tudo', papel: 'cp_cliente', eu: 'lucas@clientex.com.br',
                                  modo: 'cliente', abas: ['plano'] }));
  await p.waitForSelector('#pl-conteudo section');
  ok(await p.$eval('[data-plsub="pendencias"]', e => e.classList.contains('is-active') && e.textContent.includes('Minhas')),
     'CP do cliente abre em Minhas pendências');
  const pend = await p.textContent('#pl-conteudo');
  ok(pend.includes('Entrega dos cadastros') && !pend.includes('Re-parametrização da base'), 'só o lado do cliente');
  ok(pend.includes('vence em 2d'), 'cadastro com limite em 2 dias destacado');
  ok(pend.includes('Aguardando aprovação') && pend.includes('Treinamento de processos'), 'aguardando aprovação');
  ok(await p.isVisible('#pl-upload-wrap'), 'CP do cliente também importa');
  ok(erros.length === 0, 'zero erro de JS (cliente): ' + erros.join(' | '));
  await p.context().close();

  // ── consultor ───────────────────────────────────────────────────────────
  ({ p, erros, posts } = await abre(b, { perm: 'proprio', papel: 'consultor', eu: 'bruno.souza@totvs.com.br' }));
  await p.click('.tab-btn[data-tab="plano"]');
  await p.waitForSelector('#pl-conteudo section');
  ok(await p.$eval('[data-plsub="pendencias"]', e => e.classList.contains('is-active')), 'consultor abre nas pendências');
  ok(!(await p.isVisible('#pl-upload-wrap')) && !(await p.isVisible('#pl-nova-ativ')), 'consultor não importa nem cria');
  ok((await p.textContent('#pl-conteudo')).includes('Reunião vencida'), 'itens dele');
  await p.click('[data-plsub="grade"]');
  await p.click('details.pl-mod[data-mod="Financeiro"] > summary');
  await p.waitForSelector('details.pl-mod[data-mod="Financeiro"] tr[data-pl-item]');
  ok(await p.$$eval('details.pl-mod[data-mod="Financeiro"] select[data-pl-status]', l => l.length) === 1,
     'consultor só tem select nas linhas dele');
  await p.click('details.pl-mod[data-mod="Financeiro"] tr.pl-atrasado [data-pl-abre]');
  await p.waitForSelector('.pl-gaveta');
  ok(await p.$eval('.pl-gaveta [data-c="atividade"]', e => e.disabled) &&
     !(await p.$eval('.pl-gaveta [data-c="observacoes"]', e => e.disabled)), 'gaveta: descrição travada, observação livre');
  ok(!(await p.$('.pl-gaveta [data-remove]')), 'consultor não remove');
  ok(erros.length === 0, 'zero erro de JS (consultor): ' + erros.join(' | '));

  await b.close();
  console.log(`plano-front: ${OK} asserções OK`);
})().catch(e => { console.error(e.message || e); process.exit(1); });
