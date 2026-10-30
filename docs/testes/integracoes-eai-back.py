# Teste das funções PURAS do grupo EAI × Schedule da aba Integrações (30/10/2026).
#
# Como rodar, de qualquer lugar:  python3 docs/testes/integracoes-eai-back.py
# Mesmo método do integracoes-crm-back.py: extrai o trecho do módulo em vez de
# importá-lo. Cobre: SQL dos blocos (sufixo só nas tabelas da empresa, sem ';',
# só SELECT, sem relógio do banco, sem URL/TRANS da XX3, máscara de senha,
# corte), e os níveis de cada indicador com o retrato REAL da Produção da
# Dígitro em 30/10/2026 (969 entregues sem retorno, 12 não entregues, XXF
# vazia, FWEAIRECE/FWEAISEND nunca executados, tabela de preço sem envio).
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
AGORA = datetime(2026, 10, 30, 10, 20, tzinfo=TZ)

# ── grupos ──────────────────────────────────────────────────────────────────
confere('eai é grupo conhecido', 'eai' in ns['INTEG_GRUPOS_BASE'])
confere('nulo continua = só RH', ns['_integ_grupos'](None) == ('rh',))
confere('eai sozinho', ns['_integ_grupos'](['eai']) == ('eai',))
confere('crm + eai na ordem da base', ns['_integ_grupos'](['eai', 'crm']) == ('crm', 'eai'))

# ── SQL dos blocos ──────────────────────────────────────────────────────────
scripts = ns['_integ_scripts']('010', HOJE, None, 'oracle', ['eai'], AGORA)
ids = [s['id'] for s in scripts]
ESPERADOS = ['eai_config', 'eai_adapters', 'eai_status', 'eai_abertas', 'eai_depara', 'eai_empresa',
             'eai_cadastros', 'eai_agendamentos', 'eai_agend_empfil', 'eai_tarefas', 'eai_agents',
             'eai_pendentes_lista']
confere('blocos do grupo EAI', ids == ESPERADOS)
confere('um detalhe, no fim', [s['id'] for s in scripts if s.get('detalhe')] == ['eai_pendentes_lista'])
SEM_SUFIXO = {'eai_depara', 'eai_empresa', 'eai_agendamentos', 'eai_agend_empfil', 'eai_tarefas', 'eai_agents'}
for s in scripts:
    for k, sql in enumerate(s['sqls']):
        nome = f'{s["id"]}[{k}]'
        confere(f'{nome}: sem ; no fim', not sql.rstrip().endswith(';'))
        confere(f'{nome}: começa com SELECT', sql.startswith('SELECT'))
        confere(f'{nome}: filtra deletados', "D_E_L_E_T_ = ' '" in sql)
        confere(f'{nome}: sem relógio do banco', not re.search(r'SYSDATE|GETDATE|CURRENT_DATE', sql, re.I))
        confere(f"{nome}: sem <> ''", "<> ''" not in sql)
        confere(f'{nome}: sem concatenação de campo', '||' not in sql)
        limpo = sql.replace("RTRIM(XX3_URL) > ' '", '')
        confere(f'{nome}: nunca lê XX3_URL ou XX3_TRANS em claro',
                'XX3_URL' not in limpo and 'XX3_TRANS' not in limpo)
        for proib in ('INSERT', 'UPDATE', 'DELETE ', 'MERGE', 'DROP', 'EXEC', ' INTO '):
            confere(f'{nome}: sem {proib}', proib not in sql.upper())
        if s['id'] in SEM_SUFIXO:
            confere(f'{nome}: tabela do framework sem sufixo', '010' not in sql)
        else:
            confere(f'{nome}: usa o sufixo', '010' in sql)
