#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Projetos · TOTVS SC — backend serverless (Vercel)
=================================================
Porte do Projetos/server.py + pci_client.py para função serverless.

- Lista de projetos: lida de cockpit.projetos (Supabase), sincronizada sob
  demanda pelo botão "Atualizar" (POST /api/sync?page=N, paginado pelo front
  para não estourar o timeout de 60s).
- Detalhe (mapa/cronograma): AO VIVO na API PCI, com cache curto em memória.
- Login e recorte por cliente: mesmos do ecossistema (cockpit.usuarios_login +
  cockpit.usuario_clientes). Admin vê todos os clientes.
"""
from __future__ import annotations

import base64, csv, email.message, hashlib, hmac, imaplib, io, json, os, re, time, \
    unicodedata, urllib.parse
from pathlib import Path

import psycopg2, psycopg2.extras, requests
from psycopg2.extras import execute_values
from flask import Flask, Response, request, redirect, make_response
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"          # NÃO usar "public/": a Vercel serviria estático
                                    # antes da função e furaria a porta de login.

DATABASE_URL = os.environ.get("DATABASE_URL", "")
TASKS_BASE = os.environ.get("TASKS_SC_BASE_URL", "https://api.tscst.com.br/restAPI").rstrip("/")
TASKS_USER = os.environ.get("TASKS_USERNAME", "")
TASKS_PASS = os.environ.get("TASKS_PASSWORD", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-insecure-secret")
CRON_SECRET = os.environ.get("CRON_SECRET", "")
SESSION_TTL = 12 * 3600
COOKIE_NAME = "proj_sess"

LISTA_URL = f"{TASKS_BASE}/custom/tscst/pci/api/v1/projetos"
MAPA_URL = f"{TASKS_BASE}/PCITConectaProjetos/mapa"
CRONO_URL = f"{TASKS_BASE}/PCITConectaProjetos/cronograma"

app = Flask(__name__)

# ── Roteamento na Vercel — o contrato "?__path=" ────────────────────────────
# Com `destination: "/api/index"` (seco), a Vercel entrega à função o caminho de
# DESTINO: o Flask recebe PATH_INFO=/api/index em TODA request, nenhuma rota casa
# e tudo cai no catch-all `/<path:asset>` → 404 "Rota de API desconhecida." (o
# site inteiro morre, inclusive `/` e `/api/health`). O `vercel.json` passa o
# caminho original em `?__path=/$1` e este middleware o devolve ao PATH_INFO.
# Os dois andam em par: mexeu no destination, mexa aqui.
FUNC_PATHS = ("/api/index", "/api/index.py")


class _VercelRewritePath:
    """Devolve ao PATH_INFO o caminho original vindo em ?__path=.
    Inerte quando o PATH_INFO já chega certo (dev local ou se a Vercel voltar a
    preservar o caminho)."""

    def __init__(self, wsgi):
        self.wsgi = wsgi

    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO", "") in FUNC_PATHS:
            pares = urllib.parse.parse_qsl(environ.get("QUERY_STRING", ""),
                                           keep_blank_values=True)
            resto = [(k, v) for k, v in pares if k != "__path"]
            path = next((v for k, v in pares if k == "__path"), "") \
                or environ.get("HTTP_X_VERCEL_ORIGINAL_PATH", "")
            if path:
                if "?" in path:                      # query que veio no próprio $1
                    path, extra = path.split("?", 1)
                    resto += urllib.parse.parse_qsl(extra, keep_blank_values=True)
                environ["PATH_INFO"] = path if path.startswith("/") else "/" + path
                environ["QUERY_STRING"] = urllib.parse.urlencode(resto)
        return self.wsgi(environ, start_response)


app.wsgi_app = _VercelRewritePath(app.wsgi_app)


class PCIUnavailable(Exception):
    """API PCI indisponível (timeout/5xx persistente) — erro esperado."""


# ── util ────────────────────────────────────────────────────────────────────
def _json(o, code=200):
    return Response(json.dumps(o, ensure_ascii=False, default=str), status=code,
                    mimetype="application/json")


def _err(code, msg):
    return _json({"ok": False, "error": msg}, code)


def _slug(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


@app.errorhandler(Exception)
def _on_error(e):
    if isinstance(e, HTTPException):
        return e
    if isinstance(e, PCIUnavailable):
        return _json({"ok": False, "error": str(e), "api_indisponivel": True}, 503)
    return _json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)


# ── Postgres (Supabase) ─────────────────────────────────────────────────────
def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")
    c = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    c.autocommit = True
    return c


def q(sql, params=None, one=False):
    with db() as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        if cur.description is None:
            return None
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows


def execute(sql, params=None):
    with db() as c, c.cursor() as cur:
        cur.execute(sql, params or ())


# ── Sessão / login (mesmo padrão do ecossistema) ────────────────────────────
def _sign(p):
    return hmac.new(SESSION_SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()


def make_session(email, nome, view_as=None):
    d = {"e": email, "n": nome, "x": int(time.time()) + SESSION_TTL}
    if view_as:
        d["v"] = view_as          # admin simulando a visão de outro usuário
    raw = json.dumps(d)
    b = base64.urlsafe_b64encode(raw.encode()).decode()
    return f"{b}.{_sign(b)}"


def read_session():
    tok = request.cookies.get(COOKIE_NAME, "")
    if not tok or "." not in tok:
        return None
    b, sig = tok.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(b)):
        return None
    try:
        d = json.loads(base64.urlsafe_b64decode(b.encode()).decode())
    except Exception:
        return None
    return d if int(d.get("x", 0)) > time.time() else None


def current_user():
    """Usuário REAL do login (nunca o simulado). Use para auditoria/escrita."""
    s = read_session()
    return s.get("e") if s else None


def is_admin(email):
    if not email:
        return False
    r = q("select coalesce(is_admin,false) adm from cockpit.usuarios_login "
          "where lower(email)=%s", (email.lower(),), one=True)
    return bool(r and r["adm"])


def effective_user():
    """Usuário cuja VISÃO vale. É o simulado (view_as) somente se quem está
    logado for admin de verdade — a simulação jamais amplia acesso, só restringe."""
    s = read_session()
    if not s:
        return None
    alvo = s.get("v")
    if alvo and is_admin(s.get("e")):
        return alvo
    return s.get("e")


def require_auth():
    return None if current_user() else _err(401, "Não autenticado.")


def require_admin():
    if not current_user():
        return _err(401, "Não autenticado.")
    if not is_admin(current_user()):
        return _err(403, "Apenas administradores.")
    return None


def verify_scrypt(stored, senha):
    """scrypt$salt$hash. O Cockpit gera com Node scryptSync(pw, saltString, 64):
    o salt vai como STRING (o hex em UTF-8). Tentamos essa variante primeiro e,
    como fallback, o salt decodificado de hex (formato legado)."""
    try:
        scheme, salt_hex, hash_hex = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    dklen = len(hash_hex) // 2
    variants = [salt_hex.encode()]
    try:
        variants.append(bytes.fromhex(salt_hex))
    except ValueError:
        pass
    for salt in variants:
        for n in (16384, 32768, 8192, 65536):
            try:
                dk = hashlib.scrypt(senha.encode(), salt=salt, n=n, r=8, p=1,
                                    dklen=dklen, maxmem=132 * 1024 * 1024)
            except Exception:
                continue
            if hmac.compare_digest(dk.hex(), hash_hex):
                return True
    return False


# ── Acesso por cliente (admin vê tudo; comum só os liberados) ───────────────
def allowed_customers():
    email = effective_user()      # respeita o "ver como"
    if not email:
        return set()
    row = q("select coalesce(is_admin,false) adm from cockpit.usuarios_login "
            "where lower(email)=%s", (email.lower(),), one=True)
    if row and row["adm"]:
        return None
    rows = q("select customer from cockpit.usuario_clientes where lower(email)=%s",
             (email.lower(),))
    return {r["customer"] for r in rows}


def deny_customer(cust):
    a = allowed_customers()
    return None if (a is None or cust in a) else _err(403, "Sem acesso a este cliente.")


# ── OAuth Tasks SC (a API PCI usa o mesmo) ──────────────────────────────────
_tok = {"t": None, "exp": 0}


def _token(force=False):
    now = time.time()
    if not force and _tok["t"] and _tok["exp"] - 120 > now:
        return _tok["t"]
    r = requests.post(f"{TASKS_BASE}/api/oauth2/v1/token",
                      data={"grant_type": "password", "username": TASKS_USER,
                            "password": TASKS_PASS},
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"OAuth falhou HTTP {r.status_code}: {r.text[:200]}")
    d = r.json()
    _tok["t"] = d["access_token"]
    _tok["exp"] = now + int(d.get("expires_in", 3600))
    return _tok["t"]


def pci_get(url, params):
    """GET na API PCI com retry (401/5xx) e o encoding mentiroso (cp1252)."""
    ultimo = None
    for i in range(3):
        try:
            r = requests.get(url, params=params, timeout=(8, 40),
                             headers={"Authorization": f"Bearer {_token(force=i >= 1)}",
                                      "Accept": "application/json"})
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout) as ex:
            ultimo = ex
            time.sleep(1.5 * (i + 1))
            continue
        if r.status_code == 401 and i < 2:
            continue
        # 500 incluído: a API da TOTVS devolve 500 em soluços transitórios.
        if r.status_code in (500, 502, 503, 504) and i < 2:
            ultimo = f"HTTP {r.status_code}"
            time.sleep(1.5 * (i + 1))
            continue
        r.raise_for_status()
        txt = r.content.decode("utf-8", errors="replace")
        if "�" not in txt:
            return json.loads(txt)
        try:
            return json.loads(r.content.decode("cp1252"))
        except Exception:
            return json.loads(txt)
    raise PCIUnavailable(f"API Totvs SC indisponível após 3 tentativas — {ultimo}. "
                         f"Instabilidade temporária; tente novamente em instantes.")


# ── Páginas ─────────────────────────────────────────────────────────────────
def serve(name, ctype="text/html; charset=utf-8"):
    f = WEB_DIR / name
    if not f.exists():
        return _err(404, f"{name} não encontrado.")
    return Response(f.read_bytes(), mimetype=ctype)


@app.get("/login")
def page_login():
    return serve("login.html")


@app.get("/")
def page_root():
    return serve("index.html") if current_user() else redirect("/login", 302)


@app.get("/index.html")
def page_index():
    return serve("index.html") if current_user() else redirect("/login", 302)


# ── Auth API ────────────────────────────────────────────────────────────────
@app.post("/api/login")
def api_login():
    b = request.get_json(silent=True) or {}
    email = (b.get("email") or "").strip().lower()
    senha = b.get("senha") or ""
    if not email or not senha:
        return _err(400, "Informe e-mail e senha.")
    row = q("select email, nome, senha_hash, ativo from cockpit.usuarios_login "
            "where lower(email)=%s", (email,), one=True)
    if not row or not row["ativo"]:
        return _err(401, "Usuário não autorizado.")
    if not verify_scrypt(row["senha_hash"], senha):
        return _err(401, "Credenciais inválidas.")
    resp = make_response(_json({"ok": True, "email": row["email"], "nome": row["nome"]}))
    resp.set_cookie(COOKIE_NAME, make_session(row["email"], row["nome"] or ""),
                    max_age=SESSION_TTL, httponly=True, secure=True, samesite="Lax", path="/")
    return resp


@app.post("/api/logout")
def api_logout():
    r = make_response(_json({"ok": True}))
    r.set_cookie(COOKIE_NAME, "", max_age=0, path="/")
    return r


@app.get("/api/me")
def api_me():
    s = read_session()
    if not s:
        return _err(401, "Não autenticado.")
    real = s["e"]
    adm = is_admin(real)
    alvo = s.get("v") if (s.get("v") and adm) else None
    return _json({"ok": True, "email": real, "nome": s.get("n"), "is_admin": adm,
                  "view_as": alvo, "efetivo": alvo or real})


@app.get("/api/usuarios")
def api_usuarios():
    """Lista de usuários para o seletor 'ver como' — só admin."""
    if (r := require_admin()):
        return r
    rows = q("""select u.email, u.nome, coalesce(u.is_admin,false) as is_admin, u.ativo,
                       (select count(*) from cockpit.usuario_clientes uc
                         where lower(uc.email)=lower(u.email)) as n_clientes
                from cockpit.usuarios_login u order by u.nome""")
    return _json({"ok": True, "usuarios": rows})


@app.post("/api/view-as")
def api_view_as():
    """Liga/desliga a simulação. Só admin. Body: {email} ou {email: null} p/ sair."""
    if (r := require_admin()):
        return r
    body = request.get_json(silent=True) or {}
    alvo = (body.get("email") or "").strip().lower() or None
    if alvo:
        u = q("select email from cockpit.usuarios_login where lower(email)=%s",
              (alvo,), one=True)
        if not u:
            return _err(404, "Usuário não encontrado.")
        alvo = u["email"]
    s = read_session()
    resp = make_response(_json({"ok": True, "view_as": alvo}))
    resp.set_cookie(COOKIE_NAME, make_session(s["e"], s.get("n"), view_as=alvo),
                    max_age=SESSION_TTL, httponly=True, secure=True,
                    samesite="Lax", path="/")
    return resp


@app.get("/api/health")
def api_health():
    info = {"ok": True, "service": "projetos-vercel",
            "env": {"DATABASE_URL": bool(DATABASE_URL), "TASKS_USERNAME": bool(TASKS_USER),
                    "TASKS_PASSWORD": bool(TASKS_PASS), "SESSION_SECRET": SESSION_SECRET != "dev-insecure-secret"},
            "db": False}
    try:
        r = q("select 1 ok", one=True)
        info["db"] = bool(r and r.get("ok") == 1)
        c = q("select count(*) n, max(synced_at) s from cockpit.projetos", one=True)
        info["projetos"] = c["n"]
        info["ultimo_sync"] = c["s"]
    except Exception as e:
        info["ok"] = False
        info["db_error"] = f"{type(e).__name__}: {e}"
    return _json(info)


# ── Dados ───────────────────────────────────────────────────────────────────
@app.get("/api/clientes")
def api_clientes():
    if (r := require_auth()):
        return r
    allowed = allowed_customers()
    rows = q("select customer, nome from cockpit.clientes order by nome")
    out = [{"codigo": r["customer"], "nome": r["nome"], "chave": _slug(r["nome"])}
           for r in rows if allowed is None or r["customer"] in allowed]
    return _json({"ok": True, "clientes": out})


@app.get("/api/projetos")
def api_projetos():
    """Lista da tabela sincronizada, já recortada pelos clientes liberados."""
    if (r := require_auth()):
        return r
    allowed = allowed_customers()
    rows = q("select * from cockpit.projetos order by nome_cliente_projeto, codigo_projeto")
    nomes = {r["customer"]: r["nome"] for r in q("select customer, nome from cockpit.clientes")}
    projetos, sync = [], None
    for r in rows:
        cli = r["codigo_cliente_projeto"]
        if allowed is not None and cli not in allowed:
            continue
        sync = sync or r["synced_at"]
        p = dict(r.get("raw") or {})
        p.update({
            "codigo_projeto": r["codigo_projeto"],
            "codigo_cliente_projeto": cli,
            "nome_cliente_projeto": r["nome_cliente_projeto"],
            "descricao_projeto": r["descricao_projeto"],
            "nome_coordenador_projeto": r["nome_coordenador_projeto"],
            "status_projeto": r["status_projeto"],
            "tipo_projeto": r["tipo_projeto"],
            "versao_projeto": r["versao_projeto"],
            "_nome_cliente_local": nomes.get(cli) or r["nome_cliente_projeto"],
        })
        projetos.append(p)
    return _json({"ok": True, "total": len(projetos), "projetos": projetos,
                  "sincronizado_em": sync})


@app.post("/api/sync")
def api_sync():
    """Sincroniza UMA página da API PCI para cockpit.projetos.
    O front chama page=1,2,3… enquanto hasNext for true (evita timeout)."""
    if (r := require_auth()):
        return r
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de sincronizar.")
    page = int(request.args.get("page", 1))
    size = int(request.args.get("pageSize", 200))
    data = pci_get(LISTA_URL, {"page": page, "pageSize": size})
    if not isinstance(data, dict):
        return _err(502, "Resposta inesperada da API PCI.")
    items = data.get("items") or []
    for p in items:
        cod = p.get("codigo_projeto")
        if not cod:
            continue
        execute("""
            insert into cockpit.projetos (codigo_projeto, codigo_cliente_projeto,
              nome_cliente_projeto, descricao_projeto, nome_coordenador_projeto,
              status_projeto, tipo_projeto, versao_projeto, raw, synced_at)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
            on conflict (codigo_projeto) do update set
              codigo_cliente_projeto=excluded.codigo_cliente_projeto,
              nome_cliente_projeto=excluded.nome_cliente_projeto,
              descricao_projeto=excluded.descricao_projeto,
              nome_coordenador_projeto=excluded.nome_coordenador_projeto,
              status_projeto=excluded.status_projeto,
              tipo_projeto=excluded.tipo_projeto,
              versao_projeto=excluded.versao_projeto,
              raw=excluded.raw, synced_at=now()
        """, (cod, p.get("codigo_cliente_projeto"), p.get("nome_cliente_projeto"),
              p.get("descricao_projeto"), p.get("nome_coordenador_projeto"),
              p.get("status_projeto"), p.get("tipo_projeto"), p.get("versao_projeto"),
              json.dumps(p)))
    return _json({"ok": True, "page": page, "gravados": len(items),
                  "hasNext": bool(data.get("hasNext"))})


# ── Sync completo para o CRON (pg_cron + pg_net) ────────────────────────────
def _upsert_projetos(items):
    """Upsert em LOTE (execute_values) — muito mais rápido que 1 insert por linha,
    o que é o que permite sincronizar as ~9 páginas dentro dos 60s da função."""
    rows = [(p.get("codigo_projeto"), p.get("codigo_cliente_projeto"),
             p.get("nome_cliente_projeto"), p.get("descricao_projeto"),
             p.get("nome_coordenador_projeto"), p.get("status_projeto"),
             p.get("tipo_projeto"), p.get("versao_projeto"), json.dumps(p))
            for p in items if p.get("codigo_projeto")]
    if not rows:
        return 0
    with db() as c, c.cursor() as cur:
        execute_values(cur, """
            insert into cockpit.projetos (codigo_projeto, codigo_cliente_projeto,
              nome_cliente_projeto, descricao_projeto, nome_coordenador_projeto,
              status_projeto, tipo_projeto, versao_projeto, raw, synced_at)
            values %s
            on conflict (codigo_projeto) do update set
              codigo_cliente_projeto=excluded.codigo_cliente_projeto,
              nome_cliente_projeto=excluded.nome_cliente_projeto,
              descricao_projeto=excluded.descricao_projeto,
              nome_coordenador_projeto=excluded.nome_coordenador_projeto,
              status_projeto=excluded.status_projeto,
              tipo_projeto=excluded.tipo_projeto,
              versao_projeto=excluded.versao_projeto,
              raw=excluded.raw, synced_at=now()
        """, rows, template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", page_size=200)
    return len(rows)


def _cron_autorizado():
    """O cron não tem sessão: autentica por Authorization: Bearer <CRON_SECRET>.
    Aceita também ?secret= para facilitar teste manual."""
    if not CRON_SECRET:
        return False
    auth = request.headers.get("Authorization", "")
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    return hmac.compare_digest(tok or request.args.get("secret", ""), CRON_SECRET)


@app.route("/api/cron/sync", methods=["GET", "POST"])
def api_cron_sync():
    """Sincroniza TODAS as páginas da API PCI numa tacada. Disparado de hora em
    hora pelo pg_cron do Supabase (via pg_net). Não exige login — exige o Bearer."""
    if not _cron_autorizado():
        return _err(401, "CRON_SECRET inválido ou ausente.")
    ini = time.time()
    page, total, paginas = 1, 0, 0
    while page <= 50:
        data = pci_get(LISTA_URL, {"page": page, "pageSize": 200})
        if not isinstance(data, dict):
            break
        items = data.get("items") or []
        total += _upsert_projetos(items)
        paginas += 1
        if not data.get("hasNext"):
            break
        page += 1
    dur = int((time.time() - ini) * 1000)
    try:
        execute("""insert into cockpit.sync_log
                   (source, status, started_at, finished_at, duration_ms,
                    tickets_processed, tickets_upserted)
                   values ('projetos-vercel','success', to_timestamp(%s), now(), %s, %s, %s)""",
                (ini, dur, total, total))
    except Exception:
        pass
    return _json({"ok": True, "paginas": paginas, "projetos": total, "duration_ms": dur})


# ── MONITCAD — status dos cadastros (aba "Cadastros") ───────────────────────
def _data_iso(v):
    """Aceita '20260427' (AAAAMMDD) ou '2026-04-27'; devolve ISO ou None."""
    s = str(v or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def _dt_hora(v):
    """('11/08/2026 11:43') -> ('2026-08-11', '11:43'). Aceita também ISO e AAAAMMDD."""
    s = str(v or "").strip()
    if not s:
        return None, None
    hora = None
    if " " in s:
        s, _, h = s.partition(" ")
        hora = h.strip()[:8] or None
    if m := re.fullmatch(r"(\d{2})[/-](\d{2})[/-](\d{4})", s):
        d, mes, a = m.groups()
        return f"{a}-{mes}-{d}", hora
    return _data_iso(s), hora


# Nomes de coluna aceitos no CSV (sem acento, maiúsculo, sem espaço/underscore)
CSV_COLS = {
    "MODULO": "modulo", "TABELA": "tabela", "DESCRICAO": "descricao",
    "QTDE": "realizado", "QUANTIDADE": "realizado", "REALIZADO": "realizado",
    "REGISTROS": "realizado", "ESTIMATIVA": "estimativa", "META": "estimativa",
    "FILTRO": "filtro", "ETAPA": "etapa", "RESPONSAVEL": "responsavel",
    "STATUS": "status", "DATAPREV": "data_prev", "PREVISAO": "data_prev",
    "DTLEITURA": "_dt", "DATA": "_dt", "DATAMEDICAO": "_dt", "SEMANA": "_semana",
}


def _norm_col(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _csv_para_body(texto):
    """Converte o CSV de status de cadastros no mesmo formato do
    historico-semanal.json. Uma medição por data encontrada em DT_LEITURA."""
    amostra = texto[:4096]
    try:
        dial = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
    except csv.Error:
        dial = csv.excel
    linhas = list(csv.reader(io.StringIO(texto), dial))
    if not linhas:
        raise ValueError("CSV vazio.")
    cabec = [CSV_COLS.get(_norm_col(c)) for c in linhas[0]]
    if "tabela" not in cabec:
        raise ValueError("CSV sem a coluna TABELA. Esperado: MODULO, TABELA, "
                         "DESCRICAO, DT_LEITURA, SEMANA, QTDE.")

    por_data = {}
    for linha in linhas[1:]:
        if not any((c or "").strip() for c in linha):
            continue
        reg = {}
        for col, val in zip(cabec, linha):
            if col:
                reg[col] = (val or "").strip()
        if not reg.get("tabela"):
            continue
        dt, hora = _dt_hora(reg.pop("_dt", ""))
        if not dt:
            raise ValueError("CSV sem data válida em DT_LEITURA (ex.: 11/08/2026 11:43).")
        semana = reg.pop("_semana", "")
        med = por_data.setdefault(dt, {
            "data_iso": dt, "hora_medicao": hora,
            "semana": int(re.sub(r"^.*W", "", semana) or 0) or None,
            "tabelas": [],
        })
        for k in ("realizado", "estimativa"):
            if k in reg:
                reg[k] = float(str(reg[k]).replace(".", "").replace(",", ".") or 0)
        if "data_prev" in reg:
            reg["data_prev"] = _dt_hora(reg["data_prev"])[0]
        med["tabelas"].append(reg)

    if not por_data:
        raise ValueError("CSV sem linhas de tabela.")
    return {"medicoes": [por_data[d] for d in sorted(por_data)]}


@app.get("/api/monitcad/<customer>")
def api_monitcad(customer):
    """Última medição + histórico de carga dos cadastros do cliente.
    Enquanto o U_MONITPUSH() do Protheus não publicar, devolve vazio:true."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    proj = q("select * from cockpit.monitcad_projetos where customer=%s",
             (customer,), one=True)
    meds = q("""select id, data_medicao, semana, hora_medicao, origem
                  from cockpit.monitcad_medicoes
                 where customer=%s order by data_medicao""", (customer,))
    if not meds:
        return _json({"ok": True, "customer": customer, "projeto": proj,
                      "vazio": True, "tabelas": [], "serie": [], "total_medicoes": 0})
    ult = meds[-1]
    tabelas = q("""select tabela, descricao, modulo, filtro, realizado, estimativa,
                          percentual, data_prev, etapa, responsavel, status
                     from cockpit.monitcad_tabelas
                    where medicao_id=%s
                    order by modulo nulls last, realizado desc, tabela""", (ult["id"],))
    # Sem monitcad.estimativas cadastradas não existe % de carga — só contagem.
    tem_est = any(float(t["estimativa"] or 0) > 0 for t in tabelas)
    modulos = q("""select coalesce(modulo,'(sem módulo)') as modulo,
                          count(*) as tabelas,
                          count(*) filter (where realizado > 0) as com_carga,
                          sum(realizado) as registros
                     from cockpit.monitcad_tabelas
                    where medicao_id=%s group by 1 order by 4 desc, 1""", (ult["id"],))
    serie = q("""select m.data_medicao, m.semana,
                        sum(t.realizado)  as realizado,
                        sum(t.estimativa) as estimativa,
                        count(*) filter (where t.realizado > 0) as tabelas_com_carga,
                        case when sum(t.estimativa) > 0
                             then round(100.0 * sum(t.realizado) / sum(t.estimativa), 1)
                             else null end as pct
                   from cockpit.monitcad_medicoes m
                   join cockpit.monitcad_tabelas t on t.medicao_id = m.id
                  where m.customer=%s
                  group by m.data_medicao, m.semana
                  order by m.data_medicao""", (customer,))
    return _json({"ok": True, "customer": customer, "projeto": proj, "vazio": False,
                  "ultima_medicao": ult["data_medicao"], "total_medicoes": len(meds),
                  "tem_estimativa": tem_est, "tabelas": tabelas, "modulos": modulos,
                  "serie": serie})


