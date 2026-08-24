#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
用法:
  curl -fsSL http://<web-host>/monitor/categraf/install.sh | sudo bash -s -- \
    --base-url http://<web-host>/monitor/categraf \
    --n9e http://<n9e-host>:17000 \
    --region <region> [选项]

必填:
  --base-url  安装资源所在目录，例如 http://10.0.0.10/monitor/categraf
  --n9e       n9e HTTP 地址，例如 http://10.0.0.10:17000
  --region    地域标签，例如 idc-hz、aliyun-hz、tencent-sh

可选:
  --env       环境标签，默认 prod
  --team      团队标签，默认 ops
  --service   服务标签，默认 infra
  --role      角色标签，Docker 主机默认 docker-host，非 Docker 主机建议 linux-host
  --hostname  上报主机名，默认自动生成 当前hostname-主IP
  --image     Categraf 镜像，默认 flashcatcloud/categraf:latest
  --dir       安装目录，默认 /opt/categraf
  --no-docker 不挂载 Docker socket，适用于非 Docker 主机
  --profile   采集模板，可重复或逗号分隔，例如 linux-basic,docker-host,mysql-rds

应用采集可选:
  --mysql-address     MySQL/RDS 地址，例如 rm-xxx.mysql.rds.aliyuncs.com:3306
  --mysql-user        MySQL 只读监控账号
  --mysql-password    MySQL 只读监控账号密码
  --mysql-parameters  MySQL 连接参数，默认 tls=false
  --redis-address     Redis 地址，例如 r-xxx.redis.rds.aliyuncs.com:6379
  --redis-username    Redis 用户名，可选
  --redis-password    Redis 密码，可选
  --nginx-status-url  Nginx stub_status 地址，例如 http://127.0.0.1/nginx_status
EOF
}

detect_primary_ip() {
  local ip_addr=""

  if command -v ip >/dev/null 2>&1; then
    ip_addr="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')" || true
  fi

  if [[ -z "$ip_addr" ]] && command -v hostname >/dev/null 2>&1; then
    ip_addr="$(hostname -I 2>/dev/null | tr ' ' '\n' | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ && $0 !~ /^127\./ {print; exit}')" || true
  fi

  printf '%s' "$ip_addr"
}

sanitize_ident_part() {
  printf '%s' "$1" | sed -E 's/[^A-Za-z0-9_.-]+/-/g; s/^[.-]+//; s/[.-]+$//'
}

default_client_hostname() {
  local base_name primary_ip safe_base safe_ip

  base_name="$(hostname 2>/dev/null || echo unknown-host)"
  primary_ip="$(detect_primary_ip)"
  safe_base="$(sanitize_ident_part "$base_name")"

  if [[ -n "$primary_ip" ]]; then
    safe_ip="$(sanitize_ident_part "${primary_ip//./-}")"
    printf '%s-%s\n' "${safe_base:-unknown-host}" "$safe_ip"
  else
    printf '%s\n' "${safe_base:-unknown-host}"
  fi
}

BASE_URL="${INSTALL_BASE_URL:-}"
N9E_URL="${N9E_URL:-}"
REGION="${REGION:-}"
ENV_LABEL="${ENV_LABEL:-prod}"
TEAM="${TEAM:-ops}"
SERVICE="${SERVICE:-infra}"
ROLE="${ROLE:-docker-host}"
ROLE_PROVIDED=0
CLIENT_HOSTNAME="${CLIENT_HOSTNAME:-}"
CATEGRAF_IMAGE="${CATEGRAF_IMAGE:-flashcatcloud/categraf:latest}"
INSTALL_DIR="${INSTALL_DIR:-/opt/categraf}"
MOUNT_DOCKER=1
PROFILE_LIST="${PROFILE_LIST:-}"
MYSQL_ADDRESS="${MYSQL_ADDRESS:-}"
MYSQL_USER="${MYSQL_USER:-}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_PARAMETERS="${MYSQL_PARAMETERS:-tls=false}"
REDIS_ADDRESS="${REDIS_ADDRESS:-}"
REDIS_USERNAME="${REDIS_USERNAME:-}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
NGINX_STATUS_URL="${NGINX_STATUS_URL:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --n9e)
      N9E_URL="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --env)
      ENV_LABEL="${2:-}"
      shift 2
      ;;
    --team)
      TEAM="${2:-}"
      shift 2
      ;;
    --service)
      SERVICE="${2:-}"
      shift 2
      ;;
    --role)
      ROLE="${2:-}"
      ROLE_PROVIDED=1
      shift 2
      ;;
    --hostname)
      CLIENT_HOSTNAME="${2:-}"
      shift 2
      ;;
    --image)
      CATEGRAF_IMAGE="${2:-}"
      shift 2
      ;;
    --dir)
      INSTALL_DIR="${2:-}"
      shift 2
      ;;
    --no-docker)
      MOUNT_DOCKER=0
      shift
      ;;
    --profile)
      PROFILE_LIST="${PROFILE_LIST:+$PROFILE_LIST,}${2:-}"
      shift 2
      ;;
    --mysql-address)
      MYSQL_ADDRESS="${2:-}"
      shift 2
      ;;
    --mysql-user)
      MYSQL_USER="${2:-}"
      shift 2
      ;;
    --mysql-password)
      MYSQL_PASSWORD="${2:-}"
      shift 2
      ;;
    --mysql-parameters)
      MYSQL_PARAMETERS="${2:-}"
      shift 2
      ;;
    --redis-address)
      REDIS_ADDRESS="${2:-}"
      shift 2
      ;;
    --redis-username)
      REDIS_USERNAME="${2:-}"
      shift 2
      ;;
    --redis-password)
      REDIS_PASSWORD="${2:-}"
      shift 2
      ;;
    --nginx-status-url)
      NGINX_STATUS_URL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$BASE_URL" || -z "$N9E_URL" || -z "$REGION" ]]; then
  echo "缺少必填参数 --base-url、--n9e 或 --region" >&2
  usage
  exit 1
