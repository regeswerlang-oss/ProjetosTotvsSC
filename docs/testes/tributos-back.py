# Teste das funções PURAS da aba Tributos — Configurador de Tributos (30/10/2026).
#
# Como rodar, de qualquer lugar:  python3 docs/testes/tributos-back.py
# Extrai o trecho do módulo em vez de importá-lo (o módulo exige Supabase e
# chaves). Cobre: SQL da fase 0 (só SELECT, sem ';', sufixo, deletados fora),
# leitura de conteúdo com memo em variantes, chave de negócio (TRIB_CHAVE →
# SIX sem ID técnico), comparação por chave e por conteúdo, "mesmo conteúdo,
# outro código", referências quebradas, vigência, status de teste, CBS/IBS por
# filial, dependências da migração e a coleta faseada com uma REST fingida.
import ast, csv, io, json, pathlib, re, time, unicodedata
from datetime import date, datetime, timedelta

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
arv = ast.parse(src)
AUX = {'_integ_memo_exprs', '_integ_motivo', '_integ_csv', '_integ_int', '_integ_norm'}
aux_src = '\n\n'.join(ast.get_source_segment(src, n) for n in arv.body
                      if isinstance(n, ast.FunctionDef) and n.name in AUX)
ini = src.index('# ── CONFIGURADOR DE TRIBUTOS (FISA170)')
fim = src.index('# ── estáticos do web/ (assets)')


class _App:
    def _dec(self, *a, **k):
        return lambda f: f
    get = post = delete = _dec


ns = {'re': re, 'csv': csv, 'io': io, 'json': json, 'time': time, 'unicodedata': unicodedata,
      'datetime': datetime, 'timedelta': timedelta,
      'app': _App(), 'INTEG_TEMPO_MIN': 4, 'TIMEOUT_TETO': 50}
exec(compile(aux_src, 'aux', 'exec'), ns)
exec(compile(src[ini:fim], 'tributos', 'exec'), ns)

ok = falhou = 0


def confere(nome, cond, extra=None):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome, '' if extra is None else extra)


HOJE = '20261030'

# ── aba registrada ──────────────────────────────────────────────────────────
confere('aba tributos no catálogo e liberável', re.search(
    r'\{"id": "tributos",\s+"label": "Configurador de Tributos", "cliente": True\}', src) is not None)
confere('rota de leitura passa por deny_aba("tributos")', 'deny_aba(customer, "tributos")' in src[ini:fim])
confere('coleta exige interno (_guarda_ambiente escrita)', '_guarda_ambiente(customer, request.args.get("ambiente") or "producao", escrita=True)' in src[ini:fim])

# ── SQL da fase 0 ───────────────────────────────────────────────────────────
for banco in ('oracle', 'mssql', 'postgres'):
    for s in ns['_trib_scripts_meta']('010', banco):
        for sql in s['sqls']:
            confere(f'{banco}/{s["id"]} só SELECT', sql.lstrip().upper().startswith('SELECT'), sql[:60])
            confere(f'{banco}/{s["id"]} sem ;', ';' not in sql)
meta_sql = {s['id']: s['sqls'][0] for s in ns['_trib_scripts_meta']('010', 'oracle')}
confere('colunas pelo USER_TAB_COLUMNS no Oracle', 'USER_TAB_COLUMNS' in meta_sql['colunas'])
confere('F2B010 na lista de tabelas', "'F2B010'" in meta_sql['colunas'])
confere('SX2/SX3/SIX com sufixo e sem deletados', all("D_E_L_E_T_ = ' '" in meta_sql[k] and f'{k.upper()}010' in meta_sql[k]
                                                         for k in ('sx2', 'sx3', 'six')))
confere('SIX só ordem 1', "ORDEM = '1'" in meta_sql['six'])
confere('mssql pelo INFORMATION_SCHEMA', 'INFORMATION_SCHEMA.COLUMNS' in ns['_trib_scripts_meta']('010', 'mssql')[0]['sqls'][0])

