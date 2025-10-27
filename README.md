
<!-- Banner -->
<h1 align="center">🧬 Avatar_ENU — Lip-Sync Video Pipeline</h1>
<p align="center">
  <b>Flask + Celery + RabbitMQ · Wav2Lip · TTS/NLP · Template-based Video Rendering</b>
</p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white"></a>
  <a href="#"><img alt="Ubuntu" src="https://img.shields.io/badge/Ubuntu-24.04-E95420?logo=ubuntu&logoColor=white"></a>
  <a href="https://flask.palletsprojects.com/"><img alt="Flask" src="https://img.shields.io/badge/Flask-backend-000000?logo=flask&logoColor=white"></a>
  <a href="https://docs.celeryq.dev/"><img alt="Celery" src="https://img.shields.io/badge/Celery-task%20queue-37814A?logo=celery&logoColor=white"></a>
  <a href="https://www.rabbitmq.com/"><img alt="RabbitMQ" src="https://img.shields.io/badge/RabbitMQ-broker-FF6600?logo=rabbitmq&logoColor=white"></a>
  <a href="https://docs.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/Docker-optional-2496ED?logo=docker&logoColor=white"></a>
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/License-see%20file-blue"></a>
</p>

<p align="center">
  Template-driven, async lip-sync video generation. Audio in → Wav2Lip → composited video out.
</p>

---

## ✨ Features

- 🎤 **Lip-Sync (Wav2Lip)** — Drive face videos from audio.
- 🎬 **Template-based composition** — Ready-made video templates (female `f_*`, male `m_*`) and green-screen assets.
- ⚙️ **Asynchronous pipeline** — Celery + RabbitMQ for robust background jobs and batching.
- 🧠 **Text/TTS/NLP utilities** — Flexible helpers for text→audio workflows.
- 🧩 **Modular structure** — Clean `routes/`, `utils/`, and `wav2lip/` layout.
- 🧪 **Local or Docker** — Run natively or via Docker/Compose. GPU optional.
- 📈 **Logs & observability** — Structured logs under `logs/` and RabbitMQ management UI.

---

### Architecture (Step-by-step)

1. **Frontend UI** (`templates/index.html`) accepts audio/text input and shows progress.  
2. **Routes** (`routes/text_processing.py`, `routes/video_generation.py`) validate input and enqueue jobs.  
3. **Celery Tasks** (`tasks.py`, `celery_app.py`) orchestrate the pipeline:  
   - Push/pull via **RabbitMQ** (AMQP 5672; UI 15672).  
   - Run **Wav2Lip** inference under `wav2lip/`.  
   - Compose with `utils/video_utils.py` and **FFmpeg**.  
4. **Outputs** are written to `videoset/output/` (final) and `temp/` (intermediate).  
5. **UI** fetches results for preview/download.

---

## 📦 Directory Overview

<details>
<summary><b>Click to expand tree</b></summary>

```

app.py                # Flask entrypoint
celery_app.py         # Celery application configuration
cli.py                # Optional CLI utilities
consumer_celery.py    # Optional consumer
docker-compose.yml    # Compose for broker/app (optional)
Dockerfile            # Container build (optional)
requirements.txt      # Python dependencies
package.json          # Frontend deps (wavesurfer.js)
templates/index.html  # UI
static/               # CSS/JS/images/templates (f_*.mp4, m_*.mp4, green_bg.png)
routes/               # API routes: text_processing, video_generation
utils/                # TTS/NLP/merge/video utils
wav2lip/              # Wav2Lip module & scripts
weights/              # Model weights (kept out of VCS)
videoset/             # Samples & outputs
logs/                 # Runtime logs
temp/                 # Intermediate artifacts
LICENSE               # License file
README.md             # This document

````

</details>

---

## 🚀 Quick Start (Local)

> **Prereqs**: Ubuntu 24.04, Python 3.12+, `ffmpeg`, `sox`, `libsndfile1`.  
> **Broker**: RabbitMQ (Docker recommended).

```bash
# 0) System deps
sudo apt update
sudo apt install -y python3-venv python3-dev ffmpeg sox libsox-fmt-all libsndfile1 \
                    build-essential git curl unzip tmux

# 1) RabbitMQ (Docker is the easiest)
sudo apt install -y docker.io
sudo systemctl enable --now docker
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin \
  rabbitmq:3.13-management
# RabbitMQ UI: http://127.0.0.1:15672  (admin/admin) — change in production!

# 2) Python env
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 3) Environment
cp .env.example .env    # then edit values if needed

# 4) Run (two terminals)
# Terminal A — Flask
source .venv/bin/activate && python app.py
# Terminal B — Celery worker
source .venv/bin/activate && celery -A celery_app worker -l INFO

