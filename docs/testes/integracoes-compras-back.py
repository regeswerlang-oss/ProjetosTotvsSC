# Teste das funções PURAS do grupo Compras × Transmite × Contas a Pagar da aba
# Integrações (15/11/2026).
#
# Como rodar, de qualquer lugar:  python3 docs/testes/integracoes-compras-back.py
# Mesmo método do integracoes-eai-back.py: extrai o trecho do módulo em vez de
# importá-lo. Cobre: unidade fixa por cliente (Cresol 010000, início 26/10),
# cliente sem unidade não lê a base, SQL dos blocos (sufixo, sem ';', só
# SELECT, sem relógio do banco, sem concatenação, filial por prefixo, janela
# limitada pelo início da unidade, variantes) e os níveis de cada indicador
# com um retrato SIMULADO da unidade.
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


def confere(nome, cond, extra=None):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome, '' if extra is None else extra)


HOJE = date(2026, 11, 15)
TZ = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 11, 15, 10, 0, tzinfo=TZ)
CRESOL = 'TFCTQI00'

# ── grupo e unidade ─────────────────────────────────────────────────────────
confere('compras é grupo conhecido', 'compras' in ns['INTEG_GRUPOS_BASE'])
confere('nulo continua = só RH', ns['_integ_grupos'](None) == ('rh',))
confere('transmite + compras na ordem da base', ns['_integ_grupos'](['compras', 'transmite']) == ('transmite', 'compras'))
cfg = ns['_com_cfg'](CRESOL)
confere('Cresol: unidade 010000', cfg['filiais'] == ('010000',), cfg)
confere('Cresol: início 26/10/2026', cfg['inicio'] == date(2026, 10, 26), cfg)
confere('código do cliente em minúsculas também', ns['_com_cfg']('tfctqi00')['filiais'] == ('010000',))
confere('cliente sem unidade: vazio', ns['_com_cfg']('000348D0')['filiais'] == ())
confere('integ_params sobrepõe (uso interno)',
        ns['_com_cfg'](CRESOL, {'com_filiais': '900000, 900001'})['filiais'] == ('900000', '900001'))
confere('filial com caractere estranho é descartada',
        ns['_com_cfg'](CRESOL, {'com_filiais': ["01' OR '1'='1"]})['filiais'] == ())
confere('sem filial = 1 = 0', ns['_com_fil']('F1_FILIAL', ()) == '1 = 0')
confere('filial por prefixo', ns['_com_fil']('F.F1_FILIAL', ('010000',)) == "(F.F1_FILIAL LIKE '010000%')")
confere('valor em reais', ns['_com_brl']('1234.5') == 'R$ 1.234,50')

# ── SQL dos blocos ──────────────────────────────────────────────────────────
scripts = ns['_integ_scripts']('010', HOJE, None, 'oracle', ['compras'], AGORA, {}, CRESOL)
ids = [s['id'] for s in scripts]
ESPERADOS = ['com_pc_resumo', 'com_doc_resumo', 'com_mon_resumo', 'com_cp_resumo',
             'com_pc_lista', 'com_pc_aprov', 'com_doc_lista', 'com_mon_lista', 'com_cp_lista']
confere('blocos do grupo Compras', ids == ESPERADOS, ids)
confere('resumos antes dos detalhes',
        [s['id'] for s in scripts if s.get('detalhe')] == ESPERADOS[4:])
for s in scripts:
    confere(f'{s["id"]}: rótulo cita a filial', '010000' in s['rotulo'] or s['id'] == 'com_pc_aprov')
    for k, sql in enumerate(s['sqls']):
        nome = f'{s["id"]}[{k}]'
        confere(f'{nome}: sem ; no fim', not sql.rstrip().endswith(';'))
        confere(f'{nome}: começa com SELECT', sql.startswith('SELECT'))
        confere(f'{nome}: filtra deletados', "D_E_L_E_T_ = ' '" in sql)
        confere(f'{nome}: sem relógio do banco', not re.search(r'SYSDATE|GETDATE|CURRENT_DATE|NOW\(', sql, re.I))
        confere(f"{nome}: sem <> ''", "<> ''" not in sql)
        confere(f'{nome}: sem concatenação', '||' not in sql)
        confere(f'{nome}: filial da unidade', "LIKE '010000%'" in sql)
        confere(f'{nome}: sem RTRIM na coluna de filial', not re.search(r"RTRIM\(\w+\.\w+_FIL\w*\)", sql))
        confere(f'{nome}: tabelas com sufixo', not re.search(r'\b(SC7|SF1|SD1|SE2|SDS|SCR|SA2|SAK)\s', sql))
