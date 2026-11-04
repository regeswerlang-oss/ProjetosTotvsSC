# Teste das ROTAS de transferência de cadastros entre bases (04/11/2026).
#
# Como rodar, da raiz do repo:  python3 docs/testes/transferencia-rotas.py
# Sobe o Flask de verdade, troca q/execute por um banco em memória e
# requests.post/get por um stub que responde como o TSCTRANSREST nas DUAS bases
# (cada uma com a sua tabela SA1 em memória, chave A1_FILIAL+A1_COD+A1_LOJA e
# o seu MV_TSCGRAV). Cobre: roteamento (transferir ≠ salvar ambiente),
# simulação sem gravar, gravação na teste, modo incluir × incluir_alterar,
# paginação em vários lotes, de-para de filial, guarda de produção (admin +
# frase), MV_TSCGRAV fechado, tabela de movimento/dicionário, filtro proibido,
# 404 do fonte não compilado e o log de coletas.
import base64, json, os, pathlib, sys

os.environ.setdefault("DATABASE_URL", "postgres://fake")
os.environ["PROTHEUS_CRED_KEY"] = base64.b64encode(b"k" * 32).decode()
RAIZ = pathlib.Path(__file__).resolve().parents[2]
import importlib.util
spec = importlib.util.spec_from_file_location("app_idx", RAIZ / "api" / "index.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ok = falhou = 0


def confere(nome, cond, extra=None):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print("FALHOU:", nome, "" if extra is None else extra)


CUST = "HSABV6"
LOG = []


def cfg(amb, porta, ativo=True):
    aad = m._aad(CUST, amb)
    return {"customer": CUST, "ambiente": amb,
            "url_rest": f"https://digitro.cloudtotvs.com.br:{porta}/rest/tscmonit",
            "environment": f"CQU194_{amb.upper()}", "empresa": "01", "filial": "01",
            "usuario": "monitor", "senha_enc": m._cifra("s3nha", aad),
            "token_enc": m._cifra("tok", aad), "banco": "oracle", "sufixo": "010",
            "timeout_s": 45, "limite_linhas": 50000, "ativo": ativo, "ssl_verificar": True}


CFGS = {"producao": cfg("producao", 1001), "teste": cfg("teste", 1002)}


def fake_q(sql, params=None, one=False):
    s = " ".join(sql.split()).lower()
    if "from cockpit.protheus_ambientes" in s:
        return CFGS.get(params[1])
    if "is_admin" in s:
        return {"adm": ADMIN["v"]}
    raise AssertionError("SQL inesperado: " + s[:120])


def fake_execute(sql, params=None):
    s = " ".join(sql.split()).lower()
    if s.startswith("insert into cockpit.protheus_coletas"):
        LOG.append({"amb": params[1], "tipo": params[2], "ok": params[5],
                    "linhas": params[7], "itens": params[9], "erro": params[12]})
        return
    raise AssertionError("execute inesperado: " + s[:120])


ADMIN = {"v": True}
m.q, m.execute = fake_q, fake_execute
m.require_interno = lambda: None
m.deny_customer = lambda c: None
m.current_user = lambda: "reges@totvs.com.br"
m.effective_user = lambda: "reges@totvs.com.br"


# ── as duas bases fingidas ───────────────────────────────────────────────────
def reg(recno, fil, cod, loja, nome):
    return {"__recno": recno, "A1_FILIAL": fil, "A1_COD": cod, "A1_LOJA": loja, "A1_NOME": nome,
            "A1_LC": 1000.5, "A1_DTCAD": "20261001", "A1_XCAMPO": "só na origem"}


BASES = {
    1001: {"amb": "producao", "grav": False, "existe": True,
           "SA1": [reg(10 + i, "01", f"{i:06d}", "01", f"CLIENTE {i}") for i in range(1, 8)]},
    1002: {"amb": "teste", "grav": True, "existe": True,
           "SA1": [reg(500, "0101", "000002", "01", "JA EXISTIA NA TESTE")]},
}
CAMPOS_DESTINO = {"A1_FILIAL", "A1_COD", "A1_LOJA", "A1_NOME", "A1_LC", "A1_DTCAD"}
CHAMADAS = []


class R:
    def __init__(self, status, corpo):
        self.status_code = status
        self._c = corpo
        self.text = json.dumps(corpo) if isinstance(corpo, dict) else str(corpo)
        self.url = ""

    def json(self):
        if isinstance(self._c, dict):
            return self._c
        raise ValueError("não é json")


def _base(url):
    return BASES[int(url.split(":")[2].split("/")[0])]


def fake_post(url, json=None, headers=None, auth=None, params=None, timeout=None, verify=None):
    CHAMADAS.append({"url": url, "corpo": json, "token": headers.get("X-TSC-Token"), "timeout": timeout})
    b = _base(url)
    if not b["existe"]:
        return R(404, "<html>404 Not Found</html>")
    assert "/rest/tsctrans/" in url, url
    tab = b["SA1"]
    if url.endswith("/ler"):
        lim, apos = json["limite"], json["apos_recno"]
        fila = [r for r in sorted(tab, key=lambda r: r["__recno"]) if r["__recno"] > apos]
        sai = fila[:lim]
        return R(200, {"ok": True, "registros": sai, "lidos": len(sai), "chave": "A1_FILIAL+A1_COD+A1_LOJA",
                       "ultimo_recno": sai[-1]["__recno"] if sai else apos,
                       "fim": len(fila) <= lim, "environment": f"ENV_{b['amb']}"})
    if url.endswith("/gravar"):
        if not json["simular"] and not b["grav"]:
            return R(403, {"ok": False, "erro": "Gravação desligada nesta base (CQU194). Para liberar, crie o parâmetro MV_TSCGRAV"})
        inc = alt = ign = 0
        sem = set()
        for r in json["registros"]:
            novo = {k: v for k, v in r.items() if k in CAMPOS_DESTINO and k not in json["campos_excluir"]}
            sem |= {k for k in r if k not in CAMPOS_DESTINO and k != "__recno"}
            if json["filial_de"] and novo["A1_FILIAL"].strip() == json["filial_de"]:
                novo["A1_FILIAL"] = json["filial_para"]
            chave = (novo["A1_FILIAL"], novo["A1_COD"], novo["A1_LOJA"])
            achou = next((x for x in tab if (x["A1_FILIAL"], x["A1_COD"], x["A1_LOJA"]) == chave), None)
            if achou and json["modo"] == "incluir":
                ign += 1
                continue
            if json["simular"]:
                alt, inc = (alt + 1, inc) if achou else (alt, inc + 1)
                continue
            if achou:
                achou.update(novo)
                alt += 1
            else:
                novo["__recno"] = 1000 + len(tab)
                tab.append(novo)
                inc += 1
        return R(200, {"ok": True, "incluidos": inc, "alterados": alt, "ignorados": ign, "erros": [],
                       "campos_sem_destino": sorted(sem), "chave": "A1_FILIAL+A1_COD+A1_LOJA",
                       "environment": f"ENV_{b['amb']}"})
    raise AssertionError(url)


def fake_get(url, headers=None, auth=None, params=None, timeout=None, verify=None):
    b = _base(url)
    if not b["existe"]:
        return R(404, "nao achou")
    return R(200, {"ok": True, "versao": "1.0", "environment": f"ENV_{b['amb']}",
                   "token_ok": headers.get("X-TSC-Token") == "tok", "gravacao_liberada": b["grav"]})


m.requests.post, m.requests.get = fake_post, fake_get
cli = m.app.test_client()


def transf(**kw):
    corpo = {"origem": "producao", "destino": "teste", "tabela": "SA1", "lote": 3,
             "modo": "incluir", "simular": True, "apos_recno": 0}
    corpo.update(kw)
    r = cli.post(f"/api/protheus/{CUST}/transferir", json=corpo)
    return r.status_code, r.get_json()


def roda_tudo(**kw):
    apos, tot, lotes = 0, {"lidos": 0, "incluidos": 0, "alterados": 0, "ignorados": 0}, 0
    while True:
        st, j = transf(apos_recno=apos, **kw)
        assert st == 200, (st, j)
        lotes += 1
        for k in tot:
            tot[k] += j[k]
        if j["fim"]:
            return tot, lotes, j
        apos = j["ultimo_recno"]


# ── utilitários ──────────────────────────────────────────────────────────────
confere("URL do TSCTRANSREST sai da do TSCMONITREST",
        m._trans_url({"url_rest": "https://h:10257/rest/tscmonit"}) == "https://h:10257/rest/tsctrans")
confere("filtro com D_E_L_E_T_ passa", m._trans_filtro("D_E_L_E_T_ = ' ' AND A1_EST='SC'")[1] is None)
confere("filtro com DELETE recusa", m._trans_filtro("1=1 or delete from x")[1] is not None)
confere("filtro com ; recusa", m._trans_filtro("A1_EST='SC'; drop")[1] is not None)
confere("filtro com DBMS_ recusa", m._trans_filtro("DBMS_LOCK.SLEEP(9)=1")[1] is not None)
confere("campos excluir normaliza", m._trans_campos("a1_userlgi, A1_USERLGA;x") == ["A1_USERLGA", "A1_USERLGI"])
confere("confirmação aceita acento", m._trans_norm(" Produção  sa1 ") == "PRODUCAO SA1")

# ── roteamento ───────────────────────────────────────────────────────────────
st, j = transf()
confere("POST /transferir cai na rota de transferência (não no salvar ambiente)",
        st == 200 and "lidos" in j, (st, j))

# ── simulação ────────────────────────────────────────────────────────────────
antes = len(BASES[1002]["SA1"])
tot, lotes, ult = roda_tudo(simular=True)
confere("simulação lê os 7 da origem em 3 lotes de 3", tot["lidos"] == 7 and lotes == 3, (tot, lotes))
confere("simulação conta 7 inclusões (filial 01 ≠ 0101 do que já existe)", tot["incluidos"] == 7, tot)
confere("simulação não grava nada", len(BASES[1002]["SA1"]) == antes)
confere("campo que não existe no destino é avisado", "A1_XCAMPO" in ult["campos_sem_destino"])
confere("simulação não entra no log", not LOG)
confere("token vai nas duas chamadas", all(c["token"] == "tok" for c in CHAMADAS))
confere("ler + gravar cabem nos 60 s", all(c["timeout"] <= 47 for c in CHAMADAS))

# ── de-para de filial + modo incluir ─────────────────────────────────────────
tot, _l, _u = roda_tudo(simular=True, filial_de="01", filial_para="0101")
confere("com de-para 01→0101 o 000002 já existe e é ignorado", tot["ignorados"] == 1 and tot["incluidos"] == 6, tot)

# ── gravação de verdade na teste ─────────────────────────────────────────────
tot, _l, _u = roda_tudo(simular=False, filial_de="01", filial_para="0101", campos_excluir="A1_LC")
confere("grava 6 novos na teste", tot["incluidos"] == 6 and len(BASES[1002]["SA1"]) == 7, tot)
confere("o que já existia não foi tocado no modo incluir",
        next(x for x in BASES[1002]["SA1"] if x["A1_COD"] == "000002")["A1_NOME"] == "JA EXISTIA NA TESTE")
confere("filial gravada com a máscara do destino", all(x["A1_FILIAL"] == "0101" for x in BASES[1002]["SA1"]))
confere("campo excluído não foi copiado", all("A1_LC" not in x for x in BASES[1002]["SA1"] if x["__recno"] >= 1000))
confere("lote gravado entra no log como transferencia na base destino",
        LOG and all(l["tipo"] == "transferencia" and l["amb"] == "teste" and l["ok"] for l in LOG), LOG)

tot, _l, _u = roda_tudo(simular=False, filial_de="01", filial_para="0101", modo="incluir_alterar")
confere("incluir_alterar sobrescreve os 7", tot["alterados"] == 7 and tot["incluidos"] == 0, tot)
confere("e o 000002 recebeu o nome da produção",
        next(x for x in BASES[1002]["SA1"] if x["A1_COD"] == "000002")["A1_NOME"] == "CLIENTE 2")

# ── guarda de produção ───────────────────────────────────────────────────────
st, j = transf(origem="teste", destino="producao", simular=False)
confere("gravar em produção sem a frase → 409", st == 409 and "PRODUCAO SA1" in j["error"], (st, j))
ADMIN["v"] = False
st, j = transf(origem="teste", destino="producao", simular=False, confirmacao="PRODUCAO SA1")
confere("gravar em produção sem ser admin → 403", st == 403, (st, j))
ADMIN["v"] = True
st, j = transf(origem="teste", destino="producao", simular=False, confirmacao="produção sa1")
confere("produção com a frase, mas MV_TSCGRAV fechado na base → 403 com o motivo",
        st == 403 and "MV_TSCGRAV" in j["error"], (st, j))
st, j = transf(origem="teste", destino="producao", simular=True)
confere("simular rumo à produção não pede frase", st == 200, (st, j))

# ── recusas ──────────────────────────────────────────────────────────────────
st, j = transf(destino="producao")
confere("origem = destino → 400", st == 400)
st, j = transf(tabela="SD2")
confere("tabela de movimento sem marcar → 409", st == 409 and "MOVIMENTO" in j["error"], (st, j))
st, j = transf(tabela="SX5")
confere("dicionário → 400", st == 400)
st, j = transf(tabela="SA")
confere("alias inválido → 400", st == 400)
st, j = transf(filtro="A1_COD IN (SELECT 1 FROM DUAL) UNION SELECT 1")
confere("filtro com UNION → 400", st == 400)
st, j = transf(modo="apagar")
confere("modo inválido → 400", st == 400)
CFGS["teste"]["ativo"] = False
st, j = transf()
confere("destino inativo → 409", st == 409)
CFGS["teste"]["ativo"] = True

BASES[1002]["existe"] = False
st, j = transf()
confere("fonte não compilado no destino → mensagem do TSCTRANSREST", st == 502 or st == 404, (st, j))
confere("… e a mensagem diz o que fazer", "TSCTRANSREST" in (j.get("error") or ""), j)
r = cli.post(f"/api/protheus/{CUST}/teste/transferir-ping")
confere("ping do destino sem o fonte → ok false com orientação",
        r.get_json()["ok"] is False and "TSCTRANSREST" in r.get_json()["mensagem"], r.get_json())
BASES[1002]["existe"] = True
r = cli.post(f"/api/protheus/{CUST}/producao/transferir-ping").get_json()
confere("ping da produção mostra gravação fechada", r["ok"] and r["gravacao_liberada"] is False and r["token_ok"], r)

# ── a rota antiga continua a mesma ───────────────────────────────────────────
regras = {(str(x.rule), x.endpoint) for x in m.app.url_map.iter_rules()}
confere("rota de salvar ambiente intacta", ("/api/protheus/<customer>/<ambiente>", "api_protheus_salvar") in regras)

# ── o fonte TLPP ─────────────────────────────────────────────────────────────
tl = (RAIZ / "fontes" / "tlpp" / "TSCTRANSREST.tlpp").read_bytes().decode("cp1252")
for rota in ('@Get("/tsctrans/ping")', '@Post("/tsctrans/ler")', '@Post("/tsctrans/gravar")'):
    confere(f"fonte publica {rota}", rota in tl)
confere("fonte exige MV_TSCGRAV para gravar", "MV_TSCGRAV" in tl and "gravacaoLiberada()" in tl)
confere("fonte simula por padrão", 'Local lSimular  := .T.' in tl)
confere("fonte usa FWExecStatement com parâmetro no recno", "SetNumeric(1, nApos)" in tl)

print(f"{ok} ok, {falhou} falhou")
sys.exit(1 if falhou else 0)
