# Teste das funções PURAS da aba Integrações.
#
# Como rodar, de qualquer lugar:  python3 docs/testes/integracoes-back.py
# Extrai o trecho do módulo em vez de importá-lo: api/index.py sobe Flask e
# exige DATABASE_URL. Cobre: SQL dos blocos (sufixo, datas, sem ';', sem
# credencial), parser do CSV do TSCMONITREST, classificação de tabela
# inexistente, itens do healthcheck e as regras de nível de cada indicador.
import csv, io, json, pathlib, re
from datetime import date, timedelta

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('INTEG_PARAMS = (')
fim = src.index('def _integ_health(cfg')
import unicodedata
ns = {'re': re, 'csv': csv, 'io': io, 'json': json, 'date': date, 'timedelta': timedelta,
      'unicodedata': unicodedata}
exec(compile(src[ini:fim], 'integ', 'exec'), ns)

ok = falhou = 0


def confere(nome, cond):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome)


HOJE = date(2026, 10, 13)

# ── SQL dos blocos ──────────────────────────────────────────────────────────
scripts = ns['_integ_scripts']('010', HOJE)
ids = [s['id'] for s in scripts]
confere('dez blocos', len(scripts) == 10)
confere('resumos antes dos detalhes',
        ids.index('rje_sst') < ids.index('rum_pendencias'))
for s in scripts:
    confere(f'{s["id"]}: sem ; no fim', not s['sql'].rstrip().endswith(';'))
    confere(f'{s["id"]}: começa com SELECT', s['sql'].startswith('SELECT'))
    confere(f'{s["id"]}: usa o sufixo', '010' in s['sql'])
    confere(f'{s["id"]}: filtra deletados', "D_E_L_E_T_ = ' '" in s['sql'])
    for proib in ('INSERT', 'UPDATE', 'DELETE ', 'MERGE', 'DROP', 'EXEC', ' INTO '):
        confere(f'{s["id"]}: sem {proib}', proib not in s['sql'].upper())
cfg_sql = scripts[0]['sql']
for segredo in ('MV_EMAILQR', 'MV_SENHAQR', 'MV_AHGORA1', 'MV_AHGORA2'):
    confere(f'config não lê {segredo}', segredo not in cfg_sql)
rum = next(s for s in scripts if s['id'] == 'rum_resumo')['sql']
confere('data de hoje como literal', "'20261013'" in rum)
vaz = next(s for s in scripts if s['id'] == 'rjp_vazao')['sql']
confere('janela de 7 dias', "'20261006'" in vaz)
fila = next(s for s in scripts if s['id'] == 'rjp_fila')['sql']
confere('vazio robusto (Oracle e SQL Server)',
        "RTRIM(RJP_DTIN) IS NULL OR RTRIM(RJP_DTIN) = ''" in fila)
confere('sufixo de outra base', 'RUM020' in ns['_integ_scripts']('020', HOJE)[4]['sql'])

# ── corte por data (13/10/2026) ─────────────────────────────────────────────
corte = {x['id']: x['sql'] for x in ns['_integ_scripts']('010', HOJE, date(2026, 10, 1))}
confere('corte na fila RJP', "RJP_DTGER >= '20261001'" in corte['rjp_fila'])
confere('corte nas pendências RJP', "RJP_DTGER >= '20261001'" in corte['rjp_antigos'])
confere('corte no resumo RUM', "RUM_DATMOV >= '20261001'" in corte['rum_resumo'])
confere('corte no detalhe RUM', "RUM.RUM_DATMOV >= '20261001'" in corte['rum_pendencias'])
confere('corte no RJE', "RJE_DTG >= '20261001'" in corte['rje_sst'] and "RJE_DTG >= '20261001'" in corte['rje_pendentes'])
confere('corte não mexe nos parâmetros', 'DTGER' not in corte['config'] and '2026' not in corte['config'])
confere('janela de 7 dias continua quando o corte é mais antigo', "'20261006'" in corte['rjp_vazao'])
recente = {x['id']: x['sql'] for x in ns['_integ_scripts']('010', HOJE, date(2026, 10, 10))}
confere('corte mais recente encurta a janela', "'20261010'" in recente['rjp_vazao'] and "'20261010'" in recente['ru7_erros'])
sem = {x['id']: x['sql'] for x in ns['_integ_scripts']('010', HOJE, None)}
confere('sem corte não filtra', 'RJP_DTGER >=' not in sem['rjp_fila'] and 'RUM_DATMOV >=' not in sem['rum_resumo'])
confere('corte sem ;', all(not v.rstrip().endswith(';') for v in corte.values()))
confere('_integ_desde aceita ISO', ns['_integ_desde']('2026-10-01') == date(2026, 10, 1))
confere('_integ_desde aceita date', ns['_integ_desde'](date(2026, 10, 1)) == date(2026, 10, 1))
confere('_integ_desde vazio', ns['_integ_desde'](None) is None and ns['_integ_desde']('xx') is None)

# ── motivo da inconsistência (14/10/2026) ───────────────────────────────────
cl = ns['_integ_classifica']
casos = {
    'E-mail já cadastrado.': ('cadastro', 'duplicidade/conflito'),
    'PIS já cadastrado.': ('cadastro', 'duplicidade/conflito'),
    'matrícula: 998877 - O afastamento possui intersecção com outro(s) já cadastrado(s).': ('cadastro', 'duplicidade/conflito'),
    'Centro de custo inválido': ('cadastro', 'tabela de apoio'),
    'CNPJ inválido': ('cadastro', 'tabela de apoio'),
    'Escala 0101001 não encontrada': ('cadastro', 'tabela de apoio'),
    'CPF Inválido': ('campo', None),
    'Data de nascimento inválida': ('campo', None),
    'Nao existe licenca disponivel no License Server para atender a requisicao nesse momento.': ('licenca', None),
    'Internal Server Error': ('integracao', None),
    'Unauthorized': ('integracao', None),
    'xyz qualquer coisa': ('outros', None),
    '': ('outros', None),
}
for txt, esperado in casos.items():
    confere(f'classifica: {txt[:40]}', cl(txt) == esperado)
