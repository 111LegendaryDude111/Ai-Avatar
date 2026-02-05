# AI Video Avatar Studio (MVP)

Прототип приложения из описанной архитектуры: React фронтенд + FastAPI бэкенд + асинхронная очередь задач.

Реализованы 2 режима:

- **`sadtalker` (по умолчанию)** — talking-head генерация через SadTalker (нужно отдельно поставить репозиторий + веса)
- **`mock`** — быстрый демо-режим: собирает `MP4` из статичной картинки и аудио (или текста через локальный TTS), чтобы проверить end-to-end поток и инфраструктуру

## Структура

- `backend/` — FastAPI API + in-process worker/queue, сохранение артефактов в `storage/`
- `frontend/` — React UI (Vite), отправка job → polling статуса → показ видео

## Быстрый старт (dev)

### 1) Зависимости

- Python 3.10+ (рекомендуется 3.11/3.12)
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

Пример: `backend/.env.example` (скопируйте в `backend/.env`).

## Следующие шаги

- SadTalker уже подключён (см. раздел ниже).
- Для `wav2lip` или `svd` реализуйте генераторы в `backend/app/pipeline/` и обновите `backend/app/pipeline/factory.py`.

## SadTalker (вместо `mock`)

Интеграция SadTalker уже добавлена в `backend/app/pipeline/sadtalker_generator.py:1`, но **репозиторий и веса моделей нужно поставить отдельно**.

### Вариант A (проще): отдельное окружение для SadTalker

1) Склонируйте SadTalker в `third_party/SadTalker`:

```bash
mkdir -p third_party
git clone https://github.com/OpenTalker/SadTalker third_party/SadTalker
```

2) Создайте отдельный venv для SadTalker и установите зависимости.

macOS (Apple Silicon) — рабочий набор версий (иначе возможны ошибки совместимости `torchvision`):

```bash
python3.9 -m venv third_party/SadTalker/.venv  # или используйте pyenv/conda с Python 3.9
third_party/SadTalker/.venv/bin/pip install -U pip
third_party/SadTalker/.venv/bin/pip install "torch==2.0.1" "torchvision==0.15.2" "torchaudio==2.0.2"
third_party/SadTalker/.venv/bin/pip install -r third_party/SadTalker/requirements.txt opencv-python
```

3) Скачайте checkpoints/weights **по их README** (обычно это `third_party/SadTalker/checkpoints/...`).

4) Включите backend SadTalker:

```bash
cd backend
export AVATAR_GENERATOR_BACKEND=sadtalker
export AVATAR_SADTALKER_REPO_DIR=../third_party/SadTalker
export AVATAR_SADTALKER_PYTHON=/ABS/PATH/TO/SADTALKER/VENV/bin/python
uvicorn app.main:app --reload --port 8000
```

### Вариант B: ставить SadTalker в то же окружение, что и backend

Можно установить зависимости SadTalker прямо в `backend/.venv`, но это чаще приводит к конфликтам версий `torch/torchvision`. Рекомендуется вариант A.

## Важно (этика/безопасность)

Используйте talking avatar только с согласия человека на фото и явно помечайте синтетический контент, если публикуете его.
