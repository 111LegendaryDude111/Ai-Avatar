.DEFAULT_GOAL := help

ROOT_DIR := $(CURDIR)
BACKEND_DIR := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend
SADTALKER_DIR := $(ROOT_DIR)/third_party/SadTalker

BACKEND_HOST ?= 0.0.0.0
BACKEND_PORT ?= 8000
FRONTEND_HOST ?= 0.0.0.0
FRONTEND_PORT ?= 5173

POETRY ?= poetry
NPM ?= npm
PYTHON ?= python3

# Override if you want a different CUDA wheel (see https://pytorch.org/get-started/locally/).
PYTORCH_CUDA_INDEX_URL ?= https://download.pytorch.org/whl/cu121

.PHONY: help doctor env env-backend env-frontend \
	setup setup-backend setup-backend-svd setup-frontend \
	setup-svd-mps setup-svd-cuda setup-svd-cuda-xformers torch-mps torch-cuda \
	setup-sadtalker sadtalker-torch-mps sadtalker-torch-cuda \
	backend-dev frontend-dev health \
	run-sadtalker run-svd-m4 run-svd-5080

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## Check required tools are installed
	@command -v $(POETRY) >/dev/null 2>&1 || (echo "Missing: poetry (https://python-poetry.org/docs/#installation)"; exit 1)
	@command -v $(NPM) >/dev/null 2>&1 || (echo "Missing: npm / Node.js 18+ (https://nodejs.org/)"; exit 1)
	@command -v ffmpeg >/dev/null 2>&1 || (echo "Missing: ffmpeg (macOS: brew install ffmpeg)"; exit 1)
	@echo "OK"

env: env-backend env-frontend ## Create .env files (if missing)

env-backend: ## Create backend/.env from backend/.env.example (if missing)
	@test -f "$(BACKEND_DIR)/.env" || cp "$(BACKEND_DIR)/.env.example" "$(BACKEND_DIR)/.env"

env-frontend: ## Create frontend/.env from frontend/.env.example (if missing)
	@test -f "$(FRONTEND_DIR)/.env" || cp "$(FRONTEND_DIR)/.env.example" "$(FRONTEND_DIR)/.env"

setup: doctor setup-backend setup-frontend ## Install base deps (backend+frontend)

setup-backend: env-backend ## Install backend deps via Poetry (base)
	cd "$(BACKEND_DIR)" && $(POETRY) install

setup-backend-svd: env-backend ## Install backend deps + SVD extras group
	cd "$(BACKEND_DIR)" && $(POETRY) install --with svd

setup-frontend: env-frontend ## Install frontend deps (Vite/React)
	cd "$(FRONTEND_DIR)" && $(NPM) install

torch-mps: ## Install PyTorch into Poetry env (macOS / Apple Silicon)
	cd "$(BACKEND_DIR)" && $(POETRY) run python -m pip install -U pip
	cd "$(BACKEND_DIR)" && $(POETRY) run python -m pip install torch torchvision torchaudio

torch-cuda: ## Install PyTorch into Poetry env (Linux + NVIDIA CUDA)
	cd "$(BACKEND_DIR)" && $(POETRY) run python -m pip install -U pip
	cd "$(BACKEND_DIR)" && $(POETRY) run python -m pip install torch torchvision torchaudio --index-url "$(PYTORCH_CUDA_INDEX_URL)"

setup-svd-mps: setup-backend-svd torch-mps ## Setup backend for SVD on Apple Silicon (MPS)

setup-svd-cuda: setup-backend-svd torch-cuda ## Setup backend for SVD on CUDA

setup-svd-cuda-xformers: setup-svd-cuda ## Optional: install xformers (can fail on some setups)
	cd "$(BACKEND_DIR)" && $(POETRY) run python -m pip install xformers

setup-sadtalker: ## Create SadTalker venv + install deps (torch installed separately)
	@test -d "$(SADTALKER_DIR)" || (echo "SadTalker repo not found at: $(SADTALKER_DIR)"; exit 1)
	@test -x "$(SADTALKER_DIR)/.venv/bin/python" || $(PYTHON) -m venv "$(SADTALKER_DIR)/.venv"
	"$(SADTALKER_DIR)/.venv/bin/python" -m pip install -U pip
	"$(SADTALKER_DIR)/.venv/bin/python" -m pip install -r "$(SADTALKER_DIR)/requirements.txt"

