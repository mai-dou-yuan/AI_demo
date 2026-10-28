#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PROJECT_ROOT="$PWD"
ENV_PREFIX="$PROJECT_ROOT/.conda/ai-brain"
MODE="${INSTALL_NETWORK:-auto}"
PROXY_URL="${INSTALL_PROXY:-http://127.0.0.1:10808}"
case "$MODE" in auto|direct|mirror|proxy) ;; *) echo 'INSTALL_NETWORK 必须为 auto/direct/mirror/proxy' >&2; exit 1 ;; esac
command -v conda >/dev/null || { echo '请先安装并初始化 conda。' >&2; exit 1; }
command -v curl >/dev/null || { echo '需要 curl 来检查下载源。' >&2; exit 1; }
mkdir -p .cache/conda/pkgs .cache/npm .cache/pip
export CONDA_PKGS_DIRS="$PROJECT_ROOT/.cache/conda/pkgs"
export PIP_CACHE_DIR="$PROJECT_ROOT/.cache/pip"
export npm_config_cache="$PROJECT_ROOT/.cache/npm"
# 仅影响本脚本，不修改用户的 shell、conda、pip 或 npm 全局配置。
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
unset npm_config_proxy npm_config_https_proxy NPM_CONFIG_PROXY NPM_CONFIG_HTTPS_PROXY PIP_PROXY
export no_proxy=localhost,127.0.0.1,::1
export NO_PROXY="$no_proxy"

probe() {
  local route="$1" url="$2"
  if [[ "$route" == proxy ]]; then
    curl -fsSLI --proxy "$PROXY_URL" --connect-timeout 5 --max-time 12 "$url" >/dev/null 2>&1
  else
    curl -fsSLI --noproxy '*' --connect-timeout 5 --max-time 12 "$url" >/dev/null 2>&1
  fi
}

choose() {
  local direct_url="$1" mirror_url="$2" route url
  local routes=(direct mirror proxy)
  [[ "$MODE" == auto ]] || routes=("$MODE")
  for route in "${routes[@]}"; do
    url="$direct_url"
    [[ "$route" != mirror ]] || url="$mirror_url"
    if probe "$route" "$url"; then printf '%s\n' "$route"; return 0; fi
  done
  echo '下载源均不可达，请检查网络或本地代理；已安装内容会保留。' >&2
  return 1
}

set_route() {
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
  if [[ "$1" == proxy ]]; then
    export http_proxy="$PROXY_URL" https_proxy="$PROXY_URL"
    export HTTP_PROXY="$PROXY_URL" HTTPS_PROXY="$PROXY_URL"
  fi
}

route=$(choose 'https://conda.anaconda.org/conda-forge/linux-64/repodata.json' 'https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/linux-64/repodata.json')
set_route "$route"
channel=https://conda.anaconda.org/conda-forge
[[ "$route" != mirror ]] || channel=https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
echo "conda 下载方式：$route"
action=create
[[ ! -d "$ENV_PREFIX/conda-meta" ]] || action=install
conda "$action" --prefix "$ENV_PREFIX" --override-channels -c "$channel" python=3.11 nodejs=24 pip -y
export PATH="$ENV_PREFIX/bin:$PATH"
hash -r

# 每类软件源单独检查，避免强制所有下载都走代理。
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
route=$(choose 'https://pypi.org/simple/fastapi/' 'https://pypi.tuna.tsinghua.edu.cn/simple/fastapi/')
set_route "$route"
index=https://pypi.org/simple
[[ "$route" != mirror ]] || index=https://pypi.tuna.tsinghua.edu.cn/simple
echo "pip 下载方式：$route"
python -m pip install --index-url "$index" -r requirements.txt
python -m pip check

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
route=$(choose 'https://registry.npmjs.org/create-next-app' 'https://registry.npmmirror.com/create-next-app')
set_route "$route"
export npm_config_registry=https://registry.npmjs.org
[[ "$route" != mirror ]] || export npm_config_registry=https://registry.npmmirror.com
echo "npm 下载方式：$route"
if [[ ! -e frontend/package.json ]]; then
  npx --yes create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --use-npm --import-alias '@/*' --yes --disable-git
fi
cd frontend
if [[ -e package-lock.json ]]; then npm ci; else npm install; fi
npm install lucide-react motion
if [[ ! -e components.json ]]; then npx --yes shadcn@latest init --defaults; fi
npm run build
cd "$PROJECT_ROOT"
python -m pip freeze > requirements.lock.txt
conda list --prefix "$ENV_PREFIX" --explicit > .cache/conda-explicit.txt
python -c "import fastapi, langgraph, openai, pymupdf, chromadb, pptx, aiosqlite; from langgraph.checkpoint.sqlite import SqliteSaver; print('后端关键依赖导入成功')"
printf '\n安装完成。激活环境：conda activate "%s"\n' "$ENV_PREFIX"
echo '外部 API 和 SMTP 仍需单独配置；项目业务功能尚待开发。'
