#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Projetos · TOTVS SC — backend serverless (Vercel)
=================================================
Porte do Projetos/server.py + pci_client.py para função serverless.

- Lista de projetos: lida de cockpit.projetos (Supabase), sincronizada de HORA
  em HORA pelo pg_cron do Supabase (jobid 7 "projetos-sync" -> GET
  /api/cron/sync com Bearer CRON_SECRET) e sob demanda pelo botão "Sincronizar
  API" (POST /api/sync?page=N, paginado pelo front para não estourar os 60s).
- RECORTE: só entram projetos da regional (região do coordenador titular ou
  auxiliar em SYNC_REGIOES), de clientes de cockpit.clientes, ou de clientes da
  regional com projeto ainda vivo. Ver no_recorte() — e a MESMA regra em SQL em
  purga_fora_do_recorte().
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

# ── Recorte do sync (regional SC Sul + clientes do Cockpit) ─────────────────
# A API PCI devolve os ~1.7 mil projetos de TODA a TOTVS SC. Só interessam os da
# regional e os dos clientes atendidos: sem isso a lista vira palheiro e o cron
# grava 700 projetos que ninguém abre. Um projeto entra se a REGIÃO do
# coordenador (titular OU auxiliar) estiver em SYNC_REGIOES, ou se o cliente
# estiver em cockpit.clientes. SYNC_REGIOES vazio = sem filtro (volta ao antigo).
SYNC_REGIOES = {r.strip() for r in os.environ.get("SYNC_REGIOES", "201,202,211").split(",")
                if r.strip()}
# O cron apaga o que está fora do recorte (projeto que trocou de coordenador/
# região some da base). SYNC_PURGE=0 desliga.
SYNC_PURGE = os.environ.get("SYNC_PURGE", "1").strip().lower() not in ("0", "false", "off")
# Terceiro critério: cliente DA regional cujo projeto ainda está vivo, mesmo com
# coordenador de outra região (ex.: PRODUZA/203, GROWTH/601, SOLFACIL/302 — todos
# clientes 201). Sem o corte por status isso arrastaria 644 projetos finalizados.
SYNC_ENCERRADOS = {"finalizado", "cancelado"}
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
            "recorte": {"regioes": sorted(SYNC_REGIOES), "purga": SYNC_PURGE},
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
    items, ignorados = filtra_recorte(data.get("items") or [])
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
                  "ignorados": ignorados, "hasNext": bool(data.get("hasNext"))})


# ── Recorte: quem entra na base ─────────────────────────────────────────────
_CLIENTES_CACHE = {"t": 0.0, "v": frozenset()}


def clientes_cockpit(force=False):
    """customers liberados em cockpit.clientes — cache de 5 min.
    Se o banco falhar, devolve o último valor conhecido (nunca vazio por erro:
    conjunto vazio + regiões vazias apagaria a base inteira na purga)."""
    if not force and _CLIENTES_CACHE["v"] and time.time() - _CLIENTES_CACHE["t"] < 300:
        return _CLIENTES_CACHE["v"]
    try:
        v = frozenset(str(r["customer"] or "").strip()
                      for r in q("select customer from cockpit.clientes"))
    except Exception:
        return _CLIENTES_CACHE["v"]
    if v:
        _CLIENTES_CACHE.update(t=time.time(), v=v)
    return v


def no_recorte(p, clientes=None):
    """True se o projeto é da regional (região do coordenador titular ou auxiliar)
    ou de um cliente do Cockpit."""
    if not SYNC_REGIOES:
        return True
    for k in ("regiao_coordenador_projeto", "regiao_coordenador_auxiliar"):
        if str(p.get(k) or "").strip() in SYNC_REGIOES:
            return True
    if str(p.get("regiao_cliente_projeto") or "").strip() in SYNC_REGIOES \
            and str(p.get("status_projeto") or "").strip().lower() not in SYNC_ENCERRADOS:
        return True
    cli = str(p.get("codigo_cliente_projeto") or "").strip()
    return bool(cli) and cli in (clientes if clientes is not None else clientes_cockpit())


def filtra_recorte(items, clientes=None):
    if not SYNC_REGIOES:
        return list(items), 0
    clientes = clientes_cockpit() if clientes is None else clientes
    dentro = [p for p in items if no_recorte(p, clientes)]
    return dentro, len(items) - len(dentro)


def purga_fora_do_recorte():
    """Apaga de cockpit.projetos o que não casa mais com o recorte. Roda no fim do
    cron; a regra SQL é a MESMA do no_recorte() — mexeu numa, mexa na outra."""
    if not (SYNC_PURGE and SYNC_REGIOES):
        return 0
    regs = list(SYNC_REGIOES)
    with db() as c, c.cursor() as cur:
        cur.execute("""
            delete from cockpit.projetos
             where coalesce(btrim(raw->>'regiao_coordenador_projeto'), '') <> all(%s)
               and coalesce(btrim(raw->>'regiao_coordenador_auxiliar'), '') <> all(%s)
               and not (coalesce(btrim(raw->>'regiao_cliente_projeto'), '') = any(%s)
                        and lower(coalesce(btrim(status_projeto), '')) <> all(%s))
               and coalesce(btrim(codigo_cliente_projeto), '') not in (
                     select coalesce(btrim(customer), '') from cockpit.clientes)
        """, (regs, regs, regs, list(SYNC_ENCERRADOS)))
        return cur.rowcount or 0


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
    page, total, paginas, ignorados = 1, 0, 0, 0
    clientes = clientes_cockpit(force=True)
    while page <= 50:
        data = pci_get(LISTA_URL, {"page": page, "pageSize": 200})
        if not isinstance(data, dict):
            break
        items, fora = filtra_recorte(data.get("items") or [], clientes)
        ignorados += fora
        total += _upsert_projetos(items)
        paginas += 1
        if not data.get("hasNext"):
            break
        page += 1
    apagados = purga_fora_do_recorte()
    dur = int((time.time() - ini) * 1000)
    try:
        execute("""insert into cockpit.sync_log
                   (source, status, started_at, finished_at, duration_ms,
                    tickets_processed, tickets_upserted)
                   values ('projetos-vercel','success', to_timestamp(%s), now(), %s, %s, %s)""",
                (ini, dur, total, total))
    except Exception:
        pass
    return _json({"ok": True, "paginas": paginas, "projetos": total,
                  "ignorados": ignorados, "apagados": apagados,
                  "regioes": sorted(SYNC_REGIOES), "duration_ms": dur})


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
# QTD_REAL / QTD_ESTIMADA estão aqui por um motivo concreto: o script SQL que a
# própria aba gera usa esses nomes, e em 18/08/2026 uma medição da Olim entrou
# com as 112 tabelas e realizado = 0 porque a coluna não era reconhecida. Ao
# acrescentar um alias novo, lembre que coluna ignorada vira ZERO silencioso.
CSV_COLS = {
    "MODULO": "modulo", "TABELA": "tabela", "DESCRICAO": "descricao",
    "QTDE": "realizado", "QTD": "realizado", "QUANTIDADE": "realizado",
    "REALIZADO": "realizado", "REGISTROS": "realizado", "CONTAGEM": "realizado",
    "QTDREAL": "realizado", "QTDATUAL": "realizado", "QTDREGISTROS": "realizado",
    "ESTIMATIVA": "estimativa", "META": "estimativa", "ESTIMADA": "estimativa",
    "PREVISTO": "estimativa", "QTDESTIMADA": "estimativa",
    "QTDESTIMATIVA": "estimativa", "QTDPREVISTA": "estimativa",
    "FILTRO": "filtro", "ETAPA": "etapa", "RESPONSAVEL": "responsavel",
    "STATUS": "status", "DATAPREV": "data_prev", "PREVISAO": "data_prev",
    "DTLEITURA": "_dt", "DATA": "_dt", "DATAMEDICAO": "_dt", "SEMANA": "_semana",
}

