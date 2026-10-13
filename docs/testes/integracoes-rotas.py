# Teste das ROTAS da aba Integrações com a REST da base e o banco FINGIDOS.
#
# Como rodar, da raiz do repo:  python3 docs/testes/integracoes-rotas.py
# (precisa do requirements.txt instalado). Sobe o Flask de verdade, troca
# q/execute por um banco em memória e requests.post/get por um stub que responde
# como o TSCMONITREST (CSV ';') e como o healthcheck do RH. Cobre: coleta feliz,
# tabela inexistente virando cinza, base fora do ar (502 sem gravar), healthcheck
# 404, guarda de sufixo/token e a leitura da série.
import base64, json, os, pathlib, sys, types

os.environ.setdefault("DATABASE_URL", "postgres://fake")
os.environ["PROTHEUS_CRED_KEY"] = base64.b64encode(b"k" * 32).decode()
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "api"))
import importlib.util
spec = importlib.util.spec_from_file_location("app_idx", RAIZ / "api" / "index.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ok = falhou = 0


def confere(nome, cond):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print("FALHOU:", nome)


# ── banco fingido ───────────────────────────────────────────────────────────
DB = {"medicoes": [], "coletas": []}
CFG = {}


def fake_q(sql, params=None, one=False):
    s = " ".join(sql.split()).lower()
    if s.startswith("insert into cockpit.integ_medicoes"):
        (cust, amb, dur, nivel, inds, blocos, health, env, por) = params
        row = {"id": len(DB["medicoes"]) + 1, "customer": cust, "ambiente": amb,
               "coletado_em": f"2026-10-13T1{len(DB['medicoes'])}:00:00", "duracao_ms": dur,
               "nivel": nivel, "indicadores": json.loads(inds), "blocos": json.loads(blocos),
               "health": json.loads(health), "environment": env, "disparado_por": por}
        DB["medicoes"].append(row)
        return {"id": row["id"]}
    if "from cockpit.integ_medicoes" in s and "limit 1" in s:
        return DB["medicoes"][-1] if DB["medicoes"] else None
    if "from cockpit.integ_medicoes m" in s:
        return [{"id": r["id"], "coletado_em": r["coletado_em"], "nivel": r["nivel"],
                 "indicadores": [{"chave": i["chave"], "valor": i["valor"], "nivel": i["nivel"]}
                                 for i in r["indicadores"]]}
                for r in reversed(DB["medicoes"])]
    if "from cockpit.protheus_coletas" in s:
        return list(reversed(DB["coletas"]))
    if "from cockpit.protheus_ambientes" in s:
        return CFG.get("cfg")
    raise AssertionError("SQL inesperado: " + s[:120])


def fake_execute(sql, params=None):
    s = " ".join(sql.split()).lower()
    if s.startswith("insert into cockpit.protheus_coletas"):
        DB["coletas"].append({"tipo": params[2], "ok": params[5], "erro": params[12],
                              "linhas": params[7], "itens": params[9]})
        return
    raise AssertionError("execute inesperado: " + s[:120])


m.q, m.execute = fake_q, fake_execute
m.require_interno = lambda: None
m.deny_customer = lambda c: None
m.deny_aba = lambda c, *a: None
m.current_user = lambda: "reges.werlang@totvs.com.br"
m.effective_user = lambda: "reges.werlang@totvs.com.br"
aad = m._aad("TFEHM600", "producao")
CFG["cfg"] = {"customer": "TFEHM600", "ambiente": "producao",
              "url_rest": "https://racli.protheus.cloudtotvs.com.br:1234/rest/tscmonit",
              "environment": "RACLI_PROD", "empresa": "01", "filial": "01",
              "usuario": "monitor", "senha_enc": m._cifra("s3nha", aad),
              "token_enc": m._cifra("tok123", aad), "banco": "oracle", "sufixo": "010",
              "timeout_s": 45, "limite_linhas": 50000, "ativo": True, "ssl_verificar": True}
BASE_CFG = dict(CFG["cfg"])

# ── REST fingida ────────────────────────────────────────────────────────────
CSV = {
    "SX6": "PARAMETRO;FILIAL;CONTEUDO\nMV_RHNG;;.T.\nMV_HISTQUI;;1\nMV_RHMSGNG;;100\nMV_URIQR;;https://app.quirons.com/ttalk/\n",
    "RJP_FILA": "FILIAL;TABELA;OPER;QTD;MAIS_ANTIGO\n  ;SRA;A;12;20261013\n",
    "RJP_VAZAO": "DIA;QTD;PRIMEIRA;ULTIMA\n20261013;9;06:00:01;09:15:00\n",
    "RU7": "DIA;COD_HTTP;QTD\n",
    "RJE_SST": "EVENTO;STATUS;QTD;MAIS_ANTIGO;MAIS_RECENTE\nS2220;4;30;20260901;20261010\n",
    "RJP_ANT": "FILIAL;TABELA;OPER;CHAVE;GERADO\n  ;SRA;A;01000123;20261013\n",
    "RJE_PEND": "FILIAL;EVENTO;STATUS;CHAVE;GERADO\n",
}
CHAMADAS = []
MODO = {"rum": "existe", "fora": False, "health": 200}


class R:
    def __init__(self, status, corpo):
        self.status_code = status
        self._c = corpo
        self.text = json.dumps(corpo) if isinstance(corpo, (dict, list)) else str(corpo)

    def json(self):
        if isinstance(self._c, (dict, list)):
            return self._c
        raise ValueError("não é json")


def fake_post(url, json=None, headers=None, auth=None, params=None, timeout=None, verify=None):
    import requests as rq
    CHAMADAS.append({"url": url, "sql": json["sql"], "token": headers.get("X-TSC-Token"),
                     "tipo": json["tipo"], "auth": auth, "limite": json["limite"]})
    if MODO["fora"]:
        raise rq.exceptions.ConnectTimeout("connect timeout")
    sql = json["sql"]
    assert not sql.rstrip().endswith(";")
    if "FROM RUM010" in sql:
        if MODO["rum"] == "ausente":
            return R(200, {"ok": False, "erro": "ORA-00942: table or view does not exist"})
        if "SRA010" in sql:
            return R(200, {"ok": True, "csv": "FILIAL;MATRICULA;NOME;COD_INTERNO;TIPO;OPER;STATUS;DT_MOV;DT_INTEG;HR_INTEG\n"
                           "01;000123;FULANO DE TAL;01|01|000123;1;A;3;20261010;20261010;08:00:00\n",
                           "linhas": 1, "truncado": False, "environment": "RACLI_PROD"})
        return R(200, {"ok": True, "csv": "TIPO;OPER;STATUS;QTD;MOV_MAIS_ANTIGO;ULT_INTEGRACAO;ATRASADOS\n"
                       "1;A;6;800;20250101;20261013;0\n1;A;3;1;20261010;20261010;0\n",
                       "linhas": 2, "truncado": False, "environment": "RACLI_PROD"})
    chave = ("SX6" if "FROM SX6010" in sql else
             "RJP_VAZAO" if "RJP_HORAIN" in sql else
             "RJP_ANT" if "RJP_KEY" in sql else
             "RJP_FILA" if "FROM RJP010" in sql else
             "RU7" if "FROM RU7010" in sql else
             "RJE_PEND" if "RJE_KEY" in sql else "RJE_SST")
    return R(200, {"ok": True, "csv": CSV[chave], "linhas": CSV[chave].count("\n") - 1,
                   "truncado": False, "environment": "RACLI_PROD"})


def fake_get(url, headers=None, auth=None, params=None, timeout=None, verify=None):
    CHAMADAS.append({"url": url, "token": headers.get("X-TSC-Token"), "auth": auth})
    if MODO["health"] == 404:
        return R(404, "Not Found")
    return R(200, {"laudo": [{"id": "P1", "status": "ok"}, {"id": "P2", "status": "aviso"},
                             {"id": "Q3", "status": "ok"}]})


m.requests.post, m.requests.get = fake_post, fake_get
cli = m.app.test_client()

# ── 1. coleta feliz ─────────────────────────────────────────────────────────
r = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=producao")
d = r.get_json()
confere("coleta 200", r.status_code == 200 and d["ok"])
confere("gravou uma medição", len(DB["medicoes"]) == 1)
confere("token só nas chamadas /query", all(c["token"] == "tok123" for c in CHAMADAS if "/query" in c["url"]))
confere("healthcheck sem token", all(c["token"] is None for c in CHAMADAS if "healthcheck" in c["url"]))
confere("healthcheck na raiz do REST",
        any(c["url"] == "https://racli.protheus.cloudtotvs.com.br:1234/rest/api/rh/v1/integrationcheck/healthcheck"
            for c in CHAMADAS))
confere("basic decifrado", all(c["auth"] == ("monitor", "s3nha") for c in CHAMADAS))
confere("tipo integracoes", all(c["tipo"] == "integracoes" for c in CHAMADAS if "/query" in c["url"]))
confere("9 consultas", sum(1 for c in CHAMADAS if "/query" in c["url"]) == 9)
ult = d["ultima"]
confere("nível geral amarelo (1 inconsistência)", ult["nivel"] == "amarelo")
inds = {i["chave"]: i for i in ult["indicadores"]}
confere("inconsistência contada", inds["ahgora_inconsistencias"]["valor"] == 1)
confere("laudo 3/3 (P2 aviso não pesa)", inds["quirons_laudo"]["valor"] == "3/3")
confere("detalhe com nome", ult["blocos"]["rum_pendencias"]["linhas"][0]["NOME"] == "FULANO DE TAL")
confere("log ok", DB["coletas"][-1]["ok"] is True and DB["coletas"][-1]["tipo"] == "integracoes")
confere("payload sem segredo", "s3nha" not in r.get_data(as_text=True) and "tok123" not in r.get_data(as_text=True))
confere("cfg devolvida sem blobs", "senha_enc" not in d["ambiente_cfg"] and d["ambiente_cfg"]["tem_senha"])

# ── 2. base sem Ahgora + healthcheck 404 ────────────────────────────────────
MODO.update(rum="ausente", health=404)
CHAMADAS.clear()
d = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=producao").get_json()
inds = {i["chave"]: i for i in d["ultima"]["indicadores"]}
confere("Ahgora cinza", inds["ahgora_nao_enviados"]["nivel"] == "cinza")
confere("motivo RUM010", "RUM010" in inds["ahgora_nao_enviados"]["texto"])
confere("bloco marcado ausente", d["ultima"]["blocos"]["rum_resumo"].get("ausente") is True)
confere("laudo cinza com motivo", inds["quirons_laudo"]["nivel"] == "cinza"
        and "GPEM926" in inds["quirons_laudo"]["texto"])
confere("geral verde sem Ahgora", d["ultima"]["nivel"] == "verde")
confere("log registra falha parcial", "rum_resumo" in (DB["coletas"][-1]["erro"] or ""))

# ── 3. leitura (GET) e série ────────────────────────────────────────────────
d = cli.get("/api/integracoes/TFEHM600?ambiente=producao").get_json()
confere("GET ok", d["ok"] and len(d["serie"]) == 2)
confere("série em ordem cronológica", d["serie"][0]["id"] == 1)
confere("hoje no payload", len(d["hoje"]) == 10)

# ── 4. base fora do ar: 502 e nada gravado ──────────────────────────────────
MODO["fora"] = True
antes = len(DB["medicoes"])
r = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=producao")
confere("fora do ar = 502", r.status_code == 502)
confere("fora do ar não grava", len(DB["medicoes"]) == antes)
confere("fora do ar loga falha", DB["coletas"][-1]["ok"] is False)
MODO["fora"] = False

# ── 5. guardas ──────────────────────────────────────────────────────────────
CFG["cfg"] = dict(CFG["cfg"], sufixo=None)
r = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=producao")
confere("sem sufixo = 409", r.status_code == 409 and "sufixo" in r.get_json()["error"])
CFG["cfg"] = dict(CFG["cfg"], sufixo="010", token_enc=None)
r = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=producao")
confere("sem token = 409", r.status_code == 409)
r = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=xpto")
confere("ambiente inválido = 400", r.status_code == 400)
CFG["cfg"] = None
r = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=producao")
confere("sem ambiente = 404", r.status_code == 404)

# ── 6. corte por data ───────────────────────────────────────────────────────
CFG["cfg"] = dict(BASE_CFG)
UPD = []
_exec_orig = m.execute
def exec_corte(sql, params=None):
    if "set integ_desde" in sql:
        UPD.append(params); CFG["cfg"] = dict(CFG["cfg"], integ_desde=params[0]); return
    return _exec_orig(sql, params)
m.execute = exec_corte
r = cli.post("/api/integracoes/TFEHM600/corte?ambiente=producao", json={"desde": "2026-10-01"})
confere("corte gravado", r.status_code == 200 and r.get_json()["desde"] == "2026-10-01" and UPD)
r = cli.post("/api/integracoes/TFEHM600/corte?ambiente=producao", json={"desde": "2099-01-01"})
confere("corte futuro recusado", r.status_code == 400)
r = cli.post("/api/integracoes/TFEHM600/corte?ambiente=producao", json={"desde": "01/10/2026"})
confere("corte inválido recusado", r.status_code == 400)
MODO.update(rum="existe", health=200)
CHAMADAS.clear()
d = cli.post("/api/integracoes/TFEHM600/coletar?ambiente=producao").get_json()
sql_rum = [c["sql"] for c in CHAMADAS if "/query" in c["url"] and "FROM RUM010 WHERE" in c["sql"]]
confere("coleta usa o corte", sql_rum and "RUM_DATMOV >= '20261001'" in sql_rum[0])
confere("corte gravado na coleta", d["ultima"]["blocos"]["_meta"]["desde"] == "2026-10-01")
confere("_meta não vira falha no log", "_meta" not in (DB["coletas"][-1]["erro"] or ""))
confere("cfg devolve o corte", str(d["ambiente_cfg"]["integ_desde"]) == "2026-10-01")
r = cli.post("/api/integracoes/TFEHM600/corte?ambiente=producao", json={"desde": None})
confere("limpar corte", r.status_code == 200 and r.get_json()["desde"] is None and UPD[-1][0] is None)
m.execute = _exec_orig
CFG["cfg"] = None

# ── 7. scripts ──────────────────────────────────────────────────────────────
d = cli.get("/api/integracoes/TFEHM600/scripts?ambiente=producao").get_json()
confere("scripts sem cadastro usam 010", d["sufixo_usado"] == "010" and len(d["scripts"]) == 9)
confere("scripts sem ;", all(not s["sql"].rstrip().endswith(";") for s in d["scripts"]))

print(f"{ok} asserções OK, {falhou} falha(s)")
raise SystemExit(1 if falhou else 0)