sadtalker-torch-mps: ## Install PyTorch into SadTalker venv (macOS / Apple Silicon)
	"$(SADTALKER_DIR)/.venv/bin/python" -m pip install -U pip
	"$(SADTALKER_DIR)/.venv/bin/python" -m pip install torch torchvision torchaudio

sadtalker-torch-cuda: ## Install PyTorch into SadTalker venv (Linux + NVIDIA CUDA)
	"$(SADTALKER_DIR)/.venv/bin/python" -m pip install -U pip
	"$(SADTALKER_DIR)/.venv/bin/python" -m pip install torch torchvision torchaudio --index-url "$(PYTORCH_CUDA_INDEX_URL)"

backend-dev: env-backend ## Run backend (uses backend/.env)
	cd "$(BACKEND_DIR)" && $(POETRY) run uvicorn app.main:app --reload --host "$(BACKEND_HOST)" --port "$(BACKEND_PORT)"

frontend-dev: env-frontend ## Run frontend dev server
	cd "$(FRONTEND_DIR)" && $(NPM) run dev -- --host "$(FRONTEND_HOST)" --port "$(FRONTEND_PORT)"

health: ## Backend healthcheck
	@curl -fsS "http://localhost:$(BACKEND_PORT)/health" || true
	@echo

run-sadtalker: env-backend ## Run backend with SadTalker generator
	cd "$(BACKEND_DIR)" && \
	AVATAR_GENERATOR_BACKEND=sadtalker \
	AVATAR_SADTALKER_REPO_DIR="$(SADTALKER_DIR)" \
	AVATAR_SADTALKER_PYTHON="$(SADTALKER_DIR)/.venv/bin/python" \
	$(POETRY) run uvicorn app.main:app --reload --host "$(BACKEND_HOST)" --port "$(BACKEND_PORT)"

run-svd-m4: env-backend ## Run backend with SVD preset for Mac M4 Pro (MPS)
	cd "$(BACKEND_DIR)" && \
	PYTORCH_ENABLE_MPS_FALLBACK=1 \
	AVATAR_GENERATOR_BACKEND=svd \
	AVATAR_SVD_DEVICE=mps \
	AVATAR_SVD_DTYPE=float32 \
	AVATAR_SVD_DECODE_CHUNK_SIZE=1 \
	AVATAR_SVD_AUTO_DOWNSCALE=true \
	AVATAR_SVD_MPS_MAX_PIXELS=$$((768*432)) \
	AVATAR_SVD_WIDTH=768 \
	AVATAR_SVD_HEIGHT=432 \
	AVATAR_SVD_NUM_FRAMES=14 \
	AVATAR_SVD_NUM_INFERENCE_STEPS=40 \
	AVATAR_SVD_MOTION_BUCKET_ID=60 \
	AVATAR_SVD_NOISE_AUG_STRENGTH=0.005 \
	$(POETRY) run uvicorn app.main:app --reload --host "$(BACKEND_HOST)" --port "$(BACKEND_PORT)"

run-svd-5080: env-backend ## Run backend with SVD preset for a strong CUDA GPU (e.g. 5080)
	cd "$(BACKEND_DIR)" && \
	AVATAR_GENERATOR_BACKEND=svd \
	AVATAR_SVD_DEVICE=cuda \
	AVATAR_SVD_DTYPE=float16 \
	AVATAR_SVD_ENABLE_XFORMERS=true \
	AVATAR_SVD_WIDTH=1024 \
	AVATAR_SVD_HEIGHT=576 \
	AVATAR_SVD_NUM_FRAMES=25 \
	AVATAR_SVD_NUM_INFERENCE_STEPS=50 \
	AVATAR_SVD_DECODE_CHUNK_SIZE=16 \
	$(POETRY) run uvicorn app.main:app --reload --host "$(BACKEND_HOST)" --port "$(BACKEND_PORT)"
