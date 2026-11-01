# ── 前端构建 ──────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

# 使用 pnpm 9（与 pnpm-lock.yaml 的 lockfileVersion 9 匹配）
RUN npm install -g pnpm@9

WORKDIR /build

# 先安装依赖，利用 layer 缓存
COPY app/frontend/package.json app/frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 再复制源码并构建（vite build → dist）
COPY app/frontend/ ./
ENV VITE_API_BASE_URL=/
RUN pnpm build

# ── 后端运行时（含 dockerd，用于 Docker-in-Docker 沙箱）────
FROM python:3.12-slim AS backend

# 容器内无 systemd：禁止 apt 安装时自动启动服务
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d

# 安装 Docker Engine（dockerd + containerd + docker CLI）
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY app/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 后端源码（含 main.py、alembic/、alembic.ini、core/、routers/ 等）
COPY app/backend/ ./

# 前端静态产物 → 同源单镜像托管
COPY --from=frontend-builder /build/dist ./static

# dockerd 配置（数据目录挂到卷）+ 启动脚本（先起 dockerd 再起 uvicorn）
COPY docker/daemon.json /etc/docker/daemon.json
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV STATIC_DIR=/app/static \
    PORT=8080

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]