# Tabelas de CONFIGURAÇÃO do Protheus, não de cadastro do cliente: a contagem é
# do dicionário/parametrização que já vem com o produto (dezenas de milhares de
# linhas que ninguém "cadastra" no projeto), então elas poluíam a lista e nunca
# teriam estimativa. Retiradas da análise em 23/08/2026. Filtramos na importação
# para que um CSV gerado por um script antigo não as traga de volta.
# SX5 por GRUPO (SX5_S4, SX5_T3...) continua valendo — aquilo é cadastro de verdade.
TABELAS_IGNORADAS = {"SX5", "SX6", "SX7"}

# Documento e saldo NÃO são carga de cadastro: nota fiscal, pedido, título,
# ordem de produção, saldo de estoque e saldo contábil nascem da operação, não do
# trabalho de cadastramento do projeto. Somados junto, distorciam a contagem da
# aba Cadastros — e a pergunta que eles respondem ("a operação já rodou?") é a da
# aba Movimentos/Cobertura, que trabalha por cenário, não por contagem de tabela.
#
# Estas tabelas continuam sendo IMPORTADAS (o histórico não se perde); só entram
# com painel='movimento' e a aba Cadastros as filtra fora. Reversível: basta um
# update em cockpit.monitcad_tabelas.painel.
#
# Classificar aqui, e não só no script do Protheus, é o que impede a tabela de
# voltar quando alguém roda um script antigo — mesmo motivo do TABELAS_IGNORADAS.
TABELAS_MOVIMENTO = {
    "SC1", "SC7", "SC8",                       # compras: solicitação, pedido, cotação
    "SC5", "SC6",                              # pedido de venda
    "SF1", "SD1", "SF2", "SD2", "SF3",         # notas de entrada/saída e livros
    "SE1", "SE2", "SEB",                       # títulos e retorno bancário
    "SC2",                                     # ordem de produção
    "SB2", "SB8", "SB9", "SBF", "SBJ",         # saldos de estoque
    "SN3", "SN4",                              # saldos e movimentos do ativo
    "CV3",                                     # saldos contábeis
    "SL1", "SL2",                              # venda frente de loja
    "AB3", "AB4", "AB5",                       # orçamentos de serviço
    "AB6", "AB7", "AB8", "AB9", "ABC",         # ordens de serviço e apontamentos
    "CN9", "CNB",                              # contratos: cabeçalho e itens da planilha
}


def _painel_da_tabela(tabela):
    return "movimento" if (tabela or "").strip().upper() in TABELAS_MOVIMENTO else "cadastro"

# Só para a mensagem de erro — os nomes na forma em que o usuário escreve
QTD_ACEITOS = "QTDE, QTD, QTD_REAL, QUANTIDADE, REALIZADO, REGISTROS"


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
    # Sem coluna de quantidade a medição entraria inteira zerada e pareceria uma
    # base vazia. Falhar aqui é MUITO mais barato do que descobrir depois.
    if "realizado" not in cabec:
        raise ValueError(f"CSV sem coluna de quantidade — aceito: {QTD_ACEITOS}. "
                         "Cabeçalho recebido: "
                         + ", ".join(c.strip() for c in linhas[0] if c.strip()))

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


AMBIENTES = ("producao", "teste")


def _ambiente():
    """Produção e teste são bases DIFERENTES: nunca somar as duas na mesma
    leitura. O ambiente vem sempre explícito do front."""
    a = (request.args.get("ambiente") or "producao").strip().lower()
    return a if a in AMBIENTES else "producao"


