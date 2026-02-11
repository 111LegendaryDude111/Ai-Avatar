# AI Video Avatar Studio (MVP)

## Структура

- `backend/` — FastAPI API + in-process worker/queue, сохранение артефактов в `storage/`
- `frontend/` — React UI (Vite), отправка job → polling статуса → показ видео

## Быстрый старт (Makefile + Poetry)

### 0) Зависимости

- Python 3.10+ 
- Node.js 18+
- `ffmpeg` (обязателен для сборки mp4)

macOS:

```bash
brew install ffmpeg
```

### 1) Установка

```bash
make setup
```

Опционально (нужны для генераторов):

- SadTalker (говорящая голова / lip-sync):

```bash
make setup-sadtalker
make sadtalker-torch-mps   # macOS / Apple Silicon
# или:
# make sadtalker-torch-cuda PYTORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu121
```

- Stable Video Diffusion (SVD) — **image→video** (без lip-sync, звук просто добавляется в mp4):

```bash
make setup-svd-mps         # Mac (MPS)
# или:
# make setup-svd-cuda PYTORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu121
```

Если при запуске SVD видите ошибку вида:
`Could not import module 'CLIPImageProcessor'` и в traceback есть `No module named '_lzma'`,
значит Python собран без `lzma` (часто бывает с `pyenv`).
Пересоздайте backend venv на Python с `lzma`:

```bash
python3 -c "import lzma; print('lzma: OK')"
cd backend
poetry env remove --all
poetry env use "$(command -v python3)"
poetry install --with svd
poetry run python -m pip install torch torchvision torchaudio
```

### 2) Запуск

Backend (в отдельном терминале):

```bash
make run-sadtalker
# или:
# make run-svd-m4
# make run-svd-m4-low
# make run-svd-m4-tiny
# make run-svd-m4-pro
# make run-svd-5080
```

Frontend (во втором терминале):

```bash
make frontend-dev
```

Откройте `http://localhost:5173`.

Проверка backend:

```bash
make health
```

## Команды Makefile

Подсказка по всем целям:

```bash
make help
```

Основные команды:

- `make doctor` — проверка, что установлены `poetry`, `npm`, `ffmpeg`
- `make env` — создаёт `backend/.env` и `frontend/.env` из `*.env.example` (если файлов ещё нет)
- `make setup` — базовая установка зависимостей (backend + frontend)
- `make setup-backend` — `poetry install` в `backend/`
- `make setup-backend-svd` — `poetry install --with svd` (доп. зависимости для SVD)
- `make setup-frontend` — `npm install` в `frontend/`

PyTorch (ставится отдельно, внутри Poetry-окружения backend):

- `make torch-mps` — PyTorch для macOS / Apple Silicon
- `make torch-cuda PYTORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu121` — PyTorch для CUDA (обычно Linux)
- `make setup-svd-mps` — `setup-backend-svd` + `torch-mps`
- `make setup-svd-cuda` — `setup-backend-svd` + `torch-cuda`
- `make setup-svd-cuda-xformers` — опционально ставит `xformers` (ускорение/экономия VRAM на CUDA; может не собраться на некоторых системах)

SadTalker (использует отдельное venv в `third_party/SadTalker/.venv`):

- `make setup-sadtalker` — создаёт venv и ставит зависимости SadTalker (без torch)
- `make sadtalker-torch-mps` / `make sadtalker-torch-cuda ...` — ставит torch в SadTalker venv

Запуск:

- `make backend-dev` — backend по настройкам из `backend/.env`
- `make run-sadtalker` — backend с SadTalker (переменные задаются на время запуска)
- `make run-svd-m4` — backend с SVD balanced preset для Mac (MPS)
- `make run-svd-m4-low` — backend с SVD low-memory preset для Mac (MPS)
- `make run-svd-m4-tiny` — backend с SVD ultra-low-memory preset для Mac (MPS)
- `make run-svd-m4-pro` — backend с более «тяжёлым» SVD preset для Mac (MPS)
- `make run-svd-5080` — backend с SVD preset для мощной CUDA GPU
- `make frontend-dev` — frontend dev server
- `make health` — `GET /health` на backend

Полезные параметры (можно переопределять при вызове `make`):

- `BACKEND_PORT=8000`, `BACKEND_HOST=0.0.0.0`
- `FRONTEND_PORT=5173`, `FRONTEND_HOST=0.0.0.0`
- `PYTORCH_CUDA_INDEX_URL=...` — индекс PyTorch колёс под нужную версию CUDA

## Ручной запуск (без Makefile)

### Backend

```bash
cd backend
poetry install
cp .env.example .env
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Для SVD дополнительно:

```bash
cd backend
poetry install --with svd
# PyTorch поставьте отдельно под вашу платформу:
# - macOS (MPS): poetry run python -m pip install torch torchvision torchaudio
# - CUDA (Linux): poetry run python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Пресеты SVD

Готовые пресеты есть в `Makefile`:

- `make run-svd-m4` — MPS balanced: `640x360`, `10` кадров, `30` шагов, `float32`, `DECODE_CHUNK_SIZE=1`.
- `make run-svd-m4-low` — MPS low-memory: `512x288`, `8` кадров, `25` шагов, `float32`, `DECODE_CHUNK_SIZE=1`.
- `make run-svd-m4-tiny` — MPS ultra-low-memory: `384x216`, `6` кадров, `20` шагов, `float32`, `DECODE_CHUNK_SIZE=1`.
- `make run-svd-m4-pro` — MPS higher quality: `768x432`, `14` кадров, `40` шагов, `float32`, `DECODE_CHUNK_SIZE=1`.
- `make run-svd-5080` — CUDA (мощная видеокарта): `1024x576`, `25` кадров, `50` шагов, `xformers` (если установлен).

Если упираетесь в память/качество — правьте переменные `AVATAR_SVD_*` в `backend/.env` или переопределяйте их в команде.
Для качества кодирования mp4 можно дополнительно уменьшать `AVATAR_SVD_ENCODE_CRF` (например `18` → `16`; меньше = лучше качество и больше размер файла).
Если на MPS получаете чёрное видео, не используйте `float16`: ставьте `AVATAR_SVD_DTYPE=float32`.

## API

- `POST /api/v1/jobs` — multipart: `image` + (`text` **или** `audio`) + опционально `options` (JSON строка)
- `GET /api/v1/jobs/{job_id}` — статус/прогресс/ссылка на результат
- `GET /api/v1/jobs/{job_id}/result` — mp4 (когда `status=succeeded`)

## Настройки (env)

Backend читает переменные с префиксом `AVATAR_`:

- `AVATAR_GENERATOR_BACKEND=sadtalker|mock|wav2lip|svd`
- `AVATAR_STORAGE_DIR=storage`
- `AVATAR_ENABLE_CACHE=true|false`
