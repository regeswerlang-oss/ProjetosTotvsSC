# Teste das funcoes PURAS do painel CP.
#
# Como rodar, de qualquer lugar:  python3 docs/testes/painel-cp-back.py
# Testa as funções PURAS do painel CP com a forma REAL do payload da agenda
# (coletada da API Totvs SC pelo MCP tasks-sc). Extrai o trecho do módulo em
# vez de importá-lo: api/index.py sobe Flask e exige DATABASE_URL.
import pathlib, re, unicodedata, time
from datetime import date, datetime, timedelta, timezone

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('CP_AGENDA_PATHS = tuple(')
fim = src.index('@app.get("/api/cp/contexto")')
ns = {'re': re, 'unicodedata': unicodedata, 'time': time, 'date': date,
      'datetime': datetime, 'timedelta': timedelta, 'timezone': timezone,
      'os': __import__('os'), 'q': None, 'pci_get': None, 'requests': None,
      'TASKS_BASE': 'https://api.tscst.com.br/restAPI', 'PCIUnavailable': Exception}
trecho = src[ini:fim]
# tira as funcoes que dependem de rede/banco (ficam fora deste teste)
exec(compile(trecho, 'cp', 'exec'), ns)

HOJE = date(2026, 10, 5)
AGENDA = [
 {"resource": {"nome": "Geane Narloch", "code": "TEC180", "email": "geane.narloch@totvs.com.br", "region": "301"},
  "scheduleData": [
    # 1. passada, sem OS, status C, owner = CP  -> PENDENTE (owner+coord)
    {"id": 1264418, "resource": "TEC180", "date": "2026-09-24", "status": "C",
     "hourStart": "08:00", "hourEnd": "12:00", "estimativa": 4, "realizada": 0,
     "owner": "TSC623", "owner_name": "Reges Paulo Werlang", "title": "Tts Rs",
     "customer": "10028400", "customer_name": "TTS RS", "customer_region": "000",
     "project": ["1002840017"], "project_name": ["REFORMA TRIBUTARIA TIMAC"],
     "modulo": ["EXTRA PROJETO", "ACOMPANHAMENTO"], "activities": ["Atividades Diversas"],
     "local": "REMOTO        ", "observacao": "reforma timac", "service_order_exist": False},
    # 2. passada MAS com OS -> FORA
    {"id": 1270159, "resource": "TEC180", "date": "2026-09-22", "status": "C",
     "estimativa": 1, "realizada": 10, "owner": "TSC623", "owner_name": "Reges Paulo Werlang",
     "customer": "10028400", "project": ["1002840017"], "service_order_exist": True},
    # 3. FUTURA sem OS -> FORA (plano, não atraso)
    {"id": 1263879, "resource": "TEC180", "date": "2026-10-20", "status": "P",
     "estimativa": 4, "owner": "TSC623", "owner_name": "Reges Paulo Werlang",
     "customer": "10028400", "project": ["1002840017"], "service_order_exist": False},
    # 4. passada, sem OS, CANCELADA -> FORA
    {"id": 7, "resource": "TEC180", "date": "2026-09-10", "status": "ZV",
     "estimativa": 8, "owner": "TSC623", "owner_name": "Reges Paulo Werlang",
     "customer": "10028400", "project": ["1002840017"], "service_order_exist": False},
    # 5. passada, sem OS, já APONTADA (ZA) -> FORA
    {"id": 8, "resource": "TEC180", "date": "2026-09-11", "status": "ZA",
     "estimativa": 8, "owner": "TSC623", "owner_name": "Reges Paulo Werlang",
     "customer": "10028400", "project": ["1002840017"], "service_order_exist": False},
    # 6. HOJE, sem OS -> PENDENTE com 0 dias
    {"id": 9, "resource": "TEC180", "date": "2026-10-05", "status": "C",
     "estimativa": 2, "owner": "TSC623", "owner_name": "Reges Paulo Werlang",
     "customer": "10028400", "project": ["1002840017"], "service_order_exist": False},
  ]},
 {"resource": {"nome": "Bruno Marquesi de Macedo", "code": "A00219", "email": "bruno.marquesi@totvs.com.br"},
  "scheduleData": [
    # 7. owner de OUTRO CP, projeto de OUTRO CP -> FORA quando filtra por Reges
    {"id": 1269199, "resource": "A00219", "date": "2026-09-23", "status": "C",
     "estimativa": 10, "owner": "A00219", "owner_name": "Bruno Marquesi de Macedo",
     "customer": "S0018101", "customer_name": "SUPORTE INTERNO ACR",
     "project": ["S001810124"], "project_name": ["ATENDIMENTO TIC"],
     "service_order_exist": False},
    # 8. owner de outro, mas PROJETO do Reges -> PENDENTE só pela lente coord
    {"id": 11, "resource": "A00219", "date": "2026-09-25", "status": "C",
     "estimativa": 6, "owner": "TSCA92", "owner_name": "Tiago Nardi",
     "customer": "TFEGN200", "customer_name": "OLIM", "project": ["TFEGN20001"],
     "project_name": ["IMPLANTACAO OLIM"], "service_order_exist": False},
    # 9. owner pelo NOME (matrícula antiga, código não casa) -> PENDENTE
    {"id": 12, "resource": "A00219", "date": "2026-09-26", "status": "S",
     "estimativa": 3, "owner": "TSC999", "owner_name": "(*) REGES PAULO WERLANG",
     "customer": "99999900", "customer_name": "FORA DA CARTEIRA",
     "project": ["9999990001"], "service_order_exist": False},
  ]},
]
COORDS = {
  "REGES PAULO WERLANG": {"chave": "REGES PAULO WERLANG", "nome": "Reges Paulo Werlang",
    "codigos": {"TSC623"}, "clientes": {"10028400", "TFEGN200"},
    "projetos": {"1002840017": {}, "TFEGN20001": {}}, "ativos": 2},
  "TIAGO NARDI": {"chave": "TIAGO NARDI", "nome": "Tiago Nardi", "codigos": {"TSCA92"},
    "clientes": {"S0018101"}, "projetos": {"S001810124": {}}, "ativos": 1},
}