@app.get("/api/monitcad/<customer>")
def api_monitcad(customer):
    """Última medição + histórico de carga dos cadastros do cliente, no ambiente
    pedido. Sem medição naquele ambiente, devolve vazio:true."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    amb = _ambiente()
    proj = q("select * from cockpit.monitcad_projetos where customer=%s",
             (customer,), one=True)
    meds = q("""select id, data_medicao, semana, hora_medicao, origem
                  from cockpit.monitcad_medicoes
                 where customer=%s and ambiente=%s order by data_medicao""",
             (customer, amb))
    if not meds:
        return _json({"ok": True, "customer": customer, "projeto": proj, "ambiente": amb,
                      "vazio": True, "tabelas": [], "serie": [], "total_medicoes": 0})
    ult = meds[-1]
    # painel='cadastro': documento e saldo vivem na aba Movimentos (ver
    # TABELAS_MOVIMENTO). O filtro precisa estar em TODAS as consultas da aba —
    # deixar de fora a dos módulos ou a da série faria os totais brigarem com a
    # lista logo abaixo deles.
    tabelas = q("""select tabela, descricao, modulo, filtro, realizado, estimativa,
                          percentual, data_prev, etapa, responsavel, status
                     from cockpit.monitcad_tabelas
                    where medicao_id=%s and painel='cadastro'
                    order by modulo nulls last, realizado desc, tabela""", (ult["id"],))
    # Sem monitcad.estimativas cadastradas não existe % de carga — só contagem.
    tem_est = any(float(t["estimativa"] or 0) > 0 for t in tabelas)
    modulos = q("""select coalesce(modulo,'(sem módulo)') as modulo,
                          count(*) as tabelas,
                          count(*) filter (where realizado > 0) as com_carga,
                          sum(realizado) as registros
                     from cockpit.monitcad_tabelas
                    where medicao_id=%s and painel='cadastro'
                    group by 1 order by 4 desc, 1""", (ult["id"],))
    serie = q("""select m.data_medicao, m.semana,
                        sum(t.realizado)  as realizado,
                        sum(t.estimativa) as estimativa,
                        count(*) filter (where t.realizado > 0) as tabelas_com_carga,
                        case when sum(t.estimativa) > 0
                             then round(100.0 * sum(t.realizado) / sum(t.estimativa), 1)
                             else null end as pct
                   from cockpit.monitcad_medicoes m
                   join cockpit.monitcad_tabelas t on t.medicao_id = m.id
                  where m.customer=%s and m.ambiente=%s and t.painel='cadastro'
                  group by m.data_medicao, m.semana
                  order by m.data_medicao""", (customer, amb))
    return _json({"ok": True, "customer": customer, "projeto": proj, "ambiente": amb,
                  "vazio": False, "ultima_medicao": ult["data_medicao"],
                  "total_medicoes": len(meds), "tem_estimativa": tem_est,
                  "tabelas": tabelas, "modulos": modulos, "serie": serie})


SQL_EVO_MEDICOES = """
with med as (
  select id, data_medicao, hora_medicao,
         to_char(data_medicao,'IYYY')||'-W'||lpad(to_char(data_medicao,'IW'),2,'0') as semana_iso,
         row_number() over (partition by to_char(data_medicao,'IYYY-IW')
                            order by data_medicao desc, id desc) = 1 as fim_semana
    from cockpit.monitcad_medicoes
   where customer = %s and ambiente = %s
)
select m.data_medicao, m.semana_iso, m.fim_semana, m.hora_medicao,
       count(t.*)                              as tabelas,
       count(*) filter (where t.realizado > 0) as com_carga,
       sum(t.realizado)                        as realizado,
       sum(t.estimativa)                       as estimativa
  from med m
  join cockpit.monitcad_tabelas t on t.medicao_id = m.id and t.painel = 'cadastro'
 group by 1, 2, 3, 4
 order by 1
"""

SQL_EVO_MATRIZ = """
with med as (
  select id, data_medicao
    from cockpit.monitcad_medicoes
   where customer = %s and ambiente = %s
), ult as (
  select id from med order by data_medicao desc, id desc limit 1
)
select t.tabela,
       max(t.descricao) as descricao,
       max(t.modulo)    as modulo,
       max(t.estimativa) filter (where t.medicao_id = (select id from ult)) as estimativa,
       jsonb_object_agg(to_char(m.data_medicao,'YYYY-MM-DD'), t.realizado)  as serie
  from med m
  join cockpit.monitcad_tabelas t on t.medicao_id = m.id and t.painel = 'cadastro'
 group by t.tabela
 order by max(t.modulo) nulls last, t.tabela
"""


@app.get("/api/monitcad/<customer>/evolucao")
def api_monitcad_evolucao(customer):
    """Evolução dos cadastros entre medições: eixo de medições + matriz
    tabela x medição. Ranking e consolidação semanal são derivados no front a
    partir daqui — o banco devolve o retrato bruto, uma vez só.

    A estimativa vem SÓ da última medição: é o retrato vigente. Pegar o max()
    de todas faria uma estimativa antiga, já corrigida para baixo, continuar
    valendo. E `serie` só tem chave nas datas em que a tabela foi medida — a
    ausência da chave significa fora do escopo naquela data, que é diferente de
    medida com zero."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    amb = _ambiente()
    medicoes = q(SQL_EVO_MEDICOES, (customer, amb))
    if not medicoes:
        return _json({"ok": True, "customer": customer, "ambiente": amb,
                      "vazio": True, "medicoes": [], "tabelas": []})
    return _json({"ok": True, "customer": customer, "ambiente": amb,
                  "vazio": False, "medicoes": medicoes,
                  "tabelas": q(SQL_EVO_MATRIZ, (customer, amb))})


@app.delete("/api/monitcad/<customer>/medicao")
def api_monitcad_medicao_remover(customer):
    """Apaga uma medição inteira — a daquela data, naquele ambiente.

    Só admin: não há desfazer e a medição some do histórico de todo mundo. O
    caso real é o import que entrou zerado: enquanto ele está lá, a série mostra
    uma queda que não existiu."""
    if (r := require_admin()):
        return r
    if (d := deny_customer(customer)):
        return d
    amb = _ambiente()
    data = _data_iso(request.args.get("data"))
    if not data:
        return _err(400, "Informe a data da medição (AAAA-MM-DD).")

    ids = q("""select id from cockpit.monitcad_medicoes
                where customer=%s and ambiente=%s and data_medicao=%s""",
            (customer, amb, data))
    if not ids:
        return _err(404, f"Nenhuma medição de {data} na base {amb} deste cliente.")
    linhas = 0
    for a in ids:
        r0 = q("select count(*) n from cockpit.monitcad_tabelas where medicao_id=%s",
               (a["id"],), one=True)
        linhas += int(r0["n"] if r0 else 0)
        execute("delete from cockpit.monitcad_tabelas where medicao_id=%s", (a["id"],))
        execute("delete from cockpit.monitcad_medicoes where id=%s", (a["id"],))

    # ultima_medicao tem que recuar junto, senão o cabeçalho do projeto passa a
    # apontar para uma medição que não existe mais
    execute("""update cockpit.monitcad_projetos p
                  set ultima_medicao = (select max(m.data_medicao)
                                          from cockpit.monitcad_medicoes m
                                         where m.customer = p.customer
                                           and m.ambiente = 'producao'),
                      updated_at = now()
                where p.customer=%s""", (customer,))
    return _json({"ok": True, "customer": customer, "ambiente": amb, "data": data,
                  "medicoes": len(ids), "linhas": linhas})


SCRIPT_TIPOS = ("cadastros", "movimentos")


def _tipo_script():
    t = (request.args.get("tipo") or "cadastros").strip().lower()
    return t if t in SCRIPT_TIPOS else "cadastros"