confere('acento corrompido ainda classifica', cl('CPF Inv?lido')[0] == 'campo')
mot = ns['_integ_motivos']([
    {'TIPO': '2', 'OPER': 'A', 'MENSAGEM': 'matrícula: 0101002798 - O afastamento possui intersecção com outro(s) já cadastrado(s).'},
    {'TIPO': '2', 'OPER': 'A', 'MENSAGEM': 'matrícula: 0101002799 - O afastamento possui intersecção com outro(s) já cadastrado(s).'},
    {'TIPO': '1', 'OPER': 'I', 'MENSAGEM': 'Centro de custo inválido | CPF Inválido'},
    {'TIPO': '1', 'OPER': 'I', 'MENSAGEM': 'Nao existe licenca disponivel no License Server'},
    {'TIPO': '1', 'OPER': 'I', 'MENSAGEM': ''}])
confere('motivos: registros', mot['registros'] == 5 and mot['sem_mensagem'] == 1)
confere('motivos: matrícula mascarada agrupa', mot['motivos'][0]['qtd'] == 2 and '…' in mot['motivos'][0]['texto'])
confere('motivos: registro com dois motivos conta uma vez na categoria',
        mot['categorias']['cadastro'] == 3 and mot['categorias']['campo'] == 0)
confere('motivos: licença', mot['categorias']['licenca'] == 1)
confere('motivos: os dois pedaços viram motivos', mot['motivos_total'] == 4)
confere('motivos: afeta por tipo', mot['motivos'][0]['tipos'] == {'2': 2})
# variantes de leitura do memo
sc = {x['id']: x for x in ns['_integ_scripts']('010', HOJE, None, 'oracle')}
confere('memo oracle: BLOB, CLOB e sem mensagem', len(sc['rum_pendencias']['sqls']) == 3
        and 'UTL_RAW.CAST_TO_VARCHAR2(DBMS_LOB.SUBSTR(RUM.RUM_STAMSN, 400, 1))' in sc['rum_pendencias']['sqls'][0]
        and 'UTL_RAW' not in sc['rum_pendencias']['sqls'][1] and 'DBMS_LOB.SUBSTR' in sc['rum_pendencias']['sqls'][1]
        and 'STAMSN' not in sc['rum_pendencias']['sqls'][2])
confere('sql = primeira variante', sc['rum_pendencias']['sql'] == sc['rum_pendencias']['sqls'][0])
confere('motivos só status 3', "RUM_STATUS = '3'" in sc['rum_motivos']['sql'] and len(sc['rum_motivos']['sqls']) == 2)
confere('blocos sem variante têm sqls de 1', len(sc['rjp_fila']['sqls']) == 1)
ms = {x['id']: x for x in ns['_integ_scripts']('010', HOJE, None, 'mssql')}
confere('memo SQL Server', 'CONVERT(VARBINARY(400), RUM.RUM_STAMSN)' in ms['rum_pendencias']['sql'])
pg = {x['id']: x for x in ns['_integ_scripts']('010', HOJE, None, 'postgres')}
confere('postgres sem mensagem e sem bloco de motivos', 'STAMSN' not in pg['rum_pendencias']['sql'] and 'rum_motivos' not in pg)
cm = {x['id']: x['sql'] for x in ns['_integ_scripts']('010', HOJE, date(2026, 10, 1), 'oracle')}
confere('corte nos motivos', "RUM_DATMOV >= '20261001'" in cm['rum_motivos'])
# indicador detalha os motivos
com_mot = dict({'rum_resumo': {'ok': True, 'linhas': [{'TIPO': '1', 'OPER': 'I', 'STATUS': '3', 'QTD': '4',
                 'MOV_MAIS_ANTIGO': '20261013', 'ULT_INTEGRACAO': '20261014', 'ATRASADOS': '0'}]},
                'rum_motivos': {'ok': True, 'linhas': [], 'resumo': mot}})
ii = next(i for i in ns['_integ_indicadores'](com_mot, {'ok': False}, HOJE) if i['chave'] == 'ahgora_inconsistencias')
confere('indicador traz motivos', 'Cadastro 3' in ii['texto'] and 'Licença 1' in ii['texto'] and 'Campo' not in ii['texto'])

# ── CSV ─────────────────────────────────────────────────────────────────────
linhas = ns['_integ_csv']('PARAMETRO;FILIAL;CONTEUDO\nMV_URIQR;;https://app.quirons.com/ttalk/\n'
                          'MV_RHNG;  ;.T.\n')
confere('csv: duas linhas', len(linhas) == 2)
confere('csv: URL inteira (separador fixo ;)', linhas[0]['CONTEUDO'] == 'https://app.quirons.com/ttalk/')
confere('csv: strip', linhas[1]['FILIAL'] == '')
confere('csv vazio', ns['_integ_csv']('') == [])

# ── motivo do erro ──────────────────────────────────────────────────────────
aus, msg = ns['_integ_motivo']('ORA-00942: table or view does not exist', 'RUM010')
confere('tabela ausente vira ausente', aus and 'RUM010' in msg)
aus, msg = ns['_integ_motivo']('ORA-00904: "RJP_HORAIN": invalid identifier', 'RJP010')
confere('campo inexistente não é ausente', not aus and 'dicionário' in msg)

