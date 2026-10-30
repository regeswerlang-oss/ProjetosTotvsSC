# Teste das funções PURAS do grupo CRM × iPaaS da aba Integrações (30/10/2026).
#
# Como rodar, de qualquer lugar:  python3 docs/testes/integracoes-crm-back.py
# Mesmo método do integracoes-back.py: extrai o trecho do módulo em vez de
# importá-lo (api/index.py sobe Flask e exige DATABASE_URL). Cobre: SQL dos
# blocos (sufixo, sem ';', só SELECT, sem relógio do banco, sem subconsulta
# dentro de agregação, máscara de token, corte por data), causa do erro da ZA3
# e as regras de nível de cada indicador.
import csv, io, json, pathlib, re, unicodedata
from datetime import date, datetime, timedelta, timezone

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('INTEG_PARAMS = (')
fim = src.index('def _integ_health(cfg')
ns = {'re': re, 'csv': csv, 'io': io, 'json': json, 'date': date, 'datetime': datetime,
      'timedelta': timedelta, 'unicodedata': unicodedata}
exec(compile(src[ini:fim], 'integ', 'exec'), ns)

ok = falhou = 0


def confere(nome, cond):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome)


HOJE = date(2026, 10, 30)
TZ = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 10, 30, 10, 0, tzinfo=TZ)

# ── grupos ──────────────────────────────────────────────────────────────────
confere('crm é grupo conhecido', 'crm' in ns['INTEG_GRUPOS_BASE'])
confere('nulo continua = só RH', ns['_integ_grupos'](None) == ('rh',))
confere('crm sozinho', ns['_integ_grupos'](['crm']) == ('crm',))
confere('ordem estável', ns['_integ_grupos'](['crm', 'rh']) == ('rh', 'crm'))

# ── SQL dos blocos ──────────────────────────────────────────────────────────
scripts = ns['_integ_scripts']('010', HOJE, None, 'oracle', ['crm'], AGORA)
ids = [s['id'] for s in scripts]
ESPERADOS = ['crm_config', 'crm_totais', 'crm_situacao', 'crm_fila', 'crm_erros', 'crm_projetos',
             'crm_contratos', 'crm_medicoes', 'crm_cad_produtos', 'crm_cad_tabelas',
             'crm_pendentes_lista', 'crm_rastreio_lista', 'crm_sem_preco_lista']
confere('blocos do grupo CRM', ids == ESPERADOS)
confere('só CRM: nenhum bloco de RH ou Transmite', not any(i.startswith(('rj', 'ru', 'tra_', 'config')) for i in ids))
det = [s['id'] for s in scripts if s.get('detalhe')]
confere('três detalhes, no fim', det == ESPERADOS[-3:])
for s in scripts:
    for k, sql in enumerate(s['sqls']):
        nome = f'{s["id"]}[{k}]'
        confere(f'{nome}: sem ; no fim', not sql.rstrip().endswith(';'))
        confere(f'{nome}: começa com SELECT', sql.startswith('SELECT'))
        confere(f'{nome}: usa o sufixo', '010' in sql)
        confere(f'{nome}: filtra deletados', "D_E_L_E_T_ = ' '" in sql)
        confere(f'{nome}: sem relógio do banco', not re.search(r'SYSDATE|GETDATE|CURRENT_DATE', sql, re.I))
        confere(f"{nome}: sem <> ''", "<> ''" not in sql)
        confere(f'{nome}: sem subconsulta dentro de agregação',
                not re.search(r'(SUM|COUNT)\(\s*(DISTINCT\s+)?CASE WHEN (NOT )?EXISTS', sql))
        for proib in ('INSERT', 'UPDATE', 'DELETE ', 'MERGE', 'DROP', 'EXEC', ' INTO '):
            confere(f'{nome}: sem {proib}', proib not in sql.upper())