@app.get("/api/monitcad/<customer>/script")
def api_monitcad_script(customer):
    """Script SQL de contagem customizado do cliente.

    Um por tipo (cadastros/movimentos) e válido para as DUAS bases: o escopo de
    tabelas é o mesmo em produção e em teste, o que muda é onde rodar — e disso
    cuida o cabeçalho, que o front reescreve na hora de exibir."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    tipo = _tipo_script()
    row = q("""select customer, tipo, sql, dialeto, sufixo, updated_by, updated_at
                 from cockpit.monitcad_scripts
                where customer=%s and tipo=%s""", (customer, tipo), one=True)
    return _json({"ok": True, "customer": customer, "tipo": tipo, "script": row})


@app.post("/api/monitcad/<customer>/script")
def api_monitcad_script_salvar(customer):
    """Salva o script colado. Quem enxerga o cliente pode salvar — mesma régua
    da importação de medição —, e fica registrado quem foi."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de salvar o script.")
    if not q("select 1 from cockpit.clientes where customer=%s", (customer,), one=True):
        return _err(409, f"Cliente {customer} não cadastrado em cockpit.clientes.")

    body = request.get_json(silent=True) or {}
    sql = (body.get("sql") or "").strip()
    if len(sql) < 20:
        return _err(400, "Cole o script antes de salvar.")
    # O script nunca é executado aqui — vai para o console do Protheus. A única
    # checagem é que exista um SELECT, o que também deixa passar CTE (WITH ...).
    if not re.search(r"\bselect\b", sql, re.I):
        return _err(400, "O script precisa conter um SELECT.")

    tipo = _tipo_script()
    execute("""insert into cockpit.monitcad_scripts
                 (customer, tipo, sql, dialeto, sufixo, updated_by, updated_at)
               values (%s,%s,%s,%s,%s,%s, now())
               on conflict (customer, tipo) do update set
                 sql=excluded.sql, dialeto=excluded.dialeto, sufixo=excluded.sufixo,
                 updated_by=excluded.updated_by, updated_at=now()""",
            (customer, tipo, sql, (body.get("dialeto") or "")[:20] or None,
             (body.get("sufixo") or "")[:10] or None, current_user()))
    return _json({"ok": True, "customer": customer, "tipo": tipo, "bytes": len(sql)})