fi

if [[ "$MOUNT_DOCKER" -eq 0 && "$ROLE_PROVIDED" -eq 0 ]]; then
  ROLE="linux-host"
fi

if [[ "$BASE_URL" != http://* && "$BASE_URL" != https://* ]]; then
  echo "--base-url 必须包含 http:// 或 https://" >&2
  exit 1
fi

if [[ "$N9E_URL" != http://* && "$N9E_URL" != https://* ]]; then
  echo "--n9e 必须包含 http:// 或 https://" >&2
  exit 1
fi

if [[ -z "$CLIENT_HOSTNAME" ]]; then
  CLIENT_HOSTNAME="$(default_client_hostname)"
fi

has_profile() {
  local name="$1"
  [[ ",$PROFILE_LIST," == *",$name,"* ]]
}

toml_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 docker，请先安装 Docker" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "未找到 docker compose 或 docker-compose，请先安装 Docker Compose" >&2
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  download() { curl -fsSL "$1" -o "$2"; }
elif command -v wget >/dev/null 2>&1; then
  download() { wget -q "$1" -O "$2"; }
else
  echo "未找到 curl 或 wget" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
N9E_HTTP="${N9E_URL%/}"
N9E_HOSTPORT="${N9E_HTTP#http://}"
N9E_HOSTPORT="${N9E_HOSTPORT#https://}"
N9E_HOSTPORT="${N9E_HOSTPORT%%/*}"
N9E_RPC="${N9E_HOSTPORT%:*}:20090"

if [[ -z "$INSTALL_DIR" || "$INSTALL_DIR" == "/" ]]; then
  echo "安装目录无效" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
install_parent="$(dirname "$INSTALL_DIR")"
install_name="$(basename "$INSTALL_DIR")"
mkdir -p "$install_parent"
staged_dir="$(mktemp -d "${install_parent}/.${install_name}.staging.XXXXXX")"
backup_dir="${INSTALL_DIR}.backup.$(date +%s)"
backup_created=0
install_activated=0

rollback_install() {
  if [[ "$install_activated" -eq 1 ]]; then
    rm -rf "$INSTALL_DIR"
  fi
  if [[ "$backup_created" -eq 1 && -d "$backup_dir" ]]; then
    echo "新配置启动失败，正在恢复上一版本" >&2
    mv "$backup_dir" "$INSTALL_DIR"
    if ! (cd "$INSTALL_DIR" && "${COMPOSE[@]}" up -d); then
      echo "上一版本恢复后启动失败，请人工检查 $INSTALL_DIR" >&2
    fi
  fi
}

cleanup() {
  local exit_code=$?
  if [[ "$exit_code" -ne 0 ]]; then
    rollback_install
  fi
  rm -rf "$tmp_dir"
  if [[ -n "$staged_dir" && -d "$staged_dir" ]]; then
    rm -rf "$staged_dir"
  fi
  exit "$exit_code"
}
trap cleanup EXIT

download "$BASE_URL/categraf-client.tar.gz" "$tmp_dir/categraf-client.tar.gz"
download "$BASE_URL/SHA256SUMS" "$tmp_dir/SHA256SUMS"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$tmp_dir" && sha256sum -c SHA256SUMS)
else
  echo "未找到 sha256sum，跳过安装包校验" >&2
fi

mkdir -p "$tmp_dir/pkg"
tar -xzf "$tmp_dir/categraf-client.tar.gz" -C "$tmp_dir/pkg"

cp -a "$tmp_dir/pkg/conf" "$staged_dir/conf"
cp "$tmp_dir/pkg/docker-compose.yml" "$staged_dir/docker-compose.yml"

cat > "$staged_dir/.env" <<EOF
TZ=Asia/Shanghai
CATEGRAF_IMAGE=$CATEGRAF_IMAGE
HOSTNAME=$CLIENT_HOSTNAME
EOF

CONFIG="$staged_dir/conf/config.toml"
sed -i \
  -e "s|http://replace-n9e-address:17000|$N9E_HTTP|g" \
  -e "s|replace-n9e-address:20090|$N9E_RPC|g" \
  -e "s|region = \"replace-region\"|region = \"$REGION\"|g" \
  -e "s|env = \"prod\"|env = \"$ENV_LABEL\"|g" \
  -e "s|team = \"ops\"|team = \"$TEAM\"|g" \
  -e "s|service = \"infra\"|service = \"$SERVICE\"|g" \
  -e "s|role = \"docker-host\"|role = \"$ROLE\"|g" \
  "$CONFIG"

if [[ "$MOUNT_DOCKER" -eq 1 && ! -S /var/run/docker.sock ]]; then
  echo "未找到 /var/run/docker.sock，将按非 Docker 主机部署" >&2
  MOUNT_DOCKER=0
fi

if [[ "$MOUNT_DOCKER" -eq 0 ]]; then
  rm -rf "$staged_dir/conf/input.docker"
  sed -i '/docker.sock/d' "$staged_dir/docker-compose.yml"
fi

if has_profile "mysql-rds" || has_profile "mysql"; then
  if [[ -n "$MYSQL_ADDRESS" && -n "$MYSQL_USER" ]]; then
    mkdir -p "$staged_dir/conf/input.mysql"
    cat > "$staged_dir/conf/input.mysql/mysql.toml" <<EOF
[[instances]]
address = "$(toml_escape "$MYSQL_ADDRESS")"
username = "$(toml_escape "$MYSQL_USER")"
password = "$(toml_escape "$MYSQL_PASSWORD")"
parameters = "$(toml_escape "$MYSQL_PARAMETERS")"
extra_status_metrics = true
gather_schema_size = true
gather_replica_status = true
timeout_seconds = 3
labels = { instance="$(toml_escape "$MYSQL_ADDRESS")" }
EOF
  else
    echo "已选择 mysql-rds/mysql Profile，但缺少 --mysql-address 或 --mysql-user" >&2
    exit 1
  fi
fi

if has_profile "redis" || has_profile "redis-cloud"; then
  if [[ -n "$REDIS_ADDRESS" ]]; then
    mkdir -p "$staged_dir/conf/input.redis"
    cat > "$staged_dir/conf/input.redis/redis.toml" <<EOF
[[instances]]
address = "$(toml_escape "$REDIS_ADDRESS")"
username = "$(toml_escape "$REDIS_USERNAME")"
password = "$(toml_escape "$REDIS_PASSWORD")"
pool_size = 2
gather_slowlog = false
interval_times = 1
labels = { instance="$(toml_escape "$REDIS_ADDRESS")" }
EOF
  else
    echo "已选择 redis/redis-cloud Profile，但缺少 --redis-address" >&2
    exit 1
  fi
fi

if has_profile "nginx"; then
  if [[ -n "$NGINX_STATUS_URL" ]]; then
    mkdir -p "$staged_dir/conf/input.nginx"
    cat > "$staged_dir/conf/input.nginx/nginx.toml" <<EOF
[mappings]
"$(toml_escape "$NGINX_STATUS_URL")" = { service = "$(toml_escape "$SERVICE")" }

[[instances]]
urls = [
  "$(toml_escape "$NGINX_STATUS_URL")"
]
labels = { instance="$(toml_escape "$NGINX_STATUS_URL")" }
response_timeout = "5s"
EOF
  else
    echo "已选择 nginx Profile，但缺少 --nginx-status-url" >&2
    exit 1
  fi
fi

chmod -R a+rX "$staged_dir/conf"

if ! (cd "$staged_dir" && "${COMPOSE[@]}" config -q); then
  echo "Categraf Compose 配置校验失败，未修改当前运行版本" >&2
  exit 1
fi

if [[ -d "$INSTALL_DIR" ]]; then
  mv "$INSTALL_DIR" "$backup_dir"
  backup_created=1
fi
mv "$staged_dir" "$INSTALL_DIR"
staged_dir=""
install_activated=1

if ! (cd "$INSTALL_DIR" && "${COMPOSE[@]}" up -d); then
  echo "Categraf 新配置启动失败" >&2
  exit 1
fi

if ! (cd "$INSTALL_DIR" && "${COMPOSE[@]}" ps --services --filter status=running) | grep -q .; then
  echo "Categraf 新配置未检测到运行中的服务" >&2
  exit 1
fi

install_activated=0
if [[ "$backup_created" -eq 1 ]]; then
  rm -rf "$backup_dir"
  backup_created=0
fi

echo "Categraf 已部署到 $INSTALL_DIR"
echo "n9e HTTP: $N9E_HTTP"
echo "n9e RPC:  $N9E_RPC"
echo "region:   $REGION"
echo "hostname: $CLIENT_HOSTNAME"