by = {s['id']: s for s in scripts}
cfg = by['crm_config']['sql']
confere('config lê MV_ZCRMMOD', "'MV_ZCRMMOD'" in cfg)
confere('token do CRM mascarado', "'MV_ZCRMTOK'" in cfg and "'(preenchido)'" in cfg)
confere('segredo de licença mascarado', all(f"'{p}'" in cfg.split('THEN')[0] for p in ('MV_ZLICTOK', 'MV_ZLICSEC')))
confere('contrato é a chave da cadeia', "ZA3_STG2 = 'S'" in by['crm_projetos']['sql']
        and 'RTRIM(ZA0_CONTRA) IN (' in by['crm_projetos']['sql'])
confere('CN9 pela chave do contrato', 'RTRIM(CN9_NUMERO) IN (' in by['crm_contratos']['sql'])
confere('CND pela chave do contrato', 'RTRIM(CND.CND_CONTRA) IN (' in by['crm_medicoes']['sqls'][0])
confere('medição: variante sem pedido', 'SC5' in by['crm_medicoes']['sqls'][0]
        and 'SC5' not in by['crm_medicoes']['sqls'][1])
confere('produto: variante sem B1_ZFATURA', 'B1_ZFATURA' in by['crm_cad_produtos']['sqls'][0]
        and 'B1_ZFATURA' not in by['crm_cad_produtos']['sqls'][1])
confere('produto PRJ (criado pela integração) fora', "NOT LIKE 'PRJ%'" in by['crm_cad_produtos']['sql'])
confere('vigência com data de hoje', "DA0.DA0_DATDE <= '20261030'" in by['crm_cad_produtos']['sql']
        and "DA0.DA0_DATATE >= '20261030'" in by['crm_cad_produtos']['sql'])
confere('fim de vigência vazio vale', "RTRIM(DA0.DA0_DATATE) IS NULL" in by['crm_cad_produtos']['sql'])
pend = by['crm_pendentes_lista']['sqls']
confere('erro memo: BLOB → CLOB → sem mensagem', len(pend) == 3
        and 'UTL_RAW' in pend[0] and 'UTL_RAW' not in pend[1] and 'AS ERRO' not in pend[2])
confere('pendentes: erro ou fila', "ZA3_STG1 IN ('R','P')" in pend[0] and "ZA3_STG2 = 'E'" in pend[0])
confere('rastreio ignora revisão antiga', "CN9_SITUAC <> '10'" in by['crm_rastreio_lista']['sql'])
confere('sem corte: nenhuma data na ZA3', 'ZA3_DTINC >=' not in by['crm_totais']['sql'])
mssql = ns['_integ_scripts']('010', HOJE, None, 'mssql', ['crm'])
confere('SQL Server: memo por VARBINARY', 'VARBINARY' in mssql[ESPERADOS.index('crm_pendentes_lista')]['sqls'][0])
confere('sufixo de outra base', 'ZA3020' in ns['_integ_scripts']('020', HOJE, None, None, ['crm'])[1]['sql'])

corte = {x['id']: x for x in ns['_integ_scripts']('010', HOJE, date(2026, 10, 1), 'oracle', ['crm'])}
for i in ('crm_totais', 'crm_situacao', 'crm_fila'):
    confere(f'corte em {i}', "ZA3_DTINC >= '20261001'" in corte[i]['sql'])
confere('corte nos erros (alias E)', "E.ZA3_DTINC >= '20261001'" in corte['crm_erros']['sql'])
confere('corte no conjunto de contratos', "Z.ZA3_DTINC >= '20261001'" in corte['crm_contratos']['sql'])
confere('corte não mexe no cadastro', '20261001' not in corte['crm_cad_produtos']['sql'])

# Os três grupos juntos: resumos de todos antes dos detalhes (a coleta reordena)
todos = ns['_integ_scripts']('010', HOJE, None, 'oracle', ['rh', 'transmite', 'crm'], AGORA)
confere('três grupos somam os blocos', len(todos) == 10 + 13 + len(ESPERADOS))