@app.delete("/api/monitcad/<customer>/script")
def api_monitcad_script_remover(customer):
    """Apaga o script salvo — o modal volta a abrir com o gerado."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de remover o script.")
    execute("delete from cockpit.monitcad_scripts where customer=%s and tipo=%s",
            (customer, _tipo_script()))
    return _json({"ok": True, "customer": customer, "tipo": _tipo_script(), "removido": True})


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

    amb = _ambiente()
    n_med = n_tab = 0
    ultima = None
    for m in medicoes:
        dt = _data_iso(m.get("data_iso") or m.get("data_medicao"))
        if not dt:
            continue
        # regrava a medição inteira DAQUELE ambiente — produção e teste convivem
        # na mesma data sem uma apagar a outra
        antigos = q("""select id from cockpit.monitcad_medicoes
                        where customer=%s and data_medicao=%s and ambiente=%s""",
                    (customer, dt, amb))
        for a in antigos:
            execute("delete from cockpit.monitcad_tabelas where medicao_id=%s", (a["id"],))
            execute("delete from cockpit.monitcad_medicoes where id=%s", (a["id"],))
        row = q("""insert into cockpit.monitcad_medicoes
                     (customer, ambiente, data_medicao, semana, hora_medicao, origem, payload)
                   values (%s,%s,%s,%s,%s,'upload',%s) returning id""",
                (customer, amb, dt, m.get("semana"), m.get("hora_medicao"),
                 json.dumps({k: v for k, v in m.items() if k != "tabelas"})), one=True)
        mid = row["id"]
        n_med += 1
        ultima = max(ultima or dt, dt)
        linhas = []
        for t in (m.get("tabelas") or []):
            if (t.get("tabela") or "").strip().upper() in TABELAS_IGNORADAS:
                continue
            est = float(t.get("estimativa") or 0)
            real = float(t.get("realizado") or 0)
            pct = t.get("percentual")
            if pct is None:
                pct = round(100.0 * real / est, 1) if est > 0 else 0
            linhas.append((mid, customer, amb, dt, t.get("tabela"), t.get("descricao"),
                           t.get("modulo"), t.get("filtro"), real, est, pct,
                           _data_iso(t.get("data_prev")), t.get("etapa"),
                           t.get("responsavel"), t.get("status"),
                           _painel_da_tabela(t.get("tabela"))))
        if linhas:
            with db() as c, c.cursor() as cur:
                execute_values(cur, """
                    insert into cockpit.monitcad_tabelas
                      (medicao_id, customer, ambiente, data_medicao, tabela, descricao,
                       modulo, filtro, realizado, estimativa, percentual, data_prev,
                       etapa, responsavel, status, painel)
                    values %s""", linhas, page_size=200)
            n_tab += len(linhas)

    if ultima and amb == "producao":     # o marco do projeto é a base de produção
        execute("update cockpit.monitcad_projetos set ultima_medicao=%s, updated_at=now() "
                "where customer=%s", (ultima, customer))
    return _json({"ok": True, "customer": customer, "ambiente": amb,
                  "formato": "csv" if ehcsv else "json", "medicoes": n_med,
                  "tabelas": n_tab, "ultima_medicao": ultima})


# ── MOVIMENTOS — cobertura de cenários, não volume por tabela ───────────────
# O total por tabela responde "tem movimento?". A pergunta que decide go-live é
# outra: "qual cenário ainda não rodou?" — venda para contribuinte de outro
# estado, NCM com ST, baixa com adiantamento, transferência entre contas. Numa
# contagem por tabela isso tudo vira uma linha só.
# Por isso a medição de movimentos carrega uma quebra dimensional
# (cockpit.monitmov_dimensoes, alimentada pelo SQL D5) e é cruzada com a lista
# de cenários combinados com o cliente (cockpit.monitmov_cenarios).
# Spec: docs/specs/2026-08-25-movimentos-cobertura-cenarios.md

# Colunas DIM1..DIM4 genéricas de propósito: incluir uma análise nova
# (SD1 de entrada, SD3 de estoque) não muda layout de arquivo nem banco nem tela.
MOV_CSV_COLS = {
    "ANALISE": "analise", "ANALISE1": "analise", "TIPOANALISE": "analise",
    "DESCRICAO": "descricao", "DESCR": "descricao", "OBSERVACAO": "descricao",
    "DIM1NOME": "dim1_nome", "DIM2NOME": "dim2_nome",
    "DIM3NOME": "dim3_nome", "DIM4NOME": "dim4_nome",
    "DIM1": "dim1", "DIM2": "dim2", "DIM3": "dim3", "DIM4": "dim4",
    "PERIODO": "periodo",
    "QTDE": "qtde", "QTD": "qtde", "QUANTIDADE": "qtde", "REGISTROS": "qtde",
    "CONTAGEM": "qtde", "LINHAS": "qtde", "REALIZADO": "qtde",
    "QTDDOC": "qtd_doc", "QTDDOCS": "qtd_doc", "DOCUMENTOS": "qtd_doc",
    "QTDDOCUMENTOS": "qtd_doc", "DOCS": "qtd_doc",
    "DTLEITURA": "_dt", "DATA": "_dt", "DATAMEDICAO": "_dt", "SEMANA": "_semana",
}

# Uma linha em monitmov_itens por análise, derivada da quebra — assim os KPIs e
# o gráfico por módulo que já existiam continuam de pé sem um segundo arquivo.
MOV_ANALISES = {
    "SD2_FISCAL":   ("SD2", "Fiscal",     "Itens de NF de saída (UF × contribuinte × NCM × CFOP)"),
    "SE5_BANCARIO": ("SE5", "Financeiro", "Movimento bancário (operação × sentido × tipo)"),
}


def _periodo_datas(txt):
    """'20260101-20991231' → (date, date). Aceita AAAAMMDD, AAAA-MM-DD e
    DD/MM/AAAA dos dois lados; qualquer coisa fora disso vira (None, None) e o
    período fica só como texto — não é motivo para recusar o arquivo."""
    partes = re.split(r"\s*(?:-{1,2}|até|ate|to|a)\s*", (txt or "").strip(),
                      maxsplit=1, flags=re.I)
    if len(partes) != 2:
        m = re.fullmatch(r"(\d{8})\D+(\d{8})", (txt or "").strip())
        partes = [m.group(1), m.group(2)] if m else []
    saida = []
    for p in partes[:2]:
        p = (p or "").strip()
        if re.fullmatch(r"\d{8}", p):
            saida.append(f"{p[0:4]}-{p[4:6]}-{p[6:8]}")
        else:
            saida.append(_dt_hora(p)[0])   # aceita DD/MM/AAAA além de ISO
    return (saida + [None, None])[:2]


def _num_br(v):
    """Número do export do Protheus: '1.240' é mil duzentos e quarenta, mas
    '1240.5' é um decimal. Só trata ponto como separador de milhar quando o
    formato é inequívoco — trocar sempre quebraria a segunda forma."""
    s = str(v if v is not None else "").strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _csv_movimentos(texto):
    """CSV do D5 → mesmo formato do JSON de importação. Uma medição por data
    encontrada em DT_LEITURA."""
    try:
        dial = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t|")
    except csv.Error:
        dial = csv.excel
    linhas = list(csv.reader(io.StringIO(texto), dial))
    if not linhas:
        raise ValueError("CSV vazio.")
    cabec = [MOV_CSV_COLS.get(_norm_col(c)) for c in linhas[0]]
    if "analise" not in cabec:
        raise ValueError("CSV sem a coluna ANALISE. Esperado o layout do D5: "
                         "ANALISE, DESCRICAO, DIM1_NOME, DIM1 … QTDE, QTD_DOC.")
    # Mesma lição do import de cadastros: coluna de quantidade não reconhecida
    # entraria como medição inteira zerada e pareceria base vazia.
    if "qtde" not in cabec:
        raise ValueError("CSV sem coluna de quantidade — aceito: QTDE, QTD, "
                         "QUANTIDADE, REGISTROS, LINHAS. Cabeçalho recebido: "
                         + ", ".join(c.strip() for c in linhas[0] if c.strip()))

    por_data = {}
    for linha in linhas[1:]:
        if not any((c or "").strip() for c in linha):
            continue
        reg = {}
        for col, val in zip(cabec, linha):
            if col:
                reg[col] = (val or "").strip()
        if not reg.get("analise"):
            continue
        dt, hora = _dt_hora(reg.pop("_dt", ""))
        if not dt:
            raise ValueError("CSV sem data válida em DT_LEITURA (ex.: 25/08/2026 11:43).")
        semana = reg.pop("_semana", "")
        med = por_data.setdefault(dt, {
            "data_iso": dt, "hora_medicao": hora,
            "semana": int(re.sub(r"^.*W", "", semana) or 0) or None,
            "periodo": reg.get("periodo") or "",
            "dimensoes": [],
        })
        reg["qtde"] = _num_br(reg.get("qtde"))
        reg["qtd_doc"] = _num_br(reg.get("qtd_doc")) if reg.get("qtd_doc") else None
        med["dimensoes"].append(reg)
    return {"medicoes": list(por_data.values())}


def _norm_dim(v):
    return (v or "").strip().upper()


def _casa_cenario(cen, obs):
    """Coringa '*' (ou vazio) casa com qualquer valor. Comparação é por texto
    normalizado: o que vem do banco do cliente tem padding e caixa variável."""
    if _norm_dim(cen["analise"]) != _norm_dim(obs["analise"]):
        return False
    for k in ("dim1", "dim2", "dim3", "dim4"):
        alvo = _norm_dim(cen.get(k)) or "*"
        if alvo == "*":
            continue
        if _norm_dim(obs.get(k)) != alvo:
            return False
    return True


def _cobertura(dimensoes, cenarios):
    """Cruza esperado × observado. Devolve a lista de cenários com status e a
    lista do que foi observado sem cenário que case.

    NÃO PREVISTO não é erro: numa base de produção é o normal enquanto a lista
    de cenários não está fechada. Vira sinal depois que o cliente combinou tudo.
    """
    cobertura, casados = [], set()
    for c in cenarios:
        achou = [o for o in dimensoes if _casa_cenario(c, o)]
        qtde = sum(float(o.get("qtde") or 0) for o in achou)
        for o in achou:
            casados.add(id(o))
        cobertura.append({
            **c,
            "qtde": qtde,
            "qtd_doc": sum(float(o.get("qtd_doc") or 0) for o in achou),
            "ocorrencias": len(achou),
            "status": ("COBERTO" if qtde > 0
                       else ("FALTANTE" if c.get("esperado", True) else "OPCIONAL")),
        })
    # Só faz sentido apontar "não previsto" para a análise que já tem cenário
    # combinado — senão a primeira medição do cliente vira uma lista de acusações.
    com_cenario = {_norm_dim(c["analise"]) for c in cenarios}
    nao_previstos = [o for o in dimensoes
                     if id(o) not in casados
                     and _norm_dim(o.get("analise")) in com_cenario
                     and float(o.get("qtde") or 0) > 0]
    ordem = {"FALTANTE": 0, "COBERTO": 1, "OPCIONAL": 2}
    cobertura.sort(key=lambda c: (ordem.get(c["status"], 9), c["analise"],
                                  c.get("descricao") or ""))
    nao_previstos.sort(key=lambda o: -float(o.get("qtde") or 0))
    return cobertura, nao_previstos


@app.get("/api/monitmov/<customer>")
def api_monitmov(customer):
    """Última medição de MOVIMENTOS do cliente no ambiente pedido: totais por
    análise, quebra dimensional e cobertura de cenários."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    amb = _ambiente()
    meds = q("""select id, data_medicao, semana, periodo_ini, periodo_fim, origem
                  from cockpit.monitmov_medicoes
                 where customer=%s and ambiente=%s order by data_medicao""",
             (customer, amb))
    cenarios = q("""select id, analise, dim1, dim2, dim3, dim4, descricao,
                           esperado, etapa, responsavel
                      from cockpit.monitmov_cenarios where customer=%s
                     order by analise, descricao""", (customer,))
    if not meds:
        return _json({"ok": True, "customer": customer, "ambiente": amb, "vazio": True,
                      "itens": [], "modulos": [], "serie": [], "total_medicoes": 0,
                      "dimensoes": [], "analises": [], "cenarios": cenarios,
                      "cobertura": [], "nao_previstos": [], "a_classificar": []})
    ult = meds[-1]
    itens = q("""select tabela, descricao, modulo, filtro, quantidade, valor, periodo
                   from cockpit.monitmov_itens where medicao_id=%s
                  order by modulo nulls last, quantidade desc, tabela""", (ult["id"],))
    modulos = q("""select coalesce(modulo,'(sem módulo)') as modulo, count(*) as tabelas,
                          count(*) filter (where quantidade > 0) as com_movimento,
                          sum(quantidade) as registros
                     from cockpit.monitmov_itens where medicao_id=%s
                    group by 1 order by 4 desc, 1""", (ult["id"],))
    serie = q("""select m.data_medicao, m.semana, sum(i.quantidade) as realizado,
                        count(*) filter (where i.quantidade > 0) as tabelas_com_carga
                   from cockpit.monitmov_medicoes m
                   join cockpit.monitmov_itens i on i.medicao_id = m.id
                  where m.customer=%s and m.ambiente=%s
                  group by m.data_medicao, m.semana order by m.data_medicao""",
              (customer, amb))
    dimensoes = q("""select analise, descricao, dim1_nome, dim1, dim2_nome, dim2,
                            dim3_nome, dim3, dim4_nome, dim4, periodo, qtde, qtd_doc
                       from cockpit.monitmov_dimensoes where medicao_id=%s
                      order by analise, qtde desc, dim1, dim2, dim3, dim4""",
                  (ult["id"],))
    analises = q("""select analise, count(*) as combinacoes,
                           count(*) filter (where qtde > 0) as com_movimento,
                           count(distinct dim1) as valores_dim1,
                           max(dim1_nome) as dim1_nome, max(dim2_nome) as dim2_nome,
                           max(dim3_nome) as dim3_nome, max(dim4_nome) as dim4_nome,
                           sum(qtde) as qtde, sum(qtd_doc) as qtd_doc
                      from cockpit.monitmov_dimensoes where medicao_id=%s
                     group by analise order by analise""", (ult["id"],))
    cobertura, nao_previstos = _cobertura(dimensoes, cenarios)
    # Fila de trabalho do consultor: o que o de-para bancário ainda não sabe ler
    a_classificar = [d for d in dimensoes if _norm_dim(d.get("dim1")) == "(A CLASSIFICAR)"]
    return _json({"ok": True, "customer": customer, "ambiente": amb, "vazio": False,
                  "ultima_medicao": ult["data_medicao"], "total_medicoes": len(meds),
                  "periodo_ini": ult["periodo_ini"], "periodo_fim": ult["periodo_fim"],
                  "itens": itens, "modulos": modulos, "serie": serie,
                  "dimensoes": dimensoes, "analises": analises, "cenarios": cenarios,
                  "cobertura": cobertura, "nao_previstos": nao_previstos,
                  "a_classificar": a_classificar})


