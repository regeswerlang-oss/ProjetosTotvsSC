# Teste das ROTAS da aba Tributos com a REST das bases e o banco FINGIDOS.
#
# Como rodar, da raiz do repo:  python3 docs/testes/tributos-rotas.py
# (precisa do requirements.txt instalado). Sobe o Flask de verdade, troca
# q/execute por uma cockpit.trib_coletas em memória e requests.post por um stub
# que responde como o TSCMONITREST (CSV ';'). Cobre: coleta faseada (fase 0 →
# conteúdo → concluída), histórico curto, leitura com as duas bases e a guarda
# de tabela ausente no Supabase.
import base64, json, os, pathlib, sys, time

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


ROWS, LOG = [], []
CFG = {}


def fake_q(sql, params=None, one=False):
    s = " ".join(sql.split()).lower()
    if s.startswith("insert into cockpit.trib_coletas"):
        cust, amb, meta, pend, env, suf, por = params
        r = {"id": len(ROWS) + 1, "customer": cust, "ambiente": amb, "status": "coletando",
             "meta": json.loads(meta), "dados": {}, "pendentes": list(pend), "environment": env,
             "sufixo": suf, "disparado_por": por, "chamadas": 1, "iniciado_em": f"2026-10-30T14:0{len(ROWS)}:00",
             "concluido_em": None, "duracao_ms": None}
        ROWS.append(r)
        return {"id": r["id"]}
    if s.startswith("select id, meta, pendentes, status from cockpit.trib_coletas"):
        cid, cust, amb = params
        return next((r for r in ROWS if r["id"] == cid and r["customer"] == cust and r["ambiente"] == amb), None)
    if s.startswith("select dados from cockpit.trib_coletas"):
        return next((r for r in ROWS if r["id"] == params[0]), None)
    if "from cockpit.trib_coletas" in s and "status in ('ok','parcial')" in s:
        lst = [r for r in ROWS if r["customer"] == params[0] and r["ambiente"] == params[1]
               and r["status"] in ("ok", "parcial")]
        return lst[-1] if lst else None
    if "from cockpit.trib_coletas" in s and "status='coletando'" in s:
        lst = [r for r in ROWS if r["customer"] == params[0] and r["ambiente"] == params[1] and r["status"] == "coletando"]
        return lst[-1] if lst else None
    if "from cockpit.protheus_ambientes" in s:
        return CFG.get(params[1])
    raise AssertionError("SQL inesperado: " + s[:140])


def fake_execute(sql, params=None):
    s = " ".join(sql.split()).lower()
    if s.startswith("update cockpit.trib_coletas set chamadas"):
        next(r for r in ROWS if r["id"] == params[0])["chamadas"] += 1
        return
    if s.startswith("update cockpit.trib_coletas set dados = dados ||"):
        dados, pend, status, _st2, dur, cid = params
        r = next(r for r in ROWS if r["id"] == cid)
        r["dados"].update(json.loads(dados)); r["pendentes"] = list(pend); r["status"] = status
        r["duracao_ms"] = (r["duracao_ms"] or 0) + dur
        if status != "coletando":
            r["concluido_em"] = "2026-10-30T14:10:00"
        return
    if s.startswith("update cockpit.trib_coletas set status='erro'"):
        next(r for r in ROWS if r["id"] == params[1])["status"] = "erro"
        return
    if s.startswith("delete from cockpit.trib_coletas"):
        cust, amb, _c, _a, n = params
        mine = [r for r in ROWS if r["customer"] == cust and r["ambiente"] == amb]
        manter = {r["id"] for r in sorted(mine, key=lambda r: r["iniciado_em"], reverse=True)[:n]}
        ROWS[:] = [r for r in ROWS if r["customer"] != cust or r["ambiente"] != amb or r["id"] in manter]
        return
    if s.startswith("insert into cockpit.protheus_coletas"):
        LOG.append({"tipo": params[2], "ok": params[5], "erro": params[12]})
        return
    raise AssertionError("execute inesperado: " + s[:140])


