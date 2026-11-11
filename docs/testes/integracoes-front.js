// Teste da ABA INTEGRAÇÕES (front), com as rotas /api/* interceptadas.
//
// Como rodar, da raiz do repo:
//   cd web && python3 -m http.server 8731 --bind 127.0.0.1 &
//   node docs/testes/integracoes-front.js
//
// Cobre: barra de estado (sem cadastro, sem coleta, retrato velho, coletando,
// falha), cartões por grupo com status em texto (não só cor), indicador cinza
// de tabela ausente, caixas recolhíveis sem DOM quando fechadas, tabelas de
// detalhe, histórico, troca de base refazendo a leitura, coleta pelo botão do
// topo e pelo rail, modal de scripts e zero erro de JS da aba.
const { chromium } = require('playwright');

const AGORA = new Date().toISOString();
const IND = (chave, grupo, rotulo, valor, nivel, texto) => ({ chave, grupo, rotulo, valor, nivel, texto });
const INDS = [
  IND('quirons_fila', 'quirons', 'Fila Quírons', 12, 'verde', 'Mais antiga de 13/10/2026 (0 dia(s)). Lote do JOB (MV_RHMSGNG) = 100.'),
  IND('quirons_envios', 'quirons', 'Envios Quírons (7 dias)', 49, 'verde', 'Último envio em 13/10/2026 às 09:15.'),
  IND('quirons_erros', 'quirons', 'Erros Quírons (7 dias)', 1, 'vermelho', 'Códigos HTTP: 401. 401 = credencial do Quírons recusada.'),
  IND('ahgora_inconsistencias', 'ahgora', 'Ahgora — inconsistências', 1, 'amarelo', 'A Ahgora recusou.'),
  IND('ahgora_aguardando', 'ahgora', 'Ahgora — retorno perdido', null, 'cinza', 'A tabela RUM010 não existe nesta base.'),
  IND('ahgora_nao_enviados', 'ahgora', 'Ahgora — não enviados', 0, 'verde', '0 com movimento anterior a hoje.'),
  IND('sst_pendentes', 'esocial', 'eSocial SST não transmitidos', 0, 'verde', '30 evento(s), todos transmitidos.'),
  IND('quirons_laudo', 'quirons', 'Laudo Quírons (GPEM926)', '3/3', 'verde', 'Todos os requisitos OK.'),
];
const BLOCOS = {
  config: { ok: true, linhas: [{ PARAMETRO: 'MV_RHNG', FILIAL: '', CONTEUDO: '.T.' }] },
  rjp_fila: { ok: true, linhas: [{ FILIAL: '', TABELA: 'SRA', OPER: 'A', QTD: '12', MAIS_ANTIGO: '20261013' }] },
  rjp_vazao: { ok: true, linhas: [{ DIA: '20261013', QTD: '9', PRIMEIRA: '06:00', ULTIMA: '09:15' }] },
  ru7_erros: { ok: true, linhas: [{ DIA: '20261012', COD_HTTP: '401', QTD: '1' }] },
  rum_resumo: { ok: false, ausente: true, erro: 'A tabela RUM010 não existe nesta base.', linhas: [] },
  rje_sst: { ok: true, linhas: [{ EVENTO: 'S2220', STATUS: '4', QTD: '30', MAIS_ANTIGO: '20260901', MAIS_RECENTE: '20261010' }] },
  rum_pendencias: { ok: true, truncado: true, limite: 300, variante: 1, linhas: [
    { FILIAL: '01', MATRICULA: '000123', NOME: 'FULANO <b>X</b>', TIPO: '1', OPER: 'A', STATUS: '3', DT_MOV: '20261010', DT_INTEG: '20261010', HR_INTEG: '08:00', MENSAGEM: 'Centro de custo inválido | CPF Inválido' },
    { FILIAL: '01', MATRICULA: '000124', NOME: 'BELTRANO', TIPO: '2', OPER: 'A', STATUS: '3', DT_MOV: '20261010', DT_INTEG: '20261010', HR_INTEG: '08:00', MENSAGEM: 'Nao existe licenca disponivel no License Server' },
    { FILIAL: '01', MATRICULA: '000125', NOME: 'CICLANO', TIPO: '1', OPER: 'I', STATUS: '0', DT_MOV: '20261010', DT_INTEG: '', HR_INTEG: '', MENSAGEM: '' }] },
  rum_motivos: { ok: true, linhas: [], resumo: { registros: 12, sem_mensagem: 1,
    categorias: { licenca: 2, integracao: 0, cadastro: 7, campo: 2, outros: 0 }, motivos_total: 3,
    motivos: [{ texto: 'E-mail já cadastrado', categoria: 'cadastro', sub: 'duplicidade/conflito', qtd: 5, tipos: { 1: 5 } },
              { texto: 'Centro de custo inválido', categoria: 'cadastro', sub: 'tabela de apoio', qtd: 2, tipos: { 1: 2 } },
              { texto: 'Nao existe licenca disponivel no License Server', categoria: 'licenca', sub: null, qtd: 2, tipos: { 2: 2 } }] } },
  rjp_antigos: { ok: true, linhas: [] },
  rje_pendentes: { ok: true, linhas: [] },
};
const ULTIMA = (quando, desde = '2026-10-01') => ({ id: 2, coletado_em: quando, duracao_ms: 8300, nivel: 'vermelho',
  indicadores: INDS, blocos: Object.assign({ _meta: { desde } }, BLOCOS), environment: 'RACLI_PROD', disparado_por: 'reges.werlang@totvs.com.br',
  health: { ok: true, url: 'https://x/rest/api/rh/v1/integrationcheck/healthcheck',
            itens: [{ id: 'P1', status: 'ok', mensagem: '' }, { id: 'P2', status: 'aviso', mensagem: '401' }, { id: 'Q3', status: 'ok', mensagem: '' }] } });
const CFG = { url_rest: 'https://x/rest/tscmonit', environment: 'RACLI_PROD', banco: 'oracle', sufixo: '010',
              ativo: true, tem_token: true, tem_senha: true, integ_desde: '2026-10-01' };
const SERIE = [
  { id: 1, coletado_em: '2026-10-12T12:00:00Z', nivel: 'amarelo', indicadores: [{ chave: 'quirons_fila', valor: 40, nivel: 'amarelo' }] },
  { id: 2, coletado_em: AGORA, nivel: 'vermelho', indicadores: [{ chave: 'quirons_fila', valor: 12, nivel: 'verde' }] },
];
const PAYLOAD = (o = {}) => Object.assign({ ok: true, customer: 'TFEHM600', ambiente: 'producao', hoje: '2026-10-13',
  ambiente_cfg: CFG, ultima: ULTIMA(AGORA), serie: SERIE,
  coletas: [{ iniciado_em: AGORA, duracao_ms: 8300, ok: true, linhas: 20, itens: 8, erro: 'rum_resumo: tabela não existe', disparado_por: 'reges' }] }, o);

