# AI Video Avatar Studio (MVP)

## Структура

- `backend/` — FastAPI API + in-process worker/queue, сохранение артефактов в `storage/`
- `frontend/` — React UI (Vite), отправка job → polling статуса → показ видео

## Быстрый старт (dev)

### 1) Зависимости

- Python 3.10+ 
- Node.js 18+
- `ffmpeg` (обязателен для сборки mp4)

macOS:

```bash
brew install ffmpeg
```

### 2) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Если SadTalker ещё не настроен — переключитесь на mock в backend/.env:
# AVATAR_GENERATOR_BACKEND=mock
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Проверка:

```bash
curl http://localhost:8000/health
```

### 3) Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Откройте `http://localhost:5173`.

## API

- `POST /api/v1/jobs` — multipart: `image` + (`text` **или** `audio`) + опционально `options` (JSON строка)
- `GET /api/v1/jobs/{job_id}` — статус/прогресс/ссылка на результат
- `GET /api/v1/jobs/{job_id}/result` — mp4 (когда `status=succeeded`)

## Настройки (env)

Backend читает переменные с префиксом `AVATAR_`:

- `AVATAR_GENERATOR_BACKEND=sadtalker|mock|wav2lip|svd`
- `AVATAR_STORAGE_DIR=storage`
- `AVATAR_ENABLE_CACHE=true|false`