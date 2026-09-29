"""Testes das regras da aba Estrutura, sem Flask e sem banco.

O que é testado é o que dói no cliente: a comparação "mais compartilhada",
que é a regra 1:n da TDN, e a conferência dos códigos contra o leiaute.
As funções são carregadas do próprio api/index.py por extração de texto — não
dá para importar o módulo (ele conecta no Postgres ao subir).
"""
import re
import sys

FONTE = open("api/index.py", encoding="utf-8").read()


def extrai(nome):
    m = re.search(r"(?ms)^def %s\(.*?(?=^\S|\Z)" % nome, FONTE)
    assert m, nome
    return m.group(0)


ns = {}
for f in ("_estrut_niveis", "_estrut_compart_ok", "_estrut_mais_compart",
          "_estrut_tam_esperado"):
    exec(extrai(f), ns)
exec(re.search(r"(?ms)^ESTRUT_LEIAUTES = \{.*?^\}", FONTE).group(0), ns)

niveis = ns["_estrut_niveis"]
mais = ns["_estrut_mais_compart"]
tam = ns["_estrut_tam_esperado"]

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


# ── níveis que valem por leiaute ───────────────────────────────────────────
ok(niveis("FF") == [2], "FF deveria valer só a posição da filial")
ok(niveis("EEFF") == [0, 2], "EEFF deveria valer empresa e filial, não unidade")
ok(niveis("EEUUFF") == [0, 1, 2], "EEUUFF deveria valer os três níveis")

# ── mais compartilhada (a regra 1:n) ───────────────────────────────────────
n = [0, 1, 2]
ok(mais("CCC", "EEE", n), "CCC é mais compartilhada que EEE")
ok(not mais("EEE", "CCC", n), "EEE não é mais compartilhada que CCC")
ok(not mais("ECC", "ECC", n), "iguais não são 'mais compartilhada'")
ok(mais("ECC", "ECE", n), "ECC é mais compartilhada que ECE (só a filial muda)")
ok(not mais("ECE", "ECC", n), "ECE não é mais compartilhada que ECC")
# Cruzado: mais amplo num nível e menos noutro NÃO é comparável — e não pode
# virar alerta, senão a tela acusa erro que ninguém consegue resolver.
ok(not mais("CEE", "ECC", n), "modos cruzados não são comparáveis")
ok(not mais("ECC", "CEE", n), "modos cruzados não são comparáveis (inverso)")
# O nível que o leiaute não usa não entra na conta: em EEFF a posição do meio
# é decorativa e diferença ali não pode gerar alerta.
ok(not mais("ECC", "EEC", [0, 2]), "em EEFF a unidade não entra na comparação")
ok(mais("ECC", "EEC", [0, 1, 2]), "em EEUUFF a unidade entra na comparação")
# Entrada inválida nunca vira alerta.
ok(not mais("", "ECC", n), "compartilhamento vazio não gera alerta")
ok(not mais("EC", "ECC", n), "compartilhamento com 2 posições não gera alerta")
ok(not mais("EXC", "ECC", n), "letra fora de E/C não gera alerta")

# ── tamanho esperado do código ─────────────────────────────────────────────
ok(tam({"leiaute": "EEFF", "tam_empresa": 2, "tam_unidade": 0, "tam_filial": 2}) == 4,
   "EEFF 2+0+2 = 4")
ok(tam({"leiaute": "FF", "tam_empresa": 0, "tam_unidade": 0, "tam_filial": 2}) == 2,
   "FF = 2")
ok(tam({"leiaute": "EEUUFF", "tam_empresa": 2, "tam_unidade": 2, "tam_filial": 2}) == 6,
   "EEUUFF 2+2+2 = 6")

# ── cenário real: SA1 x SE1 (o exemplo da própria TDN) ─────────────────────
# "Título a receber não pode ser mais compartilhado que o cliente."
casos = [("CCC", "CCC", False), ("CCC", "ECE", False),
         ("ECE", "CCC", True), ("ECE", "ECE", False)]
for sa1, se1, deve_alertar in casos:
    ok(mais(se1, sa1, [0, 2]) == deve_alertar,
       f"SA1={sa1} SE1={se1} deveria {'' if deve_alertar else 'NÃO '}alertar")

if falhas:
    print("FALHOU:")
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("todos os testes passaram")
