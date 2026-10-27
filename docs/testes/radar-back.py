# Teste das funções PURAS da aba Radar (validação do que vem da tela).
#
# Como rodar, de qualquer lugar:  python3 docs/testes/radar-back.py
# Extrai o trecho do módulo em vez de importá-lo (api/index.py exige DATABASE_URL).
import pathlib, re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
src = (RAIZ / 'api' / 'index.py').read_text(encoding='utf-8')
ini = src.index('RADAR_STATUS = (')
fim = src.index('def _radar_proc_ok(')
ns = {'re': re, 'require_interno': lambda: None, 'deny_customer': lambda c: None}
exec(compile(src[ini:fim], 'radar', 'exec'), ns)
campos = ns['_radar_campos']

ok = falhou = 0


def confere(nome, cond):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print('FALHOU:', nome)


# Novo item: título e processo são obrigatórios
confere('novo sem título', campos({'processo_id': '5'}, novo=True)[1] == 'O título é obrigatório.')
confere('novo sem processo', campos({'titulo': 'x'}, novo=True)[1] == 'Escolha o processo.')
c, e = campos({'titulo': '  Regra  ', 'processo_id': '5', 'ligacao_id': '', 'task_ids': '00017713, 00012345;9',
               'prazo': '2026-11-09', 'contexto': '', 'status': 'aberta'}, novo=True)
confere('novo válido', e is None)
confere('título aparado', c['titulo'] == 'Regra')
confere('processo vira int', c['processo_id'] == 5)
confere('ligação vazia vira None', c['ligacao_id'] is None)
confere('tasks separadas', c['task_ids'] == ['00017713', '00012345', '9'])
confere('contexto vazio vira None', c['contexto'] is None)

# Enumerações
confere('status inválido', campos({'status': 'fechado'})[1] == 'Status inválido.')
confere('lado inválido', campos({'dono_lado': 'CLIENTE'})[1] == 'Dono (lado) inválido.')
confere('prioridade inválida', campos({'prioridade': 'urgente'})[1] == 'Prioridade inválida.')
confere('tipo inválido', campos({'tipo': 'risco'})[1] == 'Tipo inválido.')
confere('prazo inválido', campos({'prazo': '09/11/2026'})[1].startswith('Prazo inválido'))

# Vazio em coluna NOT NULL = não mexer (não apaga, não reprova)
c, e = campos({'status': '', 'dono_lado': '', 'prioridade': '', 'tipo': '', 'processo_id': ''})
confere('enum vazio não reprova', e is None)
confere('enum vazio não entra no update', not ({'status', 'dono_lado', 'prioridade', 'tipo', 'processo_id'} & set(c)))
confere('título vazio na edição reprova', campos({'titulo': '  '})[1] == 'O título é obrigatório.')
confere('campo desconhecido é ignorado', 'customer' not in campos({'customer': 'OUTRO', 'codigo': 'X-1'})[0])
confere('task_ids lista', campos({'task_ids': ['1', ' 2 ', '']})[0]['task_ids'] == ['1', '2'])

# A aba é interna: não pode ser liberável para cliente
abas = src[src.index('ABAS = ['):src.index('ABAS_IDS =')]
confere('aba radar no catálogo', '"id": "radar"' in abas)
confere('aba radar não liberável a cliente', re.search(r'"id": "radar".*"cliente": False', abas) is not None)
# Toda rota /api/radar passa pelo portão
rotas = re.findall(r'@app\.(?:get|post)\("/api/radar[^"]*"\)\ndef (\w+)\(.*?\):\n(.*?)(?=\n@app|\n# ──)', src, re.S)
confere('sete rotas radar', len(rotas) == 7)
for nome, corpo in rotas:
    confere(f'{nome}: usa _radar_gate', '_radar_gate(customer)' in corpo.split('\n')[0:8].__str__() or '_radar_gate(customer)' in corpo[:400])

print(f'{ok} ok, {falhou} falhou')
raise SystemExit(1 if falhou else 0)