# ── causa do erro ───────────────────────────────────────────────────────────
C = ns['_crm_causa']
confere('produto sem preço na tabela = tabela', C('Produto 000123 sem preço na tabela de preço 001') == 'tabela')
confere('cliente', C('Cliente 000045/01 não encontrado (SA1)') == 'cliente')
confere('vendedor', C('Vendedor 000010 inexistente') == 'vendedor')
confere('produto', C('Produto XPTO não cadastrado na SB1') == 'produto')
confere('condição', C('Condição de pagamento C36 não existe') == 'condicao')
confere('tipo de contrato', C('tipoVenda 007 não existe na CN1') == 'tipo_contrato')
confere('duplicidade antes de tudo', C('Oportunidade já recebida (messageId duplicado)') == 'duplicidade')
confere('JSON', C('JSON inválido: campo garantia obrigatório') == 'mensagem')
confere('infra', C('Timeout na conexão') == 'ambiente')
confere('vazio', C('') == 'sem_texto' and C(None) == 'sem_texto')
confere('outros', C('Falha desconhecida xyz') == 'outros')

blk = {'ok': True, 'linhas': [
    {'STG1': 'L', 'STG2': 'E', 'ERRO': 'Cliente 1 inexistente', 'JA_OK': 'N'},
    {'STG1': 'E', 'STG2': 'N', 'ERRO': 'messageId já recebido', 'JA_OK': 'N'},
    {'STG1': 'L', 'STG2': 'E', 'ERRO': 'Produto X não existe', 'JA_OK': 'S'},
    {'STG1': 'L', 'STG2': 'A', 'ERRO': '', 'JA_OK': 'N'}]}
ns['_crm_anota_causas'](blk)
confere('causa por linha em erro', blk['linhas'][0]['CAUSA'] == 'cliente' and blk['linhas'][2]['CAUSA'] == 'produto')
confere('linha da fila sem causa', 'CAUSA' not in blk['linhas'][3])
confere('resumo ignora erro já reprocessado', blk['causas'] == {'cliente': 1, 'duplicidade': 1})

# ── idade na fila ───────────────────────────────────────────────────────────
confere('idade em minutos', ns['_crm_idade_min']('20261030', '08:30:00', AGORA) == 90)
confere('idade de ontem', ns['_crm_idade_min']('20261029', '10:00:00', AGORA) == 1440)
confere('sem relógio = None', ns['_crm_idade_min']('20261030', '08:30', None) is None)


def ind(inds, chave):
    return next(i for i in inds if i['chave'] == chave)


def B(linhas, **kw):
    return {'ok': True, 'linhas': linhas, **kw}