# ── dicionário e contagem ───────────────────────────────────────────────────
COLS = [
    ('F2B010', 'F2B_FILIAL', 'VARCHAR2'), ('F2B010', 'F2B_ID', 'VARCHAR2'), ('F2B010', 'F2B_REGRA', 'VARCHAR2'),
    ('F2B010', 'F2B_DESC', 'VARCHAR2'), ('F2B010', 'F2B_TRIB', 'VARCHAR2'), ('F2B010', 'F2B_VIGINI', 'VARCHAR2'),
    ('F2B010', 'F2B_VIGFIM', 'VARCHAR2'), ('F2B010', 'F2B_STATUS', 'VARCHAR2'), ('F2B010', 'F2B_RBASE', 'VARCHAR2'),
    ('F2B010', 'F2B_RALIQ', 'VARCHAR2'), ('F2B010', 'F2B_PERFPR', 'VARCHAR2'), ('F2B010', 'F2B_USERGI', 'VARCHAR2'),
    ('F2B010', 'D_E_L_E_T_', 'CHAR'), ('F2B010', 'R_E_C_N_O_', 'NUMBER'),
    ('CIN010', 'CIN_FILIAL', 'VARCHAR2'), ('CIN010', 'CIN_CODIGO', 'VARCHAR2'), ('CIN010', 'CIN_FORMUL', 'BLOB'),
    ('F29010', 'F29_CODIGO', 'VARCHAR2'),
    ('SA1010', 'A1_COD', 'VARCHAR2'),          # fora do Configurador: ignorada
]
linhas = [{'TABLE_NAME': t, 'COLUMN_NAME': c, 'DATA_TYPE': d} for t, c, d in COLS]
dic = ns['_trib_dicionario'](linhas, '010')
confere('dicionário só com tabelas do Configurador', sorted(dic) == ['CIN', 'F29', 'F2B'], sorted(dic))
cont = ns['_trib_sql_contagem'](dic)
confere('contagem em UMA consulta com UNION ALL', cont.count('UNION ALL') == 2 and ';' not in cont)
confere('contagem por filial quando há _FILIAL', 'F2B_FILIAL FIL' in cont and 'GROUP BY F2B_FILIAL' in cont)
confere("tabela sem filial conta com ' ' FIL", "SELECT 'F29' TAB, ' ' FIL, COUNT(*)" in cont)
confere('contagem sem deletados', cont.count("D_E_L_E_T_ = ' '") == 3)

esc, memo = ns['_trib_cols_leitura']('F2B', dic['F2B']['colunas'])
confere('técnicas e log de usuário fora', not ({'D_E_L_E_T_', 'R_E_C_N_O_', 'F2B_USERGI'} & set(esc)))
sqls, _e, mm = ns['_trib_sqls_tabela']('CIN', dic['CIN'], 'oracle', ['CIN_FILIAL', 'CIN_CODIGO'])
confere('memo do Oracle: BLOB → CLOB → sem memo', len(sqls) == 3 and 'UTL_RAW' in sqls[0]
        and 'UTL_RAW' not in sqls[1] and 'DBMS_LOB' in sqls[1] and 'CIN_FORMUL' not in sqls[2], sqls)
confere('memo com apelido do campo', 'CIN_FORMUL' in sqls[0].split('FROM')[0])
confere('ordem pela chave', sqls[0].endswith('ORDER BY CIN_FILIAL, CIN_CODIGO'))
sqls2, _e, _m = ns['_trib_sqls_tabela']('F2B', dic['F2B'], 'oracle', None)
confere('tabela sem memo = 1 variante', len(sqls2) == 1 and sqls2[0].startswith('SELECT F2B_FILIAL'))
confere('mssql memo por CONVERT', 'CONVERT(VARCHAR(1000)' in ns['_trib_sqls_tabela']('CIN', dic['CIN'], 'mssql', None)[0][0])

# ── chave, SIX, CBOX ────────────────────────────────────────────────────────
confere('SIX com DTOS', ns['_trib_six_chave']('F2B_FILIAL+F2B_REGRA+DTOS(F2B_VIGINI)', 'F2B')
        == ['F2B_FILIAL', 'F2B_REGRA', 'F2B_VIGINI'])
t_f2b = {'colunas': [c for _t, c, _d in COLS if _t == 'F2B010'], 'filial_col': 'F2B_FILIAL',
         'six': ['F2B_FILIAL', 'F2B_ID']}
