# Teste das funções PURAS do Diagnóstico de Sobrevivência e dos portões das
# rotas novas (aba Radar → Estratégico/Diagnóstico e aba Pendências).
#
#   python3 docs/testes/diag-back.py
import json, pathlib, re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('DIAG_CAMADAS = (')
fim = src.index('def _diag_monitcad(')
ns = {'re': re, 'os': __import__('os')}
exec(compile(src[ini:fim], 'diag', 'exec'), ns)
st, dsql, num = ns['_diag_status'], ns['_diag_sql'], ns['_diag_num']

ok = falhou = 0


def confere(nome, cond):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome)


Z = {'modo': 'zero'}
confere('zero verde', st(Z, 'teste', 0, 100) == 'verde')
confere('zero amarelo até 10%', st(Z, 'teste', 10, 100) == 'amarelo')
confere('zero vermelho acima', st(Z, 'teste', 11, 100) == 'vermelho')
confere('zero sem base = cinza', st(Z, 'teste', 0, 0) == 'cinza')
confere('zero teto amarelo', st({'modo': 'zero', 'teto': 'amarelo'}, 'teste', 90, 100) == 'amarelo')
confere('sem valor = cinza', st(Z, 'teste', None, None) == 'cinza')
M = {'modo': 'minimo', 'min': 7}
confere('minimo verde', st(M, 'producao', 7, None) == 'verde')
confere('minimo amarelo', st(M, 'producao', 2, None) == 'amarelo')
confere('minimo vermelho', st(M, 'producao', 0, None) == 'vermelho')
P = {'modo': 'minimo', 'min': 1, 'producao': {'modo': 'info'}}
confere('override por ambiente', st(P, 'producao', 0, None) == 'info' and st(P, 'teste', 0, None) == 'vermelho')
C = {'modo': 'cobertura', 'meta': 600, 'verde': 0.95, 'amarelo': 0.3}
confere('cobertura com meta', st(C, 'producao', 100, None) == 'vermelho' and st(C, 'producao', 300, None) == 'amarelo'
        and st(C, 'producao', 590, None) == 'verde')
confere('paridade sem teste = cinza', st({'modo': 'paridade'}, 'producao', 5, None) == 'cinza')
confere('paridade', st({'modo': 'paridade', 'verde': 0.9, 'amarelo': 0.5}, 'producao', 5, 1388) == 'vermelho')
confere('info', st({'modo': 'info'}, 'teste', 3, 3) == 'info')

confere('sufixo nas tabelas', dsql("SELECT 1 FROM {SB1} JOIN {CT5} ON 1=1 WHERE X='{abc}'", '010')
        == "SELECT 1 FROM SB1010 JOIN CT5010 ON 1=1 WHERE X='{abc}'")
confere('num vírgula', num('1,5') == 1.5 and num('') is None and num(None) is None and num('x') is None)

# Catálogo padrão: SQL do jeito que a TSCMONITREST aceita
cat = json.loads((RAIZ / 'docs' / 'diagnostico' / 'catalogo_padrao.json').read_text(encoding='utf-8'))
ids = [c['check_id'] for c in cat]
confere('catálogo sem id repetido', len(ids) == len(set(ids)))
for c in cat:
    confere(f'{c["check_id"]} camada', c['camada'] in ns['DIAG_CAMADAS'])
    if c['tipo'] != 'sql':
        continue
    s = c['sql'].strip()
    confere(f'{c["check_id"]} começa em SELECT/WITH', re.match(r'^(SELECT|WITH)\b', s) is not None)
    confere(f'{c["check_id"]} sem ;', ';' not in s)
    confere(f'{c["check_id"]} sem DBMS_/INTO/EXEC', not re.search(r'\b(DBMS_|INTO|EXEC)\b', s))
    confere(f'{c["check_id"]} devolve VALOR/TOTAL/AMOSTRA', all(k in s for k in ('AS VALOR', 'AS TOTAL', 'AS AMOSTRA')))
    confere(f'{c["check_id"]} tabelas com {{}}', not re.search(r'\bFROM\s+[A-Z][A-Z0-9]{2}\d{3}\b', s))
    confere(f'{c["check_id"]} parênteses', s.count('(') == s.count(')'))
    confere(f'{c["check_id"]} sem dado de cliente', not re.search(r'D[ií]gitro|MIT006', json.dumps(c, ensure_ascii=False)))

# Abas: Pendências é liberável; Radar continua interno
abas = src[src.index('ABAS = ['):src.index('ABAS_IDS =')]
confere('aba pendencias liberável', re.search(r'"id": "pendencias".*"cliente": True', abas) is not None)
confere('aba radar interna', re.search(r'"id": "radar".*"cliente": False', abas) is not None)


def corpo(rota):
    m = re.search(r'@app\.(?:get|post|route)\("' + re.escape(rota) + r'"[^\n]*\)\ndef \w+\(.*?\):\n(.*?)(?=\n@app|\n# ──)', src, re.S)
    return m.group(1) if m else ''


for rota in ('/api/diag/<customer>', '/api/diag/<customer>/check/<check_id>', '/api/diag/<customer>/catalogo'):
    confere(f'{rota} interno', '_diag_gate(customer)' in corpo(rota))
confere('coletar exige ambiente/escrita', '_guarda_ambiente(customer' in corpo('/api/diag/<customer>/coletar')
        and 'escrita=True' in corpo('/api/diag/<customer>/coletar'))
confere('cron exige segredo', '_cron_autorizado()' in corpo('/api/cron/diagnostico'))
p = corpo('/api/pendencias/<customer>')
confere('pendências passa pela aba', 'deny_aba(customer, "pendencias")' in p)
confere('pendências só visível ao cliente', 'visivel_cliente' in p and 'completo=False' in p)
confere('pendências não expõe contexto', 'contexto' not in p)
pay = src[src.index('def _diag_payload('):src.index('def _diag_gate(')]
confere('recorte do cliente sem sql/amostra/nota', 'if not c["visivel_cliente"]' in pay and
        '("valor", "total", "status", "coletado_em")' in pay)

print(f'{ok} ok, {falhou} falhou')
raise SystemExit(1 if falhou else 0)