S = {s['id']: s for s in scripts}
confere('janela começa no início da unidade', "F.F1_DTDIGIT >= '20261026'" in S['com_doc_resumo']['sql'])
confere('contas a pagar na mesma janela', "E.E2_EMIS1 >= '20261026'" in S['com_cp_resumo']['sql'])
confere('entrega vencida contra hoje (literal)', "C7.C7_DATPRF < '20261115'" in S['com_pc_resumo']['sql'])
confere('aprovação antiga = emissão até hoje - 5', "C7.C7_EMISSAO <= '20261110'" in S['com_pc_resumo']['sql'])
confere('pedido em aberto: resíduo e encerrado vazios',
        'RTRIM(C7.C7_RESIDUO) IS NULL' in S['com_pc_resumo']['sql'] and 'RTRIM(C7.C7_ENCER) IS NULL' in S['com_pc_resumo']['sql'])
confere('pedido também pela filial de entrega', "C7.C7_FILENT LIKE '010000%'" in S['com_pc_resumo']['sql'])
confere('variante sem C7_QTDACLA', 'C7_QTDACLA' in S['com_pc_resumo']['sqls'][0]
        and 'C7_QTDACLA' not in S['com_pc_resumo']['sqls'][1])
confere('variante E2_FILORIG → E2_FILIAL', 'E2_FILORIG' in S['com_cp_resumo']['sqls'][0]
        and 'E2_FILORIG' not in S['com_cp_resumo']['sqls'][1])
confere('origem Transmite = existe SDS', 'FROM SDS010 DS' in S['com_doc_resumo']['sql'])
confere('título de documento = E2_ORIGEM MATA10', "E.E2_ORIGEM LIKE 'MATA10%'" in S['com_cp_resumo']['sql'])
confere('sem abatimentos', "E2_TIPO NOT LIKE '%-'" in S['com_cp_resumo']['sql'])
confere('alçada pendente = CR_STATUS 02', "CR.CR_STATUS = '02'" in S['com_pc_aprov']['sql'])
confere('aprovador pelo nome da SAK, com variante sem', 'SAK010' in S['com_pc_aprov']['sqls'][0]
        and 'SAK010' not in S['com_pc_aprov']['sqls'][1])
confere('monitor: status vazio também conta', 'RTRIM(DS.DS_STATUS) IS NULL' in S['com_mon_resumo']['sql'])
confere('monitor: variante com e sem DS_EMISSA', 'DS_EMISSA' in S['com_mon_lista']['sqls'][0]
        and 'DS_EMISSA' not in S['com_mon_lista']['sqls'][1])

# corte da base mais recente que o início vale
sc2 = ns['_integ_scripts']('010', HOJE, date(2026, 11, 1), 'oracle', ['compras'], AGORA, {}, CRESOL)
confere('corte da base mais recente vale', "F.F1_DTDIGIT >= '20261101'" in sc2[1]['sql'])
# cliente sem unidade: nada é lido
sc3 = ns['_integ_scripts']('010', HOJE, None, 'oracle', ['compras'], AGORA, {}, '000348D0')
confere('sem unidade: todo SQL com 1 = 0', all('1 = 0' in x for s in sc3 for x in s['sqls']))
# grupo desligado não gera bloco
sc4 = ns['_integ_scripts']('010', HOJE, None, 'oracle', ['transmite'], AGORA, {}, CRESOL)
confere('transmite sozinho não lê compras', not any(s['id'].startswith('com_') for s in sc4))

# ── indicadores ─────────────────────────────────────────────────────────────
def B(linhas):
    return {'ok': True, 'linhas': linhas}


