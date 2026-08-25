#!/bin/bash
# Publicar Projetos TOTVS SC — add + commit + push (duplo-clique no Finder).
# Roda na pasta do projeto e dispara o deploy automatico do Vercel.

cd "$(dirname "$0")" || exit 1
echo "==> Pasta: $(pwd)"

if [ ! -d ".git" ]; then
  echo "ERRO: esta pasta nao e um repositorio git (.git nao encontrado)."
  read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
  exit 1
fi

# Limpa locks presos (o Cowork/ponte nao consegue apagar sozinho)
find .git -name '*.lock' -delete 2>/dev/null

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
echo "==> Branch: $BRANCH"

# Gate: o Flask e um arquivo so. Se ele nao compila, o site inteiro cai.
echo "==> Verificando sintaxe (python3 -m py_compile api/index.py)..."
if ! python3 -m py_compile api/index.py; then
  echo ""
  echo "ABORTADO: api/index.py nao compila. Nada foi publicado."
  read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
  exit 1
fi
rm -rf api/__pycache__ 2>/dev/null
echo "    sintaxe OK."

# Repo PUBLICO: barra HTML de cliente indo junto por engano.
if git status --porcelain | grep -qiE '^\?\?.*(status|painel|cliente).*\.html$'; then
  echo ""
  echo "ATENCAO: ha HTML novo com cara de dado de cliente:"
  git status --porcelain | grep -iE '^\?\?.*(status|painel|cliente).*\.html$'
  echo "Este repo e PUBLICO — painel de cliente vai para cockpit.paineis_cliente,"
  echo "pela aba Transicao, nao para o git."
  read -r -p "Publicar mesmo assim? (s/N) " OK
  [ "$OK" = "s" ] || [ "$OK" = "S" ] || { echo "Cancelado."; exit 1; }
fi

MSG="${1:-projetos: ajustes $(date '+%Y-%m-%d %H:%M')}"

echo "==> git add -A"
git add -A

if git diff --cached --quiet; then
  echo "Nada novo para commitar. Tentando apenas o push..."
else
  echo "==> git commit -m \"$MSG\""
  git commit -m "$MSG"
fi

echo "==> git push origin $BRANCH"
if git push origin "$BRANCH"; then
  echo ""
  echo "OK! Push concluido. O Vercel vai iniciar o deploy automaticamente."
  echo "Acompanhe em: https://vercel.com  (projeto projetos-totvs-sc)"
else
  echo ""
  echo "FALHA no push. Se pedir, rode antes:  git pull --rebase origin $BRANCH"
fi

echo ""
read -n 1 -s -r -p "Pressione qualquer tecla para fechar..."