(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage();
  const erros = [];
  // Tailwind/fontes vêm de CDN, que o laboratório não alcança: erro de rede não é da aba.
  pg.on('pageerror', e => { if (!/tailwind|lucide|Chart/i.test(e.message)) erros.push('pageerror: ' + e.message); });
  pg.on('dialog', d => d.accept());

  let modo = { leitura: PAYLOAD(), coleta: { status: 200, json: PAYLOAD() } };
  const pedidos = [];
  pg.on('request', r => { if (r.url().includes('/api/integracoes')) pedidos.push(`${r.method()} ${r.url()}`); });

  await pg.route('**/api/**', r => r.fulfill({ json: { ok: true } }));
  await pg.route('**/api/me', r => r.fulfill({ json: { ok: true, email: 'reges.werlang@totvs.com.br', nome: 'Reges', perfil: 'admin', is_admin: true, interno: true } }));
  await pg.route('**/api/projetos*', r => r.fulfill({ json: { ok: true, total: 0, projetos: [] } }));
  await pg.route('**/api/integracoes/TFEHM600?*', r => r.fulfill({ json: modo.leitura }));
  const OCORR = [{ id: 7, ocorrido_em: '2026-11-10T19:20:00Z', tipo: 'pdf', usuario: 'Bruna', descricao: 'PDF não abre desde 16h', chamado: '998877', criado_por: 'reges.werlang@totvs.com.br' }];
  const postsOcorr = [];
  await pg.route('**/api/integracoes/*/ocorrencias*', r => {
    if (r.request().method() === 'POST') { postsOcorr.push(r.request().postDataJSON()); return r.fulfill({ json: { ok: true, id: 8 } }); }
    return r.fulfill({ json: { ok: true, ocorrencias: OCORR } });
  });
  const postsParams = [];
  await pg.route('**/api/integracoes/*/params*', r => { postsParams.push(r.request().postDataJSON()); return r.fulfill({ json: { ok: true } }); });
  globalThis.__postsOcorr = postsOcorr; globalThis.__postsParams = postsParams;
  await pg.route('**/api/integracoes/TFEHM600/coletar*', async r => {
    await new Promise(res => setTimeout(res, 300));
    r.fulfill({ status: modo.coleta.status, json: modo.coleta.json });
  });
  const cortes = [];
  await pg.route('**/api/integracoes/TFEHM600/corte*', r => {
    cortes.push(JSON.parse(r.request().postData() || '{}'));
    r.fulfill({ json: { ok: true, desde: cortes[cortes.length - 1].desde } });
  });
  await pg.route('**/api/integracoes/TFEHM600/scripts*', r => r.fulfill({ json: { ok: true, sufixo: '010', sufixo_usado: '010',
    scripts: [{ id: 'config', rotulo: 'Parâmetros (SX6)', tabela: 'SX6010', sql: "SELECT X6_VAR FROM SX6010 WHERE D_E_L_E_T_ = ' '" },
              { id: 'rjp_fila', rotulo: 'Fila RJP', tabela: 'RJP010', sql: 'SELECT 1 FROM RJP010' }] } }));

  await pg.goto('http://127.0.0.1:8731/index.html');
  await pg.waitForTimeout(400);

  const ok = [], bad = [];
  const t = (nome, cond, extra) => (cond ? ok : bad).push(nome + (extra ? ` [${extra}]` : ''));
  const txt = (sel) => pg.$eval(sel, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');

  await pg.evaluate(() => {
    state.selected = { cli: 'TFEHM600', cod: 'TFEHM60001', ver: '01', loja: '00',
                       projeto: { nome_cliente_projeto: 'RACLI LIMPEZA' } };
    $('#view-lista').classList.add('hidden');
    $('#view-detalhe').classList.remove('hidden');
    $('#detalhe-conteudo').classList.remove('hidden');
    setTab('integracoes');
  });
  await pg.waitForFunction(() => document.querySelectorAll('#int-conteudo [data-int-ind]').length > 0, null, { timeout: 5000 }).catch(() => {});

  t('aba listada na barra', await pg.$('button[data-tab="integracoes"]') !== null);
  t('painel visível', await pg.$eval('#tab-integracoes', n => !n.classList.contains('hidden')));
  t('rail das integrações visível', await pg.$eval('[data-rail="int"]', n => !n.classList.contains('hidden')));
  t('nome do cliente', (await txt('#int-cliente-nome')) === 'RACLI LIMPEZA');
  t('leu a produção ao abrir', pedidos.some(p => /GET .*\/api\/integracoes\/TFEHM600\?ambiente=producao/.test(p)), pedidos.join(' | '));
  t('abrir NÃO coleta', !pedidos.some(p => p.includes('/coletar')));
  t('input de corte preenchido', (await pg.$eval('#int-desde', n => n.value)) === '2026-10-01');
  t('barra diz o corte usado', /movimentos a partir de 01\/10\/2026/.test(await txt('#int-conteudo')));
  t('sem aviso de corte alterado', !/Corte alterado/.test(await txt('#int-conteudo')));
  t('8 cartões', (await pg.$$('#int-conteudo [data-int-ind]')).length === 8);
  const conteudo = await txt('#int-conteudo');
  t('barra com data da coleta e environment', /Coleta de .*RACLI_PROD.*8\.3 s/.test(conteudo), conteudo.slice(0, 160));
  t('situação geral em texto', /Situação geral\s*✕ Crítico/.test(conteudo));
  t('grupos nomeados', /Quírons \(NG\)/.test(conteudo) && /Ahgora PontoWeb/.test(conteudo) && /eSocial SST/.test(conteudo));
  const erroCard = await txt('[data-int-ind="quirons_erros"]');
  t('status com rótulo, não só cor', /✕ Crítico/.test(erroCard) && /401/.test(erroCard), erroCard);
  const cinza = await txt('[data-int-ind="ahgora_aguardando"]');
  t('tabela ausente vira "Sem dado" com motivo', /– Sem dado/.test(cinza) && /RUM010/.test(cinza) && /—/.test(cinza), cinza);
  t('sparkline com 2 pontos', await pg.$('[data-int-ind="quirons_fila"] svg polyline') !== null);
  t('sem sparkline para valor não numérico', await pg.$('[data-int-ind="quirons_laudo"] svg') === null);
  t('quirons aberta: fila por tabela', /Fila pendente por tabela/.test(conteudo) && /SRA/.test(conteudo));
  t('bloco ausente explicado', /ℹ A tabela RUM010 não existe/.test(conteudo));
  t('lista truncada avisada', /300 primeiras linhas/.test(conteudo));
  t('nome escapado (sem HTML injetado)', await pg.$('#int-conteudo b:has-text("X")') === null && /FULANO <b>X<\/b>/.test(conteudo));
  t('config fechada não gera DOM', !/Laudo do healthcheck/.test(conteudo));
  t('histórico fechado não gera DOM', !/Últimos disparos/.test(conteudo));

  // ── motivos das inconsistências (caixa Ahgora já abre aberta) ────────────
  const ahg = await txt('#int-conteudo');
  t('quadro de motivos', /Motivos das inconsistências/.test(ahg));
  const tile = async (c) => pg.$eval(`[data-int-cat="${c}"]`, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');
  t('contagem por categoria', /Cadastro 7/.test(await tile('cadastro')) && /Licença 2/.test(await tile('licenca'))
    && /Campo 2/.test(await tile('campo')) && /Integração 0/.test(await tile('integracao')), await tile('cadastro'));
  t('categoria diz quem resolve', /License Server/.test(await tile('licenca')));
  t('lista de motivos com sub-tipo', /E-mail já cadastrado/.test(ahg) && /Cadastro · duplicidade\/conflito/.test(ahg) && /Cadastro · tabela de apoio/.test(ahg));
  t('motivo afeta funcionário', /Funcionário 5/.test(ahg));
  t('registros sem mensagem avisados', /1 registro\(s\) sem mensagem/.test(ahg));
  const linhas = await pg.$$eval('#int-conteudo table tr', trs => trs.map(tr => tr.textContent.replace(/\s+/g, ' ').trim()));
  const lFul = linhas.find(l => /000123/.test(l)) || '';
  const lBel = linhas.find(l => /000124/.test(l)) || '';
  const lCic = linhas.find(l => /000125/.test(l)) || '';
  t('coluna motivo na lista', linhas.some(l => /Motivo/.test(l) && /Matrícula/.test(l)));
  t('linha: tabela de apoio vence campo', /Cadastro · tabela de apoio/.test(lFul) && /CPF Inválido/.test(lFul), lFul);
  t('linha: licença', /Licença/.test(lBel), lBel);
  t('linha não inconsistente sem motivo', !/Licença|Cadastro|Campo/.test(lCic), lCic);

  await pg.click('[data-int-caixa="config"]');
  const cfg = await txt('#int-conteudo');
  t('abre config com laudo', /Laudo do healthcheck/.test(cfg) && /P2/.test(cfg) && /MV_RHNG/.test(cfg));
  await pg.click('[data-int-caixa="historico"]');
  const hist = await txt('#int-conteudo');
  t('histórico com coletas e disparos', /Últimos disparos/.test(hist) && /2 coleta\(s\)/.test(hist) && /40/.test(hist));
  await pg.click('[data-int-caixa="quirons"]');
  t('recolher remove DOM', !/Fila pendente por tabela/.test(await txt('#int-conteudo')));

  // ── trocar o corte grava e avisa que a coleta usou outro ─────────────────
  modo.leitura = PAYLOAD({ ambiente_cfg: Object.assign({}, CFG, { integ_desde: '2026-09-15' }) });
  await pg.fill('#int-desde', '2026-09-15');
  await pg.waitForTimeout(400);
  t('corte enviado ao servidor', cortes.length === 1 && cortes[0].desde === '2026-09-15', JSON.stringify(cortes));
  t('trocar corte não coleta', !pedidos.some(p => p.includes('/coletar')));
  t('aviso de corte alterado', /Corte alterado/.test(await txt('#int-conteudo')) && /15\/09\/2026/.test(await txt('#int-conteudo')));
  modo.leitura = PAYLOAD();
  await pg.click('#int-reload'); await pg.waitForTimeout(300);

  // ── coleta pelo botão do topo: barra "coletando" durante a chamada ────────
  modo.coleta = { status: 200, json: PAYLOAD({ ultima: Object.assign(ULTIMA(AGORA), { nivel: 'verde' }) }) };
  await pg.click('#int-coletar-topo');
  await pg.waitForTimeout(80);
  t('barra coletando', /Coletando na base/.test(await txt('#int-conteudo')));
  t('botão desabilitado durante a coleta', await pg.$eval('#int-coletar-topo', n => n.disabled));
  await pg.waitForTimeout(500);
  t('POST na base escolhida', pedidos.some(p => /POST .*\/coletar\?ambiente=producao/.test(p)));
  t('resultado novo pintado', /Situação geral\s*✓ OK/.test(await txt('#int-conteudo')));

  // ── coleta com falha: mantém o retrato anterior e diz isso ────────────────
  modo.coleta = { status: 502, json: { ok: false, error: 'Falha ao chamar a base: ConnectTimeout' } };
  await pg.click('#int-coletar');
  await pg.waitForTimeout(600);
  const falha = await txt('#int-conteudo');
  t('falha explicada', /A coleta falhou: Falha ao chamar a base/.test(falha), falha.slice(0, 200));
  t('retrato anterior mantido e avisado', /coleta anterior/.test(falha) && (await pg.$$('[data-int-ind]')).length === 8);

  // ── troca de base relê, sem coletar ───────────────────────────────────────
  modo.leitura = PAYLOAD({ ambiente: 'teste', ambiente_cfg: null, ultima: null, serie: [], coletas: [] });
  const nAntes = pedidos.length;
  await pg.selectOption('#int-ambiente-sel', 'teste');
  await pg.waitForTimeout(300);
  t('troca de base relê', pedidos.slice(nAntes).some(p => /GET .*ambiente=teste/.test(p)));
  const vazio = await txt('#int-conteudo');
  t('sem cadastro pede ⚙ Ambiente', /Base de Testes ainda não cadastrada/.test(vazio) && /⚙ Ambiente/.test(vazio));
  t('sem coleta orienta o botão', /Nenhuma coleta ainda/.test(vazio));
  t('sem cartões sem coleta', (await pg.$$('[data-int-ind]')).length === 0);

  // ── retrato velho ─────────────────────────────────────────────────────────
  modo.leitura = PAYLOAD({ ultima: ULTIMA('2026-10-01T10:00:00Z') });
  await pg.selectOption('#int-ambiente-sel', 'producao');
  await pg.waitForTimeout(300);
  t('retrato > 24 h avisado', /mais de 24 h/.test(await txt('#int-conteudo')));

  // ── modal de scripts ──────────────────────────────────────────────────────
  await pg.click('#int-scripts');
  await pg.waitForTimeout(200);
  const modalTxt = await pg.$eval('.fixed.inset-0', n => n.textContent.replace(/\s+/g, ' ')).catch(() => '');
  t('modal de scripts', /Scripts SQL da coleta/.test(modalTxt) && /sufixo 010/.test(modalTxt) && /Fila RJP/.test(modalTxt), modalTxt.slice(0, 160));
  t('modal largo', await pg.$('.fixed.inset-0 .max-w-3xl') !== null);
  const sqls = await pg.$$eval('.fixed.inset-0 textarea', ns => ns.map(n => n.value));
  t('SQL sem ;', sqls.length === 2 && sqls.every(s => !s.trim().endsWith(';')));
  await pg.click('.fixed.inset-0 [data-fechar]');

  // ── exportar: a aba entra no relatório ────────────────────────────────────
  const rel = await pg.evaluate(() => { const r = relatorioDaAba(); return r && { titulo: r.titulo, base: r.base }; });
  t('exportar reconhece a aba', rel && rel.titulo === 'Monitoramento de Integrações' && rel.base === 'producao', JSON.stringify(rel));

  // ── grupo TOTVS Transmite (16/10/2026): base de Compras, sem RH ───────────
  const HOJE_RD = '2026-10-16';
  const TINDS = [
    IND('tra_sem_retorno', 'transmite', 'Classificadas sem retorno ao Transmite', 35, 'vermelho', 'CKO_STRAN ≠ 4. Por filial: 0101 31.'),
    IND('tra_prazo', 'transmite', 'Prazo do evento (90 dias)', 8, 'vermelho', 'Emissão: 1 com o prazo vencido (> 90 dias).'),
    IND('tra_hora_futura', 'transmite', 'Digitação com data/hora futura', 0, 'verde', 'Nenhuma nota.'),
    IND('tra_revisao', 'transmite', 'Importador em revisão cadastral (B)', 6, 'amarelo', 'Parados no Importador.'),
    IND('tra_fila', 'transmite', 'XML parados > 30 dias', 10, 'vermelho', 'DisponivelCancelamento.'),
    IND('tra_entrada', 'transmite', 'Dias sem importar XML', 0, 'verde', 'Último XML importado em 16/10/2026.'),
    IND('tra_sem_monitor', 'transmite', 'Lançadas fora do Importador', 2, 'amarelo', 'Sem SDS.'),
    IND('tra_params', 'transmite', 'Parâmetros do Importador', '2/14', 'verde', 'MV_IMPXML = .T.'),
    IND('tra_erros', 'transmite', 'XML parados por erro do Importador', 37, 'vermelho', 'Por motivo: COM007 Fornecedor inexistente na base (35).'),
  ];
  const TBLOCOS = {
    _meta: { desde: null, grupos: ['transmite'], tra_prazo: 90 },
    tra_captura: { ok: true, linhas: [
      { ESPECIE: 'SPED', QTD: '4728', ATE1: '4472', D2A3: '61', D4A7: '114', MAIS7: '81', MAXIMO: '71' },
      { ESPECIE: 'CTE', QTD: '969', ATE1: '707', D2A3: '131', D4A7: '99', MAIS7: '32', MAXIMO: '62' }] },
    tra_captura_lista: { ok: true, linhas: [
      { FILIAL: '010110', ESPECIE: 'CTE', DOC: '000000777', SERIE: '1', FORNECEDOR: 'T001', LOJA: '01', CNPJ: '12345678000199', EMISSAO: '20261030', DT_IMP: '20261101', HR_IMP: '08:10:00', DS_STATUS: '', CHAVE: 'KCTE777', DIAS: '2' }] },
    tra_ultima: { ok: true, linhas: [
      { EDI: '214', ULT_DATA: '20261108', ULT_HORA: '15:00:00', QTD: '30' }, { EDI: '109', ULT_DATA: '20261110', ULT_HORA: '09:00:00', QTD: '200' }] },
    tra_transf: { ok: true, linhas: [
      { FILIAL: '010113', ESPECIE: 'SPED', CK: 'N', QTD: '1', MAIS_ANTIGA: '20261109', MAIS_RECENTE: '20261109' }] },
    tra_sem_retorno_lista: { ok: true, linhas: [
      { FILIAL: '0101', DOC: '000013687', SERIE: '1', FORNECEDOR: 'F00001', LOJA: '01', EMISSAO: '20260804', DTDIGIT: '20261001',
        HORA: '10:00:00', STRAN: '2', CODEDI: '109', DT_IMP: '20260805', DS_STATUS: 'B', CHAVE: '42261027968581000106550010000136871530601731' },
      { FILIAL: '0102', DOC: '000000001', SERIE: '1', FORNECEDOR: 'F00002', LOJA: '01', EMISSAO: '20260701', DTDIGIT: '20261002',
        HORA: '11:00:00', STRAN: '', CODEDI: '214', DT_IMP: '20260702', DS_STATUS: '', CHAVE: '4226<i>zz</i>' },
      { FILIAL: '010113', DOC: '000121659', SERIE: '2', FORNECEDOR: '83286500', LOJA: '0012', EMISSAO: '20261020', DTDIGIT: '20261020',
        HORA: '11:16:00', STRAN: '2', CODEDI: '109', DT_IMP: '20261020', DS_STATUS: '', TEM_SDS: 'S', TIPO_NF: 'N', CHAVE: '42261083286500001211550020001216591539161896',
        DS_DOC: '000121659', DS_SERIE: '002', DS_FORNEC: '83286500', DS_LOJA: '0012' },
      { FILIAL: '010112', DOC: '000689328', SERIE: '2', FORNECEDOR: '04195643', LOJA: '0006', EMISSAO: '20261015', DTDIGIT: '20261020',
        HORA: '13:57:24', STRAN: '2', CODEDI: '214', DT_IMP: '20261015', DS_STATUS: '', TEM_SDS: 'S', TIPO_NF: 'C', CHAVE: '35261004195643000601570020006893281066893285' },
      { FILIAL: '010112', DOC: '000041132', SERIE: '1', FORNECEDOR: '08432868', LOJA: '0001', EMISSAO: '20261028', DTDIGIT: '20261028',
        HORA: '16:01:36', STRAN: '2', CODEDI: '109', DT_IMP: '20261028', DS_STATUS: '', TEM_SDS: 'N', TIPO_NF: 'I', CHAVE: '42261008432868000172550010000411321211839841' }] },
    tra_erros: { ok: true, linhas: [], resumo: { acao: 37, sem_acao: 55, sem_erro: 614, sem_erro_por_situacao: { '2': 614 },
      mais_antigo_acao: '20261001', codigos: [
        { codigo: 'COM007', qtd: 35, tipos: { NFE: 30, NFSE: 5 }, texto: 'Fornecedor inexistente na base', fonte: 'padrao', quem: 'cadastro', mais_antigo: '20261001', mais_recente: '20261030' },
        { codigo: 'COM099', qtd: 2, tipos: { CTE: 2 }, texto: 'Código sem <b>descrição</b>', fonte: 'nenhuma', quem: 'outros', mais_antigo: '20261010', mais_recente: '20261010' },
        { codigo: 'COM052', qtd: 34, tipos: { NFE: 34 }, texto: 'Este XML não pertence a nenhuma empresa/filial e não podera ser processado.', fonte: 'base', quem: 'nada', mais_antigo: '20261001', mais_recente: '20261029' },
        { codigo: 'COM040', qtd: 21, tipos: { NFE: 21 }, texto: 'NF-e cancelada', fonte: 'padrao', quem: 'nada', mais_antigo: '20260920', mais_recente: '20261029' },
        { codigo: 'COM004', qtd: 25, tipos: { NFE: 25 }, texto: 'Tipo NF-e de ajustes não será tratado pelo Importador XML.', fonte: 'base', quem: 'fiscal', mais_antigo: '20261001', mais_recente: '20261104' },
        { codigo: 'COM047', qtd: 9, tipos: { CTE: 9 }, texto: 'Complemento de imposto não é tratado pelo Totvs Colaboração/Importador.', fonte: 'base', quem: 'outros', mais_antigo: '20261104', mais_recente: '20261104' }] } },
    tra_erros_lista: { ok: true, linhas: [
      { ERRO: 'COM007', STRAN: '2', CODEDI: '109', DT_IMP: '20261001', DOC: '123', DESTINO: '83286500001211', CHAVE: '42261000000000000000550010000001231000000010' },
      { ERRO: 'COM047', STRAN: '2', CODEDI: '214', DT_IMP: '20261104', DOC: '777', DESTINO: '83286500001211', CHAVE: '42261100000000000000570010000007771000000010' }] },
    tra_sem_retorno: { ok: true, linhas: [{ FILIAL: '0101', QTD: '31', DIGIT_MAIS_ANTIGA: '20260905', EMISSAO_MAIS_ANTIGA: '20260701', VENCIDAS: '1', CRITICAS: '2', ATENCAO: '5' }] },
    tra_futuras_lista: { ok: true, linhas: [] },
    tra_revisao: { ok: true, linhas: [{ STATUS: 'B', QTD: '6', MAIS_ANTIGO: '20260920', MAIS_RECENTE: '20261010' }] },
    tra_revisao_lista: { ok: false, erro: 'Não lido: o tempo da coleta acabou antes deste bloco.', linhas: [] },
    tra_fila: { ok: true, linhas: [{ CODEDI: '109', STRAN: '4', QTD: '300', MAIS_ANTIGO: '20260701', MAIS_RECENTE: '20261016' }] },
    tra_fila_antigos: { ok: true, linhas: [] },
    tra_sem_monitor: { ok: true, linhas: [
      { FILIAL: '070701', ESPECIE: 'NF3E', QTD: '1', MAIS_ANTIGO: '20261010', MAIS_RECENTE: '20261010' },
      { FILIAL: '010113', ESPECIE: 'SPED', QTD: '1', MAIS_ANTIGO: '20261109', MAIS_RECENTE: '20261109' },
      { FILIAL: '010113', ESPECIE: 'NFCOM', QTD: '1', MAIS_ANTIGO: '20261009', MAIS_RECENTE: '20261009' }] },
    tra_sem_monitor_cfop: { ok: true, linhas: [
      { FILIAL: '010113', ESPECIE: 'SPED', CFOP: '1101', TES: '001', NOTAS: '1', ITENS: '2', VALOR: '1500.5' },
      { FILIAL: '010113', ESPECIE: 'SPED', CFOP: '1556', TES: '010', NOTAS: '1', ITENS: '1', VALOR: '99.9' }] },
    tra_empresas: { ok: true, linhas: [
      { EMPRESA: '01', FILIAL: '010113', NOME: 'FILIAL CRICIUMA', RAZAO: 'INDUSTRIA CARBONIFERA RIO DESERTO', CNPJ: '83286500001211' },
      { EMPRESA: '01', FILIAL: '010101', NOME: 'MATRIZ', RAZAO: 'INDUSTRIA CARBONIFERA RIO DESERTO', CNPJ: '83286500000187' }] },
    tra_sem_monitor_lista: { ok: true, linhas: [
      { FILIAL: '010113', ESPECIE: 'SPED', DOC: '000500001', SERIE: '1', FORNECEDOR: 'F1', LOJA: '01', EMISSAO: '20261109', DTDIGIT: '20261109', HORA: '08:00:00', TIPO_NF: 'N', CHAVE: 'K1', STRAN: '2', NA_CKO: '1',
        VALOR: '1600.4', UF: 'SC', FORN_NOME: 'FILIAL MATRIZ', FORN_CGC: '83286500000187', CFOP_MIN: '1101', CFOP_MAX: '1556', N_CFOP: '2', TES_MIN: '001', TES_MAX: '010', ITENS: '3' },
      { FILIAL: '010113', ESPECIE: 'NFCOM', DOC: '000500002', SERIE: '1', FORNECEDOR: 'F2', LOJA: '01', EMISSAO: '20261009', DTDIGIT: '20261009', HORA: '09:00:00', TIPO_NF: 'N', CHAVE: 'K2', STRAN: '', NA_CKO: '0' },
      { FILIAL: '070701', ESPECIE: 'NF3E', DOC: '000500003', SERIE: '1', FORNECEDOR: 'F3', LOJA: '01', EMISSAO: '20261009', DTDIGIT: '20261010', HORA: '10:00:00', TIPO_NF: 'N', CHAVE: 'K3', STRAN: '', NA_CKO: '0' }] },
    tra_config: { ok: true, linhas: [{ PARAMETRO: 'MV_APITRAN', FILIAL: '', CONTEUDO: '(preenchido)' }] },
  };
  const RD_CFG = Object.assign({}, CFG, { environment: 'RDESERTO_PROD', integ_desde: null, integ_grupos: ['transmite'], tem_senha: false });
  const RD = (o = {}) => Object.assign({ ok: true, customer: 'TFDPHR00', ambiente: 'producao', hoje: HOJE_RD,
    ambiente_cfg: RD_CFG, coletas: [],
    ultima: { id: 9, coletado_em: AGORA, duracao_ms: 5100, nivel: 'vermelho', indicadores: TINDS, blocos: TBLOCOS,
              environment: 'RDESERTO_PROD', disparado_por: 'reges', health: { ok: false, mensagem: 'Grupo RH desligado nesta base.' } },
    serie: [{ id: 9, coletado_em: AGORA, nivel: 'vermelho', indicadores: TINDS.map(i => ({ chave: i.chave, valor: i.valor, nivel: i.nivel })) }] }, o);
  let rdLeitura = RD();
  const gruposPost = [];
  await pg.route('**/api/integracoes/TFDPHR00?*', r => r.fulfill({ json: rdLeitura }));
  await pg.route('**/api/integracoes/TFDPHR00/grupos*', r => {
    gruposPost.push(JSON.parse(r.request().postData() || '{}').grupos);
    r.fulfill({ json: { ok: true, grupos: gruposPost[gruposPost.length - 1] } });
  });
  await pg.evaluate(() => {
    state.selected = { cli: 'TFDPHR00', cod: 'TFDPHR0001', ver: '01', loja: '00', projeto: { nome_cliente_projeto: 'RIO DESERTO' } };
    initIntegracoes();
  });
  await pg.waitForFunction(() => document.querySelector('[data-int-ind="tra_sem_retorno"]'), null, { timeout: 5000 }).catch(() => {});
  if (process.env.SHOT) {   // captura opcional dos cartões (revisão visual do tema)
    await pg.setViewportSize({ width: 1600, height: 1000 });
    await pg.$eval('[data-int-ind="tra_sem_retorno"]', n => n.scrollIntoView({ block: 'start' }));
    await pg.screenshot({ path: process.env.SHOT });
    await pg.$eval('[data-int-tra-quem="cadastro"]', n => n.scrollIntoView({ block: 'center' })).catch(() => {});
    await pg.screenshot({ path: process.env.SHOT.replace('.png', '-2.png') });
    const cx = await pg.$('[data-int-caixa="transmite"]');
    if (cx) await (await cx.evaluateHandle(n => n.closest('.rel-bloco'))).asElement().screenshot({ path: process.env.SHOT.replace('.png', '-3.png') });
  }
  const rd = await txt('#int-conteudo');
  t('transmite: 9 cartões, nenhum de RH', (await pg.$$('[data-int-ind]')).length === 9 && await pg.$('[data-int-ind^="quirons"]') === null);
  t('transmite: grupo nomeado', /TOTVS Transmite/.test(rd));
  t('transmite: caixas de RH somem', await pg.$('[data-int-caixa="quirons"]') === null && await pg.$('[data-int-caixa="config"]') === null);
  t('transmite: sem aviso de senha do RH', !/healthcheck da Quírons exige/.test(rd));
  t('transmite: caixa aberta com a lista', /Classificadas no Protheus sem "Classificada"/.test(rd) && /000013687\/1/.test(rd));
  // detalhes recolhidos por padrão; expandir/recolher todos e um a um
  const abertas = () => pg.$$eval('#int-conteudo details[data-int-sub]', ds => ds.filter(d => d.open).length);
  const nDobras = (await pg.$$('#int-conteudo details[data-int-sub]')).length;
  t('detalhes recolhidos por padrão', nDobras >= 10 && await abertas() === 0, `${nDobras} dobras`);
  t('dobra mostra a quantidade de linhas', /^3$/.test(await pg.$eval('details[data-int-sub^="Classificadas no Protheus"] .int-sub-n', n => n.textContent).catch(() => '')));
  await pg.click('details[data-int-sub="Parâmetros do Importador (SX6)"] > summary');
  t('expande um a um', await abertas() === 1);
  await pg.click('[data-int-sub-barra="transmite"] [data-int-sub-todos="abrir"]');
  t('expandir todos', await abertas() === nDobras);
  await pg.click('[data-int-sub-barra="transmite"] [data-int-sub-todos="fechar"]');
  t('recolher todos', await abertas() === 0);
  await pg.click('[data-int-ind="tra_sem_retorno"]'); await pg.waitForTimeout(300);
  t('clique no cartão abre só o seu detalhe', await abertas() === 1
    && await pg.$eval('details[data-int-sub^="Classificadas no Protheus"]', d => d.open));
  await pg.click('[data-int-sub-barra="transmite"] [data-int-sub-todos="abrir"]');
  const tl = await pg.$$eval('#int-conteudo table tr', trs => trs.map(tr => tr.textContent.replace(/\s+/g, ' ').trim()));
  const l1 = tl.find(l => /000013687/.test(l)) || '', l2 = tl.find(l => /000000001/.test(l)) || '';
  t('transmite: prazo em texto (73 d, faltam 17)', /! 73 d · faltam 17/.test(l1), l1);
  t('transmite: vencido', /✕ 107 d · vencido/.test(l2), l2);
  t('transmite: STRAN e tipo legíveis', /2 · Exportada/.test(l1) && /109 · NF-e/.test(l1) && /B · revisão cadastral/.test(l1));
  t('transmite: STRAN vazio e sem SDS', /\(vazio\) · não classificada/.test(l2) && /sem SDS/.test(l2) && /214 · CT-e/.test(l2));
  const l3 = tl.find(l => /000121659/.test(l)) || '';
  t('transmite: Importador com status vazio ≠ sem SDS', /\(vazio\) · sem status/.test(l3) && !/sem SDS/.test(l3), l3);
  const lCompl = tl.find(l => /000689328/.test(l)) || '';
  t('complementos: fora da lista de sem retorno, em lista própria', /C · compl\. preço\/frete/.test(lCompl) && /Complementos fora do Transmite/.test(rd)
    && /C · compl\. preço\/frete: 1 · I · compl\. ICMS: 1/.test(rd), lCompl);
  t('complementos: a lista principal mostra só as normais', await pg.$$eval('#int-conteudo table', ts => {
    const t0 = ts.find(t => /000013687/.test(t.textContent)); return !!t0 && !/000689328|000041132/.test(t0.textContent); }));
  t('erros: quadro do Importador', /Por que o Importador parou/.test(rd));
  // ── 10/11/2026: melhorias M1–M8 ──
  t('M1/M5/M2/M8 seções novas', /Última importação por tipo/.test(rd) && /Atraso de captura por espécie/.test(rd)
    && /Notas que mais demoraram a chegar ao Monitor/.test(rd) && /Transferências entre filiais fora do Importador/.test(rd)
    && /Ocorrências do portal do Transmite/.test(rd));
  t('M1 captura: CT-e 27% tarde, NF-e 4% com 4+ dias', /27%\s*> 1 dia/.test(rd) && /4%\s*4\+ dias/.test(rd) && /KCTE777/.test(rd));
  t('M3 motivo provável: série diferente', /série SDS "002" × SF1 "2"/.test(rd));
  t('M4 prazo da base no seletor (90)', await pg.$eval('[data-int-tra-prazo]', s => s.value) === '90' && /alertas em 60 e 80 dias/.test(rd));
  await pg.selectOption('[data-int-tra-prazo]', '60');
  await pg.waitForTimeout(300);
  t('M4 grava o prazo', JSON.stringify(globalThis.__postsParams.at(-1)) === '{"tra_prazo_dias":60}');
  t('M2 transferência aberta com a filial emitente', /FILIAL MATRIZ/.test(rd) && /01\/010101 · MATRIZ/.test(rd));
  t('M8 ocorrência listada', /PDF não abre desde 16h/.test(rd) && /998877/.test(rd));
  await pg.click('[data-int-sub-barra="transmite"] [data-int-sub-todos="abrir"]');
  await pg.fill('[data-int-ocorr-form] [name="descricao"]', 'Busca sem a nota 123');
  await pg.selectOption('[data-int-ocorr-form] [name="tipo"]', 'busca');
  await pg.click('[data-int-ocorr-form] button[type="submit"]');
  await pg.waitForTimeout(300);
  t('M8 registra ocorrência', globalThis.__postsOcorr.length === 1 && globalThis.__postsOcorr[0].tipo === 'busca' && /Busca sem a nota 123/.test(globalThis.__postsOcorr[0].descricao));
  if (process.env.SHOT) {
    for (const [tit, nome] of [['Atraso de captura por espécie (emissão → Monitor)', 'cap'], ['Transferências entre filiais fora do Importador', 'tf'],
                               ['Ocorrências do portal do Transmite (registro manual)', 'oc'], ['Classificadas no Protheus sem "Classificada" no Transmite', 'sr']]) {
      const el = await pg.$(`details[data-int-sub="${tit.replace(/"/g, '\\"')}"]`);
      if (el) await el.screenshot({ path: process.env.SHOT.replace('.png', `-${nome}.png`) });
    }
    const bar = await pg.$('[data-int-tra-barra]'); if (bar) await bar.screenshot({ path: process.env.SHOT.replace('.png', '-barra.png') });
  }
  const [dl] = await Promise.all([pg.waitForEvent('download'), pg.click('[data-int-tra-dossie]')]);
  const dossie = require('fs').readFileSync(await dl.path(), 'utf8');
  t('M7 dossiê com P1 a P5 e backlog', /Dossiê TOTVS Transmite/.test(dossie) && /PDF não abre desde 16h/.test(dossie) && /KCTE777/.test(dossie)
    && /série SDS/.test(dossie) && /FILIAL MATRIZ/.test(dossie) && /Já levantados/.test(dossie), dl.suggestedFilename());
  // popup do código: notas com CNPJ, empresa/filial, chave e tipo
  await pg.click('[data-int-tra-cod="COM007"]');
  if (process.env.SHOT) await pg.screenshot({ path: process.env.SHOT.replace('.png', '-pop1.png') });
  const pop = await pg.$eval('[data-int-pop="COM007"]', n => n.textContent.replace(/\s+/g, ' ')).catch(() => '');
  t('popup do CKO_CODERR com CNPJ de destino, empresa/filial, tipo e chave', /COM007 · 1 XML/.test(pop) && /83\.286\.500\/0012-11/.test(pop)
    && /01\/010113 · FILIAL CRICIUMA/.test(pop) && /109 · NF-e/.test(pop) && /CNPJ emitente/.test(pop), pop.slice(0, 200));
  await pg.keyboard.press('Escape');
  t('popup fecha com Esc', await pg.$('[data-int-pop]') === null);
  // clique no cartão → detalhamento abaixo
  await pg.click('[data-int-ind="tra_sem_monitor"], [data-int-ind="tra_sem_retorno"]');
  await pg.waitForTimeout(400);
  const flash = await pg.$eval('.int-flash', n => n.dataset.intSub || '').catch(() => '');
  t('cartão leva ao detalhamento (e destaca)', /Lançadas fora do Importador — notas uma a uma|Classificadas no Protheus sem/.test(flash), flash);
  const todosTem = await pg.$$eval('#int-conteudo .int-link[data-int-ind]', (cs, M) => cs.every(c => {
    const t = M[c.dataset.intInd]; return !t || !!document.querySelector(`[data-int-sub="${t.replace(/"/g, '\\"')}"]`); }),
    await pg.evaluate(() => INT_DETALHE));
  t('todo cartão do Transmite aponta para um detalhe que existe', todosTem);
  const leg = await pg.$eval('[data-int-legenda-stran]', n => n.textContent.replace(/\s+/g, ' ')).catch(() => '');
  t('legenda do CKO_STRAN com os 5 valores e o que fazer', /Fora da integração/.test(leg) && /Recebido, sem aviso/.test(leg)
    && /Integrada \(pré-nota\)/.test(leg) && /Classificar a pré-nota/.test(leg) && /MV_DTINITR/.test(leg), leg.slice(0, 120));
  t('CKO_STRAN com dica ao passar o mouse', await pg.$eval('#int-conteudo span[title^="Exportada —"]', n => /O que fazer/.test(n.title)).catch(() => false));
  const tq = async (q) => pg.$eval(`[data-int-tra-quem="${q}"]`, n => n.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');
  t('erros: contagem por quem resolve', /Cadastro 35/.test(await tq('cadastro')) && /Sem ação 55/.test(await tq('nada'))
    && /Não mapeado 2/.test(await tq('outros')) && /Não atendido pelo Importador 34/.test(await tq('nao_atendido')) && await pg.$('[data-int-tra-quem="fiscal"]') === null, await tq('nao_atendido'));
  const tNa = await pg.$eval('[data-int-tra-nao-atendidos]', n => n.textContent.replace(/\s+/g, ' ')).catch(() => '');
  t('erros: não atendidos em quadro próprio (COM004 antigo "fiscal" e COM047)', /COM004/.test(tNa) && /COM047/.test(tNa) && !/COM007/.test(tNa), tNa);
  const lNa = tl.find(l => /^COM047/.test(l) && /777/.test(l)) || '';
  t('erros: XML não atendido na lista própria', /Não atendido pelo Importador/.test(lNa) && /Não atendidos pelo Importador, um a um/.test(rd), lNa);
  const lc = tl.find(l => /^COM007/.test(l)) || '';
  t('erros: linha do código com motivo, quem e tipo', /Fornecedor inexistente na base/.test(lc) && /Cadastro/.test(lc) && /NF-e 30 · NFS-e 5/.test(lc), lc);
  t('erros: texto da base marcado', /não podera ser processado\. \(texto da base\)/.test(rd));
  t('erros: texto escapado', await pg.$('#int-conteudo b:has-text("descrição")') === null && /Código sem <b>descrição<\/b>/.test(rd));
  t('erros: fila sem motivo explicada', /Sem motivo gravado: 614 XML/.test(rd) && /2 · Exportada 614/.test(rd));
  // ordenação por Filial/Espécie na tabela agrupada
  const ordem = () => pg.$$eval('[data-int-semmon-grp]', trs => trs.map(t => t.dataset.intSemmonGrp).join(','));
  await pg.click('[data-int-ord="semmon_grp"][data-k="FILIAL"]');
  t('ordena por filial (crescente)', (await ordem()).startsWith('010113|'), await ordem());
  await pg.click('[data-int-ord="semmon_grp"][data-k="ESPECIE"]');
  t('ordena por espécie', await ordem() === '070701|NF3E,010113|NFCOM,010113|SPED', await ordem());
  await pg.click('[data-int-ord="semmon_grp"][data-k="ESPECIE"]');
  t('segundo clique inverte', (await ordem()).startsWith('010113|SPED'), await ordem());
  // popup por filial + espécie
  await pg.click('[data-int-semmon-grp="010113|SPED"]');
  const pg2 = await pg.$eval('[data-int-pop="010113|SPED"]', n => n.textContent.replace(/\s+/g, ' ')).catch(() => '');
  t('popup filial/espécie: notas, CFOP × TES, tipo, valor, fornecedor', /Filial 010113 · SPED/.test(pg2) && /CFOP × TES/.test(pg2)
    && /1556/.test(pg2) && /1101 … 1556/.test(pg2) && /FILIAL MATRIZ/.test(pg2) && /N · normal: 1/.test(pg2) && /R\$\s?1\.600,40/.test(pg2), pg2.slice(0, 300));
  await pg.click('[data-int-pop] [data-int-ord="semmon_pop"][data-k="VALOR"]');
  t('popup reordena e continua aberto', !!(await pg.$('[data-int-pop="010113|SPED"]')));
  if (process.env.SHOT) await pg.screenshot({ path: process.env.SHOT.replace('.png', '-pop2.png') });
  await pg.keyboard.press('Escape');
  t('sem SDS: notas abertas com filtro', /Lançadas fora do Importador — notas uma a uma/.test(rd) && /3 de 3 nota\(s\)/.test(rd)
    && /não chegou ao Transmite/.test(rd) && /000500003/.test(rd));
  await pg.selectOption('[data-int-semmon="filial"]', '010113');
  const rdF = await txt('#int-conteudo');
  t('sem SDS: filtro por filial', /2 de 3 nota\(s\)/.test(rdF) && /000500001/.test(rdF) && !/000500003/.test(rdF));
  await pg.selectOption('[data-int-semmon="especie"]', 'NFCOM');
  const rdE = await txt('#int-conteudo');
  const rdE1 = rdE.split('notas uma a uma')[1] || '';
  t('sem SDS: filial + espécie', /1 de 3 nota\(s\)/.test(rdE1) && /000500002/.test(rdE1) && !/000500001/.test(rdE1));
  await pg.selectOption('[data-int-semmon="filial"]', ''); await pg.selectOption('[data-int-semmon="especie"]', '');
  await pg.selectOption('[data-int-semmon="natureza"]', 'consumo');
  const rdN = await txt('#int-conteudo');
  const rdN1 = rdN.split('notas uma a uma')[1] || '';
  t('M6 filtro por natureza (contas de consumo: NF3E e NFCOM)', /2 de 3 nota\(s\)/.test(rdN1) && /000500003/.test(rdN1) && /000500002/.test(rdN1) && !/000500001/.test(rdN1));
  await pg.selectOption('[data-int-semmon="natureza"]', '');
  const ll = tl.find(l => /83286500001211/.test(l) && /COM007/.test(l)) || '';
  t('erros: lista um a um com destino e quem resolve', /Cadastro/.test(ll) && /123/.test(ll), ll);
  t('transmite: chave escapada', await pg.$('#int-conteudo i:has-text("zz")') === null && /4226<i>zz<\/i>/.test(rd));
  t('transmite: bloco não lido explicado', /tempo da coleta acabou/.test(rd));
  t('transmite: credencial mascarada', /\(preenchido\)/.test(rd));
  t('transmite: checkboxes refletem a base', await pg.$eval('[data-int-grupo="transmite"]', n => n.checked)
    && !(await pg.$eval('[data-int-grupo="rh"]', n => n.checked)));
  if (!/Últimos disparos/.test(await txt('#int-conteudo'))) await pg.click('[data-int-caixa="historico"]');
  const th = await pg.$$eval('#int-conteudo th', ns => ns.map(n => n.textContent.trim()));
  t('histórico só com colunas do grupo', th.includes('Transm. sem retorno') && !th.includes('Fila Quírons'), th.join('|'));
  rdLeitura = RD({ ambiente_cfg: Object.assign({}, RD_CFG, { integ_grupos: ['rh', 'transmite'] }) });
  await pg.click('[data-int-grupo="rh"]');
  await pg.waitForTimeout(400);
  t('ligar RH grava os dois grupos', JSON.stringify(gruposPost[0]) === '["rh","transmite"]', JSON.stringify(gruposPost));
  t('ligar grupo não coleta', !pedidos.some(p => p.includes('TFDPHR00/coletar')));
  t('aviso de grupos alterados', /Grupos alterados/.test(await txt('#int-conteudo')));
  rdLeitura = RD();
  await pg.click('#int-reload'); await pg.waitForTimeout(300);
  await pg.click('[data-int-grupo="transmite"]');            // desmarcar o único: bloqueado
  await pg.waitForTimeout(300);
  t('não deixa ficar sem grupo', gruposPost.length === 1 && await pg.$eval('[data-int-grupo="transmite"]', n => n.checked));

  t('zero erro de JS', erros.length === 0, erros.join(' | '));
  await b.close();
  console.log(`${ok.length} OK, ${bad.length} falha(s)`);
  bad.forEach(x => console.log('FALHOU:', x));
  process.exit(bad.length ? 1 : 0);
})();
