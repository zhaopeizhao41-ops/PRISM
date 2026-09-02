# ---------- Stage 1: 前端构建 ----------
FROM node:20-alpine AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# locales 位于 frontend/../locales，构建时按相同相对路径复制（i18n 别名 @locales 与相对导入均依赖它）
COPY locales/ ../locales/
RUN npm run build

# ---------- Stage 2: 运行时 ----------
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PRISM_FRONTEND_DIST=/app/frontend/dist

WORKDIR /app

# 先复制依赖描述文件以利用缓存
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev

# 复制源码与前端产物
COPY backend/ ./backend/
COPY locales/ ./locales/
COPY --from=frontend-build /build/dist ./frontend/dist/

EXPOSE 5001

WORKDIR /app/backend
# 单 worker 多线程：TaskManager 为进程内存态，多 worker 会导致任务轮询错位
CMD ["uv", "run", "--no-dev", "gunicorn", \
     "--bind", "0.0.0.0:5001", \
     "--workers", "1", "--threads", "8", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "wsgi:app"]
