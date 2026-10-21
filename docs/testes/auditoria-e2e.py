"""Aba Auditoria de Tabelas — teste de ponta a ponta, sem a base do cliente.

Sobe o Flask de verdade (api/index.py) contra um Postgres LOCAL e um stub do
TSCMONITREST que responde ao /query com CSV de duas bases plantadas:

  Teste    : F22 E C C (o caso do fornecedor da Cresol), CIN/F27 E E E, F0V com
             zero, CK3 ausente, F2D estrutural E E E, SA2 C C C
  Produção : F22 C C C, F27 E E C, F2D C C C (estrutural divergente)

O stub também aplica um porte da trava do SqlSeguro (só SELECT/WITH, sem ';',
sem DML): a regra que recusa o script mora na base, e descobrir depois do
deploy sai caro.

Uso:  DATABASE_URL=postgresql://postgres@/postgres?host=/tmp&port=5433 \
      python3 docs/testes/auditoria-e2e.py
Imprime o JSON do GET final em /home/claude/w/aud.json (insumo do teste de tela).
"""
import base64, http.server, json, os, re, sys, threading

os.environ.setdefault("PROTHEUS_CRED_KEY", base64.b64encode(b"k" * 32).decode())
os.environ.setdefault("SESSION_SECRET", "teste-auditoria")
sys.path.insert(0, "api")
import psycopg2  # noqa: E402

DDL = """
drop schema if exists cockpit cascade; create schema cockpit;
create extension if not exists pgcrypto;
create table cockpit.clientes (customer text primary key, nome text, tipo text);
create table cockpit.usuarios_login (email text primary key, senha_hash text, nome text,
  ativo boolean default true, is_admin boolean default false, perfil text);
create table cockpit.usuario_clientes (email text, customer text, abas text[], papel text);
create table cockpit.protheus_ambientes (customer text, ambiente text, url_rest text, environment text,
  empresa text default '01', filial text default '01', usuario text, senha_enc text, token_enc text,
  banco text, sufixo text, timeout_s integer default 45, limite_linhas integer default 50000,
  ativo boolean default true, ssl_verificar boolean, primary key (customer, ambiente));
create table cockpit.protheus_coletas (id bigint generated always as identity primary key,
  customer text, ambiente text, tipo text, iniciado_em timestamptz, duracao_ms integer, ok boolean,
  http_status integer, linhas integer, medicoes integer, itens integer, bytes integer,
  data_medicao date, erro text, disparado_por text);
create table cockpit.estrut_tabelas (id uuid primary key default gen_random_uuid(), customer text,
  modulo text, tabela text, descricao text, tipo text default 'cadastro', compart text, sugestao text,
  origem text default 'manual', observacao text, ativo boolean default true, definido_por text,
  definido_em timestamptz, created_at timestamptz default now(), comparar boolean);
create table cockpit.estrut_propostas (id uuid primary key default gen_random_uuid(), tabela_id uuid,
  customer text, tabela text, compart text, compart_na_hora text, motivo text, autor text,
  criado_em timestamptz default now(), status text default 'aberta');
create table cockpit.estrut_config (customer text primary key, leiaute text, tam_empresa smallint,
  tam_unidade smallint, tam_filial smallint);
create table cockpit.monitemp_sm0 (customer text, ambiente text, empresa text, filial text, leiaute text);
create table cockpit.estrut_regras (id bigserial primary key, tipo text, tab_a text, tab_b text,
  motivo text, fonte text, unique (tipo, tab_a, tab_b));
"""

