# Teste das funções PURAS da aba Protótipo Core (09/11/2026).
#
# Como rodar, de qualquer lugar:  python3 docs/testes/core-back.py
# Mesmo método dos outros testes: extrai o trecho do módulo em vez de
# importá-lo (api/index.py sobe Flask e exige DATABASE_URL). Cobre: SQL do
# dicionário e das tabelas (sufixo, sem ';', só SELECT, memo em hex por banco,
# limite por dialeto, campos virtuais fora), decodificação do memo em hex,
# JSON tolerante, leitura da proposta (nomes do de-para) e as regras de
# conceito/estágio nos cenários sucesso, locação, erro na Etapa 1 e fila.
import csv, io, json, pathlib, re, unicodedata, time
from datetime import date, datetime, timedelta, timezone

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('CORE_TABELAS = (')
fim = src.index('def _core_gate(customer)')
ns = {'re': re, 'csv': csv, 'io': io, 'json': json, 'date': date, 'datetime': datetime,
      'timedelta': timedelta, 'unicodedata': unicodedata, 'time': time,
      'BANCOS': ('oracle', 'mssql', 'postgres'), 'CRM_PRJ': 'PRJ',
      'TZ_SP': timezone(timedelta(hours=-3))}
# dependências puras de outras partes do módulo
for nome, fimtag in (('def _integ_csv(texto)', '# ── Motivo da inconsistência'),):
    i = src.index(nome); f = src.index(fimtag, i)
    exec(compile(src[i:f], nome, 'exec'), ns)
exec(compile(src[ini:fim], 'core', 'exec'), ns)

ok = falhou = 0


def confere(nome, cond):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome)


DIC = {t: [{'campo': c, 'tipo': tp, 'tam': None, 'dec': None, 'titulo': c, 'cbox': ''} for c, tp in lst]
       for t, lst in ns['CORE_CAMPOS_MINIMOS'].items()}

# ── SQL do dicionário ───────────────────────────────────────────────────────
sqld = ns['_core_sql_dicionario']('010')
confere('dicionário lê SX3010', 'FROM SX3010' in sqld)
confere('dicionário só SELECT', sqld.strip().upper().startswith('SELECT'))
confere('dicionário sem ;', ';' not in sqld)
confere('dicionário cobre ZA3 e CNB', "'ZA3'" in sqld and "'CNB'" in sqld)
confere('dicionário traz contexto (virtual)', 'X3_CONTEXT' in sqld)

# ── SELECT por tabela e memo em hex ─────────────────────────────────────────
s_ora = ns['_core_select'](DIC, 'ZA3', '010', "RTRIM(ZA3_MSGID) = 'abc'", 'ZA3_DTINC DESC', 'oracle', 2, 0, 50)
confere('oracle: RAWTOHEX(DBMS_LOB.SUBSTR)', 'RAWTOHEX(DBMS_LOB.SUBSTR(ZA3_JSONFI, 1900, 1))' in s_ora)
confere('oracle: 2º pedaço no offset 1901', 'DBMS_LOB.SUBSTR(ZA3_JSONFI, 1900, 1901)) AS ZA3_JSONFI__1' in s_ora)
confere('oracle: limite por ROWNUM em subconsulta', s_ora.startswith('SELECT * FROM (SELECT') and 'ROWNUM <= 50' in s_ora)
confere('oracle: RTRIM nos caracteres', 'RTRIM(ZA3_MSGID) AS ZA3_MSGID' in s_ora)
confere('oracle: RECNO', 'R_E_C_N_O_ AS RECNO' in s_ora)
confere('sem ;', ';' not in s_ora)
s_clob = ns['_core_select'](DIC, 'ZA3', '010', None, None, 'oracle', 1, 1)
confere('oracle CLOB: UTL_RAW.CAST_TO_RAW', 'RAWTOHEX(UTL_RAW.CAST_TO_RAW(DBMS_LOB.SUBSTR(ZA3_ERRO, 1900, 1)))' in s_clob)
s_sem = ns['_core_select'](DIC, 'ZA3', '010', None, None, 'oracle', 1, None)
confere('sem memo: nenhum campo memo', 'ZA3_JSONFI' not in s_sem and 'ZA3_MSGID' in s_sem)
s_ms = ns['_core_select'](DIC, 'CN9', '010', "RTRIM(CN9_NUMERO) = '0001/2026'", 'CN9_REVISA DESC', 'mssql', 3, 0, 20)
confere('mssql: TOP', s_ms.startswith('SELECT TOP 20 '))
confere('mssql: CONVERT(..., 2) hex', "CONVERT(VARCHAR(MAX), SUBSTRING(CONVERT(VARBINARY(MAX), CN9_ZMEMOR), 1, 1900), 2) AS CN9_ZMEMOR__0" in s_ms)
confere('mssql: 3º pedaço', 'CN9_ZMEMOR), 3801, 1900), 2) AS CN9_ZMEMOR__2' in s_ms)
confere('mssql sem ROWNUM', 'ROWNUM' not in s_ms)
confere('mssql: variante 1 não existe', ns['_core_memo_hex']('X', 'mssql', 1, 1) is None)
confere('variantes oracle', ns['_core_variantes']('oracle') == [0, 1, None])
confere('variantes mssql', ns['_core_variantes']('mssql') == [0, None])
confere('chunks=0 → memo fora', 'ZA3_JSONFI' not in ns['_core_select'](DIC, 'ZA3', '010', None, None, 'oracle', 0, 0))
for sql in (s_ora, s_ms, s_clob, sqld):
    confere('sem palavra proibida', not re.search(r'\b(INSERT|UPDATE|DELETE|DROP|EXEC|INTO)\b', sql))