@app.post("/api/monitmov/<customer>/upload")
def api_monitmov_upload(customer):
    """Importa o export do D5 (CSV) ou o mesmo conteúdo em JSON. Idempotente:
    regrava a medição inteira daquela data, naquele ambiente."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de subir movimentos.")

    if (f := request.files.get("arquivo")):
        bruto, nome = f.read(), (f.filename or "")
    else:
        bruto, nome = request.get_data(), ""
    if not bruto:
        return _err(400, "Arquivo vazio.")
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
    try:
        body = _csv_movimentos(texto) if ehcsv else json.loads(texto)
    except Exception as e:
        return _err(400, f"{'CSV' if ehcsv else 'JSON'} inválido: {e}")
    if not isinstance(body, dict) or not body.get("medicoes"):
        return _err(400, "Arquivo sem medições.")
    if not q("select 1 from cockpit.clientes where customer=%s", (customer,), one=True):
        return _err(409, f"Cliente {customer} não cadastrado em cockpit.clientes.")

    amb = _ambiente()
    n_med = n_dim = 0
    ultima = None
    for m in body["medicoes"]:
        dt = _data_iso(m.get("data_iso") or m.get("data_medicao"))
        if not dt:
            continue
        dims = m.get("dimensoes") or []
        periodo = m.get("periodo") or (dims[0].get("periodo") if dims else "")
        p_ini, p_fim = _periodo_datas(periodo)
        for a in q("""select id from cockpit.monitmov_medicoes
                       where customer=%s and data_medicao=%s and ambiente=%s""",
                   (customer, dt, amb)):
            execute("delete from cockpit.monitmov_dimensoes where medicao_id=%s", (a["id"],))
            execute("delete from cockpit.monitmov_itens where medicao_id=%s", (a["id"],))
            execute("delete from cockpit.monitmov_medicoes where id=%s", (a["id"],))
        row = q("""insert into cockpit.monitmov_medicoes
                     (customer, ambiente, data_medicao, semana, hora_medicao,
                      periodo_ini, periodo_fim, origem, payload)
                   values (%s,%s,%s,%s,%s,%s,%s,'upload',%s) returning id""",
                (customer, amb, dt, m.get("semana"), m.get("hora_medicao"),
                 p_ini, p_fim,
                 json.dumps({k: v for k, v in m.items() if k != "dimensoes"})), one=True)
        mid = row["id"]
        n_med += 1
        ultima = max(ultima or dt, dt)

        linhas, porAnalise = [], {}
        for x in dims:
            analise = (x.get("analise") or "").strip().upper()
            if not analise:
                continue
            qt = float(x.get("qtde") or 0)
            qd = x.get("qtd_doc")
            linhas.append((mid, customer, amb, dt, analise, x.get("descricao"),
                           x.get("dim1_nome"), x.get("dim1"), x.get("dim2_nome"), x.get("dim2"),
                           x.get("dim3_nome"), x.get("dim3"), x.get("dim4_nome"), x.get("dim4"),
                           x.get("periodo") or periodo, qt,
                           float(qd) if qd not in (None, "") else None))
            ag = porAnalise.setdefault(analise, {"qtde": 0.0, "periodo": x.get("periodo") or periodo})
            ag["qtde"] += qt
        if linhas:
            with db() as c, c.cursor() as cur:
                execute_values(cur, """
                    insert into cockpit.monitmov_dimensoes
                      (medicao_id, customer, ambiente, data_medicao, analise, descricao,
                       dim1_nome, dim1, dim2_nome, dim2, dim3_nome, dim3,
                       dim4_nome, dim4, periodo, qtde, qtd_doc)
                    values %s""", linhas, page_size=200)
            n_dim += len(linhas)
        # itens = um resumo por análise, para os KPIs e o gráfico por módulo
        resumo = []
        for analise, ag in porAnalise.items():
            tab, mod, desc = MOV_ANALISES.get(
                analise, (analise.split("_")[0], "(sem módulo)", analise))
            resumo.append((mid, customer, amb, dt, tab, desc, mod, None,
                           ag["qtde"], None, ag["periodo"]))
        if resumo:
            with db() as c, c.cursor() as cur:
                execute_values(cur, """
                    insert into cockpit.monitmov_itens
                      (medicao_id, customer, ambiente, data_medicao, tabela, descricao,
                       modulo, filtro, quantidade, valor, periodo)
                    values %s""", resumo, page_size=100)
    return _json({"ok": True, "customer": customer, "ambiente": amb,
                  "formato": "csv" if ehcsv else "json", "medicoes": n_med,
                  "dimensoes": n_dim, "ultima_medicao": ultima})


CEN_CAMPOS = ("analise", "dim1", "dim2", "dim3", "dim4", "descricao",
              "esperado", "etapa", "responsavel")


def _cenarios_do_txt(texto):
    """Lê o CENARIOS_MONITOR.TXT — o mesmo arquivo que vai para a \\system\\ do
    Protheus. Uma fonte, dois consumidores: o job TLPP e este painel."""
    fora = []
    for n, linha in enumerate(texto.splitlines(), 1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        p = [c.strip() for c in linha.split(";")]
        if len(p) < 5:
            raise ValueError(f"Linha {n}: esperado ANALISE;DIM1;DIM2;DIM3;DIM4;"
                             f"DESCRICAO;ESPERADO;ETAPA;RESPONSAVEL — veio {len(p)} campo(s).")
        p += [""] * (9 - len(p))
        fora.append({
            "analise": p[0].upper(),
            "dim1": p[1] or "*", "dim2": p[2] or "*",
            "dim3": p[3] or "*", "dim4": p[4] or "*",
            "descricao": p[5] or None,
            "esperado": (p[6] or "S").strip().upper() not in ("N", "NAO", "NÃO", "0", "FALSE"),
            "etapa": p[7] or None, "responsavel": p[8] or None,
        })
    if not fora:
        raise ValueError("Nenhum cenário no arquivo (só comentários?).")
    return fora


@app.get("/api/monitmov/<customer>/cenarios")
def api_monitmov_cenarios(customer):
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    return _json({"ok": True, "customer": customer,
                  "cenarios": q("""select id, analise, dim1, dim2, dim3, dim4, descricao,
                                          esperado, etapa, responsavel, updated_by, updated_at
                                     from cockpit.monitmov_cenarios where customer=%s
                                    order by analise, descricao""", (customer,))})


@app.post("/api/monitmov/<customer>/cenarios")
def api_monitmov_cenarios_salvar(customer):
    """Substitui a lista inteira. O arquivo é a verdade — mesma regra do
    TABELAS_MONITOR.TXT: editar em dois lugares é como as listas divergem."""
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de salvar cenários.")
    if not q("select 1 from cockpit.clientes where customer=%s", (customer,), one=True):
        return _err(409, f"Cliente {customer} não cadastrado em cockpit.clientes.")
    b = request.get_json(silent=True) or {}
    if isinstance(b.get("texto"), str):
        try:
            cens = _cenarios_do_txt(b["texto"])
        except Exception as e:
            return _err(400, str(e))
    elif isinstance(b.get("cenarios"), list):
        cens = [{k: c.get(k) for k in CEN_CAMPOS} for c in b["cenarios"]]
    else:
        return _err(400, "Envie o conteúdo do CENARIOS_MONITOR.TXT em 'texto' "
                         "ou a lista em 'cenarios'.")
    execute("delete from cockpit.monitmov_cenarios where customer=%s", (customer,))
    gravados = 0
    for c in cens:
        if not (c.get("analise") or "").strip():
            continue
        execute("""insert into cockpit.monitmov_cenarios
                     (customer, analise, dim1, dim2, dim3, dim4, descricao,
                      esperado, etapa, responsavel, updated_by, updated_at)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                   on conflict (customer, analise, dim1, dim2, dim3, dim4)
                   do update set descricao=excluded.descricao,
                                 esperado=excluded.esperado, etapa=excluded.etapa,
                                 responsavel=excluded.responsavel,
                                 updated_by=excluded.updated_by, updated_at=now()""",
                (customer, (c["analise"] or "").strip().upper(),
                 (c.get("dim1") or "*").strip(), (c.get("dim2") or "*").strip(),
                 (c.get("dim3") or "*").strip(), (c.get("dim4") or "*").strip(),
                 c.get("descricao"), bool(c.get("esperado", True)),
                 c.get("etapa"), c.get("responsavel"), current_user()))
        gravados += 1
    return _json({"ok": True, "customer": customer, "cenarios": gravados})


@app.delete("/api/monitmov/<customer>/cenarios")
def api_monitmov_cenarios_remover(customer):
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de remover cenários.")
    execute("delete from cockpit.monitmov_cenarios where customer=%s", (customer,))
    return _json({"ok": True, "customer": customer, "removidos": True})


# ── GAPs (aba "GAPs") ───────────────────────────────────────────────────────
# GAP = ticket com a tag EXATA "GAP" em cockpit.ticket_tags. Existe também o
# campo tipo_atividade='GAP', que quase coincide (630 nos dois, 15 só em cada) —
# a tag é a fonte da verdade aqui, por decisão de 11/08/2026.
DECISOES = ("aprovar", "segunda_fase", "contorno", "entendimento_projeto",
            "recusar", "pendente")

SQL_GAPS = """
  select t.uuid_ticket, t.raw->>'id' as id, t.titulo, t.status_tasks,
         t.status_temporario, t.etapa_gap, t.classificacao_gap, t.produto,
         t.competencia, t.projeto, t.prioridade, t.time_estimate, t.aging_dias,
         t.due_date, t.atrasado, t.bloqueado, t.user_assigned,
         u.nome as responsavel_nome, t.assigned_customer, t.observador,
         t.ult_ocorr_texto, t.ult_ocorr_data, t.ult_ocorr_autor, t.updated_at,
         d.decisao, d.estimativa as decisao_estimativa, d.observacao as decisao_obs,
         d.decided_by, d.decided_at,
         (a.uuid_ticket is not null) as tem_alinhamento,
         coalesce((select array_agg(g2.raw_tag order by g2.raw_tag)
                     from cockpit.ticket_tags g2
                    where g2.uuid_ticket = t.uuid_ticket
                      and g2.raw_tag <> 'GAP'), '{}') as tags
    from cockpit.tickets t
    join cockpit.ticket_tags g
      on g.uuid_ticket = t.uuid_ticket and g.raw_tag = 'GAP'
    left join cockpit.usuarios u on u.codigo = t.user_assigned
    left join cockpit.decisoes d on d.uuid_ticket = t.uuid_ticket
    left join cockpit.gap_alinhamentos a on a.uuid_ticket = t.uuid_ticket
   where t.customer = %s
   order by t.time_estimate desc nulls last, t.titulo