m.q, m.execute = fake_q, fake_execute
m.require_interno = lambda: None
m.require_auth = lambda: None
m.deny_customer = lambda c: None
m.deny_aba = lambda c, *a: None
m.eh_interno = lambda e=None: True
m.current_user = lambda: "reges.werlang@totvs.com.br"
m.effective_user = lambda: "reges.werlang@totvs.com.br"
for amb, porta, env in (("producao", 10207, "producao"), ("teste", 10257, "desenvolvimento")):
    aad = m._aad("000348D0", amb)
    CFG[amb] = {"customer": "000348D0", "ambiente": amb, "ativo": True,
                "url_rest": f"https://digitro.protheus.cloudtotvs.com.br:{porta}/rest/tscmonit",
                "environment": env, "empresa": "01", "filial": "01", "usuario": "admin",
                "senha_enc": m._cifra("s", aad), "token_enc": m._cifra("t", aad), "banco": "oracle",
                "sufixo": "010", "timeout_s": 45}

COLS = [("F2B010", "F2B_FILIAL"), ("F2B010", "F2B_ID"), ("F2B010", "F2B_REGRA"), ("F2B010", "F2B_TRIB"),
        ("F2B010", "F2B_VIGINI"), ("F2B010", "F2B_VIGFIM"), ("F2B010", "F2B_RALIQ"), ("F2B010", "D_E_L_E_T_"),
        ("F28010", "F28_FILIAL"), ("F28010", "F28_CODIGO"), ("F28010", "F28_ALIQ"),
        ("F2E010", "F2E_FILIAL"), ("F2E010", "F2E_TRIB"), ("F2D010", "F2D_FILIAL")]
F2B = {"producao": "01;a1;TR0001;CBSFED;20260101;;TA0001\n",
       "teste": "01;b1;TR0001;CBSFED;20260101;;TA0001\n01;b2;TR0002;IBSEST;20260101;;TA0002\n"}
F28 = {"producao": " ;TA0001;0.9\n", "teste": " ;TA0001;0.9\n ;TA0002;0.1\n"}
PEDIDOS = []
LENTO = {"on": False}


class R:
    def __init__(self, j, code=200):
        self._j, self.status_code, self.text = j, code, json.dumps(j)

    def json(self):
        return self._j


def fake_post(url, json=None, **k):
    amb = "producao" if ":10207" in url else "teste"
    sql = json["sql"]
    PEDIDOS.append((amb, sql))
    assert ";" not in sql and sql.upper().startswith("SELECT"), sql
    if LENTO["on"] and "FROM F2B010 WHERE" in sql:
        time.sleep(0)   # o prazo é que corta (ver abaixo)
    ok = lambda c: R({"ok": True, "csv": c, "environment": CFG[amb]["environment"]})
    if "USER_TAB_COLUMNS" in sql:
        return ok("TABLE_NAME;COLUMN_NAME;DATA_TYPE;COLUMN_ID\n" + "".join(f"{t};{c};VARCHAR2;1\n" for t, c in COLS))
    if "FROM SX2" in sql:
        return ok("X2_CHAVE;X2_NOME;X2_MODO;X2_MODOUN;X2_MODOEMP\nF2B;Regra;E;E;E\nF28;Aliq;C;C;C\n")
    if "FROM SX3" in sql:
        return ok("X3_ARQUIVO;X3_CAMPO;X3_TITULO;X3_CBOX;X3_CONTEXT\nF2B;F2B_RALIQ;Aliquota;;R\n")
    if "FROM SIX" in sql:
        return ok("INDICE;ORDEM;CHAVE\n")
    if "SYS_COMPANY" in sql:
        return ok("M0_CODIGO;M0_CODFIL;M0_FILIAL;M0_ESTENT\n01;01;MATRIZ;SC\n")
    if "COUNT(*)" in sql:
        n = 1 if amb == "producao" else 2
        return ok(f"TAB;FIL;QTD\nF2B;01;{n}\nF28; ;{n}\nF2E; ;0\nF2D;01;50\n")
    if "FROM F2B010" in sql:
        return ok("F2B_FILIAL;F2B_ID;F2B_REGRA;F2B_TRIB;F2B_VIGINI;F2B_VIGFIM;F2B_RALIQ\n" + F2B[amb])
    if "FROM F28010" in sql:
        return ok("F28_FILIAL;F28_CODIGO;F28_ALIQ\n" + F28[amb])
    return R({"ok": False, "erro": "inesperado"}, 500)


m.requests.post = fake_post
c = m.app.test_client()
H = {"Content-Type": "application/json"}

# guarda: tabela do Supabase ausente
orig_ultima = m._trib_ultima
m._trib_ultima = lambda *a: (_ for _ in ()).throw(m.psycopg2.errors.UndefinedTable("x"))
r = c.get("/api/tributos/000348D0")
confere("sem a tabela: 503 com o SQL a rodar", r.status_code == 503 and "2026-10-30-tributos.sql" in r.get_json()["error"])
m._trib_ultima = orig_ultima

