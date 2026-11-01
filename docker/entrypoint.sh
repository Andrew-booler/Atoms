#!/bin/sh
set -e

# dockerd 数据目录（来自挂载卷，避免 rootfs 每次重建丢镜像）
mkdir -p /data/docker

# 后台启动 dockerd（DinD），日志落盘便于排障
dockerd > /var/log/dockerd.log 2>&1 &
dockerd_pid=$!

# 等待 docker daemon 就绪（最多 60 秒）
ready=0
for _ in $(seq 1 60); do
  if docker info >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "dockerd 启动失败" >&2
  tail -n 100 /var/log/dockerd.log >&2
  exit 1
fi

echo "dockerd 就绪"

# 数据库迁移 + 启动应用（同源托管前端静态资源）
alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"