BLOCOS = {
    'com_pc_resumo': B([
        {'APROVACAO': 'B', 'ITENS': '9', 'PEDIDOS': '4', 'SALDO': '18500.40', 'MAIS_ANTIGO': '20261103',
         'PEDIDOS_ANTIGOS': '2', 'ENTREGA_VENCIDA': '3', 'PARCIAIS': '0', 'EM_PRENOTA': '0', 'ANTES_INICIO': '0'},
        {'APROVACAO': 'L', 'ITENS': '30', 'PEDIDOS': '17', 'SALDO': '120000', 'MAIS_ANTIGO': '20261027',
         'PEDIDOS_ANTIGOS': '12', 'ENTREGA_VENCIDA': '5', 'PARCIAIS': '4', 'EM_PRENOTA': '2', 'ANTES_INICIO': '0'},
        {'APROVACAO': 'R', 'ITENS': '1', 'PEDIDOS': '1', 'SALDO': '300', 'MAIS_ANTIGO': '20261105',
         'PEDIDOS_ANTIGOS': '1', 'ENTREGA_VENCIDA': '1', 'PARCIAIS': '0', 'EM_PRENOTA': '0', 'ANTES_INICIO': '0'}]),
    'com_doc_resumo': B([
        {'ORIGEM': 'T', 'TIPO': 'N', 'PC': 'COM', 'STATUS': 'A', 'QTD': '40', 'VALOR': '200000', 'MAIS_ANTIGA': '20261026', 'SEM_TITULO': '1'},
        {'ORIGEM': 'T', 'TIPO': 'N', 'PC': 'SEM', 'STATUS': 'A', 'QTD': '3', 'VALOR': '9000', 'MAIS_ANTIGA': '20261030', 'SEM_TITULO': '0'},
        {'ORIGEM': 'T', 'TIPO': 'N', 'PC': 'COM', 'STATUS': 'P', 'QTD': '2', 'VALOR': '1500', 'MAIS_ANTIGA': '20261106', 'SEM_TITULO': '0'},
        {'ORIGEM': 'M', 'TIPO': 'N', 'PC': 'SEM', 'STATUS': 'A', 'QTD': '5', 'VALOR': '4200.5', 'MAIS_ANTIGA': '20261028', 'SEM_TITULO': '0'},
        {'ORIGEM': 'M', 'TIPO': 'N', 'PC': 'PARCIAL', 'STATUS': 'A', 'QTD': '1', 'VALOR': '800', 'MAIS_ANTIGA': '20261102', 'SEM_TITULO': '0'},
        {'ORIGEM': 'M', 'TIPO': 'D', 'PC': 'SEM', 'STATUS': 'A', 'QTD': '2', 'VALOR': '300', 'MAIS_ANTIGA': '20261101', 'SEM_TITULO': '0'}]),
    'com_mon_resumo': B([{'STATUS': 'E', 'QTD': '2', 'JA_SF1': '0'}, {'STATUS': 'B', 'QTD': '1', 'JA_SF1': '0'},
                         {'STATUS': '-', 'QTD': '3', 'JA_SF1': '1'}]),
    'com_cp_resumo': B([
        {'CLASSE': 'DOC_TRANSMITE', 'ORIGEM': 'MATA100', 'QTD': '44', 'VALOR': '205000', 'SALDO': '90000', 'VENCIDOS': '2', 'SALDO_VENCIDO': '3100'},
        {'CLASSE': 'DOC_MANUAL', 'ORIGEM': 'MATA100', 'QTD': '6', 'VALOR': '5000', 'SALDO': '1000', 'VENCIDOS': '0', 'SALDO_VENCIDO': '0'},
        {'CLASSE': 'DOC_IMPOSTOS', 'ORIGEM': 'MATA100', 'QTD': '9', 'VALOR': '700', 'SALDO': '700', 'VENCIDOS': '0', 'SALDO_VENCIDO': '0'},
        {'CLASSE': 'FINANCEIRO', 'ORIGEM': 'FINA050', 'QTD': '7', 'VALOR': '10464.28', 'SALDO': '4153.34', 'VENCIDOS': '1', 'SALDO_VENCIDO': '500'}]),
}
inds = ns['_integ_indicadores'](BLOCOS, {}, HOJE, ['compras'], AGORA, {}, CRESOL)
I = {i['chave']: i for i in inds}
confere('todos os cartões do grupo', set(I) == {'com_pc_aprovacao', 'com_pc_abertos', 'com_pc_entrega', 'com_doc_transmite',
                                                'com_doc_sem_pc', 'com_doc_prenota', 'com_doc_sem_titulo', 'com_monitor',
                                                'com_cp_origem', 'com_cp_vencidos'}, sorted(I))
