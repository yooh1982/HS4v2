#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)"

echo "[*] Project root: $ROOT_DIR"
echo "[*] Ensuring required directories..."
mkdir -p install
mkdir -p frontend/src
mkdir -p backend/app

# Host persistent data/log paths
mkdir -p data/logs/backend
mkdir -p data/logs/postgres
mkdir -p data/db/postgres

echo "[*] Writing .env..."
cat > .env <<'ENV'
# Host ports (avoid conflicts)
DB_PORT=15432
API_PORT=18000
WEB_PORT=15173

# Postgres
POSTGRES_DB=iolist
POSTGRES_USER=iolist
POSTGRES_PASSWORD=iolistpass

# CORS / Frontend API base
CORS_ORIGINS=http://localhost:15173

# Backend log file (inside container; bind-mounted to host ./data/logs)
BACKEND_LOG_FILE=/data/logs/backend/backend.log
ENV

echo "[*] Writing docker-compose.yml..."
cat > docker-compose.yml <<'YAML'
services:
  db:
    image: postgres:16
    container_name: dp-manager-db
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-iolist}
      POSTGRES_USER: ${POSTGRES_USER:-iolist}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-iolistpass}
      TZ: Asia/Seoul
    ports:
      - "${DB_PORT:-15432}:5432"
    volumes:
      # DB data persists on host
      - ./data/db/postgres:/var/lib/postgresql/data
      # Postgres logs persist on host
      - ./data/logs/postgres:/var/log/postgresql
    command: >
      postgres
      -c logging_collector=on
      -c log_destination=stderr
      -c log_directory=/var/log/postgresql
      -c log_filename=postgresql-%Y-%m-%d_%H%M%S.log
      -c log_rotation_age=1d
      -c log_rotation_size=0
      -c log_statement=none
      -c log_min_duration_statement=-1
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-iolist} -d ${POSTGRES_DB:-iolist}"]
      interval: 5s
      timeout: 5s
      retries: 20

  backend:
    build:
      context: ./backend
    container_name: dp-manager-backend
    environment:
      TZ: Asia/Seoul
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-iolist}:${POSTGRES_PASSWORD:-iolistpass}@db:5432/${POSTGRES_DB:-iolist}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:15173}
      LOG_FILE: ${BACKEND_LOG_FILE:-/data/logs/backend/backend.log}
    ports:
      - "${API_PORT:-18000}:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app
      # 모든 로그는 호스트에서 확인 가능해야 함
      - ./data/logs:/data/logs
      # 향후 업로드/산출물(예: DP XML)도 호스트에 남기고 싶으면 사용
      - ./data:/data
    command: >
      uvicorn app.main:app
      --host 0.0.0.0
      --port 8000
      --reload

  frontend:
    build:
      context: ./frontend
    container_name: dp-manager-frontend
    environment:
      TZ: Asia/Seoul
      VITE_API_BASE_URL: "http://localhost:${API_PORT:-18000}"
    ports:
      - "${WEB_PORT:-15173}:5173"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: >
      sh -lc "npm install && npm run dev -- --host 0.0.0.0 --port 5173"
YAML

echo "[*] Writing backend files..."
cat > backend/Dockerfile <<'DOCKER'
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
DOCKER

cat > backend/requirements.txt <<'REQ'
fastapi==0.115.0
uvicorn[standard]==0.30.6
SQLAlchemy==2.0.34
psycopg[binary]==3.2.2
python-multipart==0.0.9
pydantic==2.9.2
REQ

cat > backend/app/__init__.py <<'PY'
# empty
PY

cat > backend/app/db.py <<'PY'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def db_ping() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
PY

cat > backend/app/main.py <<'PY'
import os
import logging
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from .db import db_ping


def setup_logging() -> None:
    log_file = os.getenv("LOG_FILE", "/data/logs/backend/backend.log")
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 중복 핸들러 방지(uvicorn reload 환경)
    if root.handlers:
        return

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)


setup_logging()
logger = logging.getLogger("dp-manager")

app = FastAPI(title="DP Manager API", version="0.1.0")

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:15173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    ok = db_ping()
    logger.info("health check db=%s", ok)
    return {"ok": True, "db": ok}


@app.post("/upload/iolist")
async def upload_iolist(file: UploadFile = File(...)):
    # TODO: 여기서 엑셀 파싱 + 검증 + DP XML 생성 로직으로 확장
    content = await file.read()
    logger.info("uploaded file=%s type=%s size=%d", file.filename, file.content_type, len(content))
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "message": "uploaded (not processed yet)"
    }
PY

echo "[*] Writing frontend files..."
cat > frontend/Dockerfile <<'DOCKER'
FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json
RUN npm install

COPY . /app

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
DOCKER

cat > frontend/package.json <<'JSON'
{
  "name": "dp-manager-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 0.0.0.0 --port 5173"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.5.4",
    "vite": "^5.4.3",
    "@vitejs/plugin-react": "^4.3.1"
  }
}
JSON

cat > frontend/vite.config.ts <<'TS'
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173
  }
});
TS

cat > frontend/tsconfig.json <<'JSON'
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
JSON

cat > frontend/index.html <<'HTML'
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>DP Manager</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
HTML

cat > frontend/src/main.tsx <<'TSX'
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
TSX

cat > frontend/src/App.tsx <<'TSX'
import React, { useMemo, useState } from "react";

export default function App() {
  const apiBase = useMemo(
    () => import.meta.env.VITE_API_BASE_URL || "http://localhost:18000",
    []
  );
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>("");

  const upload = async () => {
    setError("");
    setResult(null);

    if (!file) {
      setError("엑셀 파일을 선택해줘.");
      return;
    }

    const form = new FormData();
    form.append("file", file);

    const res = await fetch(`${apiBase}/upload/iolist`, {
      method: "POST",
      body: form
    });

    if (!res.ok) {
      setError(`업로드 실패: ${res.status}`);
      return;
    }

    const data = await res.json();
    setResult(data);
  };

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <h1>DP Manager - IOLIST 업로드 (로컬)</h1>

      <div style={{ padding: 16, border: "1px solid #ddd", borderRadius: 12 }}>
        <p style={{ marginTop: 0 }}>
          API: <code>{apiBase}</code>
        </p>

        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />

        <div style={{ marginTop: 12 }}>
          <button onClick={upload}>업로드</button>
        </div>

        {error && <p style={{ color: "crimson" }}>{error}</p>}

        {result && (
          <pre style={{ marginTop: 12, padding: 12, background: "#f7f7f7", borderRadius: 12, overflow: "auto" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>

      <div style={{ marginTop: 16, color: "#666", fontSize: 14 }}>
        로그 경로: ./data/logs (backend/postgres)
      </div>
    </div>
  );
}
TSX

echo "[*] Bootstrap done."
echo "Next:"
echo "  docker compose up -d --build"