# antes de coletar
r = c.get("/api/tributos/000348D0").get_json()
confere("sem coleta: payload vazio e ok", r["ok"] and r["bases"]["producao"]["coleta"] is None and r["comparacao"] == {})

# fase 0 + conteúdo numa chamada só (tudo cabe)
for amb in ("producao", "teste"):
    j = c.post(f"/api/tributos/000348D0/coletar?ambiente={amb}", data="{}", headers=H).get_json()
    confere(f"{amb}: coleta concluída na 1ª chamada", j["ok"] and j["pendentes"] == [] and j["status"] == "ok", j)
confere("F2E vazia (total 0) não vira leitura", not any(s.startswith("SELECT F2E_FILIAL") for _a, s in PEDIDOS))
confere("F2D (movimento) só conta", not any("FROM F2D010 WHERE D_E_L_E_T_ = ' ' ORDER" in s for _a, s in PEDIDOS))
confere("log da coleta", [x["tipo"] for x in LOG] == ["tributos", "tributos"] and all(x["ok"] for x in LOG))

d = c.get("/api/tributos/000348D0").get_json()
confere("duas bases coletadas", d["bases"]["producao"]["coleta"]["status"] == "ok" and d["bases"]["teste"]["coleta"]["environment"] == "desenvolvimento")
cmp = d["comparacao"]["F2B"]
confere("F2B: 1 igual, 1 só em Teste", cmp["resumo"]["iguais"] == 1 and cmp["resumo"]["so_teste"] == 1, cmp["resumo"])
confere("migração: TR0002 leva TA0002", [(x["regra"], [y["codigo"] for y in x["deps"]]) for x in d["migracao"]] == [("TR0002", ["TA0002"])],
        d["migracao"])
q = {x["tab"]: x for x in d["quantidades"]}
confere("quantidades: F2D 50 × 50, F2B 1 × 2", q["F2D"]["p"] == 50 and q["F2B"]["t"] == 2)
confere("reforma: filiais do SYS_COMPANY", d["reforma"]["filiais"] == ["01"])
confere("título do SX3 chega", cmp["titulos"].get("F2B_RALIQ") == "Aliquota")

# coleta faseada: prazo curto → fase 0 grava e devolve pendentes
orig = m._trib_le_tabelas
m._trib_le_tabelas = lambda cfg, h, a, t, meta, pend, prazo: ({}, list(pend))
j = c.post("/api/tributos/000348D0/coletar?ambiente=producao", data="{}", headers=H).get_json()
confere("fase 0 devolve pendentes", j["status"] == "coletando" and sorted(j["pendentes"]) == ["F28", "F2B"], j)
m._trib_le_tabelas = orig
d2 = c.get("/api/tributos/000348D0").get_json()
confere("leitura usa a última concluída enquanto outra coleta anda",
        d2["bases"]["producao"]["coleta"]["status"] == "ok" and d2["bases"]["producao"]["andamento"]["id"] == j["coleta_id"])
j2 = c.post("/api/tributos/000348D0/coletar?ambiente=producao", data=json.dumps({"coleta_id": j["coleta_id"]}), headers=H).get_json()
confere("2ª chamada conclui", j2["pendentes"] == [] and j2["status"] == "ok", j2)
r3 = next(r for r in ROWS if r["id"] == j["coleta_id"])
confere("chamadas contadas", r3["chamadas"] == 2)
j3 = c.post("/api/tributos/000348D0/coletar?ambiente=producao", data=json.dumps({"coleta_id": j["coleta_id"]}), headers=H).get_json()
confere("coleta concluída não relê", j3["pendentes"] == [] and j3["status"] == "ok")

# histórico curto
for _ in range(8):
    c.post("/api/tributos/000348D0/coletar?ambiente=teste", data="{}", headers=H)
confere("histórico: no máximo 6 por base", sum(1 for r in ROWS if r["ambiente"] == "teste") == m.TRIB_HISTORICO)

# guardas
CFG["teste"]["sufixo"] = ""
r = c.post("/api/tributos/000348D0/coletar?ambiente=teste", data="{}", headers=H)
confere("sem sufixo: 409", r.status_code == 409)
r = c.post("/api/tributos/000348D0/coletar?ambiente=xpto", data="{}", headers=H)
confere("ambiente inválido: 400", r.status_code == 400)

print(f"{ok} ok, {falhou} falhou")
raise SystemExit(1 if falhou else 0)