# ── hex → texto ─────────────────────────────────────────────────────────────
txt = '{"numeroProposta":"PROP-2026-0001","cliente":{"codigo":"000123","loja":"01","nome":"Dígitro"}}'
h = txt.encode('utf-8').hex().upper()
p1, p2 = h[:3800], h[3800:]
confere('junta pedaços e decodifica UTF-8', ns['_core_hex_texto']([p1, p2, '']) == txt)
confere('cp1252 quando não é UTF-8', ns['_core_hex_texto'](['Dígitro'.encode('cp1252').hex()]) == 'Dígitro')
confere('pedaço vazio encerra', ns['_core_hex_texto'](['41', '', '42']) == 'A')
confere('hex inválido volta cru', ns['_core_hex_texto'](['ZZ']) == 'ZZ')
confere('vazio → vazio', ns['_core_hex_texto']([None, '']) == '')

# ── linhas: memo juntado ────────────────────────────────────────────────────
csv_txt = 'ZA3_MSGID;ZA3_STG1;ZA3_JSONFI__0;ZA3_JSONFI__1;RECNO\nm1;L;' + p1 + ';' + p2 + ';7\n'
linhas = ns['_core_linhas'](csv_txt, DIC, 'ZA3')
confere('linha com memo juntado', linhas[0]['ZA3_JSONFI'] == txt and linhas[0]['ZA3_STG1'] == 'L')
confere('pedaços não vazam', 'ZA3_JSONFI__0' not in linhas[0])

# ── JSON tolerante e leitura da proposta ────────────────────────────────────
confere('json com lixo no fim', ns['_core_json'](txt + '\x00\x00 resto') == json.loads(txt))
confere('json inválido → None', ns['_core_json']('abc') is None)
confere('vazio → None', ns['_core_json']('') is None)