confere('grupo = compras', all(i['grupo'] == 'compras' for i in inds))
confere('aprovação: 4 pedidos, crítico (2 antigos)', I['com_pc_aprovacao']['valor'] == 4 and I['com_pc_aprovacao']['nivel'] == 'vermelho')
confere('aprovação: data do mais antigo', '03/11/2026' in I['com_pc_aprovacao']['texto'])
confere('em aberto: 22 pedidos, informativo', I['com_pc_abertos']['valor'] == 22 and I['com_pc_abertos']['nivel'] == 'info')
confere('em aberto: rejeitado citado', '1 pedido(s) rejeitado(s)' in I['com_pc_abertos']['texto'])
confere('entrega vencida só de liberado (5)', I['com_pc_entrega']['valor'] == 5 and I['com_pc_entrega']['nivel'] == 'amarelo')
confere('Transmite 45/51 notas normais', I['com_doc_transmite']['valor'] == '45/51' and I['com_doc_transmite']['nivel'] == 'amarelo')
confere('devolução fora da conta de normais', '6 nota(s)' in I['com_doc_transmite']['texto'])
confere('sem PC: 9 (3 Transmite + 6 manual, 1 parcial)', I['com_doc_sem_pc']['valor'] == 9
        and '3 veio(ram) pelo Transmite' in I['com_doc_sem_pc']['texto'] and '1 com pedido só em parte' in I['com_doc_sem_pc']['texto'])
confere('pré-nota de 06/11 = 9 dias, atenção', I['com_doc_prenota']['valor'] == 2 and I['com_doc_prenota']['nivel'] == 'amarelo')
confere('sem título = crítico', I['com_doc_sem_titulo']['valor'] == 1 and I['com_doc_sem_titulo']['nivel'] == 'vermelho')
confere('monitor: 6, crítico por ocorrência', I['com_monitor']['valor'] == 6 and I['com_monitor']['nivel'] == 'vermelho')
confere('monitor: lançado por fora citado', '1 já lançado(s) na SF1' in I['com_monitor']['texto'])
confere('CP: 66 títulos, informativo', I['com_cp_origem']['valor'] == 66 and I['com_cp_origem']['nivel'] == 'info')
confere('CP: Financeiro citado', '7 lançado(s) direto no Financeiro' in I['com_cp_origem']['texto'])
confere('CP: vencidos 3, R$ 3.600,00', I['com_cp_vencidos']['valor'] == 3 and 'R$ 3.600,00' in I['com_cp_vencidos']['texto'])
confere('pior nível do grupo = vermelho', ns['_integ_pior'](i['nivel'] for i in inds) == 'vermelho')

# tudo em ordem
LIMPO = {
    'com_pc_resumo': B([{'APROVACAO': 'L', 'PEDIDOS': '3', 'SALDO': '10', 'ENTREGA_VENCIDA': '0', 'PARCIAIS': '0',
                         'EM_PRENOTA': '0', 'ANTES_INICIO': '0', 'PEDIDOS_ANTIGOS': '0'}]),
    'com_doc_resumo': B([{'ORIGEM': 'T', 'TIPO': 'N', 'PC': 'COM', 'STATUS': 'A', 'QTD': '10', 'VALOR': '1', 'SEM_TITULO': '0'}]),
    'com_mon_resumo': B([]),
    'com_cp_resumo': B([{'CLASSE': 'DOC_TRANSMITE', 'QTD': '10', 'VALOR': '1', 'SALDO': '0', 'VENCIDOS': '0', 'SALDO_VENCIDO': '0'}]),
}
inds = ns['_integ_indicadores'](LIMPO, {}, HOJE, ['compras'], AGORA, {}, CRESOL)
confere('fluxo limpo: nenhum amarelo/vermelho', all(i['nivel'] in ('verde', 'info', 'cinza') for i in inds),
        [(i['chave'], i['nivel']) for i in inds])

# bloco não lido = cinza com motivo
inds = ns['_integ_indicadores']({'com_doc_resumo': {'ok': False, 'erro': 'Tabela SDS010 não existe'}}, {}, HOJE,
                                ['compras'], AGORA, {}, CRESOL)
I = {i['chave']: i for i in inds}
confere('doc não lido: 4 cinzas com motivo', all(I[k]['nivel'] == 'cinza' and 'SDS010' in I[k]['texto']
                                               for k in ('com_doc_transmite', 'com_doc_sem_pc', 'com_doc_prenota', 'com_doc_sem_titulo')))
confere('cliente sem unidade: um cartão cinza', [i['chave'] for i in ns['_integ_indicadores']({}, {}, HOJE, ['compras'], AGORA, {}, 'X')]
        == ['com_unidade'])

print(f'{ok} asserções OK, {falhou} falha(s)')
raise SystemExit(1 if falhou else 0)
