# Integração das rotas /api/docs contra um Postgres DE TESTE (nunca o Supabase):
# cria séries pelo pacote .zip, publica, libera, recorta para o cliente, confere
# as travas e o arquivo servido. Precisa das tabelas mínimas (usuarios_login,
# usuario_clientes, radar_processos) + docs/sql/2026-10-30-documentacao.sql.
#
#   DATABASE_URL=postgresql://postgres@/postgres?host=/tmp&port=54329 \
#   DOC_PACOTES="a.zip b.zip" python3 docs/testes/doc-integracao.py
import io, json, os, sys, zipfile
assert 'supabase' not in os.environ.get('DATABASE_URL', ''), 'use um Postgres de teste'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'api'))
os.environ.setdefault('SESSION_SECRET', 'teste')
import index as A

CLI = '000348D0'
cli = A.app.test_client()
ok = falhou = 0
def confere(nome, cond, extra=''):
    global ok, falhou
    if cond: ok += 1
    else: falhou += 1; print('FALHOU:', nome, extra)
def como(email):
    cli.set_cookie(A.COOKIE_NAME, A.make_session(email, email.split('@')[0]))

como('reges@totvs.com.br')
pacotes = os.environ.get('DOC_PACOTES', '').split()
if not pacotes:      # pacote sintético
    b = io.BytesIO(); z = zipfile.ZipFile(b, 'w')
    z.writestr('manifest.json', json.dumps({'series': [
        {'serie': 'fluxo-painel', 'tipo': 'fluxo', 'titulo': 'Fluxo do Painel', 'processos': ['PNL', 'iPaaS → Painel de Projetos'],
         'versoes': [{'arquivo': 'v1.html', 'versao': 'v1', 'vigente': False}, {'arquivo': 'v2.html', 'versao': 'v2', 'data': '2026-10-30'}, {'arquivo': 'f.jpg'}]},
        {'serie': 'desenho', 'tipo': 'tecnico', 'titulo': 'Desenho técnico', 'processos': ['CRM'], 'versoes': [{'arquivo': 'd.html'}]}]}))
    z.writestr('v1.html', '<h1>v1</h1>'); z.writestr('v2.html', '<!DOCTYPE html><meta charset="utf-8"><h1>v2 ção</h1>')
    z.writestr('f.jpg', b'\xff\xd8\xff\xe0fake'); z.writestr('d.html', '<h1>interno</h1>'); z.close()
    pacotes = [('sintetico.zip', b.getvalue())]
else:
    pacotes = [(p, open(p, 'rb').read()) for p in pacotes]
for nome, dados in pacotes:
    r = cli.post(f'/api/docs/{CLI}/pacote', data={'pacote': (io.BytesIO(dados), nome)}, content_type='multipart/form-data')
    confere(f'pacote {nome}', r.status_code == 200 and r.json['ok'], r.get_data(as_text=True)[:300])
    print('  ', nome, r.json)
r = cli.post(f'/api/docs/{CLI}/pacote', data={'pacote': (io.BytesIO(pacotes[0][1]), 'de novo.zip')}, content_type='multipart/form-data')
confere('reimportar não duplica', r.json.get('versoes_novas') == 0, r.json)

d = cli.get(f'/api/docs/{CLI}').json
confere('interno vê tudo', d['interno'] and len(d['series']) >= 2)
S = {s['serie']: s for s in d['series']}
s_fluxo = next(s for s in d['series'] if s['tipo'] == 'fluxo')
s_int = next(s for s in d['series'] if s['tipo'] in ('tecnico', 'registro', 'parecer'))
v_html = next(v for v in s_fluxo['versoes'] if v['vigente'] and v['formato'] in ('html', 'jpeg', 'png'))
confere('uma vigente por formato', all(sum(v['vigente'] for v in s['versoes'] if v['formato'] == f) <= 1
                                        for s in d['series'] for f in {v['formato'] for v in s['versoes']}))
confere('cobertura calculada', any(c['exigidos'] for c in d['cobertura']))

# arquivo (interno) + cabeçalhos
r = cli.get(f'/api/docs/{CLI}/arquivo/{v_html["id"]}')
confere('arquivo 200', r.status_code == 200 and len(r.data) > 0)
if v_html['formato'] == 'html':
    confere('html com CSP sandbox', 'sandbox' in r.headers.get('Content-Security-Policy', ''))
confere('nosniff', r.headers.get('X-Content-Type-Options') == 'nosniff')
confere('baixar = attachment', cli.get(f'/api/docs/{CLI}/arquivo/{v_html["id"]}?baixar=1').headers['Content-Disposition'].startswith('attachment'))