JS = {
  "oportunidade": {"opportunityId": "9f1c-…", "numeroProposta": "PRP-0001", "tipoVenda": "001",
                    "modalidade": "1", "unidadeNegocio": "NVC", "tabelaPreco": "08",
                    "condicaoPagamento": {"codigo": "C12"}, "consultorVendedor": {"codigo": "000045", "nome": "Ana"},
                    "garantia": "12 meses", "monitoramento": "NOC 24h", "memorialCalculo": "desconto 10% site A",
                    "cliente": {"codigo": "000123", "loja": "01", "nome": "Cliente Teste"}},
  "ordensVenda": [
    {"id": "OV1", "descricao": "NGC Corporate", "plataforma": "1", "tipoProduto": "1", "natureza": "1",
     "instrucaoTecnica": "instalar em 2 dias",
     "itens": [{"produto": {"codigo": "P001"}, "quantidade": 2, "valorUnitario": 100.0},
               {"produto": {"codigo": "P000"}, "quantidade": 1, "valorUnitario": 0}]},
    {"id": "OV2", "descricao": "Licença Nexus", "plataforma": "2", "tipoProduto": "2",
     "itens": [{"produto": {"codigo": "L001"}, "quantidade": 3, "valorUnitario": 50.0}]},
  ],
}
res = ns['_core_proposta_resumo'](JS)
confere('nº proposta', res['numeroProposta'] == 'PRP-0001')
confere('cliente código/loja/nome', (res['cliente'], res['clienteLoja'], res['clienteNome']) == ('000123', '01', 'Cliente Teste'))
confere('condição pega o código do objeto', res['condicaoPagamento'] == 'C12')
confere('vendedor pega o código', res['vendedor'] == '000045')
confere('UN', res['unidadeNegocio'] == 'NVC')
ords = ns['_core_ordens'](JS)
confere('2 ordens', len(ords) == 2 and ords[0]['tipoProduto'] == '1' and ords[1]['tipoProduto'] == '2')
confere('itens e valores', ords[0]['itens'][0]['codigo'] == 'P001' and ords[0]['valorTotal'] == 200.0 and ords[1]['valorTotal'] == 150.0)
confere('busca em lista', ns['_core_busca']({'a': [{'b': {'tipoVenda': '005'}}]}, 'tipoVenda') == '005')
confere('busca normaliza acento/caixa', ns['_core_busca']({'Tipo_de_Venda': '002'}, 'tipoDeVenda') == '002')

# ── conceitos e estágios: cenário de SUCESSO (venda) ────────────────────────
ZA3 = {'ZA3_MSGID': 'm1', 'ZA3_IDCRM': '9f1c', 'ZA3_STG1': 'L', 'ZA3_STG2': 'S', 'ZA3_STIPA': 'N',
       'ZA3_CONTRA': '0001/2026', 'ZA3_DTINC': '20261109', 'ZA3_HRINC': '10:05', 'ZA3_DTFIM': '20261109', 'ZA3_HRFIM': '10:06'}
PRJ = [{'ZA0_CODIGO': '000010 2026', 'ZA0_TPPROD': '1', 'ZA0_MODALI': '1', 'ZA0_PLATAF': '1', 'ZA0_PROPOS': 'PRP-0001',
        'ZA0_CODCLI': '000123', 'ZA0_LOJCLI': '01', 'ZA0_IT': 'instalar em 2 dias', 'ZA0_STATUS': '1', 'ZA0_NOME': 'NGC', 'ZA0_CONTRA': '0001/2026'},
       {'ZA0_CODIGO': '000011 2026', 'ZA0_TPPROD': '2', 'ZA0_MODALI': '1', 'ZA0_PLATAF': '2', 'ZA0_PROPOS': 'PRP-0001',
        'ZA0_NUMSER': 'V00000000012', 'ZA0_CODCLI': '000123', 'ZA0_LOJCLI': '01', 'ZA0_STATUS': '1', 'ZA0_NOME': 'Nexus', 'ZA0_CONTRA': '0001/2026'}]
ITENS = [{'_PRJ': '000010 2026', '_PRODUTO': 'P001', 'ZA1_CRM': 'S', 'ZA1_AUTO': ''},
         {'_PRJ': '000010 2026', '_PRODUTO': 'P000', 'ZA1_CRM': 'S', 'ZA1_AUTO': ''},
         {'_PRJ': '000010 2026', '_PRODUTO': 'PRJ0000102026', 'ZA1_CRM': '', 'ZA1_AUTO': 'S'},
         {'_PRJ': '000011 2026', '_PRODUTO': 'L001', 'ZA1_CRM': 'S', 'ZA1_AUTO': ''}]
SB1 = [{'B1_COD': 'PRJ0000102026', 'B1_PRV1': '200'}]
CTD = [{'CTD_ITEM': '0000102026'}, {'CTD_ITEM': '0000112026'}]
CN9 = [{'CN9_NUMERO': '0001/2026', 'CN9_REVISA': '001', 'CN9_SITUAC': '05', 'CN9_TPCTO': '001', 'CN9_ZMODAL': '1',
        'CN9_ZUNNEG': '1', 'CN9_ZTABPR': '08', 'CN9_VIGE': '12', 'CN9_UNVIGE': 'M', 'CN9_ZMEMOR': 'desconto 10% site A',
        'CN9_ZCODVD': '000045', 'CN9_ZNOMVD': 'Ana', 'CN9_ZGARAA': '12 meses', 'CN9_ZMONIT': 'NOC 24h', 'CN9_XOPORT': 'PRP-00', 'CN9_VLTOT': '350'}]
