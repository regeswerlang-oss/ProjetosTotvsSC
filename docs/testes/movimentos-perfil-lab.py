# Laboratório da coleta de movimentos por PERFIL (30/10/2026).
# Postgres local + stub HTTP do TSCMONITREST; roda o fluxo inteiro pelas rotas
# Flask (login trocado por stub): coletar legado com trava, blocos com
# placeholders por base, tabela inexistente = não se aplica, falha de coluna,
# gravação parcial, trava + forçar, NAO_MEDIDO e o cron com orçamento/retomada.
#
# Como rodar:
#   createdb lab && psql -d lab -f docs/testes/movimentos-perfil-lab-schema.sql \
#     && psql -d lab -f docs/sql/2026-10-30-monitmov-perfil-coleta.sql
#   LAB_DATABASE_URL=postgresql://postgres@/lab?host=/tmp python3 docs/testes/movimentos-perfil-lab.py
import base64, json, os, pathlib, sys, threading, time, re
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ["DATABASE_URL"] = os.environ.get("LAB_DATABASE_URL", "postgresql://postgres@/lab?host=/tmp&port=55432")
os.environ["PROTHEUS_CRED_KEY"] = base64.b64encode(b"k" * 32).decode()
os.environ["CRON_SECRET"] = "cron-secreto"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "api"))
import index as app_mod  # noqa: E402

CHAMADAS = []
DELAY = [0]


def csv_de(linhas):
    cab = "ANALISE;DESCRICAO;DIM1_NOME;DIM1;DIM2_NOME;DIM2;DIM3_NOME;DIM3;DIM4_NOME;DIM4;PERIODO;DT_LEITURA;SEMANA;QTDE;QTD_DOC"
    return "\n".join([cab] + [";".join(map(str, l)) for l in linhas])


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        b = json.loads(self.rfile.read(n) or b"{}")
        sql = b.get("sql", "")
        time.sleep(DELAY[0])
        CHAMADAS.append({"path": self.path, "sql": sql, "tenant": self.headers.get("tenantId")})
        def resp(code, obj):
            raw = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        if self.headers.get("X-TSC-Token") != "tok":
            return resp(401, {"ok": False, "erro": "token invalido"})
        if "{{" in sql:
            return resp(400, {"ok": False, "erro": "placeholder nao trocado: " + sql[sql.index("{{"):][:20]})
        if "ZZZ_INEXISTE" in sql:
            return resp(500, {"ok": False, "erro": "Falha: Error : 942 - ORA-00942: table or view does not exist"})
        if "BOOM" in sql:
            return resp(500, {"ok": False, "erro": "ORA-00904: \"X\": invalid identifier"})
        dt = "30/10/2026 03:10"
        if "GCT_CAMPO" in sql:
            return resp(200, {"ok": True, "linhas": 2, "csv": csv_de([
                ["GCT_CAMPO", "x", "T", "CN9", "C", "CN9_X", "", "", "", "", "total", dt, "2026-W44", 1, ""],
                ["GCT_TABELA", "x", "T", "CN9", "", "", "", "", "", "", "total", dt, "2026-W44", 9, ""]])})
        if "SE5_BANCARIO" in sql:
            suf = re.search(r"FROM SE5(\d{3})", sql).group(1)
            if "'19000101' AND '20991231'" not in sql and "BETWEEN '2026" not in sql:
                return resp(400, {"ok": False, "erro": "janela ausente"})
            return resp(200, {"ok": True, "linhas": 2, "csv": csv_de([
                ["SE5_BANCARIO", "motbx=NOR", "OPERACAO", "BAIXA A RECEBER", "SENTIDO", "RECEBIMENTO", "TIPO_DOC", "VL", "TIPO_TITULO", "NF", "total", dt, "2026-W44", 12 if suf == "010" else 3, 10],
                ["SE5_BANCARIO", "motbx=-", "OPERACAO", "ADIANTAMENTO", "SENTIDO", "PAGAMENTO", "TIPO_DOC", "PA", "TIPO_TITULO", "PA", "total", dt, "2026-W44", 2, 2]])})
        if "CN9_CONTRATO" in sql:
            return resp(200, {"ok": True, "linhas": 1, "csv": csv_de([
                ["CN9_CONTRATO", "c", "ESPECIE", "VENDA", "TIPO", "001", "SITUACAO", "05", "VIGENCIA", "VIGENTE", "total", dt, "2026-W44", 4, 4]])})
        if "VAZIO_OK" in sql:
            return resp(200, {"ok": True, "linhas": 0, "csv": ""})
        return resp(200, {"ok": True, "linhas": 0, "csv": ""})