# ── as duas bases plantadas ─────────────────────────────────────────────────
BASES = {
    "teste": {
        "sx2": {"F20": "CCC", "F22": "ECC", "F27": "EEE", "CIN": "EEE", "F0V": "EEE",
                "F2D": "EEE", "SA2": "CCC", "SA1": "CCC", "SB1": "CCC"},
        "fisicas": {"F20", "F22", "F27", "CIN", "F0V", "F2D", "SA2", "SA1"},   # SB1 sem tabela física
        "dados": {"F22": [("01", 40)], "F27": [("01260001", 12), ("01010001", 3)],
                  "CIN": [("01260001", 5)], "F0V": [("01260001", 2)], "SA2": [("", 3200)],
                  "F20": [("", 6)], "F2D": [("01260001", 900)]},
    },
    "producao": {
        "sx2": {"F20": "CCC", "F22": "CCC", "F27": "EEC", "CIN": "EEC", "F2D": "CCC",
                "SA2": "CCC", "SA1": "CCC", "SB1": "CCC"},
        "fisicas": {"F20", "F22", "F27", "CIN", "F2D", "SA2", "SA1", "SB1"},
        "dados": {"F22": [("", 52)], "F27": [("0126", 30), ("0101", 20), ("01", 4)],
                  "CIN": [("0126", 9)], "SA2": [("", 4100)], "F2D": [("", 15000)]},
    },
}
# Dicionário plantado: A2_NOME com tamanho diferente, F22_XCUSTOM só em Teste,
# F27_DESC só em Produção; MV_ESTADO igual, MV_CFGTRIB com conteúdo diferente,
# MV_SOTESTE só em Teste, MV_FILX com X6_FIL diferente, conteúdo com vírgula,
# aspas e ponto: nada disso pode quebrar o CSV.
X3 = {
    "teste": [("SA2", "A2_NOME", "C", 40, 0), ("SA2", "A2_COD", "C", 6, 0), ("F22", "F22_CLIFOR", "C", 6, 0),
              ("F22", "F22_XCUSTOM", "C", 10, 0), ("F27", "F27_VALOR", "N", 14, 2)],
    "producao": [("SA2", "A2_NOME", "C", 60, 0), ("SA2", "A2_COD", "C", 6, 0), ("F22", "F22_CLIFOR", "C", 6, 0),
                 ("F27", "F27_VALOR", "N", 14, 2), ("F27", "F27_DESC", "C", 30, 0)],
}
X6 = {
    "teste": [("MV_ESTADO", "", "C", "SC"), ("MV_CFGTRIB", "", "L", ".T."), ("MV_SOTESTE", "", "C", "x"),
              ("MV_FILX", "01260001", "C", "1"), ("MV_LISTA", "", "C", 'A,B "C". D')],
    "producao": [("MV_ESTADO", "", "C", "SC"), ("MV_CFGTRIB", "", "L", ".F."),
                 ("MV_FILX", "", "C", "1"), ("MV_LISTA", "", "C", 'A,B "C". D')],
}
VISTOS = []
# Mesma lista do aProib do TSCMONITREST.tlpp (SqlSeguro), palavra inteira.
PROIBIDAS = (r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXECUTE|EXEC|CALL|"
             r"COMMIT|ROLLBACK|INTO|OPENROWSET|OPENQUERY|BULK)\b|\bDBMS_|\bUTL_|\bXP_|\bSP_")


def sql_seguro(sql):
    s = re.sub(r"'[^']*'", "''", re.sub(r"--[^\n]*", "", sql)).strip()
    if not re.match(r"(?i)^(SELECT|WITH)\b", s):
        return "precisa comecar com SELECT ou WITH"
    if ";" in s:
        return "segundo comando"
    if re.search(PROIBIDAS, s.upper()):
        return "Comando nao permitido"
    return None