# 5) Open UI
# http://127.0.0.1:8000
````

---

## 🐳 Docker & Compose

**Docker Compose** (uses your `docker-compose.yml`):

```bash
docker compose up -d
docker compose logs -f
```

**Dockerfile** (single image; RabbitMQ still required):

```bash
docker build -t avatar-enu:latest .
docker run --rm -p 8000:8000 --env-file .env avatar-enu:latest
```

---

## 🔧 Configuration

Put runtime settings in `.env` (do **not** commit real secrets). Example:

```ini
# Flask
APP_HOST=0.0.0.0
APP_PORT=8000
FLASK_ENV=production

# RabbitMQ / Celery
RABBITMQ_HOST=127.0.0.1
RABBITMQ_PORT=5672
RABBITMQ_VHOST=/
RABBITMQ_USER=admin
RABBITMQ_PASS=admin
CELERY_BROKER_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASS}@${RABBITMQ_HOST}:${RABBITMQ_PORT}/${RABBITMQ_VHOST}
CELERY_RESULT_BACKEND=rpc://

# Business toggles
USE_AVATAR=false
TTS_LANG=kk            # kk / ru / en

# Paths
WEIGHTS_DIR=./weights
VIDEO_TEMPLATES_DIR=./static/video_templates
TEMP_DIR=./temp
```

| Key                                              | Purpose                                             |
| ------------------------------------------------ | --------------------------------------------------- |
| `APP_HOST`, `APP_PORT`                           | Flask binding address/port                          |
| `CELERY_BROKER_URL`                              | AMQP URL to RabbitMQ (must match where broker runs) |
| `CELERY_RESULT_BACKEND`                          | Celery result backend (rpc is fine)                 |
| `USE_AVATAR`, `TTS_LANG`                         | Feature toggles (example)                           |
| `WEIGHTS_DIR`, `VIDEO_TEMPLATES_DIR`, `TEMP_DIR` | Model/templates/tmp paths                           |

---

## 🖥️ UI & Frontend

* UI at `/` → `templates/index.html` with `static/js/*` (audio preview via **wavesurfer.js**).
* Update `wavesurfer.js` if needed:

  ```bash
  sudo apt install -y nodejs npm
  npm ci   # or: npm install
  ```

---

## 🧵 Jobs & CLI

* **Web flow**: Frontend request → `routes/text_processing.py` / `routes/video_generation.py` → enqueue Celery → Wav2Lip → compose → output.
* **CLI (example)**:

  ```bash
  source .venv/bin/activate
  python cli.py --help
  # e.g.
  # python cli.py --audio input.wav --template static/video_templates/f_1.mp4 --out videoset/output/output.mp4
  ```

---

## 🎞️ Templates & Media

* **Video templates**: `static/video_templates/` (female `f_*`, male `m_*`).
* **Green screen**: `green_bg.png` for compositing.
* **Outputs**: `videoset/output/` & `temp/`.

---

## 🧠 Models / Weights

* Place weights under `weights/` (e.g., `4x_BigFace_v3_Clear.pth`).
* Consider **Git LFS** for large assets:

  ```bash
  sudo apt install -y git-lfs && git lfs install
  git lfs track "*.mp4" "*.wav" "*.pth" "*.pt" "*.onnx"
  ```

---

## 🛠️ Troubleshooting

* **`dial tcp 127.0.0.1:5672: connect: connection refused`**
  RabbitMQ not listening:

  ```bash
  docker ps | grep rabbitmq
  ss -ltnp | grep 5672
  # ensure CELERY_BROKER_URL points to the correct host (container name vs localhost)
  ```

* **Large file (>100MB) push rejected**
  Track with LFS before committing; clean history if already committed.

* **`Gtk-Message: Failed to load module "canberra-gtk-module"`**
  Harmless for backend; optionally `sudo apt install libcanberra-gtk-module`.

* **Git push rejected (non-fast-forward)**
  Remote has commits:

  ```bash
  git fetch origin
  git rebase origin/main   # or: git merge origin/main
  git push -u origin main
  ```

---

## 🔐 Security Notes

* Never commit real secrets: `.env`, keys, certs, tokens. Commit only `.env.example`.
* Change default RabbitMQ credentials in production and restrict management UI exposure.
* Use firewall/reverse proxy and log rotation for long-running deployments.

---

## 📚 Code & Data Repository (Reproducibility)


### 1) Code

* **Algorithms / Scripts**: all source files under:

  * `app.py`, `celery_app.py`, `tasks.py`, `routes/`, `utils/`, `wav2lip/`
  * CLI: `cli.py`
  * Optional: `consumer_celery.py`, `docker-compose.yml`, `Dockerfile`