# ── cenário saudável (base de testes com o fluxo rodando) ───────────────────
saudavel = {
    'crm_config': B([{'PARAMETRO': 'MV_ZCRMMOD', 'FILIAL': '', 'CONTEUDO': '2'},
                     {'PARAMETRO': 'MV_ZMAILPP', 'FILIAL': '', 'CONTEUDO': 'contratos@digitro.com'},
                     {'PARAMETRO': 'MV_ZCRMTOK', 'FILIAL': '', 'CONTEUDO': '(preenchido)'}]),
    'crm_totais': B([{'MENSAGENS': '6', 'PROPOSTAS': '5', 'LIBERADAS': '5', 'TRATADAS': '4',
                      'CONTRATOS_ZA3': '4', 'RETORNADAS': '0', 'MAIS_ANTIGA': '20261001', 'MAIS_RECENTE': '20261029'}]),
    'crm_situacao': B([{'STG1': 'L', 'STG2': 'S', 'STIPA': 'N', 'QTD': '4'},
                       {'STG1': 'L', 'STG2': 'E', 'STIPA': 'N', 'QTD': '1'},
                       {'STG1': 'L', 'STG2': 'A', 'STIPA': 'N', 'QTD': '1'}]),
    'crm_fila': B([{'STG1': 'L', 'STG2': 'A', 'DIA': '20261030', 'QTD': '1', 'PRIMEIRA': '09:40:00'}]),
    'crm_erros': B([{'STG1': 'L', 'STG2': 'E', 'DIA': '20261020', 'QTD': '1', 'PROPOSTAS': '1', 'SEM_SUCESSO': '0'}]),
    'crm_projetos': B([{'TPPROD': '1', 'STATUS': '1', 'QTD': '5', 'CONTRATOS': '3'},
                       {'TPPROD': '2', 'STATUS': '1', 'QTD': '2', 'CONTRATOS': '1'}]),
    'crm_contratos': B([{'SITUAC': '02', 'CONTRATOS': '3', 'REVISOES': '3'},
                        {'SITUAC': '05', 'CONTRATOS': '1', 'REVISOES': '2'}]),
    'crm_medicoes': B([{'SITUAC': 'E', 'QTD': '2', 'CONTRATOS': '1', 'COM_PEDIDO': '2'}]),
    'crm_cad_produtos': B([{'TIPO': 'PA', 'ATIVOS': '80', 'COM_PRECO': '76', 'COM_ZFATURA': '80'},
                           {'TIPO': 'SV', 'ATIVOS': '20', 'COM_PRECO': '19', 'COM_ZFATURA': '20'}]),
    'crm_cad_tabelas': B([{'TABELA': '001', 'ATIVO': '1', 'DE': '20260101', 'ATE': '', 'ITENS': '90', 'COM_PRECO': '90'},
                          {'TABELA': '002', 'ATIVO': '2', 'DE': '20250101', 'ATE': '20251231', 'ITENS': '5', 'COM_PRECO': '5'}]),
    'crm_rastreio_lista': B([{'CONTRATO': '0001/2026', 'MEDICOES': '2'}, {'CONTRATO': '0002/2026', 'MEDICOES': '0'},
                             {'CONTRATO': '0003/2026', 'MEDICOES': '0'}, {'CONTRATO': '0004/2026', 'MEDICOES': '0'}]),
}
inds = ns['_integ_indicadores'](saudavel, {'ok': False}, HOJE, ['crm'], AGORA)
CHAVES = ['crm_recebidas', 'crm_erros', 'crm_fila', 'crm_contratos', 'crm_medicoes', 'crm_retorno',
          'crm_cad_produtos', 'crm_cad_tabelas', 'crm_params']
confere('nove indicadores do CRM', [i['chave'] for i in inds] == CHAVES)
confere('todos no grupo crm', all(i['grupo'] == 'crm' for i in inds))
confere('recebidas = propostas distintas', ind(inds, 'crm_recebidas')['valor'] == 5
        and '4 com projetos' in ind(inds, 'crm_recebidas')['texto'])
confere('erro já reprocessado não pesa', ind(inds, 'crm_erros')['nivel'] == 'verde'
        and ind(inds, 'crm_erros')['valor'] == 0 and 'reprocessados' in ind(inds, 'crm_erros')['texto'])
confere('fila de 20 min = verde', ind(inds, 'crm_fila')['nivel'] == 'verde' and ind(inds, 'crm_fila')['valor'] == 1)
confere('contratos achados = esperados', ind(inds, 'crm_contratos')['nivel'] == 'verde'
        and ind(inds, 'crm_contratos')['valor'] == 4 and '7 projeto(s)' in ind(inds, 'crm_contratos')['texto'])
confere('medidos pelo rastreio', ind(inds, 'crm_medicoes')['valor'] == '1/4'
        and '2 com pedido' in ind(inds, 'crm_medicoes')['texto'])
confere('retorno não implementado = cinza', ind(inds, 'crm_retorno')['nivel'] == 'cinza'
        and 'P11' in ind(inds, 'crm_retorno')['texto'])
confere('cobertura 95% = verde', ind(inds, 'crm_cad_produtos')['valor'] == '95%'
        and ind(inds, 'crm_cad_produtos')['nivel'] == 'verde' and 'B1_ZFATURA' in ind(inds, 'crm_cad_produtos')['texto'])