# ── healthcheck ─────────────────────────────────────────────────────────────
laudo = {"ok": True, "laudo": {"protheus": [
    {"id": "P1", "status": "ok", "mensagem": "REST publicado"},
    {"id": "P2", "status": "aviso", "mensagem": "401 sem senha"},
    {"id": "P6", "status": "erro", "mensagem": "GPEM923 não agendado"}],
    "quirons": [{"codigo": "Q1", "ok": True}, {"codigo": "Q3", "ok": False, "message": "timeout"}]}}
itens = ns['_integ_health_itens'](laudo)
confere('health: 5 itens', len(itens) == 5)
confere('health: bool vira erro', any(i['id'] == 'Q3' and i['status'] == 'erro' for i in itens))
confere('health: mensagem', any(i['id'] == 'Q3' and i['mensagem'] == 'timeout' for i in itens))


def bloco(*linhas):
    return {'ok': True, 'linhas': list(linhas)}


def ind(inds, chave):
    return next(i for i in inds if i['chave'] == chave)


# ── indicadores: cenário saudável ───────────────────────────────────────────
saudavel = {
    'config': bloco({'PARAMETRO': 'MV_RHNG', 'FILIAL': '', 'CONTEUDO': '.T.'},
                    {'PARAMETRO': 'MV_RHMSGNG', 'FILIAL': '', 'CONTEUDO': '100'},
                    {'PARAMETRO': 'MV_HISTQUI', 'FILIAL': '', 'CONTEUDO': '1'}),
    'rjp_fila': bloco({'FILIAL': '', 'TABELA': 'SRA', 'OPER': 'A', 'QTD': '12', 'MAIS_ANTIGO': '20261013'}),
    'rjp_vazao': bloco({'DIA': '20261012', 'QTD': '40', 'PRIMEIRA': '06:00', 'ULTIMA': '18:30'},
                       {'DIA': '20261013', 'QTD': '9', 'PRIMEIRA': '06:00', 'ULTIMA': '09:15'}),
    'ru7_erros': bloco(),
    'rum_resumo': bloco({'TIPO': '1', 'OPER': 'A', 'STATUS': '6', 'QTD': '800', 'MOV_MAIS_ANTIGO': '20250101',
                         'ULT_INTEGRACAO': '20261013', 'ATRASADOS': '0'},
                        {'TIPO': '1', 'OPER': 'A', 'STATUS': '0', 'QTD': '3', 'MOV_MAIS_ANTIGO': '20261013',
                         'ULT_INTEGRACAO': '', 'ATRASADOS': '0'}),
    'rje_sst': bloco({'EVENTO': 'S2220', 'STATUS': '4', 'QTD': '30', 'MAIS_ANTIGO': '20260901', 'MAIS_RECENTE': '20261010'}),
}
health_ok = {'ok': True, 'itens': [{'id': 'P1', 'status': 'ok', 'mensagem': ''},
                                   {'id': 'P2', 'status': 'aviso', 'mensagem': '401'}]}
inds = ns['_integ_indicadores'](saudavel, health_ok, HOJE)
confere('8 indicadores', len(inds) == 8)
confere('fila Quírons verde', ind(inds, 'quirons_fila')['nivel'] == 'verde' and ind(inds, 'quirons_fila')['valor'] == 12)
confere('envios verde e somados', ind(inds, 'quirons_envios')['valor'] == 49 and ind(inds, 'quirons_envios')['nivel'] == 'verde')
confere('último envio no texto', '09:15' in ind(inds, 'quirons_envios')['texto'])
confere('erros zerados verde', ind(inds, 'quirons_erros')['nivel'] == 'verde')
confere('Ahgora do dia não é atraso', ind(inds, 'ahgora_nao_enviados')['nivel'] == 'verde'
        and ind(inds, 'ahgora_nao_enviados')['valor'] == 3)
confere('SST tudo transmitido', ind(inds, 'sst_pendentes')['nivel'] == 'verde')
confere('P2 em aviso não pesa', ind(inds, 'quirons_laudo')['nivel'] == 'verde'
        and ind(inds, 'quirons_laudo')['valor'] == '2/2')
confere('geral verde', ns['_integ_pior'](i['nivel'] for i in inds) == 'verde')

# ── indicadores: cenário com problema ───────────────────────────────────────
ruim = dict(saudavel)
ruim['rjp_fila'] = bloco({'FILIAL': '', 'TABELA': 'SRA', 'OPER': 'A', 'QTD': '250', 'MAIS_ANTIGO': '20261013'})
ruim['rjp_vazao'] = bloco({'DIA': '20261010', 'QTD': '5', 'PRIMEIRA': '06:00', 'ULTIMA': '06:10'})
ruim['ru7_erros'] = bloco({'DIA': '20261012', 'COD_HTTP': '401', 'QTD': '1'})
ruim['rum_resumo'] = bloco(
    {'TIPO': '1', 'OPER': 'A', 'STATUS': '3', 'QTD': '7', 'MOV_MAIS_ANTIGO': '20261001', 'ULT_INTEGRACAO': '20261001', 'ATRASADOS': '0'},
    {'TIPO': '2', 'OPER': 'I', 'STATUS': '4', 'QTD': '2', 'MOV_MAIS_ANTIGO': '20261005', 'ULT_INTEGRACAO': '20261005', 'ATRASADOS': '2'},
    {'TIPO': '2', 'OPER': 'I', 'STATUS': '0', 'QTD': '4', 'MOV_MAIS_ANTIGO': '20261008', 'ULT_INTEGRACAO': '', 'ATRASADOS': '4'})