CNA = [{'_PRJ': '000010 2026', 'CNA_ZPLATA': '1', 'CNA_REVISA': '001'}, {'_PRJ': '000011 2026', 'CNA_ZPLATA': '2', 'CNA_REVISA': '001'}]
CNB = [{'CNB_ITEMCTA': '0000102026', 'CNB_PRODUT': 'PRJ0000102026', 'CNB_VLTOT': '200'},
       {'CNB_ITEMCTA': '0000112026', 'CNB_PRODUT': 'L001', 'CNB_VLTOT': '150'}]
C = ns['_core_conceitos'](res, ords, ZA3, PRJ, ITENS, SB1, CTD, CN9, CNA, CNB, [])
por = {}
for c in C:
    por.setdefault(c['cod'], []).append(c)
niv = lambda cod, i=0: por[cod][i]['nivel']  # noqa: E731
confere('C23 ok (proposta igual nos projetos)', niv('C23') in ('ok', 'alerta'))
confere('C23 alerta pelo XOPORT truncado', niv('C23') == 'alerta')
confere('cardinalidade 1 projeto por OV', niv('CARD') == 'ok')
confere('1 contrato · planilhas = projetos', niv('CARD2') == 'ok')
confere('C07 físico ok (PRJ no SB1 + ZA1_AUTO)', por['C07'][0]['nivel'] == 'ok')
confere('C07 virtual ok (NS V+11)', por['C07'][1]['nivel'] == 'ok')
confere('C19 venda: 1 PRJ na CNB', niv('C19') == 'ok')
confere('VAL: preço do PRJ = Σ ordem', niv('VAL') == 'ok')
confere('C18 valor zero fora da CNB', niv('C18') == 'ok')
confere('C06 plataforma bate', all(x['nivel'] == 'ok' for x in por['C06']))
confere('C02 IT gravada', niv('C02') == 'ok')
confere('CTD dos dois projetos', all(x['nivel'] == 'ok' for x in por['CTD']))
confere('C03 tipo de venda', niv('C03') == 'ok')
confere('C04 modalidade', niv('C04') == 'ok')
confere('C05 UN NVC = 1', niv('C05') == 'ok')
confere('C13 tabela', niv('C13') == 'ok')
confere('C12 C12 → 12 meses', niv('C12') == 'ok')
confere('C01 memorial gravado', niv('C01') == 'ok')
confere('C16 vendedor', niv('C16') == 'ok')
confere('C14 clientes', niv('C14') == 'ok')
confere('VALC soma', niv('VALC') == 'ok')
confere('P11 info (não implementado)', niv('P11') == 'info')
confere('todo conceito tem estágio', all(c['estagio'] in {'crm', 'etapa1', 'etapa2', 'painel', 'contrato', 'retorno'} for c in C))

E = ns['_core_estagios'](ZA3, res, ords, PRJ, ITENS, CN9, CNA, CNB)
confere('6 estágios na ordem', [e['id'] for e in E] == ['crm', 'etapa1', 'etapa2', 'painel', 'contrato', 'retorno'])
confere('estágios ok no sucesso', [e['nivel'] for e in E[:5]] == ['ok'] * 5 and E[5]['nivel'] == 'na')

# ── LOCAÇÃO com PRJ na CNB → C19 erro ───────────────────────────────────────
PRJL = [dict(PRJ[0], ZA0_MODALI='3'), dict(PRJ[1], ZA0_MODALI='3')]
resL = dict(res, modalidade='3')
CL = ns['_core_conceitos'](resL, ords, ZA3, PRJL, ITENS, SB1, CTD, [dict(CN9[0], CN9_ZMODAL='3')], CNA, CNB, [])
c19 = [c for c in CL if c['cod'] == 'C19'][0]
confere('C19 locação: PRJ na CNB = erro', c19['nivel'] == 'erro' and 'Locação' in c19['titulo'])