by = {s['id']: s for s in scripts}
confere('fila na XX3 da empresa', 'FROM XX3010' in by['eai_status']['sql'])
confere('adapters na XX4 da empresa', 'FROM XX4010' in by['eai_adapters']['sql'])
confere('agendamentos na XX1 sem sufixo', 'FROM XX1 X' in by['eai_agendamentos']['sqls'][0])
confere('tarefas na SCHDTSK', 'FROM SCHDTSK' in by['eai_tarefas']['sql'])
confere('senha do ESB mascarada', "'MV_EAIPASS'" in by['eai_config']['sql'] and "'(preenchido)'" in by['eai_config']['sql'])
confere('URL só como S/N', "XX3_URL) > ' '" in by['eai_status']['sql'] and 'COM_DESTINO' in by['eai_status']['sql'])
confere('abertas = status diferente de finalizada', "XX3_STATUS <> '2'" in by['eai_abertas']['sql'])
confere('abertas com janela de 30 dias', "XX3_TRDATA >= '20260930'" in by['eai_abertas']['sql'])
confere('retrato sem janela', 'XX3_TRDATA >=' not in by['eai_status']['sql'])
confere('esgotadas = 4 tentativas', 'XX3_TENTAT >= 4' in by['eai_status']['sql'])
confere('cadastros: SA1 a DA1 com sufixo', all(f'FROM {a}010' in by['eai_cadastros']['sql']
                                               for a in ('SA1', 'SB1', 'SA3', 'SE4', 'DA0')))
ag = by['eai_agendamentos']['sqls']
confere('recorrência CLOB: DBMS_LOB → SUBSTR → sem', len(ag) == 3 and 'DBMS_LOB.SUBSTR' in ag[0]
        and 'DBMS_LOB' not in ag[1] and 'RECORR' not in ag[2])
confere('marca os jobs do EAI', "LIKE 'FWEAIRECE%'" in ag[0])
pend = by['eai_pendentes_lista']['sqls']
confere('retorno CLOB com variantes', 'DBMS_LOB.SUBSTR(XX3_RETURN' in pend[0] and 'AS RETORNO' not in pend[-1])
confere('pendentes: mais antigas primeiro', pend[0].rstrip().endswith('ORDER BY XX3_TRDATA, XX3_TRHORA'))
mssql = {x['id']: x for x in ns['_integ_scripts']('010', HOJE, None, 'mssql', ['eai'])}
confere('SQL Server: texto por CONVERT', 'CONVERT(VARCHAR(300), XX3_RETURN)' in mssql['eai_pendentes_lista']['sqls'][0])
confere('sufixo de outra base', 'XX3020' in {x['id']: x for x in ns['_integ_scripts']('020', HOJE, None, None, ['eai'])}['eai_status']['sql'])
corte = {x['id']: x for x in ns['_integ_scripts']('010', HOJE, date(2026, 10, 25), 'oracle', ['eai'])}
confere('corte no retrato', "XX3_TRDATA >= '20261025'" in corte['eai_status']['sql'])
confere('corte vence a janela', "XX3_TRDATA >= '20261025'" in corte['eai_abertas']['sql'])
confere('corte não mexe no Schedule', '20261025' not in corte['eai_agendamentos']['sqls'][0])
todos = ns['_integ_scripts']('010', HOJE, None, 'oracle', ['crm', 'eai'], AGORA)
confere('crm + eai somam os blocos', len(todos) == 13 + len(ESPERADOS))


def ind(inds, chave):
    return next(i for i in inds if i['chave'] == chave)


def B(linhas, **kw):
    return {'ok': True, 'linhas': linhas, **kw}


def AD(rot, msg, envia='1', canal='3', metodo='2'):
    return {'ROTINA': rot, 'MENSAGEM': msg, 'ENVIA': envia, 'RECEBE': '2', 'METODO': metodo, 'CANAL': canal}


# ── Produção da Dígitro, 30/10/2026 10:05 (leitura real, só os números) ────
ADAPTERS = [AD('APCFG060', 'WHOIS', canal='2', metodo='1'), AD('APCFG230', 'BRANCH'),
            AD('CRMA980', 'CUSTOMERVENDOR'), AD('MATA010', 'ITEM'), AD('MATA030', 'CUSTOMERVENDOR', envia='2'),
            AD('MATA035', 'STOCKGROUP'), AD('MATA040', 'SELLER'), AD('MATA050', 'CARRIER'),
            AD('MATA360', 'PAYMENTCONDITION'), AD('OMSA010', 'PRICELISTHEADERITEM'), AD('QIEA030', 'UNITOFMEASURE')]
ST = lambda m, st, ch, q, ant, rec, esg='0': {'MENSAGEM': m, 'STATUS': st, 'CANAL': ch, 'TPTRAN': '1', 'QTD': str(q),
                                             'ESGOTADAS': esg, 'MAIS_ANTIGA': ant, 'MAIS_RECENTE': rec}
