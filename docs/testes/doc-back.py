# Teste das funções PURAS da aba Documentação + portões das rotas.
#
#   python3 docs/testes/doc-back.py
#
# Extrai os trechos do módulo em vez de importá-lo (api/index.py exige DATABASE_URL).
import hashlib, json, os, pathlib, re, unicodedata

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('DOC_FORMATOS = {')
fim = src.index('def _doc_load(')
def _slug(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())
ns = {'re': re, 'os': os, 'json': json, 'unicodedata': unicodedata, '_slug': _slug}
exec(compile(src[ini:fim], 'doc', 'exec'), ns)
ini2 = src.index('def _doc_manifesto(')
fim2 = src.index('@app.post("/api/docs/<customer>/pacote")')
exec(compile(src[ini2:fim2], 'doc2', 'exec'), ns)

ok = falhou = 0
def confere(nome, cond):
    global ok, falhou
    if cond: ok += 1
    else:
        falhou += 1; print('FALHOU:', nome)

fmt = ns['_doc_formato']
confere('html', fmt('Fluxo Sistêmico Dígitro.html') == 'html')
confere('JPG maiúsculo', fmt('X.JPG') == 'jpeg')
confere('sem extensão vira txt (transcrição Gemini)', fmt('Resumo - Interno - Integração CRM') == 'txt')
confere('extensão desconhecida', fmt('planilha.xlsx') is None)
confere('link', fmt(None, 'https://youtu.be/x') == 'link')

slug = ns['_doc_serie_slug']
confere('slug acentos', slug('Fluxo Sistêmico — Painel de Projetos!') == 'fluxo-sistemico-painel-de-projetos')
confere('slug vazio', slug('  ') == 'documento')

vis = ns['_doc_vis_erro']
confere('consultoria ok', vis('consultoria', 'consultoria', False) is None)
confere('cliente ok para admin', vis('cliente', 'cliente', True) is None)
confere('cliente barrado p/ não-admin', vis('cliente', 'cliente', False).startswith('Só administrador'))
confere('tipo interno trava até admin', 'interno' in vis('cliente', 'consultoria', True))
confere('vis inválida', vis('publico', 'cliente', True) == 'Visibilidade inválida.')

ids = ns['_doc_ids']
confere('ids csv', ids('3, 1;3 x') == [1, 3])
confere('ids json', ids('[2,"4"]') == [2, 4])
confere('ids lista', ids([5, '6', None]) == [5, 6])

tipos = [{'codigo': 'fluxo', 'obrigatorio': True, 'nivel_max': 'cliente'},
         {'codigo': 'especificacao', 'obrigatorio': True, 'nivel_max': 'cliente'},
         {'codigo': 'tecnico', 'obrigatorio': False, 'nivel_max': 'consultoria'}]
procs = [{'id': 1, 'tipo': 'processo'}, {'id': 2, 'tipo': 'processo'}, {'id': 11, 'tipo': 'ligacao'}]
V = lambda vid, vig=True, vis='consultoria': {'id': vid, 'vigente': vig, 'visibilidade': vis, 'formato': 'html'}
series = [{'id': 10, 'tipo': 'fluxo', 'processos': [1, 11], 'versoes': [V(1, vis='cliente'), V(2, False)]},
          {'id': 20, 'tipo': 'tecnico', 'processos': [1], 'versoes': [V(3, vis='cliente')]},   # tipo interno "liberado" por engano
          {'id': 30, 'tipo': 'especificacao', 'processos': [2], 'versoes': [V(4, False)]}]   # só versão antiga
cob = ns['_doc_cobertura'](procs, series, tipos, [{'processo_id': 1, 'tipo': 'especificacao', 'motivo': 'sem customização'}])
c1 = next(c for c in cob if c['processo_id'] == 1); c2 = next(c for c in cob if c['processo_id'] == 2)
confere('ligação fora da matriz', len(cob) == 2)
confere('p1 fluxo ok + liberado', c1['celulas']['fluxo'] == {'status': 'ok', 'series': [10], 'cliente': True, 'motivo': None})
confere('p1 dispensa tira do exigido', c1['exigidos'] == 1 and c1['ok'] == 1)
confere('p1 opcional presente aparece', c1['celulas']['tecnico']['status'] == 'ok')
confere('p2 versão não vigente não conta', c2['celulas']['especificacao']['status'] == 'falta' and c2['ok'] == 0 and c2['exigidos'] == 2)