confere('chave preferida da F2B', ns['_trib_chave']('F2B', t_f2b) == ['F2B_FILIAL', 'F2B_REGRA', 'F2B_VIGINI'])
t_f21 = {'colunas': ['F21_FILIAL', 'F21_IDF20', 'F21_UFORI', 'F21_UFDEST'], 'filial_col': 'F21_FILIAL',
         'six': ['F21_FILIAL', 'F21_IDF20']}
confere('SIX só com ID técnico → sem chave (compara por conteúdo)', ns['_trib_chave']('F21', t_f21) is None)
confere('ID técnico reconhecido', ns['_trib_eh_id']('F2B_ID') and ns['_trib_eh_id']('F21_IDF20')
        and not ns['_trib_eh_id']('F2E_IDTRIB') and not ns['_trib_eh_id']('F2B_REGRA'))
confere('CBOX', ns['_trib_cbox']('1=Em teste;2=Aprovado') == {'1': 'Em teste', '2': 'Aprovado'})
confere('CBOX como a REST devolve (espaço no lugar do ;)', ns['_trib_cbox']('01=Origem/Destino 02=Participante 03=Operação 04=Produto')
        == {'01': 'Origem/Destino', '02': 'Participante', '03': 'Operação', '04': 'Produto'})
confere('CBOX com espaço dentro do rótulo', ns['_trib_cbox']('1=Considera valor Máximo  2=Zerar o tributo  3=Não Calcula Tributo')
        == {'1': 'Considera valor Máximo', '2': 'Zerar o tributo', '3': 'Não Calcula Tributo'})
confere('CBOX com função não decodifica', ns['_trib_cbox']('#FISCBOX()') == {})


# ── retrato fingido das duas bases ──────────────────────────────────────────
def reg(fil, regra, trib, desc, vigini='20260101', vigfim='', status='2', rbase='TB0001', raliq='TA0001',
        perfpr='TPP001', idx='x'):
    return {'F2B_FILIAL': fil, 'F2B_ID': f'{idx}' * 32, 'F2B_REGRA': regra, 'F2B_DESC': desc, 'F2B_TRIB': trib,
            'F2B_VIGINI': vigini, 'F2B_VIGFIM': vigfim, 'F2B_STATUS': status, 'F2B_RBASE': rbase,
            'F2B_RALIQ': raliq, 'F2B_PERFPR': perfpr}


def matriz(regs):
    cols = list(regs[0]) if regs else []
    return {'ok': True, 'cols': cols, 'linhas': [[r[c] for c in cols] for r in regs]}


F2B_P = [reg('01', 'TR0001', 'CBSFED', 'CBS', idx='a'),
         reg('01', 'TR0002', 'IBSEST', 'IBS', raliq='TA0002', idx='b'),
         reg('01', 'TR0009', 'IBSMUN', 'IBS MUN', status='1', idx='c'),          # em teste na Produção
         reg('01', 'PROD01', 'CBSFED', 'criada na produção', raliq='TA0099', idx='d'),   # TA0099 não existe
         reg('01', 'TR0007', 'IBSEST', 'mesmo conteúdo', raliq='TA0007', idx='e')]
F2B_T = [reg('01', 'TR0001', 'CBSFED', 'CBS', idx='f'),                          # igual (ID diferente)
         reg('01', 'TR0002', 'IBSEST', 'IBS', raliq='TA0003', idx='g'),          # diverge na alíquota
         reg('01', 'TR0009', 'IBSMUN', 'IBS MUN', status='1', idx='h'),
         reg('02', 'TR0001', 'CBSFED', 'CBS', idx='i'),                          # só Teste (filial 02)
         reg('01', 'TR0010', 'IBSMUN', 'nova', raliq='TA0004', perfpr='TPP009', idx='j'),   # só Teste, deps
         reg('01', 'TR0008', 'IBSEST', 'mesmo conteúdo', raliq='TA0007', idx='k'),          # par da TR0007
         reg('01', 'TR0000', 'CBSFED', 'vencida', vigini='20250101', vigfim='20251231', idx='l')]