STATUS = [ST('BRANCH', '7', '3', 2, '20261028', '20261029'), ST('CARRIER', '7', '3', 6, '20261029', '20261029'),
          ST('CUSTOMERVENDOR', '7', '3', 821, '20261029', '20261029'), ST('ITEM', '7', '3', 81, '20261029', '20261029'),
          ST('PAYMENTCONDITION', '5', '3', 5, '20261029', '20261029', '5'),
          ST('PAYMENTCONDITION', '7', '3', 5, '20261029', '20261029'),
          ST('SELLER', '5', '1', 6, '20261030', '20261030', '6'), ST('SELLER', '7', '3', 11, '20261030', '20261030'),
          ST('STOCKGROUP', '5', '3', 1, '20261028', '20261028', '1'), ST('STOCKGROUP', '7', '3', 1, '20261028', '20261028'),
          ST('UNITOFMEASURE', '7', '3', 42, '20261028', '20261028')]
AB = lambda m, st, dia, q, h: {'MENSAGEM': m, 'STATUS': st, 'DIA': dia, 'QTD': str(q), 'PRIMEIRA': h}
ABERTAS = [AB('UNITOFMEASURE', '7', '20261028', 42, '15:35:27'), AB('BRANCH', '7', '20261028', 1, '15:20:11'), AB('BRANCH', '7', '20261029', 1, '10:35:19'),
           AB('STOCKGROUP', '5', '20261028', 1, '16:57:03'), AB('CUSTOMERVENDOR', '7', '20261029', 821, '16:00:47'),
           AB('ITEM', '7', '20261029', 81, '11:40:33'), AB('CARRIER', '7', '20261029', 6, '10:24:34'),
           AB('PAYMENTCONDITION', '5', '20261029', 5, '10:51:34'), AB('PAYMENTCONDITION', '7', '20261029', 5, '10:52:52'),
           AB('STOCKGROUP', '7', '20261028', 1, '17:06:00'), AB('SELLER', '5', '20261030', 6, '07:56:23'),
           AB('SELLER', '7', '20261030', 11, '08:49:27')]
AGEND = lambda c, r, ini, ult='', hr='': {'CODIGO': c, 'ROTINA': r, 'STATUS': '0', 'AMBIENTE': 'PRODUCAO',
                                         'INICIO': ini, 'ULTDIA': ult, 'ULTHOR': hr, 'EAI': 'S' if r.startswith('FWEAI') else 'N'}
CAD = [{'ALIAS': a, 'QTD': str(q)} for a, q in (('SA1', 820), ('SA2', 932), ('SB1', 844), ('SA3', 11), ('SE4', 5),
                                                ('SAH', 42), ('SA4', 6), ('SBM', 3), ('DA0', 7), ('DA1', 322))]
PROD = {
    'eai_config': B([{'PARAMETRO': 'MV_EAIPORT', 'FILIAL': '', 'CONTEUDO': 'WS_ERPProtheusToGFE'},
                     {'PARAMETRO': 'MV_EAIURL', 'FILIAL': '', 'CONTEUDO': ''},
                     {'PARAMETRO': 'MV_EAIPASS', 'FILIAL': '', 'CONTEUDO': ''}]),
    'eai_adapters': B(ADAPTERS), 'eai_status': B(STATUS), 'eai_abertas': B(ABERTAS),
    'eai_depara': B([]), 'eai_empresa': B([{'REFERENCIA': 'CRM-COMPANY'}]), 'eai_cadastros': B(CAD),
    'eai_agendamentos': B([AGEND('000001', "FINA711('01')", '20260625', '20261030', '10:00'),
                           AGEND('000002', 'FWEAISEND', '20261021'), AGEND('000003', 'FWEAIRECE', '20261021'),
                           AGEND('000004', 'FWEAICLEAR', '20261021', '20261021', '09:59')]),
    'eai_tarefas': B([{'CODIGO': '000001', 'STATUS': '2', 'QTD': '521'}, {'CODIGO': '000002', 'STATUS': '4', 'QTD': '1'},
                      {'CODIGO': '000003', 'STATUS': '4', 'QTD': '1'}]),
}
inds = ns['_integ_indicadores'](PROD, {}, HOJE, ['eai'], AGORA)
chaves = [i['chave'] for i in inds]
confere('nove indicadores', chaves == ['eai_sem_retorno', 'eai_falhas', 'eai_aguardando', 'eai_canal', 'eai_depara',
                                       'eai_cobertura', 'eai_jobs', 'eai_agendamentos', 'eai_params'])
