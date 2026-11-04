# Teste das funções PURAS da aba Plano de Virada (validação do que vem da tela).
#
# Como rodar, de qualquer lugar:  python3 docs/testes/virada-back.py
# Extrai o trecho do módulo em vez de importá-lo (api/index.py exige DATABASE_URL).
import pathlib, re
from datetime import date

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('VIRADA_FASES = (')
fim = src.index('def _virada_proximo_codigo(')
ns = {'re': re, 'date': date}
exec(compile(src[ini:fim], 'virada', 'exec'), ns)
campos = ns['_virada_campos']

ok = falhou = 0


def confere(nome, cond):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome)


base = {'fase': 'corte', 'frente': ' Estoque ', 'atividade': ' Inventário ', 'data_inicio': '2026-12-30',
        'data_fim': '2026-12-31', 'criterio_go': True, 'detalhe': '', 'status': 'planejado'}
c, e = campos(base, novo=True)
confere('novo válido', e is None)
confere('texto aparado', c['frente'] == 'Estoque' and c['atividade'] == 'Inventário')
confere('vazio vira None', c['detalhe'] is None)
confere('go booleano', c['criterio_go'] is True)
confere('sem atividade', campos({**base, 'atividade': ' '}, novo=True)[1] == 'Descreva a atividade.')
confere('sem frente', campos({**base, 'frente': ''}, novo=True)[1] == 'Informe a frente (processo/área).')
confere('sem fase', campos({k: v for k, v in base.items() if k != 'fase'}, novo=True)[1] == 'Escolha a fase.')
confere('fase inválida', campos({'fase': 'producao'})[1] == 'Fase inválida.')
confere('status inválido', campos({'status': 'feito'})[1] == 'Status inválido.')
confere('lado inválido', campos({'resp_lado': 'DIGITRO'})[1] == 'Responsável (lado) inválido.')
confere('data br recusada', campos({'data_fim': '31/12/2026'})[1].startswith('Data inválida'))
confere('data impossível', campos({'data_fim': '2026-02-30'})[1].startswith('Data inválida'))
confere('fim antes do início', campos({'data_inicio': '2027-01-03', 'data_fim': '2027-01-01'})[1] == 'A data fim não pode ser antes do início.')
confere('data vazia limpa', campos({'data_fim': ''})[0]['data_fim'] is None)
confere('enum vazio não entra', 'status' not in campos({'status': ''})[0])
confere('campo desconhecido ignorado', not ({'customer', 'codigo', 'origem', 'ativo'} & set(campos({'customer': 'X', 'codigo': 'PV-1', 'origem': 'historico', 'ativo': False})[0])))
confere('edição com atividade vazia', campos({'atividade': ''})[1] == 'Descreva a atividade.')
confere('go string', campos({'criterio_go': 'false'})[0]['criterio_go'] is False)

abas = src[src.index('ABAS = ['):src.index('ABAS_IDS =')]
confere('aba virada no catálogo', '"id": "virada"' in abas)
rotas = re.findall(r'@app\.(get|post)\("(/api/virada[^"]*)"\)\ndef (\w+)\(.*?\):\n(.*?)(?=\n@app|\n# ──|\ndef )', src, re.S)
confere('cinco rotas', len(rotas) == 5)
for met, rota, nome, corpo in rotas:
    if met == 'get':
        confere(f'{nome} barra aba', 'deny_aba(customer, "virada")' in corpo)
    else:
        confere(f'{nome} exige interno', 'require_interno()' in corpo and 'deny_customer(' in corpo)

print(f'virada-back: {ok} ok, {falhou} falhou')
raise SystemExit(1 if falhou else 0)