F28_P = [{'F28_FILIAL': '', 'F28_CODIGO': c, 'F28_DESC': d, 'F28_ALIQ': a}
         for c, d, a in (('TA0001', '0,9%', '0.90'), ('TA0002', '0,1%', '0.10'), ('TA0007', 'x', '1'))]
F28_T = F28_P + [{'F28_FILIAL': '', 'F28_CODIGO': 'TA0003', 'F28_DESC': 'nova', 'F28_ALIQ': '0.05'},
                 {'F28_FILIAL': '', 'F28_CODIGO': 'TA0004', 'F28_DESC': 'mun', 'F28_ALIQ': '0.02'}]
F20_P = [{'F20_FILIAL': '01', 'F20_CODIGO': 'TPP001', 'F20_TIPO': '04', 'F20_DESC': 'todos'},
         {'F20_FILIAL': '01', 'F20_CODIGO': '000051', 'F20_TIPO': '03', 'F20_DESC': 'todos os CFOPs'}]
F20_T = F20_P + [{'F20_FILIAL': '01', 'F20_CODIGO': 'TPP009', 'F20_TIPO': '04', 'F20_DESC': 'serviços'}]
F21_P = [{'F21_FILIAL': '01', 'F21_IDF20': 'p' * 32, 'F21_UFORI': 'SC', 'F21_UFDEST': 'SC'}]
F21_T = [{'F21_FILIAL': '01', 'F21_IDF20': 't' * 32, 'F21_UFORI': 'SC', 'F21_UFDEST': 'SC'},
         {'F21_FILIAL': '01', 'F21_IDF20': 'u' * 32, 'F21_UFORI': 'SC', 'F21_UFDEST': 'PR'}]
F27 = [{'F27_FILIAL': '', 'F27_CODIGO': 'TB0001', 'F27_DESC': 'base'}]
F2E = [{'F2E_FILIAL': '', 'F2E_TRIB': t, 'F2E_DESC': t} for t in ('CBSFED', 'IBSEST', 'IBSMUN')]


def meta_de(regs_por_tab, filiais):
    tabs = {}
    for cod, (rot, grupo, tipo) in ns['TRIB_TABELAS'].items():
        r = regs_por_tab.get(cod)
        if r is None:
            tabs[cod] = {'rotulo': rot, 'grupo': grupo, 'tipo': tipo, 'existe': False}
            continue
        cols = list(r[0]) if r else []
        tabs[cod] = {'rotulo': rot, 'grupo': grupo, 'tipo': tipo, 'existe': True, 'tabela': f'{cod}010',
                     'colunas': cols, 'memos': [], 'titulos': {c: c.split('_')[1].title() for c in cols},
                     'cbox': {'F2B_STATUS': {'1': 'Em teste', '2': 'Aprovado'}} if cod == 'F2B' else {},
                     'six': [f'{cod}_FILIAL', f'{cod}_ID'], 'filial_col': f'{cod}_FILIAL' if r and f'{cod}_FILIAL' in r[0] else None,
                     'modo': 'EEE' if cod == 'F2B' else 'CCC', 'total': len(r),
                     'por_filial': {fil: sum(1 for x in r if x.get(f'{cod}_FILIAL', '') == fil)
                                    for fil in {x.get(f'{cod}_FILIAL', '') for x in r}}}
    tabs['F2D'] = {'rotulo': 'calc', 'grupo': 'movimento', 'tipo': 'mov', 'existe': True, 'total': 1500,
                   'por_filial': {'01': 1500}, 'modo': 'EEE'}
    return {'tabelas': tabs, 'filiais': filiais, 'erros': {}}