confere('todos do grupo eai', all(i['grupo'] == 'eai' for i in inds))
i = ind(inds, 'eai_sem_retorno')
confere('969 entregues sem retorno, vermelho (mais de 24 h)', i['valor'] == 969 and i['nivel'] == 'vermelho')
confere('texto cita a mais antiga e o FWEAIRECE', '1 d' in i['texto'] and 'FWEAIRECE' in i['texto'])
i = ind(inds, 'eai_falhas')
confere('12 com falha, vermelho (esgotadas)', i['valor'] == 12 and i['nivel'] == 'vermelho' and 'tentar novamente' in i['texto'])
confere('nada aguardando envio = verde', ind(inds, 'eai_aguardando')['nivel'] == 'verde')
i = ind(inds, 'eai_canal')
confere('SELLER no canal ESB = amarelo', i['valor'] == 6 and i['nivel'] == 'amarelo' and 'SELLER' in i['texto'])
i = ind(inds, 'eai_depara')
confere('XXF vazia com envio = vermelho', i['valor'] == 0 and i['nivel'] == 'vermelho' and 'SELLER' in i['texto'])
i = ind(inds, 'eai_cobertura')
confere('tabela de preço sem envio = vermelho', i['nivel'] == 'vermelho' and 'PRICELISTHEADERITEM (DA0: 7' in i['texto']
        and i['valor'] == 1)
i = ind(inds, 'eai_jobs')
confere('FWEAIRECE/SEND nunca executaram = vermelho', i['nivel'] == 'vermelho' and 'FWEAIRECE agendado (000003) e nunca executou' in i['texto']
        and i['valor'] == '0/2')
confere('FWEAICLEAR atrasado aparece', 'FWEAICLEAR sem rodar' in i['texto'])
i = ind(inds, 'eai_agendamentos')
confere('3 agendamentos parados? não: 2 (o CLEAR rodou)', i['valor'] == 2 and i['nivel'] == 'vermelho'
        and '000002 FWEAISEND' in i['texto'] and '523 tarefa(s)' in i['texto'])
i = ind(inds, 'eai_params')
confere('MV_EAIPORT sem adapter ESB = amarelo', i['nivel'] == 'amarelo' and 'WS_ERPProtheusToGFE' in i['texto'])
confere('situação geral vermelha', ns['_integ_pior'](x['nivel'] for x in inds) == 'vermelho')

# ── saudável: retorno processado, XXF populada, jobs rodando ────────────────
sau = json.loads(json.dumps(PROD))
sau['eai_status'] = B([ST('CUSTOMERVENDOR', '2', '3', 800, '20261029', '20261030'),
                       ST('ITEM', '2', '3', 80, '20261029', '20261030'),
                       ST('PRICELISTHEADERITEM', '2', '3', 7, '20261030', '20261030'),
                       ST('SELLER', '7', '3', 2, '20261030', '20261030')])
sau['eai_abertas'] = B([AB('SELLER', '7', '20261030', 2, '10:10:00')])
sau['eai_depara'] = B([{'ALIAS': 'SA1', 'QTD': '800'}, {'ALIAS': 'SB1', 'QTD': '80'}, {'ALIAS': 'DA0', 'QTD': '7'},
                       {'ALIAS': 'SA3', 'QTD': '11'}])
sau['eai_agendamentos'] = B([AGEND('000002', 'FWEAISEND', '20261021', '20261030', '10:15'),
                             AGEND('000003', 'FWEAIRECE', '20261021', '20261030', '10:18'),
                             AGEND('000004', 'FWEAICLEAR', '20261021', '20261030', '05:00')])