ruim['rje_sst'] = bloco({'EVENTO': 'S2220', 'STATUS': '3', 'QTD': '2', 'MAIS_ANTIGO': '20261001', 'MAIS_RECENTE': '20261002'})
health_ruim = {'ok': True, 'itens': [{'id': 'P6', 'status': 'erro', 'mensagem': ''}]}
inds = ns['_integ_indicadores'](ruim, health_ruim, HOJE)
confere('fila acima de 2x lote = amarelo', ind(inds, 'quirons_fila')['nivel'] == 'amarelo')
confere('fila parada com pendência = vermelho', ind(inds, 'quirons_envios')['nivel'] == 'vermelho')
confere('401 = vermelho', ind(inds, 'quirons_erros')['nivel'] == 'vermelho' and '401' in ind(inds, 'quirons_erros')['texto'])
confere('7 inconsistências = vermelho', ind(inds, 'ahgora_inconsistencias')['nivel'] == 'vermelho')
confere('retorno perdido = vermelho', ind(inds, 'ahgora_aguardando')['valor'] == 2
        and ind(inds, 'ahgora_aguardando')['nivel'] == 'vermelho')
confere('não enviado há 5 dias = vermelho', ind(inds, 'ahgora_nao_enviados')['nivel'] == 'vermelho')
confere('SST velho = vermelho', ind(inds, 'sst_pendentes')['nivel'] == 'vermelho'
        and 'S2220 2' in ind(inds, 'sst_pendentes')['texto'])
confere('laudo com erro = vermelho', ind(inds, 'quirons_laudo')['nivel'] == 'vermelho')

# fila muito grande, mas de hoje
grande = dict(saudavel)
grande['rjp_fila'] = bloco({'FILIAL': '', 'TABELA': 'SRA', 'OPER': 'I', 'QTD': '400', 'MAIS_ANTIGO': '20261013'})
confere('> 3x lote = vermelho',
        ind(ns['_integ_indicadores'](grande, health_ok, HOJE), 'quirons_fila')['nivel'] == 'vermelho')
# pendência de ontem dentro do lote
ontem = dict(saudavel)
ontem['rjp_fila'] = bloco({'FILIAL': '', 'TABELA': 'SRB', 'OPER': 'I', 'QTD': '5', 'MAIS_ANTIGO': '20261012'})
confere('pendência de ontem = amarelo',
        ind(ns['_integ_indicadores'](ontem, health_ok, HOJE), 'quirons_fila')['nivel'] == 'amarelo')

# ── base sem Ahgora e com histórico desligado ───────────────────────────────
sem = dict(saudavel)
sem['rum_resumo'] = {'ok': False, 'ausente': True, 'erro': 'A tabela RUM010 não existe nesta base', 'linhas': []}
sem['config'] = bloco({'PARAMETRO': 'MV_HISTQUI', 'FILIAL': '', 'CONTEUDO': '0'})
inds = ns['_integ_indicadores'](sem, {'ok': False, 'mensagem': 'Healthcheck não existe'}, HOJE)
confere('sem RUM = três cinzas', all(ind(inds, c)['nivel'] == 'cinza' for c in
        ('ahgora_inconsistencias', 'ahgora_aguardando', 'ahgora_nao_enviados')))
confere('motivo da tabela ausente no texto', 'RUM010' in ind(inds, 'ahgora_aguardando')['texto'])
confere('MV_HISTQUI 0 = cinza', ind(inds, 'quirons_erros')['nivel'] == 'cinza')
confere('sem laudo = cinza', ind(inds, 'quirons_laudo')['nivel'] == 'cinza')
confere('lote padrão 100 sem MV_RHMSGNG', 'MV_RHMSGNG) = 100' in ind(inds, 'quirons_fila')['texto'])
confere('cinza não piora o geral', ns['_integ_pior'](['cinza', 'verde']) == 'verde')
confere('tudo cinza = cinza', ns['_integ_pior'](['cinza']) == 'cinza')

# MV_RHNG desligado é dito no texto
off = dict(saudavel)
off['config'] = bloco({'PARAMETRO': 'MV_RHNG', 'FILIAL': '', 'CONTEUDO': '.F.'})
confere('MV_RHNG .F. avisado', 'MV_RHNG = .F.' in ind(ns['_integ_indicadores'](off, health_ok, HOJE), 'quirons_fila')['texto'])
# parâmetro global vence o de filial
par = ns['_integ_params']({'config': bloco({'PARAMETRO': 'MV_RHMSGNG', 'FILIAL': '01', 'CONTEUDO': '50'},
                                            {'PARAMETRO': 'MV_RHMSGNG', 'FILIAL': '', 'CONTEUDO': '200'})})
confere('parâmetro global vence', par['MV_RHMSGNG'] == '200')

# ══ GRUPO TOTVS TRANSMITE (16/10/2026) ══════════════════════════════════════
from datetime import datetime
gr = ns['_integ_grupos']
confere('grupos: nulo = rh', gr(None) == ('rh',) and gr([]) == ('rh',))
confere('grupos: lista do Postgres', gr(['transmite']) == ('transmite',))
confere('grupos: ordem fixa e sem lixo', gr(['TRANSMITE', 'xpto', 'rh']) == ('rh', 'transmite'))
confere('grupos: texto {rh,transmite}', gr('{rh,transmite}') == ('rh', 'transmite'))
confere('grupos: só desconhecido = rh', gr(['xpto']) == ('rh',))

AGORA = datetime(2026, 10, 13, 10, 0, 0)
hl = ns['_tra_hora_limite']
confere('hora limite = agora + 10 min', hl(AGORA) == '10:10:00')
confere('hora limite perto da meia-noite = só data', hl(datetime(2026, 10, 13, 23, 55)) is None)
confere('hora limite sem agora', hl(None) is None)

