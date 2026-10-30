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

# Datas da base fingida = HOJE (fuso de Florianópolis), senão o teste envelhece
# com o calendário: fila "de hoje" vira "de ontem" e o nível muda sozinho.
from datetime import datetime, timedelta, timezone
HOJE = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y%m%d")

# ── REST fingida ────────────────────────────────────────────────────────────
CSV = {
    "SX6": "PARAMETRO;FILIAL;CONTEUDO\nMV_RHNG;;.T.\nMV_HISTQUI;;1\nMV_RHMSGNG;;100\nMV_URIQR;;https://app.quirons.com/ttalk/\n",
    "RJP_FILA": f"FILIAL;TABELA;OPER;QTD;MAIS_ANTIGO\n  ;SRA;A;12;{HOJE}\n",
    "RJP_VAZAO": f"DIA;QTD;PRIMEIRA;ULTIMA\n{HOJE};9;06:00:01;09:15:00\n",
    "RU7": "DIA;COD_HTTP;QTD\n",
    "RJE_SST": "EVENTO;STATUS;QTD;MAIS_ANTIGO;MAIS_RECENTE\nS2220;4;30;20260901;20261010\n",
    "RJP_ANT": f"FILIAL;TABELA;OPER;CHAVE;GERADO\n  ;SRA;A;01000123;{HOJE}\n",
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
        # Memo: a base fingida tem CLOB — a 1ª variante (BLOB) falha e a 2ª vale.
        if "UTL_RAW" in sql:
            return R(200, {"ok": False, "erro": "ORA-06502: PL/SQL: numeric or value error: hex to raw conversion error"})
        if "RUM_STATUS = '3'" in sql and "SRA010" not in sql:
            return R(200, {"ok": True, "csv": "TIPO;OPER;MENSAGEM\n"
                           "1;I;E-mail já cadastrado.\n1;I;Centro de custo inválido | CPF Inválido\n"
                           "2;A;Nao existe licenca disponivel no License Server\n",
                           "linhas": 3, "truncado": False, "environment": "RACLI_PROD"})
        if "SRA010" in sql:
            return R(200, {"ok": True, "csv": "FILIAL;MATRICULA;NOME;COD_INTERNO;TIPO;OPER;STATUS;DT_MOV;DT_INTEG;HR_INTEG;MENSAGEM\n"
                           "01;000123;FULANO DE TAL;01|01|000123;1;A;3;20261010;20261010;08:00:00;E-mail já cadastrado.\n",
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
confere("12 consultas (10 blocos + 2 tentativas de memo)", sum(1 for c in CHAMADAS if "/query" in c["url"]) == 12)
bm = ult_bm = d["ultima"]["blocos"]["rum_motivos"]
confere("motivos lidos pela variante CLOB", bm["ok"] and bm["variante"] == 1 and "ORA-06502" in bm.get("aviso_variante", ""))
confere("só o resumo gravado", bm["linhas"] == [] and bm["resumo"]["registros"] == 3)
confere("categorias", bm["resumo"]["categorias"]["cadastro"] == 2 and bm["resumo"]["categorias"]["licenca"] == 1)
confere("detalhe com mensagem", d["ultima"]["blocos"]["rum_pendencias"]["linhas"][0]["MENSAGEM"] == "E-mail já cadastrado.")
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
confere("scripts sem cadastro usam 010", d["sufixo_usado"] == "010" and len(d["scripts"]) == 10)
confere("scripts sem ;", all(not s["sql"].rstrip().endswith(";") for s in d["scripts"]))

# ── 8. grupo TOTVS Transmite (16/10/2026) ───────────────────────────────────
# Base de Compras (Rio Deserto): só o grupo transmite. A SDS fingida não tem
# DS_DATAIMP — a 1ª variante da revisão falha e a 2ª (DS_EMISSA) vale.
TRA_CSV = {
    "cfg": "PARAMETRO;FILIAL;CONTEUDO\nMV_IMPXML;;.T.\nMV_DTINITR;;20260501\nMV_APITRAN;;(preenchido)\n",
    "fila": f"CODEDI;STRAN;QTD;MAIS_ANTIGO;MAIS_RECENTE;PARADOS_AMARELO;PARADOS_VERMELHO\n109;4;300;20260701;{HOJE};250;200\n109;2;24;20260922;{HOJE};24;0\n",
    "sem_ret": "FILIAL;QTD;DIGIT_MAIS_ANTIGA;EMISSAO_MAIS_ANTIGA;VENCIDAS;CRITICAS;ATENCAO\n0101;3;20261001;20260801;0;0;3\n",
    "fut": "FILIAL;DTDIGIT;QTD;PRIMEIRA;ULTIMA\n",
    "rev": "STATUS;QTD;MAIS_ANTIGO;MAIS_RECENTE\nB;2;20261010;20261012\nP;290;20260701;20261012\n",
    "mon": "FILIAL;ESPECIE;QTD;MAIS_ANTIGO;MAIS_RECENTE\n",
    "lista": "FILIAL;DOC;SERIE;FORNECEDOR;LOJA;EMISSAO;DTDIGIT;HORA;STRAN;CODEDI;DT_IMP;DS_STATUS;CHAVE\n"
             "0101;000013687;1;F00001;01;20260801;20261001;10:00:00;2;109;20260802;B;42261027968581000106550010000136871530601731\n",
    "vazio": "X\n",
}


def fake_post_tra(url, json=None, headers=None, auth=None, params=None, timeout=None, verify=None):
    sql = json["sql"]
    if not any(t in sql for t in ("CKOCOL", "SF1010", "SDS010", "MV_IMPXML")):
        return fake_post(url, json, headers, auth, params, timeout, verify)
    CHAMADAS.append({"url": url, "sql": sql, "token": headers.get("X-TSC-Token"),
                     "tipo": json["tipo"], "auth": auth, "limite": json["limite"]})
    assert not sql.rstrip().endswith(";")
    if "DS_DATAIMP" in sql:
        return R(200, {"ok": False, "erro": 'ORA-00904: "DS_DATAIMP": invalid identifier'})
    k = ("cfg" if "MV_IMPXML" in sql else
         "lista" if "INNER JOIN CKOCOL" in sql else
         "sem_ret" if "EXISTS (SELECT 1 FROM CKOCOL" in sql else
         "fila" if "FROM CKOCOL WHERE" in sql else
         "rev" if "FROM SDS010 WHERE" in sql and "COUNT(*)" in sql else
         "mon" if "NOT EXISTS" in sql else
         "fut" if "F1_DTDIGIT >" in sql and "COUNT(*)" in sql else "vazio")
    return R(200, {"ok": True, "csv": TRA_CSV[k], "linhas": TRA_CSV[k].count("\n") - 1,
                   "truncado": False, "environment": "RDESERTO_PROD"})


m.requests.post = fake_post_tra
aad_rd = m._aad("TFDPHR00", "producao")          # credencial cifrada amarra cliente+base
CFG["cfg"] = dict(BASE_CFG, customer="TFDPHR00", integ_grupos=["transmite"], integ_desde=None,
                  senha_enc=m._cifra("s3nha", aad_rd), token_enc=m._cifra("tok123", aad_rd))
CHAMADAS.clear()
DB["medicoes"].clear()
r = cli.post("/api/integracoes/TFDPHR00/coletar?ambiente=producao")
d = r.get_json()
confere("transmite: coleta 200", r.status_code == 200 and d["ok"])
q_tra = [c for c in CHAMADAS if "/query" in c["url"]]
confere("transmite: nenhuma consulta de RH", not any(t in c["sql"] for c in q_tra
                                                  for t in ("RJP010", "RUM010", "RU7010", "RJE010")))
confere("transmite: sem healthcheck da Quírons", not any("healthcheck" in c["url"] for c in CHAMADAS))
confere("transmite: 12 consultas (10 blocos + 2 variantes da SDS)", len(q_tra) == 12)
ult = d["ultima"]
inds = {i["chave"]: i for i in ult["indicadores"]}
confere("transmite: só indicadores do grupo", set(i["grupo"] for i in ult["indicadores"]) == {"transmite"})
confere("transmite: revisão pela variante DS_EMISSA", ult["blocos"]["tra_revisao"]["variante"] == 1
        and inds["tra_revisao"]["valor"] == 2)
confere("transmite: sem retorno 3, amarelo de prazo", inds["tra_sem_retorno"]["valor"] == 3
        and inds["tra_prazo"]["nivel"] == "amarelo")
confere("transmite: fila parada 24", inds["tra_fila"]["valor"] == 24)
confere("transmite: grupos gravados na coleta", ult["blocos"]["_meta"]["grupos"] == ["transmite"])
confere("transmite: cfg devolve grupos", d["ambiente_cfg"]["integ_grupos"] == ["transmite"])
confere("transmite: detalhe com a nota", ult["blocos"]["tra_sem_retorno_lista"]["linhas"][0]["DOC"] == "000013687")
d = cli.get("/api/integracoes/TFDPHR00/scripts?ambiente=producao").get_json()
confere("transmite: scripts do grupo", d["grupos"] == ["transmite"] and len(d["scripts"]) == 10
        and all(s["id"].startswith("tra_") for s in d["scripts"]))

# rota /grupos
UPG = []
def exec_grupos(sql, params=None):
    if "set integ_grupos" in sql:
        UPG.append(params); CFG["cfg"] = dict(CFG["cfg"], integ_grupos=params[0]); return
    return _exec_orig(sql, params)
m.execute = exec_grupos
r = cli.post("/api/integracoes/TFDPHR00/grupos?ambiente=producao", json={"grupos": ["transmite", "RH"]})
confere("grupos: grava na ordem fixa", r.status_code == 200 and r.get_json()["grupos"] == ["rh", "transmite"]
        and UPG[-1][0] == ["rh", "transmite"])
r = cli.post("/api/integracoes/TFDPHR00/grupos?ambiente=producao", json={"grupos": []})
confere("grupos: vazio recusado", r.status_code == 400)
r = cli.post("/api/integracoes/TFDPHR00/grupos?ambiente=producao", json={"grupos": ["fiscal"]})
confere("grupos: desconhecido recusado", r.status_code == 400 and "fiscal" in r.get_json()["error"])
CFG["cfg"] = None
r = cli.post("/api/integracoes/TFDPHR00/grupos?ambiente=producao", json={"grupos": ["rh"]})
confere("grupos: sem ambiente = 404", r.status_code == 404)
m.execute = _exec_orig
m.requests.post = fake_post

# ── grupo CRM × iPaaS (Dígitro, 30/10/2026) ─────────────────────────────────
# Base com só o grupo crm. A ZA3 fingida tem memo CLOB: a 1ª variante da
# lista de pendentes (BLOB) falha e a 2ª vale. Sem healthcheck da Quírons.
CRM_CSV = {
    "config": "PARAMETRO;FILIAL;CONTEUDO\nMV_ZCRMMOD;;2\nMV_ZMAILPP;;contratos@digitro.com.br\nMV_ZCRMTOK;;(preenchido)\n",
    "totais": f"MENSAGENS;PROPOSTAS;LIBERADAS;TRATADAS;CONTRATOS_ZA3;RETORNADAS;MAIS_ANTIGA;MAIS_RECENTE\n4;3;3;2;2;0;20261001;{HOJE}\n",
    "situacao": "STG1;STG2;STIPA;QTD;PROPOSTAS;MAIS_ANTIGO;MAIS_RECENTE\nL;S;N;2;2;20261001;20261020\nL;E;N;2;1;20261020;20261021\n",
    "fila": "STG1;STG2;DIA;QTD;PRIMEIRA\n",
    "erros": f"STG1;STG2;DIA;QTD;PROPOSTAS;SEM_SUCESSO\nL;E;{HOJE};2;1;1\n",
    "projetos": "TPPROD;STATUS;QTD;CONTRATOS;MAIS_ANTIGO;MAIS_RECENTE\n1;1;3;2;20261001;20261020\n",
    "contratos": "SITUAC;CONTRATOS;REVISOES;INICIO_MAIS_ANTIGO\n02;2;2;20261001\n",
    "medicoes": "SITUAC;QTD;CONTRATOS;COM_PEDIDO\nE;1;1;1\n",
    "produtos": "TIPO;ATIVOS;COM_PRECO;COM_ZFATURA\nPA;10;9;10\n",
    "tabelas": "FILIAL;TABELA;DESCRICAO;ATIVO;DE;ATE;ITENS;COM_PRECO\n01;001;PADRAO;1;20260101;;9;9\n",
    "pendentes": f"IDCRM;MSGID;STG1;STG2;STIPA;ETAPA;DTINC;HRINC;DTFIM;HRFIM;JA_OK;ERRO\n"
                 f"OPP-9;MSG-9;L;E;N;VALIDA CABECALHO;{HOJE};08:00:00;{HOJE};08:00:05;N;Cliente 000099/01 não encontrado\n",
    "rastreio": "IDCRM;DTINC;HRINC;DTFIM;HRFIM;CONTRATO;STIPA;PROPOSTA;PROJETOS;SITUAC;MEDICOES\n"
                "OPP-1;20261001;09:00:00;20261001;09:01:00;000000000000001;N;PROP-1;2;02;1\n"
                "OPP-2;20261020;10:00:00;20261020;10:02:00;000000000000002;N;PROP-2;1;02;0\n",
    "sem_preco": "PRODUTO;DESCRICAO;TIPO;GRUPO\nNGC-01;NGC CORPORATE;PA;0001\n",
}


def crm_chave(sql):
    if "FROM SX6010" in sql: return "config"
    if "AS JA_OK" in sql: return "pendentes"
    if "AS PROJETOS" in sql: return "rastreio"
    if "AS MENSAGENS" in sql: return "totais"
    if "AS SEM_SUCESSO" in sql: return "erros"
    if "AS PRIMEIRA" in sql: return "fila"
    if "ZA3_STIPA AS STIPA, COUNT" in sql: return "situacao"
    if "FROM ZA0010 WHERE" in sql: return "projetos"
    if "AS REVISOES" in sql: return "contratos"
    if "FROM CND010" in sql: return "medicoes"
    if "AS ATIVOS" in sql: return "produtos"
    if "PR.COD IS NULL ORDER" in sql: return "sem_preco"
    if "FROM DA0010 DA0 WHERE" in sql: return "tabelas"
    raise AssertionError("bloco CRM inesperado: " + sql[:120])


def fake_post_crm(url, json=None, headers=None, auth=None, params=None, timeout=None, verify=None):
    CHAMADAS.append({"url": url, "sql": json["sql"], "token": headers.get("X-TSC-Token"),
                     "tipo": json["tipo"], "auth": auth, "limite": json["limite"]})
    sql = json["sql"]
    assert not sql.rstrip().endswith(";")
    k = crm_chave(sql)
    if k == "pendentes" and "UTL_RAW" in sql:
        return R(200, {"ok": False, "erro": "ORA-06502: PL/SQL: numeric or value error"})
    return R(200, {"ok": True, "csv": CRM_CSV[k], "linhas": CRM_CSV[k].count("\n") - 1,
                   "truncado": False, "environment": "producao"})


m.requests.post = fake_post_crm
CHAMADAS.clear()
aad_dg = m._aad("000348D0", "producao")
CFG["cfg"] = dict(BASE_CFG, customer="000348D0", integ_grupos=["crm"], integ_desde=None,
                  environment="producao", senha_enc=m._cifra("s3nha", aad_dg),
                  token_enc=m._cifra("tok123", aad_dg))
DB["medicoes"].clear()
r = cli.post("/api/integracoes/000348D0/coletar?ambiente=producao")
d = r.get_json()
q_crm = [c for c in CHAMADAS if "/query" in c["url"]]
confere("crm: coleta 200", r.status_code == 200 and d["ok"])
confere("crm: sem healthcheck da Quírons", not any("healthcheck" in c["url"] for c in CHAMADAS))
confere("crm: 14 consultas (13 blocos + 1 variante do memo)", len(q_crm) == 14)
confere("crm: nenhuma consulta de RH ou Transmite",
        not any(t in c["sql"] for c in q_crm for t in ("RJP010", "RUM010", "CKOCOL", "SDS010")))
ult = d["ultima"]
inds = {i["chave"]: i for i in ult["indicadores"]}
confere("crm: só indicadores do grupo", set(i["grupo"] for i in ult["indicadores"]) == {"crm"})
confere("crm: 3 propostas recebidas", inds["crm_recebidas"]["valor"] == 3)
confere("crm: erro de hoje sem sucesso = amarelo", inds["crm_erros"]["nivel"] == "amarelo"
        and "Cliente 1" in inds["crm_erros"]["texto"])
confere("crm: contratos achados", inds["crm_contratos"]["valor"] == 2 and inds["crm_contratos"]["nivel"] == "verde")
confere("crm: medidos 1/2 pelo rastreio", inds["crm_medicoes"]["valor"] == "1/2")
confere("crm: retorno cinza (P11)", inds["crm_retorno"]["nivel"] == "cinza")
confere("crm: cobertura 90%", inds["crm_cad_produtos"]["valor"] == "90%")
pl = ult["blocos"]["crm_pendentes_lista"]
confere("crm: memo pela variante CLOB", pl["ok"] and pl["variante"] == 1)
confere("crm: causa anotada na linha", pl["linhas"][0]["CAUSA"] == "cliente" and pl["causas"] == {"cliente": 1})
confere("crm: grupos gravados na coleta", ult["blocos"]["_meta"]["grupos"] == ["crm"])
confere("crm: payload traz a outra base", d["outra"]["ambiente"] == "teste" and "ultima" in d["outra"])
confere("crm: payload sem segredo", "tok123" not in r.get_data(as_text=True))
d = cli.get("/api/integracoes/000348D0/scripts?ambiente=producao").get_json()
confere("crm: scripts do grupo", d["grupos"] == ["crm"] and len(d["scripts"]) == 13
        and all(s["id"].startswith("crm_") for s in d["scripts"]))
UPG = []
m.execute = exec_grupos
r = cli.post("/api/integracoes/000348D0/grupos?ambiente=producao", json={"grupos": ["crm", "rh"]})
confere("crm: grupo aceito na rota", r.status_code == 200 and r.get_json()["grupos"] == ["rh", "crm"])
m.execute = _exec_orig
m.requests.post = fake_post

# ── grupo EAI × Schedule (Dígitro, 30/10/2026) ──────────────────────────────
# REST fingida com o retrato da Produção: a XX3 só tem entregues (7) e não
# entregues (5), a XXF está vazia e o FWEAIRECE nunca rodou. A recorrência
# (CLOB) e o retorno (CLOB) respondem na 1ª variante (DBMS_LOB.SUBSTR).
EAI_CSV = {
    "config": "PARAMETRO;FILIAL;CONTEUDO\nMV_EAIPORT;;WS_ERPProtheusToGFE\nMV_EAIURL;;\nMV_EAIPASS;;\n",
    "adapters": "ROTINA;MENSAGEM;DESCRICAO;ENVIA;RECEBE;METODO;CANAL;UNICA;VERSAO;FORMATO;CONDICAO\n"
                "CRMA980;CUSTOMERVENDOR;CLIENTE;1;1;2;3;1;2.005;JSON;\n"
                "MATA040;SELLER;VENDEDOR;1;2;2;3;1;2.001;JSON;\n"
                "OMSA010;PRICELISTHEADERITEM;TABELA DE PRECO;1;2;2;3;1;2.001;JSON;\n",
    "status": "MENSAGEM;STATUS;CANAL;TPTRAN;QTD;MAX_TENTATIVAS;ESGOTADAS;COM_DESTINO;MAIS_ANTIGA;MAIS_RECENTE\n"
              "CUSTOMERVENDOR;7;3;1;821;0;0;821;20261029;20261029\n"
              f"SELLER;5;1;1;6;4;6;0;{HOJE};{HOJE}\nSELLER;7;3;1;11;0;0;11;{HOJE};{HOJE}\n",
    "abertas": "MENSAGEM;STATUS;DIA;QTD;PRIMEIRA;MAX_TENTATIVAS\nCUSTOMERVENDOR;7;20261020;821;16:00:47;0\n"
               f"SELLER;5;{HOJE};6;07:56:23;4\nSELLER;7;{HOJE};11;08:49:27;0\n",
    "depara": "ALIAS;REFERENCIA;MENSAGEM;QTD\n",
    "empresa": "REFERENCIA;EMPRESA_EXT;FILIAL_EXT;EMPRESA;FILIAL\nCRM-COMPANY;01;;01;01\n",
    "cadastros": "ALIAS;QTD\nSA1;820\nSA3;11\nDA0;7\n",
    "agend": "CODIGO;ROTINA;STATUS;AMBIENTE;INICIO;HORA;ULTDIA;ULTHOR;MODULO;EAI;RECORR\n"
             f"000001;FINA711('01');0;PRODUCAO;20260625;00:00;{HOJE};10:00;6;N;D(Each(.T.))\n"
             "000002;FWEAISEND;0;PRODUCAO;20261021;09:57;;;99;S;Smart A\n"
             "000003;FWEAIRECE;0;PRODUCAO;20261021;09:58;;;99;S;Smart A\n",
    "empfil": "CODIGO;EMPFIL\n000001;01/01\n000002;01/01\n000003;01/01\n",
    "tarefas": "CODIGO;ROTINA;STATUS;QTD;PRIMEIRA;ULTIMA;MAX_TENTATIVAS\n000001;FINA711('01');2;521;20261025;20261030;2\n"
               "000003;FWEAIRECE;4;1;;;0\n",
    "agents": "CODIGO;DESCRICAO;IP;PORTA;AMBIENTE;EMPRESA;THREADS;STATUS;ULTDIA;ULTHOR\n01;AGENT 01;127.0.0.1;6001;PRODUCAO;01;2;0;20260625;14:40\n",
    "pendentes": "MENSAGEM;STATUS;CANAL;TPTRAN;TENTATIVAS;DIA;HORA;ULT_TENTATIVA;ULT_TENT_HORA;EVENTO;WEBSERVICE;UUID;COM_DESTINO;RETORNO\n"
                 "CUSTOMERVENDOR;7;3;1;0;20261029;16:00:47;;;upsert;;u-1;S;\n",
    "ultimas": "MENSAGEM;STATUS;CANAL;TPTRAN;TENTATIVAS;DIA;HORA;PROC_DIA;PROC_HORA;EVENTO;RN\n"
               f"SELLER;7;3;1;0;{HOJE};08:49:28;;;upsert;1\n",
}


def eai_chave(sql):
    if "FROM SX6010" in sql: return "config"
    if "FROM XX4010" in sql: return "adapters"
    if "AS COM_DESTINO, MIN(" in sql or "AS ESGOTADAS" in sql: return "status"
    if "AS RETORNO" in sql or "AS UUID" in sql: return "pendentes"
    if "AS PROC_DIA" in sql: return "ultimas"
    if "FROM XX3010" in sql and "AS PRIMEIRA" in sql: return "abertas"
    if "FROM XXF" in sql: return "depara"
    if "FROM XXD" in sql: return "empresa"
    if "UNION ALL" in sql: return "cadastros"
    if "FROM XX1 X" in sql: return "agend"
    if "FROM XX2" in sql: return "empfil"
    if "FROM SCHDTSK" in sql: return "tarefas"
    if "FROM XX0" in sql: return "agents"
    raise AssertionError("bloco EAI inesperado: " + sql[:120])


def fake_post_eai(url, json=None, headers=None, auth=None, params=None, timeout=None, verify=None):
    CHAMADAS.append({"url": url, "sql": json["sql"], "token": headers.get("X-TSC-Token"),
                     "tipo": json["tipo"], "auth": auth, "limite": json["limite"]})
    sql = json["sql"]
    assert not sql.rstrip().endswith(";")
    assert "XX3_TRANS" not in sql and "XX3_URL" not in sql.replace("RTRIM(XX3_URL) > ' '", "")
    k = eai_chave(sql)
    return R(200, {"ok": True, "csv": EAI_CSV[k], "linhas": EAI_CSV[k].count("\n") - 1,
                   "truncado": False, "environment": "producao"})


m.requests.post = fake_post_eai
CHAMADAS.clear()
CFG["cfg"] = dict(BASE_CFG, customer="000348D0", integ_grupos=["eai"], integ_desde=None,
                  environment="producao", senha_enc=m._cifra("s3nha", aad_dg),
                  token_enc=m._cifra("tok123", aad_dg))
DB["medicoes"].clear()
r = cli.post("/api/integracoes/000348D0/coletar?ambiente=producao")
d = r.get_json()
q_eai = [c for c in CHAMADAS if "/query" in c["url"]]
confere("eai: coleta 200", r.status_code == 200 and d["ok"])
confere("eai: sem healthcheck da Quírons", not any("healthcheck" in c["url"] for c in CHAMADAS))
confere("eai: 13 consultas (uma por bloco)", len(q_eai) == 13)
confere("eai: nenhuma consulta de outro grupo",
        not any(t in c["sql"] for c in q_eai for t in ("RJP010", "CKOCOL", "ZA3010")))
ult = d["ultima"]
inds = {i["chave"]: i for i in ult["indicadores"]}
confere("eai: só indicadores do grupo", set(i["grupo"] for i in ult["indicadores"]) == {"eai"})
confere("eai: 832 entregues sem retorno = vermelho", inds["eai_sem_retorno"]["valor"] == 832
        and inds["eai_sem_retorno"]["nivel"] == "vermelho")
confere("eai: 6 falhas esgotadas = vermelho", inds["eai_falhas"]["valor"] == 6 and inds["eai_falhas"]["nivel"] == "vermelho")
confere("eai: SELLER no canal ESB", inds["eai_canal"]["valor"] == 6)
confere("eai: XXF vazia = vermelho", inds["eai_depara"]["nivel"] == "vermelho")
confere("eai: tabela de preço sem envio", "PRICELISTHEADERITEM" in inds["eai_cobertura"]["texto"])
confere("eai: FWEAIRECE nunca executou", inds["eai_jobs"]["nivel"] == "vermelho"
        and "FWEAIRECE agendado (000003) e nunca executou" in inds["eai_jobs"]["texto"])
confere("eai: 2 agendamentos parados", inds["eai_agendamentos"]["valor"] == 2)
confere("eai: recorrência lida", ult["blocos"]["eai_agendamentos"]["linhas"][2]["RECORR"] == "Smart A")
confere("eai: grupos gravados na coleta", ult["blocos"]["_meta"]["grupos"] == ["eai"])
pt = {t["TIPO"]: t for t in ult["blocos"]["eai_por_tipo"]["linhas"]}
confere("eai: por tipo gravado na coleta", len(pt) == 10 and pt["clientes"]["ENTREGUES"] == 821
        and pt["tabelas"]["NIVEL"] == "vermelho" and pt["vendedores"]["FALHAS"] == 6)
confere("eai: payload sem segredo", "tok123" not in r.get_data(as_text=True))
d = cli.get("/api/integracoes/000348D0/scripts?ambiente=producao").get_json()
confere("eai: scripts do grupo", d["grupos"] == ["eai"] and len(d["scripts"]) == 13
        and all(s["id"].startswith("eai_") for s in d["scripts"]))
m.execute = exec_grupos
r = cli.post("/api/integracoes/000348D0/grupos?ambiente=producao", json={"grupos": ["eai", "crm"]})
confere("eai: grupo aceito na rota", r.status_code == 200 and r.get_json()["grupos"] == ["crm", "eai"])
m.execute = _exec_orig
m.requests.post = fake_post

print(f"{ok} asserções OK, {falhou} falha(s)")
raise SystemExit(1 if falhou else 0)