ok, bad = [], []
def t(nome, cond, extra=''):
    (ok if cond else bad).append(nome + (f' [{extra}]' if extra else ''))

p = ns['_cp_pendentes'](AGENDA, HOJE, "REGES PAULO WERLANG", COORDS, None)
ids = [r['id'] for r in p]
t('só o que é dela e está pendente', sorted(ids) == [9, 11, 12, 1264418], ids)
t('ordenado do mais atrasado para o mais novo', [r['dias'] for r in p] == sorted([r['dias'] for r in p], reverse=True), [r['dias'] for r in p])
r1 = next(r for r in p if r['id'] == 1264418)
t('dias corridos corretos', r1['dias'] == 11, r1['dias'])
t('faixa pela idade', r1['faixa'] == '11-15', r1['faixa'])
t('lentes owner+coord quando as duas casam', r1['por'] == ['owner', 'coord'], r1['por'])
t('modulo em lista vira texto', r1['modulo'] == 'EXTRA PROJETO, ACOMPANHAMENTO', r1['modulo'])
t('projeto desembrulhado da lista', r1['projeto'] == '1002840017' and r1['projeto_nome'] == 'REFORMA TRIBUTARIA TIMAC')
t('local sem o padding do Protheus', r1['local'] == 'REMOTO', repr(r1['local']))
t('e-mail vem do resource, nunca do código', r1['consultor_email'] == 'geane.narloch@totvs.com.br')
t('status rotulado', r1['status_label'] == 'Confirmado', r1['status_label'])
r9 = next(r for r in p if r['id'] == 9)
t('agenda de hoje entra com 0 dias', r9['dias'] == 0 and r9['faixa'] == '0-3', r9['dias'])
r11 = next(r for r in p if r['id'] == 11)
t('só a lente de projeto quando o owner é outro', r11['por'] == ['coord'], r11['por'])
r12 = next(r for r in p if r['id'] == 12)
t('owner casado pelo NOME ignora o (*) e a matrícula velha', r12['por'] == ['owner'], r12['por'])

# recorte de acesso: usuário do cliente só vê os clientes liberados
pa = ns['_cp_pendentes'](AGENDA, HOJE, "REGES PAULO WERLANG", COORDS, {"10028400"})
t('allowed_customers corta o resto', sorted(r['id'] for r in pa) == [9, 1264418], [r['id'] for r in pa])

# sem coordenador escolhido = célula inteira (menos o que já tem OS/cancelado)
ptodos = ns['_cp_pendentes'](AGENDA, HOJE, "", COORDS, None)
t('sem CP devolve a célula toda', sorted(r['id'] for r in ptodos) == [9, 11, 12, 1264418, 1269199], [r['id'] for r in ptodos])

# outro CP
pt = ns['_cp_pendentes'](AGENDA, HOJE, "TIAGO NARDI", COORDS, None)
t('outro CP vê o que é dele', sorted(r['id'] for r in pt) == [11, 1269199], [r['id'] for r in pt])

# faixas
t('faixas', [ns['_cp_faixa'](d) for d in (0, 3, 4, 5, 6, 10, 11, 15, 16, 400)]
   == ['0-3','0-3','4-5','4-5','6-10','6-10','11-15','11-15','16+','16+'])
# normalizador
t('normaliza (*) e acento', ns['_cp_norm']('(*) José  da Silva ') == 'JOSE DA SILVA', ns['_cp_norm']('(*) José  da Silva '))
# palpite
t('palpite casa nome curto do login', ns['_cp_palpite'](COORDS, 'Reges Werlang') == 'REGES PAULO WERLANG')
t('palpite casa nome completo', ns['_cp_palpite'](COORDS, 'REGES PAULO WERLANG') == 'REGES PAULO WERLANG')
t('palpite recusa ambíguo', ns['_cp_palpite']({'ANA SILVA': {}, 'ANA PAULA SILVA': {}}, 'Ana Silva') is None)
t('palpite recusa desconhecido', ns['_cp_palpite'](COORDS, 'Maria Souza') is None)
t('palpite com nome vazio', ns['_cp_palpite'](COORDS, '') is None)
# fuso
t('hoje em Florianopolis, não em UTC', ns['_cp_hoje']() == datetime.now(timezone(timedelta(hours=-3))).date())
t('_cp_dia tolera timestamp e lixo', ns['_cp_dia']('2026-09-24T00:00:00Z') == date(2026,9,24) and ns['_cp_dia'](None) is None and ns['_cp_dia']('xx') is None)
# candidatos de rota
t('candidatos de rota sem duplicata', list(ns['CP_AGENDA_PATHS']) == ['/PCITConectaResourceSchedule', '/PCITConectaProjetos/agenda'], ns['CP_AGENDA_PATHS'])

print(f'\n== OK ({len(ok)}) ==')
for s in ok: print('  v ' + s)
if bad:
    print(f'\n== FALHOU ({len(bad)}) ==')
    for s in bad: print('  x ' + s)
raise SystemExit(1 if bad else 0)