"""


def _customer_do_ticket(uuid):
    r = q("select customer from cockpit.tickets where uuid_ticket=%s", (uuid,), one=True)
    return r["customer"] if r else None


def _guarda_ticket(uuid):
    """Autoriza pelo cliente DONO do ticket — nunca pelo que o front mandou."""
    cust = _customer_do_ticket(uuid)
    if not cust:
        return _err(404, "GAP não encontrado."), None
    return deny_customer(cust), cust


@app.get("/api/gaps/<customer>")
def api_gaps(customer):
    if (r := require_auth()):
        return r
    if (d := deny_customer(customer)):
        return d
    gaps = q(SQL_GAPS, (customer,))
    horas = sum(float(g["time_estimate"] or 0) for g in gaps)
    return _json({"ok": True, "customer": customer, "total": len(gaps),
                  "horas_estimadas": horas, "gaps": gaps})


@app.get("/api/gaps/ticket/<uuid>")
def api_gap_detalhe(uuid):
    if (r := require_auth()):
        return r
    negado, _ = _guarda_ticket(uuid)
    if negado:
        return negado
    t = q("""select t.uuid_ticket, t.raw->>'id' as id, t.titulo, t.descricao, t.cliente,
                    t.status_tasks, t.etapa_gap, t.classificacao_gap, t.produto,
                    t.competencia, t.time_estimate, t.due_date, t.aging_dias,
                    t.user_assigned, u.nome as responsavel_nome, t.assigned_customer,
                    t.observador, t.updated_at, t.synced_at
               from cockpit.tickets t
               left join cockpit.usuarios u on u.codigo = t.user_assigned
              where t.uuid_ticket = %s""", (uuid,), one=True)
    tags = q("""select raw_tag, dimensao, valor from cockpit.ticket_tags
                 where uuid_ticket=%s order by dimensao_idx nulls last, raw_tag""", (uuid,))
    ocorr = q("""select uuid_history, tipo, details, autor, occurred_at
                   from cockpit.ocorrencias where uuid_ticket=%s
                  order by occurred_at desc nulls last limit 30""", (uuid,))
    dec = q("select * from cockpit.decisoes where uuid_ticket=%s", (uuid,), one=True)
    ali = q("select * from cockpit.gap_alinhamentos where uuid_ticket=%s", (uuid,), one=True)
    return _json({"ok": True, "ticket": t, "tags": tags, "ocorrencias": ocorr,
                  "decisao": dec, "alinhamento": ali})


@app.post("/api/gaps/ticket/<uuid>/decisao")
def api_gap_decisao(uuid):
    """Grava a decisão LOCAL (cockpit.decisoes). Não toca no Tasks SC."""
    if (r := require_auth()):
        return r
    negado, _ = _guarda_ticket(uuid)
    if negado:
        return negado
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de decidir.")
    b = request.get_json(silent=True) or {}
    decisao = (b.get("decisao") or "pendente").strip()
    if decisao not in DECISOES:
        return _err(400, f"Decisão inválida: {decisao}")
    est = b.get("estimativa")
    est = float(est) if est not in (None, "") else None
    execute("""insert into cockpit.decisoes
                 (uuid_ticket, decisao, estimativa, observacao, classe,
                  decided_by, decided_at, updated_at)
               values (%s,%s,%s,%s,%s,%s, now(), now())
               on conflict (uuid_ticket) do update set
                 decisao=excluded.decisao, estimativa=excluded.estimativa,
                 observacao=excluded.observacao, classe=excluded.classe,
                 decided_by=excluded.decided_by, decided_at=now(), updated_at=now()""",
            (uuid, decisao, est, b.get("observacao"), b.get("classe"), current_user()))
    return _json({"ok": True, "uuid_ticket": uuid, "decisao": decisao})


@app.post("/api/gaps/ticket/<uuid>/alinhamento")
def api_gap_alinhamento(uuid):
    """Alinhamento comercial do GAP. ATENÇÃO: argumentacao_interna é INTERNA —
    não expor ao cliente em e-mail nem em painel compartilhado."""
    if (r := require_auth()):
        return r
    negado, cust = _guarda_ticket(uuid)
    if negado:
        return negado
    if effective_user() != current_user():
        return _err(409, "Saia da simulação ('ver como') antes de gravar.")
    b = request.get_json(silent=True) or {}
    tid = q("select raw->>'id' as id from cockpit.tickets where uuid_ticket=%s",
            (uuid,), one=True)
    execute("""insert into cockpit.gap_alinhamentos
                 (uuid_ticket, task_id, customer, questionamento_cliente,
                  argumentacao_interna, alinhamento_reuniao, retorno_cliente,
                  created_by, updated_by, updated_at)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
               on conflict (uuid_ticket) do update set
                 questionamento_cliente=excluded.questionamento_cliente,
                 argumentacao_interna=excluded.argumentacao_interna,
                 alinhamento_reuniao=excluded.alinhamento_reuniao,
                 retorno_cliente=excluded.retorno_cliente,
                 updated_by=excluded.updated_by, updated_at=now()""",
            (uuid, (tid or {}).get("id"), cust, b.get("questionamento_cliente"),
             b.get("argumentacao_interna"), b.get("alinhamento_reuniao"),
             b.get("retorno_cliente"), current_user(), current_user()))
    return _json({"ok": True, "uuid_ticket": uuid})


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