FILIAIS = [{'codigo': '01', 'nome': 'Matriz', 'uf': 'SC'}, {'codigo': '02', 'nome': 'Filial SP', 'uf': 'SP'}]
P = {'F2B': F2B_P, 'F28': F28_P, 'F20': F20_P, 'F21': F21_P, 'F27': F27, 'F2E': F2E}
T = {'F2B': F2B_T, 'F28': F28_T, 'F20': F20_T, 'F21': F21_T, 'F27': F27, 'F2E': F2E}
col_p = {'meta': meta_de(P, FILIAIS), 'dados': {k: matriz(v) for k, v in P.items()}}
col_t = {'meta': meta_de(T, FILIAIS), 'dados': {k: matriz(v) for k, v in T.items()}}
out = ns['_trib_monta'](col_p, col_t, HOJE)
json.dumps(out, ensure_ascii=False)   # serializável
# O front (tributos-front.js) usa este mesmo retrato: regerar com FIXTURE=1.
import os
if os.environ.get('FIXTURE'):
    (RAIZ / 'docs' / 'testes' / 'tributos-fixture.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
confere('payload serializável', True)

c = out['comparacao']['F2B']
confere('F2B por chave de negócio', c['chave'] == ['F2B_FILIAL', 'F2B_REGRA', 'F2B_VIGINI'])
confere('F2B_ID ignorado', c['ignoradas'] == ['F2B_ID'], c['ignoradas'])
confere('resumo F2B', c['resumo'] == {'so_teste': 4, 'so_prod': 2, 'iguais': 2, 'diverg': 1, 'mesmo_conteudo': 1},
        c['resumo'])
div = [i for i in c['itens'] if i['sit'] == 'diverg'][0]
confere('divergência campo a campo', div['k'][1] == 'TR0002' and div['difs'] == ['F2B_RALIQ'], div)
par = [i for i in c['itens'] if i.get('par') and i['sit'] == 'so_teste'][0]
confere('mesmo conteúdo, outro código (TR0008 × TR0007)', par['k'][1] == 'TR0008' and par['par'][1] == 'TR0007')

c21 = out['comparacao']['F21']
confere('F21 sem chave estável → por conteúdo', c21['chave'] is None)
confere('F21: 1 igual (ID diferente não pesa) e 1 só Teste', c21['resumo']['iguais'] == 1 and c21['resumo']['so_teste'] == 1,
        c21['resumo'])
c28 = out['comparacao']['F28']
confere('F28: 2 alíquotas só em Teste', c28['resumo']['so_teste'] == 2)

ap = out['analise']['producao']
confere('ref quebrada na Produção: PROD01 → TA0099', [(x['regra'], x['valor']) for x in ap['refs']] == [('PROD01', 'TA0099')],
        ap['refs'])
confere('ref quebrada diz o destino e o motivo', ap['refs'][0]['destino'] == 'F28' and ap['refs'][0]['motivo'] == 'não existe')
confere('regra em teste vigente na Produção', [x['regra'] for x in ap['em_teste']] == ['TR0009'])
confere('status decodificado pelo X3_CBOX', ap['status'] == {'Aprovado': 4, 'Em teste': 1}, ap['status'])
at = out['analise']['teste']
confere('vigência no Teste (1 encerrada)', at['vig'] == {'vigente': 6, 'futura': 0, 'encerrada': 1}, at['vig'])
confere('Teste: regra da filial 02 usando perfil que só existe na 01',
        [(x['filial'], x['valor'], x['motivo']) for x in at['refs']] == [('02', 'TPP001', 'existe em outra filial')], at['refs'])
confere('órfão informativo (perfil 000051 sem regra)', any(o['codigo'] == '000051' for o in ap['orfaos']))

rf = out['reforma']
confere('reforma: tributos', rf['tributos'] == ['CBSFED', 'IBSEST', 'IBSMUN'])
confere('reforma: CBS filial 02 só em Teste', rf['producao']['CBSFED'].get('02') is None and rf['teste']['CBSFED']['02'] == 1)
confere('reforma: vencida não conta', rf['teste']['CBSFED']['01'] == 1)
confere('reforma: filiais do SYS_COMPANY', rf['filiais'] == ['01', '02'])

mig = {m['regra']: m for m in out['migracao']}
confere('migração lista só-Teste e divergentes', set(mig) == {'TR0001', 'TR0010', 'TR0008', 'TR0000', 'TR0002'}, set(mig))
confere('migração: TR0010 leva TA0004 e TPP009', [(d['tabela'], d['codigo']) for d in mig['TR0010']['deps']]
        == [('F28', 'TA0004'), ('F20', 'TPP009')], mig['TR0010']['deps'])
confere('migração: divergente mostra campo e dep TA0003', mig['TR0002']['difs'] == ['F2B_RALIQ']
        and [d['codigo'] for d in mig['TR0002']['deps']] == ['TA0003'])

inds = {i['chave']: i for i in out['indicadores']}
confere('indicador só em Teste = 4, amarelo', inds['migrar']['valor'] == 4 and inds['migrar']['nivel'] == 'amarelo')
confere('indicador ref Produção vermelho', inds['refs_p']['valor'] == 1 and inds['refs_p']['nivel'] == 'vermelho')
confere('indicador ref Teste vermelho (perfil de outra filial)', inds['refs_t']['nivel'] == 'vermelho')
confere('indicador em teste na Produção', inds['em_teste_prod']['valor'] == 1)
confere('vence: nenhuma regra perto do fim no retrato fingido', inds['vence']['valor'] == 0)
an_v = ns['_trib_analisa_base']({'tabelas': {}}, {'F2B': [
    {'F2B_FILIAL': '01', 'F2B_REGRA': 'A00101', 'F2B_TRIB': 'CBSFED', 'F2B_DESC': 'CBSFED - CCLASS41099', 'F2B_VIGINI': '20260101', 'F2B_VIGFIM': '20261231'},
    {'F2B_FILIAL': '01', 'F2B_REGRA': 'E00101', 'F2B_TRIB': 'ICMS', 'F2B_DESC': 'ICMS', 'F2B_VIGINI': '20260101', 'F2B_VIGFIM': ''}]}, HOJE)
confere('vence: CBS até 31/12/2026 entra (62 dias)', [v['regra'] for v in an_v['vence']] == ['A00101'])
confere('indicador reforma amarelo (CBS/IBS faltando na 02)', inds['reforma']['nivel'] == 'amarelo', inds['reforma'])

q = {x['tab']: x for x in out['quantidades']}
confere('quantidades lado a lado', q['F2B']['p'] == 5 and q['F2B']['t'] == 7)
confere('tabela inexistente marcada', q['CJ2']['existe'] == {'p': False, 't': False})
confere('movimento só conta (F2D)', q['F2D']['tipo'] == 'mov' and q['F2D']['p'] == 1500 and 'F2D' not in out['comparacao'])
confere('por filial', any(f['fil'] == '02' and f['t'] == 1 and f['p'] is None for f in q['F2B']['filiais']))

# uma base só: sem comparação de migração, mas análise da que existe
so_p = ns['_trib_monta'](col_p, None, HOJE)
confere('só Produção: indicador migrar cinza', {i['chave']: i for i in so_p['indicadores']}['migrar']['nivel'] == 'cinza')
confere('só Produção: análise existe', so_p['analise']['producao'] and so_p['analise']['teste'] is None)
vazio = ns['_trib_monta'](None, None, HOJE)
confere('nenhuma coleta não quebra', vazio['comparacao'] == {} and vazio['migracao'] == [])


# ── versões anteriores (FISA170 guarda a antiga com *_ALTERA = 1) ──────────
F28V = [{'F28_FILIAL': '', 'F28_CODIGO': '000019', 'F28_DESC': 'INSS 11%', 'F28_ALIQ': '11', 'F28_ALTERA': '1', 'F28_ID': 'a' * 20},
        {'F28_FILIAL': '', 'F28_CODIGO': '000019', 'F28_DESC': 'INSS 11% - TOMADO', 'F28_ALIQ': '11', 'F28_ALTERA': '2', 'F28_ID': 'b' * 20},
        {'F28_FILIAL': '', 'F28_CODIGO': '000015', 'F28_DESC': 'IR 1%', 'F28_ALIQ': '1', 'F28_ALTERA': '2', 'F28_ID': 'c' * 20},
        {'F28_FILIAL': '', 'F28_CODIGO': '000016', 'F28_DESC': 'IR 1,5', 'F28_ALIQ': '1.5', 'F28_ALTERA': '2', 'F28_ID': 'd' * 20},
        {'F28_FILIAL': '', 'F28_CODIGO': 'TA001', 'F28_DESC': '0,9%', 'F28_ALIQ': '0.9', 'F28_ALTERA': '2', 'F28_ID': 'e' * 20}]
mt = {'colunas': list(F28V[0]), 'cbox': {'F28_ALTERA': {'1': 'Foi Alterado', '2': 'Não foi Alterado'}}}
atuais, nant = ns['_trib_registros'](mt, matriz(F28V), 'F28')
confere('versão anterior fora (1 de 5)', nant == 1 and len(atuais) == 4 and all(r['F28_ALTERA'] == '2' for r in atuais))
confere('CIN: vale o dado (1 = anterior), não o CBOX invertido', ns['_trib_alterado']('CIN', {'colunas': ['CIN_ALTERA'],
        'cbox': {'CIN_ALTERA': {'0': 'Foi alterado', '1': 'Não foi Alterado'}}}) == ('CIN_ALTERA', '1'))
confere('carimbo e ALTERA ignorados', ns['_trib_ignorar']('F28', [{'F28_DTALT': '', 'F28_HRALT': '', 'F28_CHVMD5': '', 'F28_ALTERA': '', 'F28_ID': '', 'F28_ALIQ': ''}], [])
        == ['F28_ALTERA', 'F28_CHVMD5', 'F28_DTALT', 'F28_HRALT', 'F28_ID'])

# ── coerência (casos REAIS da Produção da Dígitro, 30/10/2026) ─────────────
F2BC = [{'F2B_FILIAL': '01', 'F2B_REGRA': 'E00302', 'F2B_DESC': 'IR - RETENÇÃO 1% - SERVIÇO TOMADO', 'F2B_TRIB': 'IRF', 'F2B_RALIQ': '000016'},
        {'F2B_FILIAL': '01', 'F2B_REGRA': 'E00301', 'F2B_DESC': 'IR - RETENÇÃO 1% - SERVIÇO TOMADO', 'F2B_TRIB': 'IRF', 'F2B_RALIQ': '000015'},
        {'F2B_FILIAL': '01', 'F2B_REGRA': 'E00307', 'F2B_DESC': 'INSS - RETENÇÃO 11% - SERVIÇO TOMADO', 'F2B_TRIB': 'ISS', 'F2B_RALIQ': '000020'},
        {'F2B_FILIAL': '01', 'F2B_REGRA': 'S00105', 'F2B_DESC': 'PIS - ÓRG PUB FED 0,65 - SERVIÇO PRESTADO', 'F2B_TRIB': 'PISRET', 'F2B_RALIQ': '000017'},
        {'F2B_FILIAL': '01', 'F2B_REGRA': 'S00201', 'F2B_DESC': 'COFINS - SERVIÇO NÃO CUMULATIVO', 'F2B_TRIB': 'COF', 'F2B_RALIQ': '000008'}]
coe = ns['_trib_coerencia']({'F2B': F2BC, 'F28': atuais})
kinds = sorted((c['regra'], c['tipo']) for c in coe)
confere('E00302: 1% na descrição × alíquota 1,5', ('E00302', 'aliquota') in kinds, coe)
confere('E00301 coerente', not any(c['regra'] == 'E00301' for c in coe))
confere('E00307: descrição INSS, tributo ISS', ('E00307', 'tributo') in kinds)
confere('sem % na descrição não acusa (S00105)', not any(c['regra'] == 'S00105' for c in coe))
confere('TA001 fora do padrão de tamanho', any(c['tipo'] == 'codigo' and c['regra'] == 'TA001' for c in coe), coe)
confere('PISRET é família PIS, COF é família COFINS', not any(c['regra'] in ('S00105', 'S00201') and c['tipo'] == 'tributo' for c in coe))

# ── perfil com o tipo errado ────────────────────────────────────────────────
regs_tipo = {'F2B': [{'F2B_FILIAL': '01', 'F2B_REGRA': 'X1', 'F2B_TRIB': 'ICMS', 'F2B_PERFPA': '000004', 'F2B_PERFPR': '000004'}],
             'F20': [{'F20_FILIAL': '', 'F20_CODIGO': '000004', 'F20_TIPO': '04', 'F20_DESC': 'energia'}]}
an = ns['_trib_analisa_base']({'tabelas': {}}, regs_tipo, HOJE)
confere('perfil de participante com código que só existe como produto',
        [(x['campo'], x['motivo']) for x in an['refs']] == [('F2B_PERFPA', 'existe, mas com outro tipo de perfil')], an['refs'])

# ── coleta faseada com REST fingida ─────────────────────────────────────────
chamadas = []


def rest(cfg, heads, auth, tok, sql, limite, timeout):
    chamadas.append(sql)
    if 'USER_TAB_COLUMNS' in sql:
        csvt = 'TABLE_NAME;COLUMN_NAME;DATA_TYPE;COLUMN_ID\n' + '\n'.join(
            f'{t};{c};{d};1' for t, c, d in COLS if t != 'SA1010')
        return True, {'ok': True, 'csv': csvt, 'environment': 'producao'}, None
    if 'FROM SX2' in sql:
        return True, {'ok': True, 'csv': 'X2_CHAVE;X2_NOME;X2_MODO;X2_MODOUN;X2_MODOEMP\nF2B;Regra Tributaria;E;E;E\n'}, None
    if 'FROM SX3' in sql:
        return True, {'ok': True, 'csv': 'X3_ARQUIVO;X3_CAMPO;X3_TITULO;X3_CBOX;X3_CONTEXT\nF2B;F2B_STATUS;Status;1=Em teste;R\n'}, None
    if 'FROM SIX' in sql:
        return True, {'ok': True, 'csv': 'INDICE;ORDEM;CHAVE\nF2B;1;F2B_FILIAL+F2B_ID\n'}, None
    if 'SYS_COMPANY' in sql:
        return False, {'ok': False}, 'ORA-00942: table or view does not exist'
    if 'COUNT(*)' in sql:
        return True, {'ok': True, 'csv': 'TAB;FIL;QTD\nF2B;01;2\nCIN;01;1\nF29; ;0\n'}, None
    if 'UTL_RAW' in sql:
        return False, {'ok': False}, 'ORA-00932: inconsistent datatypes'
    if 'FROM CIN010' in sql:
        return True, {'ok': True, 'csv': 'CIN_FILIAL;CIN_CODIGO;CIN_FORMUL\n01;F001;O:VAL_MERCADORIA*0.9\n'}, None
    if 'FROM F2B010' in sql:
        return True, {'ok': True, 'csv': 'F2B_FILIAL;F2B_ID;F2B_REGRA\n01;abc;TR0001\n01;def;TR0002\n'}, None
    return False, {'ok': False}, 'inesperado'


ns['_trib_query'] = rest
cfg = {'banco': 'oracle', 'empresa': '01'}
meta, pend, env = ns['_trib_fase0'](cfg, {}, None, 'tok', '010', time.time() + 40)
confere('fase 0: environment', env == 'producao')
confere('fase 0: pendentes = cadastro com registro (F29 vazia fora)', sorted(pend) == ['CIN', 'F2B'], pend)
confere('fase 0: SYS_COMPANY ausente não derruba', meta['filiais'] == [] and 'filiais' in meta['erros'])
confere('fase 0: contagem por filial', meta['tabelas']['F2B']['por_filial'] == {'01': 2} and meta['tabelas']['F29']['total'] == 0)
confere('fase 0: cbox e título do SX3', meta['tabelas']['F2B']['cbox'] == {'F2B_STATUS': {'1': 'Em teste'}})
confere('fase 0: tabela inexistente', meta['tabelas']['F2E']['existe'] is False)
confere('fase 0: memo detectado', meta['tabelas']['CIN']['memos'] == ['CIN_FORMUL'])
dados, resto = ns['_trib_le_tabelas'](cfg, {}, None, 'tok', meta, pend, time.time() + 40)
confere('fase 1: leu tudo', resto == [] and dados['F2B']['ok'] and len(dados['F2B']['linhas']) == 2)
confere('fase 1: memo pela 2ª variante (CLOB)', dados['CIN']['variante'] == 1 and dados['CIN']['linhas'][0][2].startswith('O:VAL'))
confere('nenhuma chamada com ;', all(';' not in s for s in chamadas))
# sem tempo: nada lido, tudo continua pendente
dados2, resto2 = ns['_trib_le_tabelas'](cfg, {}, None, 'tok', meta, pend, time.time() + 3)
confere('sem tempo: tabelas continuam pendentes', resto2 == pend and dados2 == {})

print(f'{ok} ok, {falhou} falhou')
raise SystemExit(1 if falhou else 0)
