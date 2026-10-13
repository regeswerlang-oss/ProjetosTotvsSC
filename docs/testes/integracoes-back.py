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
ns = {'re': re, 'csv': csv, 'io': io, 'json': json, 'date': date, 'timedelta': timedelta}
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
confere('nove blocos', len(scripts) == 9)
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

print(f'{ok} asserções OK, {falhou} falha(s)')
raise SystemExit(1 if falhou else 0)