# travas de liberação
v_int = next(v for v in s_int['versoes'] if v['vigente'])
r = cli.post(f'/api/docs/{CLI}/versao/{v_int["id"]}', json={'visibilidade': 'cliente'})
confere('tipo interno não vai ao cliente (nem admin)', r.status_code == 403, r.json)
como('cons@totvs.com.br')
r = cli.post(f'/api/docs/{CLI}/versao/{v_html["id"]}', json={'visibilidade': 'cliente'})
confere('consultoria não libera', r.status_code == 403, r.json)
como('reges@totvs.com.br')
r = cli.post(f'/api/docs/{CLI}/versao/{v_html["id"]}', json={'visibilidade': 'cliente'})
confere('admin libera', r.status_code == 200, r.json)

# publicar avulso: novo documento + nova versão da mesma série
r = cli.post(f'/api/docs/{CLI}/publicar', data={'arquivo': (io.BytesIO('# Processo\n- item'.encode()), 'processo.md'), 'titulo': 'Processo X',
             'tipo': 'processo', 'processos': '3', 'versao': 'v1', 'data_documento': '2026-10-30'}, content_type='multipart/form-data')
confere('publicar novo', r.status_code == 200, r.get_data(as_text=True)[:200])
sid = r.json['serie_id']
r = cli.post(f'/api/docs/{CLI}/publicar', data={'arquivo': (io.BytesIO('# Processo v2'.encode()), 'processo.md'), 'serie_id': str(sid), 'versao': 'v2'},
             content_type='multipart/form-data')
confere('nova versão', r.status_code == 200 and r.json['novo'])
vs = [s for s in cli.get(f'/api/docs/{CLI}').json['series'] if s['id'] == sid][0]['versoes']
confere('v2 vigente, v1 histórico', [(v['versao'], v['vigente']) for v in vs] == [('v2', True), ('v1', False)], vs)
confere('sem processo reprova', cli.post(f'/api/docs/{CLI}/publicar', data={'arquivo': (io.BytesIO(b'x'), 'a.txt'), 'titulo': 'Y', 'tipo': 'processo'},
        content_type='multipart/form-data').status_code == 400)
confere('formato inválido', cli.post(f'/api/docs/{CLI}/publicar', data={'arquivo': (io.BytesIO(b'x'), 'a.xlsx'), 'serie_id': str(sid)},
        content_type='multipart/form-data').status_code == 400)
confere('acima do teto', cli.post(f'/api/docs/{CLI}/publicar', data={'arquivo': (io.BytesIO(b'0' * (A.DOC_MAX_BYTES + 1)), 'a.pdf'), 'serie_id': str(sid)},
        content_type='multipart/form-data').status_code == 413)
# dispensa
confere('dispensa sem motivo', cli.post(f'/api/docs/{CLI}/dispensa', json={'processo_id': 1, 'tipo': 'especificacao'}).status_code == 400)
confere('dispensa', cli.post(f'/api/docs/{CLI}/dispensa', json={'processo_id': 1, 'tipo': 'especificacao', 'motivo': 'sem customização'}).status_code == 200)
cel = next(c for c in cli.get(f'/api/docs/{CLI}').json['cobertura'] if c['processo_id'] == 1)['celulas']['especificacao']
confere('célula dispensada', cel['status'] == 'dispensado' and cel['motivo'] == 'sem customização')
confere('processo de outro cliente', cli.post(f'/api/docs/{CLI}/dispensa', json={'processo_id': 999, 'tipo': 'fluxo', 'motivo': 'x'}).status_code == 404)

# visão do cliente
como('aline@digitro.com.br')
c = cli.get(f'/api/docs/{CLI}').json
confere('cliente: recorte', not c['interno'] and [s['id'] for s in c['series']] == [s_fluxo['id']], c)
confere('cliente: só versão liberada', [v['id'] for v in c['series'][0]['versoes']] == [v_html['id']])
confere('cliente: sem campos internos', not ({'publicado_por', 'origem', 'nota', 'visibilidade'} & set(c['series'][0]['versoes'][0])))
confere('cliente: sem cobertura', 'cobertura' not in c and 'dispensas' not in c)
confere('cliente abre o liberado', cli.get(f'/api/docs/{CLI}/arquivo/{v_html["id"]}').status_code == 200)
confere('cliente não abre o interno', cli.get(f'/api/docs/{CLI}/arquivo/{v_int["id"]}').status_code == 404)
outra = next((v for v in s_fluxo['versoes'] if v['id'] != v_html['id']), None)
if outra:
    confere('cliente não abre versão não liberada', cli.get(f'/api/docs/{CLI}/arquivo/{outra["id"]}').status_code == 404)
confere('cliente não publica', cli.post(f'/api/docs/{CLI}/dispensa', json={}).status_code == 403)
confere('cliente sem acesso a outro cliente', cli.get('/api/docs/OUTRO').status_code == 403)

print(f'{ok} ok, {falhou} falha(s)')
print('DOC INTEGRAÇÃO: OK' if not falhou else 'DOC INTEGRAÇÃO: FALHOU')
raise SystemExit(1 if falhou else 0)