confere('1 tabela vigente', ind(inds, 'crm_cad_tabelas')['valor'] == 1 and ind(inds, 'crm_cad_tabelas')['nivel'] == 'verde')
confere('params ok', ind(inds, 'crm_params')['nivel'] == 'verde' and 'contratos@digitro.com' in ind(inds, 'crm_params')['texto'])
confere('situação geral verde (cinza não pesa)', ns['_integ_pior'](i['nivel'] for i in inds) == 'verde')

# ── cenário com problema ────────────────────────────────────────────────────
ruim = dict(saudavel)
ruim['crm_fila'] = B([{'STG1': 'L', 'STG2': 'A', 'DIA': '20261028', 'QTD': '2', 'PRIMEIRA': '15:00:00'},
                      {'STG1': 'R', 'STG2': 'N', 'DIA': '20261030', 'QTD': '1', 'PRIMEIRA': '07:00:00'}])
ruim['crm_erros'] = B([{'STG1': 'L', 'STG2': 'E', 'DIA': '20261027', 'QTD': '3', 'PROPOSTAS': '2', 'SEM_SUCESSO': '2'},
                       {'STG1': 'E', 'STG2': 'N', 'DIA': '20261030', 'QTD': '1', 'PROPOSTAS': '1', 'SEM_SUCESSO': '1'}])
ruim['crm_pendentes_lista'] = B([], causas={'produto': 2, 'duplicidade': 1})
ruim['crm_contratos'] = B([{'SITUAC': '02', 'CONTRATOS': '2', 'REVISOES': '2'},
                           {'SITUAC': '01', 'CONTRATOS': '1', 'REVISOES': '1'}])
ruim['crm_situacao'] = B([{'STG1': 'L', 'STG2': 'S', 'STIPA': 'E', 'QTD': '2'}])
ruim['crm_cad_produtos'] = B([{'TIPO': 'PA', 'ATIVOS': '100', 'COM_PRECO': '40'}])
ruim['crm_cad_tabelas'] = B([{'TABELA': '001', 'ATIVO': '1', 'DE': '20270101', 'ATE': '', 'ITENS': '9', 'COM_PRECO': '9'}])
ruim['crm_config'] = B([{'PARAMETRO': 'MV_ZCRMMOD', 'FILIAL': '', 'CONTEUDO': '1'}])
inds = ns['_integ_indicadores'](ruim, {'ok': False}, HOJE, ['crm'], AGORA)
confere('erro de 3 dias = vermelho', ind(inds, 'crm_erros')['nivel'] == 'vermelho' and ind(inds, 'crm_erros')['valor'] == 3)
confere('erro: etapas e causas no texto', 'Etapa 1 (recebimento) 1' in ind(inds, 'crm_erros')['texto']
        and 'Produto 2' in ind(inds, 'crm_erros')['texto'] and 'DIG00A05' in ind(inds, 'crm_erros')['texto'])
confere('fila parada há 1 d = vermelho', ind(inds, 'crm_fila')['nivel'] == 'vermelho' and ind(inds, 'crm_fila')['valor'] == 3)
confere('fila separa etapa 1', '1 presa(s) no recebimento' in ind(inds, 'crm_fila')['texto'])
confere('sucesso sem contrato = vermelho', ind(inds, 'crm_contratos')['nivel'] == 'vermelho'
        and 'não encontrado' in ind(inds, 'crm_contratos')['texto'] and 'cancelado' in ind(inds, 'crm_contratos')['texto'])
confere('retorno com erro = vermelho', ind(inds, 'crm_retorno')['nivel'] == 'vermelho')
confere('cobertura 40% = vermelho', ind(inds, 'crm_cad_produtos')['nivel'] == 'vermelho'
        and 'B1_ZFATURA' not in ind(inds, 'crm_cad_produtos')['texto'])
confere('tabela com início futuro não vale', ind(inds, 'crm_cad_tabelas')['nivel'] == 'vermelho')
confere('MV_ZCRMMOD 1 e sem e-mail = amarelo', ind(inds, 'crm_params')['nivel'] == 'amarelo'
        and 'MV_ZMAILPP' in ind(inds, 'crm_params')['texto'])