srv = HTTPServer(("127.0.0.1", 18999), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()

# auth trocada
for nome in ("require_interno", "require_auth"):
    setattr(app_mod, nome, lambda: None)
app_mod.deny_customer = lambda c: None
app_mod.deny_aba = lambda c, *a: None
app_mod.effective_user = lambda: "reges@totvs"
app_mod.current_user = lambda: "reges@totvs"
app_mod.CRON_SECRET = "cron-secreto"
q, execute = app_mod.q, app_mod.execute
cli = app_mod.app.test_client()

ok = falhou = 0


def confere(nome, cond, extra=""):
    global ok, falhou
    if cond:
        ok += 1
    else:
        falhou += 1
        print("FALHOU:", nome, extra)


C = "000348D0"
execute("truncate cockpit.clientes, cockpit.monitcad_scripts, cockpit.monitmov_cenarios, cockpit.monitmov_medicoes, cockpit.monitmov_dimensoes, cockpit.monitmov_itens, cockpit.protheus_ambientes, cockpit.protheus_coletas, cockpit.monitmov_perfil, cockpit.monitmov_blocos, cockpit.monitmov_lotes")
execute("insert into cockpit.clientes values (%s)", (C,))
for amb, suf in (("producao", "020"), ("teste", "010")):
    execute("""insert into cockpit.protheus_ambientes (customer, ambiente, url_rest, environment, banco, sufixo,
               empresa, filial, token_enc, timeout_s, limite_linhas, ativo)
               values (%s,%s,'http://127.0.0.1:18999/rest/tscmonit','x','oracle',%s,'01','01',%s,20,50000,true)""",
            (C, amb, suf, app_mod._cifra("tok", app_mod._aad(C, amb))))
# script salvo = D10 de contratos (fixo 010 de propósito)
execute("insert into cockpit.monitcad_scripts (customer, tipo, sql, dialeto) values (%s,'movimentos',%s,'oracle')",
        (C, "-- banner\nSELECT 'CN9_CONTRATO' AS ANALISE, 1 FROM CN9010"))
for an, d1, d3, desc in (("CN9_CONTRATO", "VENDA", "05", "vigente"), ("CN9_CONTRATO", "VENDA", "09", "revisao"),
                         ("SE5_BANCARIO", "BAIXA A RECEBER", "*", "baixa rec"), ("SE5_BANCARIO", "TRANSFERENCIA ENTRE CONTAS", "*", "transf")):
    execute("insert into cockpit.monitmov_cenarios (customer, analise, dim1, dim3, descricao) values (%s,%s,%s,%s,%s)",
            (C, an, d1, d3, desc))

# ── 1. legado: medição GCT antiga em produção, sem analises_medidas ─────────
r = cli.post(f"/api/protheus/{C}/producao/coletar?tipo=movimentos")  # script D10 → grava ok
confere("coletar legado grava", r.status_code == 200, r.get_json())
med = q("select payload from cockpit.monitmov_medicoes where customer=%s and ambiente='producao'", (C,), one=True)
confere("legado registra analises_medidas", med["payload"].get("analises_medidas") == ["CN9_CONTRATO"], med)

j = cli.get(f"/api/monitmov/{C}?ambiente=producao").get_json()
st = {c["descricao"]: c["status"] for c in j["cobertura"]}
confere("SE5 sem bloco = NAO_MEDIDO", st["baixa rec"] == "NAO_MEDIDO" and st["transf"] == "NAO_MEDIDO", st)
confere("CN9 05 coberto", st["vigente"] == "COBERTO", st)
confere("CN9 09 faltante", st["revisao"] == "FALTANTE", st)

# ── 2. trava no legado: script GCT salvo como movimentos ────────────────────
execute("update cockpit.monitcad_scripts set sql=%s where customer=%s and tipo='movimentos'",
        ("SELECT 'GCT_CAMPO' AS ANALISE FROM SX3010", C))
r = cli.post(f"/api/protheus/{C}/producao/coletar?tipo=movimentos")
confere("legado recusa GCT", r.status_code == 409 and r.get_json().get("recusa"), r.get_json())
n = q("select count(*) n from cockpit.monitmov_medicoes where customer=%s and ambiente='producao'", (C,), one=True)["n"]
confere("recusa não apaga a medição boa", n == 1)

# ── 3. perfil: script salvo GCT + bloco SE5 do catálogo com placeholders ────
execute("update cockpit.monitcad_scripts set sql=%s where customer=%s and tipo='movimentos'",
        ("-- D10\nSELECT 'CN9_CONTRATO' AS ANALISE, 1 FROM CN9010", C))
se5 = ("-- bloco\nSELECT 'SE5_BANCARIO' AS ANALISE, '{{PERIODO}}' AS PERIODO FROM SE5{{SUFIXO}} E "
       "WHERE E.D_E_L_E_T_=' ' AND E.E5_DATA BETWEEN '{{DT_INI}}' AND '{{DT_FIM}}'")
r = cli.post(f"/api/monitmov/{C}/blocos", json={"nome": "SE5 catálogo", "origem": "catalogo", "catalogo": "SE5_BANCARIO",
                                               "dialeto": "oracle", "sql": se5})
confere("salva bloco", r.status_code == 200 and r.get_json()["analises"] == ["SE5_BANCARIO"], r.get_json())
r = cli.post(f"/api/monitmov/{C}/blocos", json={"nome": "Loja", "dialeto": "oracle",
                                               "sql": "SELECT 'SL1_LOJA' AS ANALISE FROM ZZZ_INEXISTE"})
confere("salva bloco loja", r.status_code == 200)
r = cli.post(f"/api/monitmov/{C}/blocos", json={"nome": "PG", "dialeto": "postgres",
                                               "sql": "SELECT 'SD2_FISCAL' AS ANALISE FROM SD2010"})
confere("salva bloco postgres", r.status_code == 200)
r = cli.post(f"/api/monitmov/{C}/blocos", json={"nome": "Escrita", "sql": "DELETE FROM SE5010 WHERE 1=1"})
confere("recusa bloco de escrita", r.status_code == 400, r.get_json())
r = cli.post(f"/api/monitmov/{C}/blocos", json={"nome": "Blindado", "dialeto": "oracle",
             "sql": "SELECT 'SB1_X' AS ANALISE, XMLCAST(XMLQUERY('/R' PASSING DBMS_XMLGEN.GETXMLTYPE('SELECT 1 FROM DUAL') RETURNING CONTENT) AS NUMBER) Q FROM DUAL"})
confere("aceita DBMS_XMLGEN (leitura blindada)", r.status_code == 200, r.get_json())
bid_blindado = r.get_json()["id"]
cli.delete(f"/api/monitmov/{C}/blocos/{bid_blindado}")

pf = cli.get(f"/api/monitmov/{C}/perfil-coleta").get_json()
confere("perfil lista script + 3 blocos", len(pf["blocos"]) == 4, [b["nome"] for b in pf["blocos"]])
confere("cenários medidos pelo perfil", all(c["medida"] for c in pf["cenarios"]), pf["cenarios"])

for amb in ("teste", "producao"):
    r = cli.post(f"/api/monitmov/{C}/lote?ambiente={amb}")
    lj = r.get_json()
    confere(f"{amb}: abre lote", r.status_code == 200, lj)
    confere(f"{amb}: bloco postgres pulado", any(v.get("pulado") for v in lj["resultados"].values()), lj["resultados"])
    for b in lj["blocos"]:
        if b["id"] in lj["resultados"]:
            continue
        rb = cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/bloco/{b['id']}").get_json()
        if b["nome"] == "Loja":
            confere(f"{amb}: tabela inexistente = não se aplica", rb.get("nao_se_aplica") and not rb.get("ok"), rb)
        else:
            confere(f"{amb}: bloco {b['nome']} ok", rb.get("ok"), rb)
        confere("resposta do bloco sem csv", "csv" not in rb)
    r = cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/fechar")
    fj = r.get_json()
    confere(f"{amb}: fecha e grava", r.status_code == 200, fj)
    confere(f"{amb}: medidas", fj.get("medidas") == ["CN9_CONTRATO", "SE5_BANCARIO"], fj.get("medidas"))
    confere(f"{amb}: não se aplica listado", "SL1_LOJA" in fj.get("nao_se_aplica", []) and "SD2_FISCAL" in fj.get("nao_se_aplica", []), fj)
    lote = q("select status, resultados from cockpit.monitmov_lotes where id=%s", (lj["lote_id"],), one=True)
    confere(f"{amb}: lote gravado sem csv", lote["status"] == "gravado" and not any("csv" in v for v in lote["resultados"].values()))

se5_calls = [c["sql"] for c in CHAMADAS if "SE5_BANCARIO" in c["sql"]]
confere("sufixo por base (010 e 020)", any("SE5010" in s for s in se5_calls) and any("SE5020" in s for s in se5_calls))
confere("periodo total trocado", all("'total'" in s for s in se5_calls))
confere("banner cortado", all(not s.lstrip().startswith("--") for s in (c["sql"] for c in CHAMADAS)))

j = cli.get(f"/api/monitmov/{C}?ambiente=producao").get_json()
st = {c["descricao"]: c["status"] for c in j["cobertura"]}
confere("agora SE5 medido: baixa coberta", st["baixa rec"] == "COBERTO", st)
confere("transf = FALTANTE (medido, zero)", st["transf"] == "FALTANTE", st)
confere("api devolve analises_medidas", j["analises_medidas"] == ["CN9_CONTRATO", "SE5_BANCARIO"], j.get("analises_medidas"))
confere("origem coleta", j["origem"] == "coleta")
ev = cli.get(f"/api/monitmov/{C}/evolucao?ambiente=producao").get_json()
confere("evolução tem nao_medidos", "nao_medidos" in ev["serie"][-1], ev["serie"][-1])

# ── 4. lote com bloco que falha: 409, depois parcial ────────────────────────
r = cli.post(f"/api/monitmov/{C}/blocos", json={"nome": "Quebrado", "dialeto": "oracle",
                                               "sql": "SELECT 'SC7_PEDIDO' AS ANALISE, BOOM FROM SC7010"})
lj = cli.post(f"/api/monitmov/{C}/lote?ambiente=teste").get_json()
for b in lj["blocos"]:
    if b["id"] not in lj["resultados"]:
        cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/bloco/{b['id']}")
r = cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/fechar")
confere("falha de coluna não é 'não se aplica' → 409", r.status_code == 409 and r.get_json()["falhos"][0]["nome"] == "Quebrado", r.get_json())
r = cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/fechar?parcial=1")
fj = r.get_json()
confere("parcial grava e avisa", r.status_code == 200 and fj["sem_medir"] == ["SC7_PEDIDO"], fj)
qid = [b for b in cli.get(f"/api/monitmov/{C}/perfil-coleta").get_json()["blocos"] if b["nome"] == "Quebrado"][0]["id"]
cli.delete(f"/api/monitmov/{C}/blocos/{qid}")

# ── 5. trava no lote + forcar ───────────────────────────────────────────────
execute("update cockpit.monitcad_scripts set sql=%s where customer=%s", ("SELECT 'GCT_CAMPO' AS ANALISE FROM SX3010", C))
execute("update cockpit.monitmov_blocos set ativo=false where customer=%s", (C,))
lj = cli.post(f"/api/monitmov/{C}/lote?ambiente=producao").get_json()
for b in lj["blocos"]:
    cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/bloco/{b['id']}")
r = cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/fechar")
confere("lote recusa GCT", r.status_code == 409 and r.get_json()["recusa"], r.get_json())
confere("lote recusado continua aberto", q("select status from cockpit.monitmov_lotes where id=%s", (lj["lote_id"],), one=True)["status"] == "aberto")
r = cli.post(f"/api/monitmov/{C}/lote/{lj['lote_id']}/fechar?forcar=1")
confere("forcar grava", r.status_code == 200, r.get_json())
j = cli.get(f"/api/monitmov/{C}?ambiente=producao").get_json()
confere("forcada sinalizada", j["coleta_forcada"] is True)

# ── 6. cron ─────────────────────────────────────────────────────────────────
execute("update cockpit.monitcad_scripts set sql=%s where customer=%s", ("SELECT 'CN9_CONTRATO' AS ANALISE FROM CN9010", C))
execute("update cockpit.monitmov_blocos set ativo=true where customer=%s and nome='SE5 catálogo'", (C,))
r = cli.get("/api/cron/coleta-movimentos")
confere("cron sem bearer = 401", r.status_code == 401)
h = {"Authorization": "Bearer cron-secreto"}
r = cli.get("/api/cron/coleta-movimentos", headers=h).get_json()
confere("cron sem agenda não faz nada", r["bases"] == [], r)
r = cli.post(f"/api/monitmov/{C}/perfil-coleta", json={"agenda": "diaria", "agenda_ambientes": "*", "janela_dias": 30})
confere("salva perfil", r.status_code == 200 and r.get_json()["perfil"]["agenda"] == "diaria")
r = cli.get("/api/cron/coleta-movimentos", headers=h).get_json()
confere("cron respeita coleta recente (<20h)", r["bases"] == [], r)
execute("update cockpit.monitmov_lotes set fechado_em = now() - interval '2 days', iniciado_em = now() - interval '2 days' where customer=%s", (C,))
CHAMADAS.clear()
r = cli.get("/api/cron/coleta-movimentos", headers=h).get_json()
confere("cron coleta as duas bases agendadas", len(r["bases"]) == 2 and all(b["ok"] for b in r["bases"]), json.dumps(r, default=str)[:600])
confere("janela de 30 dias aplicada", any("BETWEEN '2026" in c["sql"] for c in CHAMADAS))
r = cli.get("/api/cron/coleta-movimentos", headers=h).get_json()
confere("cron não repete antes de 20h", r["bases"] == [], r)
r = cli.get(f"/api/cron/coleta-movimentos?customer={C}&ambiente=teste", headers=h).get_json()
confere("cron forçado por cliente", len(r["bases"]) == 1 and r["bases"][0]["ambiente"] == "teste" and r["bases"][0]["ok"], r)
log = q("select disparado_por, ok from cockpit.protheus_coletas where tipo='movimentos' order by id desc limit 1", one=True)
confere("log do cron com disparado_por=cron", log["disparado_por"] == "cron" and log["ok"], log)

# orçamento: cron retoma lote aberto
app_mod.MOV_CRON_ORCAMENTO_S, app_mod.MOV_CRON_FOLGA_S, DELAY[0] = 4, 1.9, 2.5  # só cabe 1 bloco
execute("update cockpit.monitmov_lotes set fechado_em = now() - interval '2 days', iniciado_em = now() - interval '2 days' where customer=%s", (C,))
r1 = cli.get("/api/cron/coleta-movimentos", headers=h).get_json()
confere("cron para no orçamento e deixa lote aberto", r1["bases"] and r1["bases"][0].get("retoma"), r1)
r2 = cli.get("/api/cron/coleta-movimentos", headers=h).get_json()
confere("próxima chamada retoma o mesmo lote", r2["bases"] and r2["bases"][0]["lote_id"] == r1["bases"][0]["lote_id"], (r1, r2))
app_mod.MOV_CRON_ORCAMENTO_S, app_mod.MOV_CRON_FOLGA_S, DELAY[0] = 48, 12, 0

print(f"\n{ok} ok, {falhou} falhou(aram)")
srv.shutdown()
sys.exit(1 if falhou else 0)