# ── valor zero DENTRO da CNB → C18 erro ─────────────────────────────────────
CNBz = CNB + [{'CNB_ITEMCTA': '0000102026', 'CNB_PRODUT': 'P000', 'CNB_VLTOT': '0'}]
Cz = ns['_core_conceitos'](res, ords, ZA3, PRJ, ITENS, SB1, CTD, CN9, CNA, CNBz, [])
confere('C18 zero na CNB = erro', [c for c in Cz if c['cod'] == 'C18'][0]['nivel'] == 'erro')

# ── ERRO na Etapa 1 ─────────────────────────────────────────────────────────
ZA3E = dict(ZA3, ZA3_STG1='E', ZA3_STG2='N', ZA3_CONTRA='', ZA3_ERRO='JSON inválido: campo tipoVenda ausente')
EE = ns['_core_estagios'](ZA3E, {}, [], [], [], [], [], [])
confere('etapa1 erro', EE[1]['nivel'] == 'erro' and 'JSON inválido' in EE[1]['resumo'][0])
confere('crm alerta sem JSON', EE[0]['nivel'] == 'alerta')
confere('painel/contrato n/a', EE[3]['nivel'] == 'na' and EE[4]['nivel'] == 'na')
CE = ns['_core_conceitos']({}, [], ZA3E, [], [], [], [], [], [], [], [])
confere('sem JSON só P11', [c['cod'] for c in CE] == ['P11'])

# ── FILA (aguardando Sincronizar) ───────────────────────────────────────────
ZA3A = dict(ZA3, ZA3_STG2='A', ZA3_CONTRA='')
EA = ns['_core_estagios'](ZA3A, res, ords, [], [], [], [], [])
confere('etapa2 aguardando = alerta', EA[2]['nivel'] == 'alerta' and 'Sincronizar' in EA[2]['resumo'][0])
CA = ns['_core_conceitos'](res, ords, ZA3A, [], [], [], [], [], [], [], [])
confere('C23 info antes da Etapa 2', [c for c in CA if c['cod'] == 'C23'][0]['nivel'] == 'info')

# ── sucesso sem ZA0/CN9 → erro nos estágios ─────────────────────────────────
ES = ns['_core_estagios'](ZA3, res, ords, [], [], [], [], [])
confere('sucesso sem projeto = erro', ES[3]['nivel'] == 'erro' and ES[4]['nivel'] == 'erro')

# ── chaves e utilitários ────────────────────────────────────────────────────
confere('chave padrão', ns['_core_chave'](DIC, 'ZA1_COD') == 'ZA1_CODIGO')
DIC2 = {'ZA1': [{'campo': 'ZA1_CODPRJ', 'tipo': 'C'}]}
confere('chave por padrão regex', ns['_core_chave'](DIC2, 'ZA1_COD') == 'ZA1_CODPRJ')
confere('lista IN escapa aspas', ns['_core_lista_in'](["a'b", 'c', ' c ']) == "'a''b', 'c'")
confere('lista IN vazia', ns['_core_lista_in'](['', None]) is None)
confere('data AAAAMMDD', ns['_core_data']('20261109') == '09/11/2026')
confere('legendas STG2', ns['CORE_LEGENDAS']['ZA3_STG2']['S'] == 'Sucesso')
# ORDER BY só com colunas do dicionário (ORA-00904 ZA4_SEQ, 09/11)
confere('ordem: só colunas existentes', ns['_core_ordem'](DIC, 'ZA4', 'ZA4_CODPRJ', 'ZA4_SEQUEN', 'ZA4_SEQ') == 'ZA4_CODPRJ, ZA4_SEQUEN')
confere('ordem: DESC preservado', ns['_core_ordem'](DIC, 'CN9', 'CN9_REVISA DESC') == 'CN9_REVISA DESC')
confere('ordem: nada existe → RECNO', ns['_core_ordem'](DIC, 'ZA4', 'ZA4_XPTO') == 'R_E_C_N_O_')
confere('chave ZA4 padrão CODPRJ', ns['_core_chave'](DIC, 'ZA4_PRJ') == 'ZA4_CODPRJ')

print(f'{ok} ok, {falhou} falhou')
raise SystemExit(1 if falhou else 0)