fila_hoje = dict(saudavel, crm_fila=B([{'STG1': 'L', 'STG2': 'A', 'DIA': '20261030', 'QTD': '1', 'PRIMEIRA': '08:00:00'}]))
confere('fila de 2 h = amarelo',
        ind(ns['_integ_indicadores'](fila_hoje, {}, HOJE, ['crm'], AGORA), 'crm_fila')['nivel'] == 'amarelo')
erro_hoje = dict(saudavel, crm_erros=B([{'STG1': 'L', 'STG2': 'E', 'DIA': '20261030', 'QTD': '1', 'SEM_SUCESSO': '1'}]))
confere('erro de hoje = amarelo',
        ind(ns['_integ_indicadores'](erro_hoje, {}, HOJE, ['crm'], AGORA), 'crm_erros')['nivel'] == 'amarelo')
sem_relogio = ind(ns['_integ_indicadores'](ruim, {}, HOJE, ['crm']), 'crm_fila')
confere('sem relógio: só a data (2 dias) = vermelho', sem_relogio['nivel'] == 'vermelho')

# ── produção ainda sem movimento (o retrato de hoje da Dígitro) ─────────────
vazio = {
    'crm_config': B([]),
    'crm_totais': B([{'MENSAGENS': '0', 'PROPOSTAS': '0', 'TRATADAS': '0', 'CONTRATOS_ZA3': '0'}]),
    'crm_situacao': B([]), 'crm_fila': B([]), 'crm_erros': B([]),
    'crm_projetos': B([]), 'crm_contratos': B([]), 'crm_medicoes': B([]),
    'crm_cad_produtos': B([]), 'crm_cad_tabelas': B([]),
}
inds = ns['_integ_indicadores'](vazio, {}, HOJE, ['crm'], AGORA)
confere('nada recebido = cinza', ind(inds, 'crm_recebidas')['nivel'] == 'cinza')
confere('sem erro e sem fila = verde', ind(inds, 'crm_erros')['nivel'] == 'verde' and ind(inds, 'crm_fila')['nivel'] == 'verde')
confere('sem contrato = cinza', ind(inds, 'crm_contratos')['nivel'] == 'cinza'
        and ind(inds, 'crm_medicoes')['nivel'] == 'cinza')
confere('sem produto ativo = vermelho (prontidão)', ind(inds, 'crm_cad_produtos')['nivel'] == 'vermelho')
confere('sem tabela = vermelho', ind(inds, 'crm_cad_tabelas')['nivel'] == 'vermelho')
confere('situação geral vermelha pelos cadastros', ns['_integ_pior'](i['nivel'] for i in inds) == 'vermelho')

# ── ZA3 inexistente (base sem o Painel compilado) ───────────────────────────
aus = {k: {'ok': False, 'ausente': True, 'erro': 'A tabela ZA3010 não existe nesta base.', 'linhas': []}
       for k in ('crm_totais', 'crm_situacao', 'crm_fila', 'crm_erros', 'crm_projetos', 'crm_contratos', 'crm_medicoes')}
aus.update({k: saudavel[k] for k in ('crm_config', 'crm_cad_produtos', 'crm_cad_tabelas')})
inds = ns['_integ_indicadores'](aus, {}, HOJE, ['crm'], AGORA)
confere('ZA3 ausente vira cinza com motivo', all(ind(inds, c)['nivel'] == 'cinza' and 'ZA3010' in ind(inds, c)['texto']
                                                for c in ('crm_recebidas', 'crm_erros', 'crm_fila', 'crm_contratos')))
confere('cadastros seguem medidos', ind(inds, 'crm_cad_produtos')['nivel'] == 'verde')
confere('bloco não lido = cinza', ind(ns['_integ_indicadores']({}, {}, HOJE, ['crm']), 'crm_params')['nivel'] == 'cinza')

print(f'{ok} asserções OK, {falhou} falha(s)')
raise SystemExit(1 if falhou else 0)