@app.post("/api/monitcad/<customer>/upload")
def api_monitcad_upload(customer):
    """Carga manual enquanto o job do Protheus não roda. Aceita DOIS formatos:
    o historico-semanal.json e o CSV de status de cadastros (MODULO, TABELA,
    DESCRICAO, DT_LEITURA, SEMANA, QTDE). Idempotente: regrava a medição inteira
    quando a data já existe."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de subir medições.")

    if (f := request.files.get("arquivo")):
        bruto, nome = f.read(), (f.filename or "")
    else:
        bruto, nome = request.get_data(), ""
    if not bruto:
        return _err(400, "Arquivo vazio.")
    # O Protheus exporta em cp1252 — tenta os encodings na ordem mais provável
    texto = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = bruto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    texto = texto if texto is not None else bruto.decode("utf-8", errors="replace")

    ehcsv = nome.lower().endswith(".csv") or "csv" in (request.content_type or "") \
        or not texto.lstrip().startswith(("{", "["))
    if ehcsv:
        try:
            body = _csv_para_body(texto)
        except Exception as e:
            return _err(400, f"CSV inválido: {e}")
    else:
        try:
            body = json.loads(texto)
        except Exception as e:
            return _err(400, f"JSON inválido: {e}")

    if not isinstance(body, dict):
        return _err(400, "Envie o historico-semanal.json ou o CSV de cadastros.")
    medicoes = body.get("medicoes") or []
    if not isinstance(medicoes, list) or not medicoes:
        return _err(400, "Arquivo sem medições.")

    # FK: o customer precisa existir em cockpit.clientes
    if not q("select 1 from cockpit.clientes where customer=%s", (customer,), one=True):
        return _err(409, f"Cliente {customer} não cadastrado em cockpit.clientes.")

    execute("""insert into cockpit.monitcad_projetos
                 (customer, slug, projeto, cliente_nome, gp_totvs_nome, gp_cliente_nome, updated_at)
               values (%s,%s,%s,%s,%s,%s, now())
               on conflict (customer) do update set
                 projeto=coalesce(excluded.projeto, cockpit.monitcad_projetos.projeto),
                 cliente_nome=coalesce(excluded.cliente_nome, cockpit.monitcad_projetos.cliente_nome),
                 gp_totvs_nome=coalesce(excluded.gp_totvs_nome, cockpit.monitcad_projetos.gp_totvs_nome),
                 gp_cliente_nome=coalesce(excluded.gp_cliente_nome, cockpit.monitcad_projetos.gp_cliente_nome),
                 updated_at=now()""",
            (customer, _slug(body.get("projeto") or "") or None, body.get("projeto"),
             body.get("cliente"), body.get("gp_totvs"), body.get("gp_cliente")))

    n_med = n_tab = 0
    ultima = None
    for m in medicoes:
        dt = _data_iso(m.get("data_iso") or m.get("data_medicao"))
        if not dt:
            continue
        # regrava a medição inteira (as tabelas caem por ON DELETE CASCADE
        # da FK medicao_id — se não houver cascade, o delete explícito cobre)
        antigos = q("select id from cockpit.monitcad_medicoes where customer=%s and data_medicao=%s",
                    (customer, dt))
        for a in antigos:
            execute("delete from cockpit.monitcad_tabelas where medicao_id=%s", (a["id"],))
            execute("delete from cockpit.monitcad_medicoes where id=%s", (a["id"],))
        row = q("""insert into cockpit.monitcad_medicoes
                     (customer, data_medicao, semana, hora_medicao, origem, payload)
                   values (%s,%s,%s,%s,'upload',%s) returning id""",
                (customer, dt, m.get("semana"), m.get("hora_medicao"),
                 json.dumps({k: v for k, v in m.items() if k != "tabelas"})), one=True)
        mid = row["id"]
        n_med += 1
        ultima = max(ultima or dt, dt)
        linhas = []
        for t in (m.get("tabelas") or []):
            est = float(t.get("estimativa") or 0)
            real = float(t.get("realizado") or 0)
            pct = t.get("percentual")
            if pct is None:
                pct = round(100.0 * real / est, 1) if est > 0 else 0
            linhas.append((mid, customer, dt, t.get("tabela"), t.get("descricao"),
                           t.get("modulo"), t.get("filtro"), real, est, pct,
                           _data_iso(t.get("data_prev")), t.get("etapa"),
                           t.get("responsavel"), t.get("status")))
        if linhas:
            with db() as c, c.cursor() as cur:
                execute_values(cur, """
                    insert into cockpit.monitcad_tabelas
                      (medicao_id, customer, data_medicao, tabela, descricao, modulo, filtro,
                       realizado, estimativa, percentual, data_prev, etapa, responsavel, status)
                    values %s""", linhas, page_size=200)
            n_tab += len(linhas)

    if ultima:
        execute("update cockpit.monitcad_projetos set ultima_medicao=%s, updated_at=now() "
                "where customer=%s", (ultima, customer))
    return _json({"ok": True, "customer": customer, "formato": "csv" if ehcsv else "json",
                  "medicoes": n_med, "tabelas": n_tab, "ultima_medicao": ultima})


# ── Gmail: rascunho por IMAP APPEND ─────────────────────────────────────────
# A App Password fica cifrada (Fernet) em cockpit.gmail_credenciais, com a chave
# derivada do SESSION_SECRET da Vercel — trocar o SESSION_SECRET invalida todas
# as credenciais salvas, e cada usuário só precisa salvar de novo pela própria
# tela. A senha NUNCA volta para o front.
IMAP_HOST = "imap.gmail.com"


def _fernet():
    from cryptography.fernet import Fernet
    if SESSION_SECRET == "dev-insecure-secret":
        raise RuntimeError("SESSION_SECRET não configurado — não dá para cifrar a senha.")
    chave = base64.urlsafe_b64encode(hashlib.sha256(SESSION_SECRET.encode()).digest())
    return Fernet(chave)


def _imap_login(gmail, senha):
    m = imaplib.IMAP4_SSL(IMAP_HOST, timeout=25)
    m.login(gmail, senha)
    return m


def _pasta_rascunhos(m):
    """O nome da pasta muda com o idioma da conta ([Gmail]/Drafts, /Rascunhos…).
    Acha pela flag \\Drafts, que é estável."""
    ok, linhas = m.list()
    if ok == "OK":
        for l in linhas:
            txt = l.decode("utf-8", "replace") if isinstance(l, bytes) else str(l)
            if "\\Drafts" in txt:
                return '"' + txt.split(' "/" ')[-1].strip().strip('"') + '"'
    return '"[Gmail]/Drafts"'


def _cred_gmail(usuario):
    row = q("select gmail_email, senha_cif from cockpit.gmail_credenciais where usuario=%s",
            (usuario,), one=True)
    if not row:
        return None, None
    try:
        return row["gmail_email"], _fernet().decrypt(row["senha_cif"].encode()).decode()
    except Exception:
        return row["gmail_email"], None      # cifrada com outro SESSION_SECRET


@app.get("/api/gmail/cred")
def api_gmail_cred_get():
    if (r := require_auth()):
        return r
    gmail, senha = _cred_gmail(current_user())
    return _json({"ok": True, "configurado": bool(gmail and senha), "gmail_email": gmail,
                  "precisa_resalvar": bool(gmail and not senha)})


@app.post("/api/gmail/cred")
def api_gmail_cred_set():
    """Valida a App Password fazendo login IMAP de verdade antes de gravar."""
    if (r := require_auth()):
        return r
    b = request.get_json(silent=True) or {}
    gmail = (b.get("gmail_email") or "").strip().lower()
    senha = (b.get("app_password") or "").replace(" ", "")
    if not gmail or not senha:
        return _err(400, "Informe o e-mail do Gmail e a App Password.")
    try:
        m = _imap_login(gmail, senha)
        m.logout()
    except Exception as e:
        return _err(400, f"O Gmail recusou a credencial: {e}")
    execute("""insert into cockpit.gmail_credenciais
                 (usuario, gmail_email, senha_cif, validado_em, updated_at)
               values (%s,%s,%s, now(), now())
               on conflict (usuario) do update set
                 gmail_email=excluded.gmail_email, senha_cif=excluded.senha_cif,
                 validado_em=now(), updated_at=now()""",
            (current_user(), gmail, _fernet().encrypt(senha.encode()).decode()))
    return _json({"ok": True, "gmail_email": gmail})


@app.delete("/api/gmail/cred")
def api_gmail_cred_del():
    if (r := require_auth()):
        return r
    execute("delete from cockpit.gmail_credenciais where usuario=%s", (current_user(),))
    return _json({"ok": True})


@app.post("/api/gmail/rascunho")
def api_gmail_rascunho():
    """Cria um rascunho HTML na conta do usuário logado (IMAP APPEND)."""
    if (r := require_auth()):
        return r
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de criar rascunhos.")
    b = request.get_json(silent=True) or {}
    assunto = (b.get("assunto") or "").strip()
    html = b.get("html") or ""
    para = (b.get("para") or "").strip()
    if not assunto or not html:
        return _err(400, "Informe assunto e corpo do e-mail.")

    gmail, senha = _cred_gmail(current_user())
    if not gmail:
        return _err(428, "Sem credencial do Gmail. Cadastre uma App Password.")
    if not senha:
        return _err(428, "A credencial do Gmail não pôde ser lida (SESSION_SECRET mudou). "
                         "Cadastre a App Password de novo.")

    msg = email.message.EmailMessage()
    msg["From"] = gmail
    if para:
        msg["To"] = para
    if cc := (b.get("cc") or "").strip():
        msg["Cc"] = cc
    msg["Subject"] = assunto
    msg.set_content("Este e-mail tem formatação HTML — abra num cliente compatível.")
    msg.add_alternative(html, subtype="html")

    try:
        m = _imap_login(gmail, senha)
        try:
            m.append(_pasta_rascunhos(m), "\\Draft", imaplib.Time2Internaldate(time.time()),
                     msg.as_bytes())
        finally:
            m.logout()
    except Exception as e:
        return _err(502, f"Falha ao criar o rascunho no Gmail: {e}")
    return _json({"ok": True, "gmail_email": gmail, "assunto": assunto, "para": para})


# ── Painéis do cliente (aba "Transição") ────────────────────────────────────
# O HTML fica em cockpit.paineis_cliente, NÃO no git: este repo é público e o
# painel carrega o plano de atividades, consultores e GAPs do cliente.
@app.get("/api/paineis")
def api_paineis():
    """Painéis disponíveis para os clientes que o usuário enxerga."""
    if (r := require_auth()):
        return r
    allowed = allowed_customers()
    rows = q("""select p.customer, p.slug, p.titulo, p.descricao, p.updated_at,
                       c.nome as cliente_nome
                  from cockpit.paineis_cliente p
                  join cockpit.clientes c on c.customer = p.customer
                 where p.ativo order by c.nome, p.slug""")
    out = [r for r in rows if allowed is None or r["customer"] in allowed]
    return _json({"ok": True, "paineis": out, "pode_subir": is_admin(current_user())})


@app.get("/painel/<customer>/<slug>")
def page_painel(customer, slug):
    """Serve o painel dentro do iframe da aba Transição — exige sessão e acesso
    ao cliente. É por isso que o HTML não pode morar em web/ (estático livre)."""
    if not current_user():
        return redirect("/login", 302)
    if (d := deny_customer(customer)):
        return d
    row = q("select html from cockpit.paineis_cliente "
            "where customer=%s and slug=%s and ativo", (customer, slug), one=True)
    if not row:
        return _err(404, "Painel não encontrado.")
    return Response(row["html"], mimetype="text/html; charset=utf-8")


@app.post("/api/paineis/<customer>/<slug>")
def api_painel_upload(customer, slug):
    """Publica/atualiza o HTML do painel. Só admin; o corpo é o arquivo inteiro."""
    if (r := require_admin()):
        return r
    if not q("select 1 from cockpit.clientes where customer=%s", (customer,), one=True):
        return _err(409, f"Cliente {customer} não cadastrado em cockpit.clientes.")
    html = request.get_data(as_text=True) or ""
    if (f := request.files.get("arquivo")):
        html = f.read().decode("utf-8", errors="replace")
    if "<" not in html or len(html) < 200:
        return _err(400, "Envie o HTML completo do painel.")
    titulo = request.args.get("titulo") or slug
    execute("""insert into cockpit.paineis_cliente
                 (customer, slug, titulo, html, updated_by, updated_at)
               values (%s,%s,%s,%s,%s, now())
               on conflict (customer, slug) do update set
                 titulo=excluded.titulo, html=excluded.html,
                 updated_by=excluded.updated_by, updated_at=now(), ativo=true""",
            (customer, slug, titulo, html, current_user()))
    return _json({"ok": True, "customer": customer, "slug": slug, "bytes": len(html)})


# detalhe AO VIVO (cache curto por instância quente)
_cache: dict = {}
TTL = 90


def _cached(key, loader):
    e = _cache.get(key)
    now = time.time()
    if e and now - e["t"] < TTL:
        return e["v"]
    try:
        v = loader()
        _cache[key] = {"t": now, "v": v}
        return v
    except PCIUnavailable:
        if e:  # serve o cache vencido em vez de tela de erro
            v = e["v"]
            if isinstance(v, dict):
                return {**v, "_stale": True, "_stale_idade_min": int((now - e["t"]) / 60)}
            return v
        raise


@app.get("/api/projeto/<cli>/<cod>/<ver>/<loja>/<kind>")
def api_projeto_detalhe(cli, cod, ver, loja, kind):
    if (r := require_auth()):
        return r
    if (d := deny_customer(cli)):
        return d
    if kind not in ("mapa", "cronograma"):
        return _err(400, "Esperado mapa|cronograma.")
    params = {"CLIENTE": cli, "CODIGO": cod, "VERSAO": ver, "LOJA": loja or "undefined"}
    if kind == "mapa":
        params["t"] = int(time.time() * 1000)
    url = MAPA_URL if kind == "mapa" else CRONO_URL
    return _json(_cached(f"{kind}:{cli}:{cod}:{ver}:{loja}", lambda: pci_get(url, params)))


# ── estáticos do web/ (assets) ──────────────────────────────────────────────
@app.get("/<path:asset>")
def static_assets(asset):
    if asset.startswith("api/"):
        return _err(404, "Rota de API desconhecida.")
    safe = (WEB_DIR / asset).resolve()
    if WEB_DIR in safe.parents and safe.is_file():
        # Nenhum HTML (fora o login) sai sem sessão — inclui transicao.html
        if safe.suffix.lower() == ".html" and safe.name != "login.html" and not current_user():
            return redirect("/login", 302)
        ext = safe.suffix.lower()
        ctype = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
                 ".css": "text/css", ".json": "application/json", ".png": "image/png",
                 ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon",
                 ".woff2": "font/woff2"}.get(ext, "application/octet-stream")
        return Response(safe.read_bytes(), mimetype=ctype)
    return _err(404, "Não encontrado.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5055)), debug=True)