* **Organization**:

  * **Backend**: Flask app in `app.py`, routes in `routes/`
  * **Tasks**: Celery configuration in `celery_app.py`, tasks in `tasks.py`
  * **Audio/Video**: `utils/tts.py`, `utils/video_utils.py`
  * **Lip-Sync**: `wav2lip/` (inference & helpers)
  * **Static/UI**: `templates/`, `static/`

### 2) README (this file)

Contains title, description, dataset info, code overview, usage, requirements, methodology, citations, license & contribution guidelines.

### 3) Dataset Information

* **Built-in samples**: `videoset/sample/` (demo videos) and template clips in `static/video_templates/`.
* **Format**: MP4 for video, WAV/MP3 for audio (16k–48kHz), PNG for overlays.

### 4) Code Information

* **Key modules**:

  * `routes/text_processing.py` — text handling & pre-TTS logic
  * `routes/video_generation.py` — job submission & result endpoints
  * `utils/tts.py` — TTS helpers for audio creation
  * `utils/video_utils.py` — FFmpeg-based composition
  * `wav2lip/` — lip-sync inference utilities
* **Entry points**:

  * Web: `python app.py`
  * Worker: `celery -A celery_app worker -l INFO`
  * CLI: `python cli.py --help`

### 5) Usage Instructions (Reproduction)

**Goal**: reproduce a lip-sync render deterministically from provided inputs.

```bash
# A) Environment
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt

# B) Broker (local Docker)
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin -e RABBITMQ_DEFAULT_PASS=admin \
  rabbitmq:3.13-management

# C) Set env
cp .env.example .env  # adjust if needed

# D) Run services
# Terminal 1:
python app.py
# Terminal 2:
celery -A celery_app worker -l INFO

# E) Reproduce from samples
# Option 1: use your own audio (WAV/MP3)
# Option 2: generate audio via utils/tts.py (if configured)
# Then enqueue a job via the UI or CLI:
python cli.py --audio path/to/audio.wav \
  --template static/video_templates/f_1.mp4 \
  --out videoset/output/output.mp4
```

**Determinism tips**:

* Fix seeds where applicable: `PYTHONHASHSEED=0`; set seeds in your ML libs.
* Pin exact dependency versions via `requirements.txt`.
* Record GPU/driver/CUDA versions in your paper or below.

### 6) Requirements

* **OS**: Ubuntu 24.04
* **Python**: 3.12
* **System deps**: `ffmpeg`, `sox`, `libsndfile1`
* **Broker**: RabbitMQ (AMQP 5672; UI 15672)
* **Optional**: NVIDIA GPU + CUDA/cuDNN matching your PyTorch build
* **Python deps**: see `requirements.txt`

### 7) Methodology

1. **Pre-processing**: (optional) TTS to synthesize narration; resample/normalize audio.
2. **Lip-Sync**: Wav2Lip model aligns mouth region with audio mel-spectrogram; frame-wise synthesis.
3. **Composition**: Merge lip-synced face with template clip via `utils/video_utils.py` (FFmpeg).
4. **Post-processing**: Mix audio tracks, apply overlays (e.g., green-screen), package MP4.
5. **Batching**: Jobs queued and executed asynchronously via Celery/RabbitMQ.

### 8) Citations

If you use this repository, please cite:

```
@software{Avatar_ENU,
  title   = {Avatar_ENU: Lip-Sync Video Pipeline},
  author  = {Altaibek M. et.all},
  year    = {2025},
  url     = {https://github.com/MMR000/Avatar_ENU}
}
```

And the original Wav2Lip work:

```
@inproceedings{prajwal2020wav2lip,
  title     = {A Lip Sync Expert Is All You Need for Speech to Lip Generation},
  author    = {Prajwal, K R and Mukhopadhyay, Rudrabha and Namboodiri, Vinay P and Jawahar, C V},
  booktitle = {ACM Multimedia},
  year      = {2020}
}
```

### 9) License & Contribution Guidelines

* **License**: see [LICENSE](./LICENSE).
* **Contributions**: PRs and issues are welcome. Keep changes modular; document public APIs; include tests when possible.

---

## 🗺️ Roadmap

* [ ] Optional GPU inference presets and auto device selection
* [ ] Job progress API & WebSocket events
* [ ] Batch CLI & resumable pipelines
* [ ] Template authoring toolkit

---

## 🤝 Contributing

PRs and issues are welcome. Please keep changes modular and documented.
Consider adding unit tests for `utils/` functions and route handlers.

---

## 📄 License

See [LICENSE](./LICENSE).

---

## 🙏 Acknowledgments

* **Wav2Lip** (lip-sync research & code)
* **wavesurfer.js** (audio visualization)
* Open-source community and tool maintainers