sau['eai_config'] = B([{'PARAMETRO': 'MV_EAIURL', 'FILIAL': '', 'CONTEUDO': ''}])
inds = ns['_integ_indicadores'](sau, {}, HOJE, ['eai'], AGORA)
confere('entregue há 10 min = verde', ind(inds, 'eai_sem_retorno')['nivel'] == 'verde' and ind(inds, 'eai_sem_retorno')['valor'] == 2)
confere('sem falha = verde', ind(inds, 'eai_falhas')['nivel'] == 'verde')
confere('canal coerente = verde', ind(inds, 'eai_canal')['nivel'] == 'verde')
confere('de-para cobrindo = verde', ind(inds, 'eai_depara')['nivel'] == 'verde')
confere('falta envio de alguns? STOCKGROUP/UNIT/CARRIER sem msg = vermelho',
        ind(inds, 'eai_cobertura')['nivel'] == 'vermelho')
lim = dict(sau, eai_depara=B(sau['eai_depara']['linhas'] + [{'ALIAS': a, 'QTD': '1'} for a in ('SBM', 'SAH', 'SA4', 'SE4')]))
confere('mensagem já limpa pelo FWEAICLEAR mas com de-para = não falta',
        ind(ns['_integ_indicadores'](lim, {}, HOJE, ['eai'], AGORA), 'eai_cobertura')['nivel'] == 'verde')
confere('jobs rodando = verde 2/2', ind(inds, 'eai_jobs')['nivel'] == 'verde' and ind(inds, 'eai_jobs')['valor'] == '2/2')
confere('nenhum agendamento parado', ind(inds, 'eai_agendamentos')['nivel'] == 'verde')
confere('parâmetros coerentes', ind(inds, 'eai_params')['nivel'] == 'verde')
i = ind(ns['_integ_indicadores'](dict(sau, eai_abertas=B([AB('SELLER', '7', '20261030', 2, '09:00:00')])),
                                 {}, HOJE, ['eai'], AGORA), 'eai_sem_retorno')
confere('entregue há 80 min = amarelo', i['nivel'] == 'amarelo')
i = ind(ns['_integ_indicadores'](dict(sau, eai_abertas=B([AB('ITEM', '0', '20261030', 3, '07:00:00')])),
                                 {}, HOJE, ['eai'], AGORA), 'eai_aguardando')
confere('parada antes do envio há 3 h = vermelho', i['nivel'] == 'vermelho' and 'FWEAISEND' in i['texto'])
esb = dict(sau, eai_adapters=B([AD('MATA040', 'SELLER', canal='1')]))
confere('adapter ESB sem MV_EAIURL = vermelho', ind(ns['_integ_indicadores'](esb, {}, HOJE, ['eai'], AGORA), 'eai_params')['nivel'] == 'vermelho')
sem_job = dict(sau, eai_agendamentos=B([]))
i = ind(ns['_integ_indicadores'](sem_job, {}, HOJE, ['eai'], AGORA), 'eai_jobs')
confere('adapter assíncrono sem FWEAIRECE agendado = vermelho', i['nivel'] == 'vermelho' and 'FWEAIRECE não agendado' in i['texto'])
confere('sem agendamento = cinza no parados', ind(ns['_integ_indicadores'](sem_job, {}, HOJE, ['eai'], AGORA),
                                                 'eai_agendamentos')['nivel'] == 'cinza')

# ── tabelas ausentes / bloco não lido ───────────────────────────────────────
aus = {k: {'ok': False, 'ausente': True, 'erro': 'A tabela XX3010 não existe nesta base.', 'linhas': []}
       for k in ('eai_status', 'eai_abertas')}
inds = ns['_integ_indicadores'](aus, {}, HOJE, ['eai'], AGORA)
confere('XX3 ausente vira cinza com motivo', all(ind(inds, c)['nivel'] == 'cinza' and 'XX3010' in ind(inds, c)['texto']
                                                 for c in ('eai_sem_retorno', 'eai_falhas', 'eai_aguardando')))
confere('nada lido = tudo cinza', ns['_integ_pior'](x['nivel'] for x in ns['_integ_indicadores']({}, {}, HOJE, ['eai'])) == 'cinza')
confere('sem relógio usa só a data', ind(ns['_integ_indicadores'](PROD, {}, HOJE, ['eai'], None), 'eai_sem_retorno')['nivel'] == 'vermelho')
confere('idade formatada', ns['_eai_fmt_idade'](45) == '45 min' and ns['_eai_fmt_idade'](125) == '2 h 5 min'
        and ns['_eai_fmt_idade'](1500) == '1 d 1 h')

print(f'{ok} asserções OK, {falhou} falha(s)')
raise SystemExit(1 if falhou else 0)