class Stub(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        amb = "teste" if self.server.server_port == 5301 else "producao"
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sql = corpo["sql"]
        VISTOS.append((amb, sql))
        erro = sql_seguro(sql)
        if erro or corpo.get("token") != "tok-" + amb or self.headers.get("X-TSC-Token") != "tok-" + amb:
            return self._r(400, {"ok": False, "erro": erro or "token"})
        b = BASES[amb]
        if "FROM SX3" in sql:
            pedidas = set(re.findall(r"'([A-Z0-9]{3})'", sql.split("IN (")[1]))
            linhas = ["ARQ;CAMPO;TIPO;TAM;DECIMAIS;TITULO;CONTEXTO"]
            linhas += [f"{t};{c};{tp};{tm};{dc};Titulo {c};R" for t, c, tp, tm, dc in X3[amb] if t in pedidas]
            return self._r(200, {"ok": True, "csv": "\n".join(linhas)})
        if "FROM SX6" in sql:
            if os.environ.get("AUD_X6_FALHA") == amb:
                return self._r(200, {"ok": True, "truncado": True, "csv": "PARAM"})
            linhas = ["PARAM;FIL;TIPO;CONTEUDO;DESCR"]
            # a REST troca ';' e quebra de linha por espaço; aspas o SQL já tirou
            linhas += [f"{p};{f};{t};{c.replace(chr(34), ' ')};Desc {p}" for p, f, t, c in X6[amb]]
            return self._r(200, {"ok": True, "csv": "\n".join(linhas)})
        if "FROM SX2" in sql:
            pedidas = re.findall(r"'([A-Z0-9]{3})'", sql.split("IN (")[1])
            linhas = ["CHAVE;NOME;ARQ;MODOEMP;MODOUN;MODO;EXISTE;TEMFIL"]
            for a in pedidas:
                if a in b["sx2"]:
                    m = b["sx2"][a]
                    ex = 1 if a in b["fisicas"] else 0
                    linhas.append(f"{a};Tabela {a};{a}010;{m[0]};{m[1]};{m[2]};{ex};{ex}")
            return self._r(200, {"ok": True, "environment": f"P12{amb.upper()}", "csv": "\n".join(linhas)})
        linhas = ["TABELA;FILIAL;QTD"]
        for a in re.findall(r"SELECT '([A-Z0-9]{3})' AS TABELA", sql):
            assert f"FROM {a}010" in sql, a
            for fil, n in b["dados"].get(a, []):
                linhas.append(f"{a};{fil.ljust(8) if fil else ' '};{n}")
        return self._r(200, {"ok": True, "csv": "\n".join(linhas)})

    def _r(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)


for porta in (5301, 5302):
    srv = http.server.HTTPServer(("127.0.0.1", porta), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

con = psycopg2.connect(os.environ["DATABASE_URL"])
con.autocommit = True
cur = con.cursor()
cur.execute(DDL)
mig = open("docs/sql/2026-10-21-auditoria-tabelas.sql", encoding="utf-8").read()
cur.execute(mig)
cur.execute(open("docs/sql/2026-10-21-auditoria-dicionario.sql", encoding="utf-8").read())

import index as app_mod  # noqa: E402

C = "TFCTQI00"
cur.execute("insert into cockpit.clientes values (%s,'CRESOL','novo')", (C,))
cur.execute("insert into cockpit.usuarios_login (email,nome,is_admin,perfil) values "
            "('reges.werlang@totvs.com.br','Reges',true,'admin')")
for t, m, obs in [("F20", "CCC", None), ("F22", "CCC", None), ("F27", "EEC", None),
                  ("CIN", "EEC", None), ("CK3", "CCC", "De/Para: fica C C C"), ("FOV", "EEC", None),
                  ("CI6", None, "Fora do TXT")]:
    cur.execute("insert into cockpit.estrut_tabelas (customer,modulo,tabela,descricao,compart,observacao) "
                "values (%s,'Configurador de Tributos',%s,%s,%s,%s)", (C, t, "Desc " + t, m, obs))
cur.execute("insert into cockpit.estrut_propostas (tabela_id,customer,tabela,compart,compart_na_hora,motivo,autor) "
            "select id, customer, tabela, 'EEC', compart, 'CJ2 e CK3 no mesmo nível', 'reges' "
            "from cockpit.estrut_tabelas where tabela='CK3'")
for amb, porta in (("teste", 5301), ("producao", 5302)):
    cur.execute("insert into cockpit.protheus_ambientes (customer,ambiente,url_rest,banco,sufixo,token_enc) "
                "values (%s,%s,%s,'oracle','010',%s)",
                (C, amb, f"http://127.0.0.1:{porta}/api/tscmonit",
                 app_mod._cifra("tok-" + amb, app_mod._aad(C, amb))))

cli = app_mod.app.test_client()
cli.set_cookie(app_mod.COOKIE_NAME, app_mod.make_session("reges.werlang@totvs.com.br", "Reges"))

falhas = []
def confere(cond, msg):
    if not cond:
        falhas.append(msg)

r = cli.get(f"/api/auditoria/{C}")
confere(r.status_code == 200, f"GET inicial {r.status_code}")
j = r.get_json()
confere(j["coletas"]["teste"] is None and j["coletas"]["producao"] is None, "sem coleta no começo")
confere([e["tabela"] for e in j["escopo"] if e["papel"] == "escopo"] == ["CI6", "F20", "F22", "CIN", "CK3", "F27", "FOV"], "escopo")
confere(j["propostas"].get("CK3"), "proposta CK3")

for amb in ("teste", "producao"):
    r = cli.post(f"/api/auditoria/{C}/coletar?ambiente={amb}")
    confere(r.status_code == 200, f"coletar {amb}: {r.status_code} {r.get_data(as_text=True)[:200]}")

j = cli.get(f"/api/auditoria/{C}").get_json()
t, p = j["coletas"]["teste"], j["coletas"]["producao"]
confere(t["tabelas"]["F22"]["sx2"] == "ECC" and p["tabelas"]["F22"]["sx2"] == "CCC", "F22 nas duas bases")
confere("F0V" in t["tabelas"] and "FOV" not in t["tabelas"], "variante com zero")
confere(t["tabelas"]["SB1"]["existe"] is False, "SB1 sem tabela física em Teste")
confere(t["tabelas"]["F22"]["filiais"] == [{"filial": "01", "qtd": 40}], "filial com espaço vira código limpo")
confere(t["fora_padrao"] if "fora_padrao" in t else True, "")
# fora do padrão do ALVO: Teste F22 '01' (alvo CCC) 40 + F27 8 dígitos (alvo EEC) 15
# + CIN 5 + F0V 2 = 62; Produção F27 '01' 4
cur.execute("select ambiente, fora_padrao, total_registros, tabelas_lidas from cockpit.audtab_coletas order by id")
res = {a: (int(f), int(tt), n) for a, f, tt, n in cur.fetchall()}
confere(res["teste"][0] == 62, f"fora_padrao teste {res['teste']}")
confere(res["producao"][0] == 4, f"fora_padrao producao {res['producao']}")
cur.execute("select tipo, ok from cockpit.protheus_coletas")
confere(cur.fetchall() == [("auditoria", True), ("auditoria", True)], "log de coleta")
confere(all(sql_seguro(s) is None for _, s in VISTOS) and len(VISTOS) == 8, f"8 SQLs, todos seguros ({len(VISTOS)})")

# ── dicionário entre as bases ──────────────────────────────────────────────
dic = j["dicionario"]
x3 = {(r["tabela"], r["campo"]): r["situacao"] for r in dic["x3"]["divergentes"]}
confere(x3 == {("SA2", "A2_NOME"): "formato", ("F22", "F22_XCUSTOM"): "so_teste",
               ("F27", "F27_DESC"): "so_producao"}, f"SX3 divergências {x3}")
x6 = {r["param"]: r["situacao"] for r in dic["x6"]["divergentes"]}
confere(x6 == {"MV_CFGTRIB": "conteudo", "MV_SOTESTE": "so_teste", "MV_FILX": "filial"}, f"SX6 divergências {x6}")
confere(dic["x6"]["total"] == 5, "SX6 total de parâmetros")

# SX6 que estoura o limite NÃO derruba a coleta: grava SX2/volume e avisa.
os.environ["AUD_X6_FALHA"] = "teste"
r = cli.post(f"/api/auditoria/{C}/coletar?ambiente=teste")
confere(r.status_code == 200, f"coleta com SX6 truncado {r.status_code}")
jt = r.get_json()
confere(jt["coletas"]["teste"]["x6_ok"] is False and "SX6" in (jt["coletas"]["teste"]["erro_dic"] or ""), "erro_dic do SX6")
confere(jt["dicionario"]["x6"] is None and jt["dicionario"]["x3"] is not None, "SX6 sem comparação, SX3 segue")
os.environ.pop("AUD_X6_FALHA")
# retenção: depois de 5 coletas de Teste, só 3 guardam o dicionário
for _ in range(3):
    cli.post(f"/api/auditoria/{C}/coletar?ambiente=teste")
cur.execute("""select count(distinct s.coleta_id) from cockpit.audtab_sx3 s
                 join cockpit.audtab_coletas c on c.id = s.coleta_id where c.ambiente='teste'""")
confere(cur.fetchone()[0] == 3, "retenção do dicionário em 3 coletas")
j = cli.get(f"/api/auditoria/{C}").get_json()

# base sem REST cadastrada → 404 legível, nada gravado
cur.execute("delete from cockpit.protheus_ambientes where ambiente='producao'")
r = cli.post(f"/api/auditoria/{C}/coletar?ambiente=producao")
confere(r.status_code == 404 and "Ambiente" in r.get_json()["error"], "sem ambiente")

open("/home/claude/w/aud.json", "w").write(json.dumps(j, default=str, ensure_ascii=False))

# ── Base SEM REST: scripts para o console + upload do CSV ──────────────────
# A base de Testes da Cresol não tem TSCMONITREST. O fluxo manual tem de chegar
# no MESMO resultado da coleta pela REST.
cur.execute("delete from cockpit.protheus_ambientes where ambiente='teste'")
r = cli.get(f"/api/auditoria/{C}/scripts?ambiente=teste&banco=oracle&sufixo=010")
confere(r.status_code == 200, f"scripts sem ambiente {r.status_code}")
sc = {x["id"]: x for x in r.get_json()["scripts"]}
confere(all(sc[k]["sql"] for k in ("sx2", "sx3", "sx6")), "scripts 1, 3 e 4 prontos")
# a última coleta de Teste (REST) existe, então o 2 já sai montado dela
confere(sc["contagem"]["sql"] and "FROM F22010" in sc["contagem"]["sql"], "script 2 a partir da última coleta")
for k, v in sc.items():
    if v["sql"]:
        corpo_sql = "\n".join(l for l in v["sql"].splitlines() if not l.startswith("--"))
        confere(sql_seguro(corpo_sql) is None and not v["sql"].rstrip().endswith(";"), f"script {k} seguro e sem ';'")
        confere(all(ord(ch) < 128 for ch in v["sql"]), f"script {k} em ASCII")

# SQL Server: SX2 em Latin1_General_BIN × catálogo na collation do banco dava
# erro 468 na base de Testes da Cresol. Os dois lados levam COLLATE.
scm = {x["id"]: x for x in cli.get(f"/api/auditoria/{C}/scripts?ambiente=teste&banco=mssql").get_json()["scripts"]}
confere(scm["sx2"]["sql"].count("COLLATE DATABASE_DEFAULT") == 4 and "SYS_CONTEXT" not in scm["sx2"]["sql"],
        "script 1 SQL Server com COLLATE e sem função de Oracle")

# Simula o console: CSV com VÍRGULA, cabeçalho entre aspas e BOM — o que o
# SQL Developer e o export do TCloud costumam gerar.
def csv_virgula(cab, linhas):
    q_ = lambda v: '"' + str(v).replace('"', '""') + '"'
    return "\ufeff" + ",".join(q_(c) for c in cab) + "\n" + "\n".join(",".join(q_(v) for v in l) for l in linhas)

b = BASES["teste"]
sx2_csv = csv_virgula(["CHAVE", "NOME", "ARQ", "MODOEMP", "MODOUN", "MODO", "EXISTE", "TEMFIL"],
                      [[a, "Tabela " + a, a + "010", m[0], m[1], m[2], int(a in b["fisicas"]), int(a in b["fisicas"])]
                       for a, m in b["sx2"].items()])
x3_csv = csv_virgula(["ARQ", "CAMPO", "TIPO", "TAM", "DECIMAIS", "TITULO", "CONTEXTO"],
                     [[t, c, tp, tm, dc, "Titulo " + c, "R"] for t, c, tp, tm, dc in X3["teste"]])
x6_csv = csv_virgula(["PARAM", "FIL", "TIPO", "CONTEUDO", "DESCR"],
                     [[p_, f, t, c, "Desc " + p_] for p_, f, t, c in X6["teste"]])
r = cli.post(f"/api/auditoria/{C}/upload?ambiente=teste",
             json={"arquivos": [{"nome": "s1.csv", "texto": sx2_csv}, {"nome": "s3.csv", "texto": x3_csv},
                                {"nome": "s4.csv", "texto": x6_csv}, {"nome": "lixo.csv", "texto": "A,B\n1,2"}]})
confere(r.status_code == 200, f"upload passo 1 {r.status_code} {r.get_data(as_text=True)[:200]}")
ju = r.get_json()
confere(ju["upload"]["falta_contagem"] and not ju["upload"]["completou"], "passo 1 avisa que falta o Script 2")
confere(ju["upload"]["ignorados"] == ["lixo.csv"], "arquivo sem cabeçalho conhecido é ignorado")
ct = ju["coletas"]["teste"]
confere(ct["origem"] == "upload" and ct["x3_ok"] and ct["x6_ok"], "coleta de upload com dicionário")
confere(ct["tabelas"]["F22"]["sx2"] == "ECC" and ct["tabelas"]["F22"]["filiais"] == [], "SX2 sem contagem ainda")
x6u = {x["param"]: x["situacao"] for x in ju["dicionario"]["x6"]["divergentes"]}
confere(x6u.get("MV_CFGTRIB") == "conteudo" and "MV_LISTA" not in x6u, f"SX6 por upload (vírgula/aspas) {x6u}")

# passo 2: o script 2 agora sai da coleta de upload
sc2 = {x["id"]: x for x in cli.get(f"/api/auditoria/{C}/scripts?ambiente=teste").get_json()["scripts"]}
confere("FROM F0V010" in sc2["contagem"]["sql"] and "FROM SB1010" not in sc2["contagem"]["sql"],
        "script 2 só com tabela que existe")
cont_csv = "TABELA;FILIAL;QTD\n" + "\n".join(f"{a};{f};{n}" for a, fs in b["dados"].items() for f, n in fs) + "\nZZZ;01;5"
r = cli.post(f"/api/auditoria/{C}/upload?ambiente=teste", json={"arquivos": [{"nome": "s2.csv", "texto": cont_csv}]})
confere(r.status_code == 200, f"upload passo 2 {r.status_code} {r.get_data(as_text=True)[:200]}")
ju2 = r.get_json()
confere(ju2["upload"]["completou"] and ju2["upload"]["estranhas"] == ["ZZZ"], "passo 2 completa e descarta tabela estranha")
ct2 = ju2["coletas"]["teste"]
confere(ct2["tabelas"]["F22"]["filiais"] == [{"filial": "01", "qtd": 40}], "contagem chegou")
confere(ct2["x3_ok"] and ct2["x6_ok"], "passo 2 preserva o dicionário do passo 1")
cur.execute("select fora_padrao from cockpit.audtab_coletas where id=%s", (ct2["id"],))
confere(int(cur.fetchone()[0]) == 62, "upload chega no MESMO fora_padrao da REST (62)")
cur.execute("select count(*) from cockpit.audtab_coletas where customer=%s and ambiente='teste' and origem='upload'", (C,))
confere(cur.fetchone()[0] == 1, "passo 2 substitui a coleta do passo 1 (não duplica)")

# passo 2 sem passo 1 → recusa
cur.execute("delete from cockpit.audtab_coletas where ambiente='producao'")
r = cli.post(f"/api/auditoria/{C}/upload?ambiente=producao", json={"arquivos": [{"nome": "s2.csv", "texto": cont_csv}]})
confere(r.status_code == 409 and "Script 1" in r.get_json()["error"], "Script 2 sem Script 1 é recusado")
print("FALHAS (com upload):", falhas or "nenhuma")
print("SQL passo 1 (teste):\n", VISTOS[0][1][:400], "...\n")
print("SQL passo 2 (teste):\n", VISTOS[1][1][:400], "...\n")
print("coletas:", res)
print("FALHAS:", falhas or "nenhuma")
sys.exit(1 if falhas else 0)