rc = ns['_doc_recorte_cliente'](
    [{**s, 'serie': 's', 'titulo': 't', 'descricao': None, 'ordem': 0,
      'versoes': [{**v, 'publicado_por': 'x@totvs', 'origem': '/Users/..', 'nota': 'interna', 'tamanho': 1,
                   'nome_arquivo': 'a.html', 'url_externa': None, 'versao': 'v', 'data_documento': None,
                   'liberado_em': None} for v in s['versoes']]} for s in series], tipos)
confere('cliente: só a série liberada de tipo liberável', [s['id'] for s in rc] == [10])
confere('cliente: só a versão vigente liberada', [v['id'] for v in rc[0]['versoes']] == [1])
confere('cliente: sem campos internos', not ({'publicado_por', 'origem', 'nota', 'visibilidade', 'vigente'} & set(rc[0]['versoes'][0])))

man = ns['_doc_manifesto']
P = [{'id': 3, 'nome': 'Painel de Projetos', 'prefixo': 'PNL'}, {'id': 12, 'nome': 'iPaaS → Painel de Projetos', 'prefixo': None}]
s, e = man({'series': [{'tipo': 'fluxo', 'titulo': 'Fluxo do Painel', 'processos': ['PNL', 'iPaaS → Painel de Projetos', 3],
                        'versoes': [{'arquivo': 'a.html'}, {'arquivo': 'a.jpg', 'data': '2026-10-30'}]}]}, P)
confere('manifesto válido', e == [])
confere('processo por prefixo, nome e id', s[0]['processo_ids'] == [3, 12])
confere('formato inferido', [v['formato'] for v in s[0]['versoes']] == ['html', 'jpeg'])
confere('slug gerado', s[0]['serie'] == 'fluxo-do-painel')
s, e = man({'series': [{'tipo': 'fluxo', 'titulo': 'X', 'processos': ['ZZZ'], 'versoes': [{'arquivo': 'a.xlsx'}]}]}, P)
confere('processo desconhecido', any('processo não encontrado' in x for x in e))
confere('formato não aceito', any('formato não aceito' in x for x in e))
confere('manifesto vazio', man({}, P)[1] == ['manifest.json sem séries.'])

# Portões: toda rota /api/docs passa por require_auth+deny_aba (leitura) ou require_interno (escrita)
abas = src[src.index('ABAS = ['):src.index('ABAS_IDS =')]
confere('aba documentos liberável', re.search(r'"id": "documentos".*"cliente": True', abas) is not None)
rotas = re.findall(r'@app\.(get|post)\("(/api/docs[^"]*)"\)\ndef \w+\(.*?\):\n(.*?)(?=\n@app|\ndef _doc|\n# ──)', src, re.S)
confere('oito rotas docs', len(rotas) == 8)
for metodo, rota, corpo in rotas:
    head = corpo[:900]
    if metodo == 'get':
        confere(f'{rota} leitura com portão', 'require_auth()' in head and 'deny_aba(customer, "documentos")' in head)
    else:
        confere(f'{rota} escrita só interno', 'require_interno()' in head and 'deny_customer(customer)' in head)
arq = src[src.index('def api_docs_arquivo('):src.index('@app.post("/api/docs/<customer>/publicar")')]
confere('arquivo: cliente só vigente+liberado+tipo liberável', 'v["vigente"] and v["visibilidade"] == "cliente"' in arq and 'v["nivel_max"] == "cliente"' in arq)
confere('arquivo: html/svg com CSP sandbox', 'DOC_CSP' in arq and 'nosniff' in arq)
confere('pacote entra como consultoria', '"consultoria",' in src[src.index('def api_docs_pacote('):src.index('# ── PLANO DE TRABALHO')])

print(f'{ok} ok, {falhou} falha(s)')
print('DOC BACK: OK' if not falhou else 'DOC BACK: FALHOU')
raise SystemExit(1 if falhou else 0)