tra = ns['_integ_scripts']('010', HOJE, None, 'oracle', ('transmite',), AGORA)
tid = [s['id'] for s in tra]
confere('transmite: 13 blocos', len(tra) == 13)
confere('transmite: nenhum bloco de RH', not any(i in tid for i in ('config', 'rjp_fila', 'rum_resumo')))
confere('transmite: resumos antes dos detalhes',
        max(tid.index(i) for i in tid if not tra[tid.index(i)].get('detalhe'))
        < min(tid.index(i) for i in tid if tra[tid.index(i)].get('detalhe')))
for s in tra:
    for sql in s['sqls']:
        confere(f'{s["id"]}: SELECT', sql.startswith('SELECT'))
        confere(f'{s["id"]}: sem ;', not sql.rstrip().endswith(';'))
        confere(f'{s["id"]}: deletados', "D_E_L_E_T_ = ' '" in sql)
        up = sql.upper()
        # DBMS_LOB/UTL_RAW só no memo do Oracle (a trava da REST compara a palavra inteira)
        extra = () if s['id'] == 'tra_erros_msg' else ('DBMS_', 'UTL_')
        for proib in ('INSERT', 'UPDATE', 'DELETE ', 'MERGE', 'DROP', 'EXEC ', ' INTO ') + extra:
            confere(f'{s["id"]}: sem {proib}', proib not in up)
        for relogio in ('SYSDATE', 'GETDATE', 'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'NOW()', 'TO_CHAR'):
            confere(f'{s["id"]}: data vem do Python ({relogio})', relogio not in up)
        confere(f'{s["id"]}: sem <> vazio (Oracle)', "<> ''" not in sql)
    confere(f'{s["id"]}: sql = 1ª variante', s['sql'] == s['sqls'][0])
T = {s['id']: s for s in tra}
confere('CKOCOL sem sufixo', 'FROM CKOCOL' in T['tra_fila']['sql'] and 'CKOCOL010' not in T['tra_fila']['sql'])
confere('SF1/SDS com sufixo', 'SF1010' in T['tra_sem_retorno']['sql'] and 'SDS010' in T['tra_sem_monitor']['sql'])
confere('janela de 120 dias', "CKO_DT_IMP >= '20260615'" in T['tra_fila']['sql']
        and "F1_DTDIGIT >= '20260615'" in T['tra_sem_retorno']['sql'])
confere('prazo: faixas pela emissão', "F1_EMISSAO < '20260715'" in T['tra_sem_retorno']['sql']
        and "'20260725'" in T['tra_sem_retorno']['sql'] and "'20260814'" in T['tra_sem_retorno']['sql'])
confere('sem retorno: só classificadas', "RTRIM(SF1.F1_STATUS) > ' '" in T['tra_sem_retorno']['sql'])
confere('sem retorno: STRAN vazio conta como não classificado',
        "((RTRIM(CKO.CKO_STRAN) IS NULL OR RTRIM(CKO.CKO_STRAN) = '') OR RTRIM(CKO.CKO_STRAN) <> '4')"
        in T['tra_sem_retorno']['sql'])
confere('sem retorno: EXISTS não duplica reimportação', 'EXISTS (SELECT 1 FROM CKOCOL CKO' in T['tra_sem_retorno']['sql'])
confere('nota própria fora', "F1_FORMUL <> 'S'" in T['tra_sem_retorno']['sql'])
confere('futuras: data e hora com folga', "F1_DTDIGIT > '20261013'" in T['tra_futuras']['sql']
        and "F1_HORA > '10:10:00'" in T['tra_futuras']['sql'])
sem_hora = {s['id']: s['sql'] for s in ns['_integ_scripts']('010', HOJE, None, 'oracle', ('transmite',), None)}
confere('futuras sem agora: só data', 'F1_HORA >' not in sem_hora['tra_futuras'])
confere('MV_APITRAN mascarado', "IN ('MV_APITRAN') THEN" in T['tra_config']['sql'] and '(preenchido)' in T['tra_config']['sql'])
confere('revisão: 3 variantes (DATAIMP, EMISSA, sem data)', len(T['tra_revisao']['sqls']) == 3
        and 'DS_DATAIMP' in T['tra_revisao']['sqls'][0] and 'DS_EMISSA' in T['tra_revisao']['sqls'][1]
        and 'DS_' not in T['tra_revisao']['sqls'][2].replace('DS_STATUS', ''))
confere('fila antiga: > 30 dias', "CKO_DT_IMP <= '20260913'" in T['tra_fila_antigos']['sql'])
cor = {s['id']: s['sql'] for s in ns['_integ_scripts']('010', HOJE, date(2026, 10, 1), 'oracle', ('transmite',), AGORA)}
confere('corte encurta a janela', "F1_DTDIGIT >= '20261001'" in cor['tra_sem_retorno'] and "'20260615'" not in cor['tra_fila'])
velho = {s['id']: s['sql'] for s in ns['_integ_scripts']('010', HOJE, date(2025, 1, 1), 'oracle', ('transmite',), AGORA)}
confere('corte mais antigo não alarga a janela', "'20260615'" in velho['tra_fila'])
ambos = ns['_integ_scripts']('010', HOJE, None, 'oracle', ('rh', 'transmite'), AGORA)
confere('rh + transmite = 23 blocos', len(ambos) == 23 and ambos[0]['id'] == 'config')
confere('padrão continua só RH', len(ns['_integ_scripts']('010', HOJE)) == 10)

# ── indicadores Transmite ───────────────────────────────────────────────────
tra_ok = {
    'tra_config': bloco({'PARAMETRO': 'MV_IMPXML', 'FILIAL': '', 'CONTEUDO': '.T.'},
                        {'PARAMETRO': 'MV_DTINITR', 'FILIAL': '', 'CONTEUDO': '20260501'}),
    'tra_fila': bloco({'CODEDI': '109', 'STRAN': '4', 'QTD': '500', 'MAIS_ANTIGO': '20260616',
                       'MAIS_RECENTE': '20261013', 'PARADOS_AMARELO': '400', 'PARADOS_VERMELHO': '300'},
                      {'CODEDI': '109', 'STRAN': '1', 'QTD': '20', 'MAIS_ANTIGO': '20261001',
                       'MAIS_RECENTE': '20261013', 'PARADOS_AMARELO': '0', 'PARADOS_VERMELHO': '0'}),
    'tra_sem_retorno': bloco(),
    'tra_futuras': bloco(),
    'tra_revisao': bloco({'STATUS': 'P', 'QTD': '480', 'MAIS_ANTIGO': '20260616', 'MAIS_RECENTE': '20261013'}),
    'tra_sem_monitor': bloco(),
}
ti = ns['_integ_indicadores'](tra_ok, {'ok': False}, HOJE, ('transmite',))
confere('transmite: 9 indicadores, nenhum de RH', len(ti) == 9 and all(i['grupo'] == 'transmite' for i in ti))
confere('transmite saudável = verde', ns['_integ_pior'](i['nivel'] for i in ti) == 'verde')
confere('classificada (4) não conta como parada', ind(ti, 'tra_fila')['valor'] == 0)
confere('última importação hoje = 0 dias', ind(ti, 'tra_entrada')['valor'] == 0)
confere('parâmetros 2/14', ind(ti, 'tra_params')['valor'] == '2/14' and '01/05/2026' in ind(ti, 'tra_params')['texto'])

tra_ruim = dict(tra_ok)
tra_ruim['tra_config'] = bloco({'PARAMETRO': 'MV_IMPXML', 'FILIAL': '', 'CONTEUDO': '.F.'})
tra_ruim['tra_fila'] = bloco({'CODEDI': '109', 'STRAN': '2', 'QTD': '24', 'MAIS_ANTIGO': '20260710',
                              'MAIS_RECENTE': '20261007', 'PARADOS_AMARELO': '10', 'PARADOS_VERMELHO': '3'})
tra_ruim['tra_sem_retorno'] = bloco(
    {'FILIAL': '0101', 'QTD': '31', 'DIGIT_MAIS_ANTIGA': '20260905', 'EMISSAO_MAIS_ANTIGA': '20260701',
     'VENCIDAS': '1', 'CRITICAS': '2', 'ATENCAO': '5'},
    {'FILIAL': '0102', 'QTD': '4', 'DIGIT_MAIS_ANTIGA': '20261012', 'EMISSAO_MAIS_ANTIGA': '20261001',
     'VENCIDAS': '0', 'CRITICAS': '0', 'ATENCAO': '0'})
tra_ruim['tra_futuras'] = bloco({'FILIAL': '0101', 'DTDIGIT': '20261016', 'QTD': '3', 'PRIMEIRA': '08:00', 'ULTIMA': '09:00'},
                                {'FILIAL': '0101', 'DTDIGIT': '20261013', 'QTD': '1', 'PRIMEIRA': '15:00', 'ULTIMA': '15:00'})
tra_ruim['tra_revisao'] = bloco({'STATUS': 'B', 'QTD': '6', 'MAIS_ANTIGO': '20260920', 'MAIS_RECENTE': '20261010'},
                                {'STATUS': 'P', 'QTD': '400', 'MAIS_ANTIGO': '20260616', 'MAIS_RECENTE': '20261013'})
tra_ruim['tra_sem_monitor'] = bloco({'FILIAL': '0101', 'ESPECIE': 'SPED', 'QTD': '2', 'MAIS_ANTIGO': '20261001', 'MAIS_RECENTE': '20261002'})
ti = ns['_integ_indicadores'](tra_ruim, {'ok': False}, HOJE, ('transmite',))
sr = ind(ti, 'tra_sem_retorno')
confere('sem retorno somado e vermelho', sr['valor'] == 35 and sr['nivel'] == 'vermelho')
confere('sem retorno cita filial e revisão B', '0101 31' in sr['texto'] and '6 documento(s) em revisão' in sr['texto'])
pz = ind(ti, 'tra_prazo')
confere('prazo: 8 em risco, vermelho', pz['valor'] == 8 and pz['nivel'] == 'vermelho' and 'vencido' in pz['texto'])
confere('hora futura vermelho com data adiantada', ind(ti, 'tra_hora_futura')['valor'] == 4
        and ind(ti, 'tra_hora_futura')['nivel'] == 'vermelho' and '16/10/2026' in ind(ti, 'tra_hora_futura')['texto'])
rv = ind(ti, 'tra_revisao')
confere('revisão B há 23 dias = vermelho', rv['valor'] == 6 and rv['nivel'] == 'vermelho' and 'P 400' in rv['texto'])
confere('fila parada > 60 dias = vermelho', ind(ti, 'tra_fila')['valor'] == 10 and ind(ti, 'tra_fila')['nivel'] == 'vermelho')
confere('6 dias sem importar = vermelho', ind(ti, 'tra_entrada')['valor'] == 6 and ind(ti, 'tra_entrada')['nivel'] == 'vermelho')
confere('fora do Importador = amarelo', ind(ti, 'tra_sem_monitor')['nivel'] == 'amarelo')
confere('MV_IMPXML .F. e DTINITR vazio', ind(ti, 'tra_params')['nivel'] == 'amarelo'
        and 'MV_IMPXML = .F.' in ind(ti, 'tra_params')['texto'] and 'MV_DTINITR vazio' in ind(ti, 'tra_params')['texto'])

so_atencao = dict(tra_ok)
so_atencao['tra_sem_retorno'] = bloco({'FILIAL': '01', 'QTD': '2', 'DIGIT_MAIS_ANTIGA': '20261013',
                                       'EMISSAO_MAIS_ANTIGA': '20260801', 'VENCIDAS': '0', 'CRITICAS': '0', 'ATENCAO': '2'})
ti = ns['_integ_indicadores'](so_atencao, {'ok': False}, HOJE, ('transmite',))
confere('classificada hoje = amarelo', ind(ti, 'tra_sem_retorno')['nivel'] == 'amarelo')
confere('só faixa 60–80 = amarelo', ind(ti, 'tra_prazo')['nivel'] == 'amarelo' and ind(ti, 'tra_prazo')['valor'] == 2)

falhos = {'tra_sem_retorno': {'ok': False, 'ausente': True, 'erro': 'A tabela CKOCOL não existe nesta base', 'linhas': []}}
ti = ns['_integ_indicadores'](falhos, {'ok': False}, HOJE, ('transmite',))
confere('bloco ausente = cinza (sem retorno e prazo)', ind(ti, 'tra_sem_retorno')['nivel'] == 'cinza'
        and ind(ti, 'tra_prazo')['nivel'] == 'cinza' and 'CKOCOL' in ind(ti, 'tra_prazo')['texto'])
confere('tudo não lido = cinza geral', ns['_integ_pior'](i['nivel'] for i in ti) == 'cinza')
sem_import = dict(tra_ok, tra_fila=bloco())
confere('nenhum XML na janela = vermelho',
        ind(ns['_integ_indicadores'](sem_import, {'ok': False}, HOJE, ('transmite',)), 'tra_entrada')['nivel'] == 'vermelho')
sem_data = dict(tra_ok, tra_revisao=dict(bloco({'STATUS': 'B', 'QTD': '2'}), variante=2))
rv = ind(ns['_integ_indicadores'](sem_data, {'ok': False}, HOJE, ('transmite',)), 'tra_revisao')
confere('revisão sem campo de data = amarelo e avisa', rv['nivel'] == 'amarelo' and 'sem janela' in rv['texto'])
ambos_i = ns['_integ_indicadores'](dict(saudavel, **tra_ok), health_ok, HOJE, ('rh', 'transmite'))
confere('rh + transmite = 17 indicadores', len(ambos_i) == 17)

# ══ Transmite: motivo do Importador (CKO_CODERR) — 30/10/2026 ═══════════════
por_banco = {b: {x['id']: x for x in ns['_integ_scripts']('010', HOJE, None, b, ('transmite',), AGORA)}
             for b in ('oracle', 'mssql', 'postgres')}
E = por_banco['oracle']['tra_erros']['sql']
confere('erros: Oracle usa SUBSTR e LENGTH', 'SUBSTR(CKO_CHVDOC, 21, 2)' in E and 'LENGTH(RTRIM(CKO_CHVDOC))' in E
        and 'SUBSTRING' not in E)
confere('erros: SQL Server usa SUBSTRING e LEN', 'SUBSTRING(CKO_CHVDOC' in por_banco['mssql']['tra_erros']['sql']
        and 'LEN(RTRIM' in por_banco['mssql']['tra_erros']['sql'])
confere('erros: Postgres usa SUBSTRING e LENGTH', 'SUBSTRING(CKO_CHVDOC' in por_banco['postgres']['tra_erros']['sql']
        and 'LENGTH(RTRIM' in por_banco['postgres']['tra_erros']['sql'])
confere('erros: GROUP BY pelas colunas da subconsulta (Oracle)', 'GROUP BY X.ERRO, X.STRAN, X.TIPO' in E)
confere('erros: sem concatenação (DBAccess Postgres)', '||' not in E)
confere('erros: só o que não chegou a 4', "RTRIM(CKO_STRAN) <> '4'" in E)
confere('erros: janela', "CKO_DT_IMP >= '20260615'" in E)
M = por_banco['postgres']['tra_erros_msg']['sqls']
confere('msg postgres: CAST do BYTEA e variante sem mensagem', 'CAST(CKO_MSGERR AS VARCHAR)' in M[0] and 'MSGERR' not in M[-1])
confere('msg oracle: BLOB, CLOB e sem mensagem', len(por_banco['oracle']['tra_erros_msg']['sqls']) == 3)
confere('msg: um XML por código', 'MIN(R_E_C_N_O_)' in M[0] and 'GROUP BY CKO_CODERR' in M[0])
confere('lista: destino (CKO_CNPJIM)', 'CKO_CNPJIM' in por_banco['oracle']['tra_erros_lista']['sql'])
confere('sem retorno: TEM_SDS separa sem registro de status vazio',
        "CASE WHEN SDS.DS_CHAVENF IS NULL THEN 'N' ELSE 'S' END AS TEM_SDS" in por_banco['oracle']['tra_sem_retorno_lista']['sql'])

tm = ns['_tra_msg']
HEX = '\\x434f4d303532202d204573746520584d4c206ee36f2070657274656e63652061206e656e68756d6120656d70726573612f66696c69616c2065206ee36f20706f64657261207365722070726f6365737361646f2e00'
confere('msg: BYTEA em hexa vira texto sem o código', tm(HEX) == 'Este XML não pertence a nenhuma empresa/filial e não podera ser processado.')
confere('msg: duas barras (CSV escapado)', tm('\\' + HEX) == tm(HEX))
confere('msg: texto puro (Oracle) só perde o prefixo', tm('COM007 - Fornecedor X inexistente na base.') == 'Fornecedor X inexistente na base.')
confere('msg: vazio', tm('') == '' and tm(None) == '')
confere('msg: hexa inválido não quebra', tm('\\xZZ') == '\\xZZ' or tm('\\xZZ') == '')

err = {
    'tra_erros': bloco(
        {'ERRO': 'COM007', 'STRAN': '2', 'TIPO': 'NFE', 'QTD': '30', 'MAIS_ANTIGO': '20261001', 'MAIS_RECENTE': '20261028'},
        {'ERRO': 'COM007', 'STRAN': '2', 'TIPO': 'NFSE', 'QTD': '5', 'MAIS_ANTIGO': '20261003', 'MAIS_RECENTE': '20261030'},
        {'ERRO': 'COM040', 'STRAN': '1', 'TIPO': 'NFE', 'QTD': '21', 'MAIS_ANTIGO': '20260920', 'MAIS_RECENTE': '20261029'},
        {'ERRO': 'COM052', 'STRAN': '0', 'TIPO': 'NFE', 'QTD': '34', 'MAIS_ANTIGO': '20261001', 'MAIS_RECENTE': '20261029'},
        {'ERRO': 'COM099', 'STRAN': '2', 'TIPO': 'CTE', 'QTD': '2', 'MAIS_ANTIGO': '20261010', 'MAIS_RECENTE': '20261010'},
        {'ERRO': '-', 'STRAN': '2', 'TIPO': 'NFSE', 'QTD': '614', 'MAIS_ANTIGO': '20261001', 'MAIS_RECENTE': '20261030'}),
    'tra_erros_msg': bloco({'ERRO': 'COM052', 'MENSAGEM': HEX}, {'ERRO': 'COM007', 'MENSAGEM': ''}),
}
res = ns['_tra_erros_resumo'](err)
cod = {c['codigo']: c for c in res['codigos']}
confere('resumo: soma por código e tipo', cod['COM007']['qtd'] == 35 and cod['COM007']['tipos'] == {'NFE': 30, 'NFSE': 5})
confere('resumo: data mais antiga e recente por código', cod['COM007']['mais_antigo'] == '20261001' and cod['COM007']['mais_recente'] == '20261030')
confere('resumo: texto da base vence o padrão', cod['COM052']['texto'].startswith('Este XML não pertence') and cod['COM052']['fonte'] == 'base')
confere('resumo: sem mensagem usa o padrão', cod['COM007']['texto'] == 'Fornecedor inexistente na base' and cod['COM007']['fonte'] == 'padrao')
confere('resumo: código desconhecido = não mapeado', cod['COM099']['quem'] == 'outros' and cod['COM099']['fonte'] == 'nenhuma')
confere('resumo: quem resolve', cod['COM007']['quem'] == 'cadastro' and cod['COM040']['quem'] == 'nada' and cod['COM052']['quem'] == 'nada')
confere('resumo: ação × sem ação × sem erro', res['acao'] == 37 and res['sem_acao'] == 55 and res['sem_erro'] == 614)
confere('resumo: sem ação vai para o fim', res['codigos'][-1]['quem'] == 'nada' and res['codigos'][0]['codigo'] == 'COM007')
confere('resumo: antigo só do que pede ação', res['mais_antigo_acao'] == '20261001')
confere('resumo: bloco não lido = None', ns['_tra_erros_resumo']({}) is None)
ti = ns['_integ_indicadores'](dict(tra_ok, **err), {'ok': False}, HOJE, ('transmite',))
ie = ind(ti, 'tra_erros')
confere('cartão erros: valor = só o que pede ação', ie['valor'] == 37)
confere('cartão erros: 12 dias = vermelho', ie['nivel'] == 'vermelho')
confere('cartão erros: texto com motivo e sem ação', 'COM007 Fornecedor inexistente na base (35)' in ie['texto'] and 'Sem ação' in ie['texto'] and '55' in ie['texto'])
so_nada = {'tra_erros': bloco({'ERRO': 'COM040', 'STRAN': '1', 'TIPO': 'NFE', 'QTD': '3', 'MAIS_ANTIGO': '20261001', 'MAIS_RECENTE': '20261002'})}
ie = ind(ns['_integ_indicadores'](dict(tra_ok, **so_nada), {'ok': False}, HOJE, ('transmite',)), 'tra_erros')
confere('cartão erros: só cancelada = verde', ie['nivel'] == 'verde' and ie['valor'] == 0 and 'Sem ação' in ie['texto'])
recente = {'tra_erros': bloco({'ERRO': 'COM007', 'STRAN': '2', 'TIPO': 'NFE', 'QTD': '1', 'MAIS_ANTIGO': '20261010', 'MAIS_RECENTE': '20261010'})}
ie = ind(ns['_integ_indicadores'](dict(tra_ok, **recente), {'ok': False}, HOJE, ('transmite',)), 'tra_erros')
confere('cartão erros: 3 dias = amarelo', ie['nivel'] == 'amarelo')
ie = ind(ns['_integ_indicadores'](dict(tra_ok), {'ok': False}, HOJE, ('transmite',)), 'tra_erros')
confere('cartão erros: bloco não lido = cinza', ie['nivel'] == 'cinza')
pronto = dict(tra_ok, tra_erros=dict(bloco(), resumo={'codigos': [], 'acao': 0, 'sem_acao': 0, 'sem_erro': 0, 'mais_antigo_acao': None}))
confere('cartão erros: usa o resumo gravado', ind(ns['_integ_indicadores'](pronto, {'ok': False}, HOJE, ('transmite',)), 'tra_erros')['nivel'] == 'verde')

print(f'{ok} asserções OK, {falhou} falha(s)')
raise SystemExit(1 if falhou else 0)
