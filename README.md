# CaptainAI

AI-powered subtitle intelligence platform. Upload an MP4 or MP3, let IBM Granite
understand the video's intent, and export a publish-ready video with styled, burned-in subtitles.

**Stack:** React + Vite + Tailwind CSS · Python + FastAPI · faster-whisper (CUDA) · IBM Granite via watsonx · FFmpeg

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | `python --version` |
| Node.js | 18+ | `node --version` |
| FFmpeg | any recent | Must be on PATH (`ffmpeg -version`) |
| CUDA | 12.x | RTX GPU required for faster-whisper performance |
| IBM watsonx account | — | Lite plan is sufficient |

---

## Local Development Setup

### 1. Clone / open the project

```
cd captainai
```

### 2. Configure environment variables

```
cp .env.example .env
# Edit .env and fill in WATSONX_API_KEY and WATSONX_PROJECT_ID
```

### 3. Start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs on: http://localhost:8000  
Health check: http://localhost:8000/health → `{"status": "ok"}`

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on: http://localhost:5173

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WATSONX_API_KEY` | — | IBM Cloud API key (required) |
| `WATSONX_PROJECT_ID` | — | watsonx project ID (required) |
| `WATSONX_URL` | `https://us-south.ml.cloud.ibm.com` | watsonx regional endpoint |
| `WATSONX_MODEL_ID` | `ibm/granite-3-3-8b-instruct` | Granite model ID |
| `TMP_DIR` | `/tmp/captainai` | Temporary job file storage |
| `MAX_FILE_SIZE_MB` | `500` | Upload size limit |
| `WHISPER_MODEL_SIZE` | `small` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v2`) |

---

## API Reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/upload` | Upload and validate file, get job_id |
| POST | `/process/{job_id}` | Start async pipeline |
| GET | `/status/{job_id}` | SSE stream of pipeline progress + final result |
| POST | `/export/{job_id}` | Burn subtitles, generate output files |
| GET | `/download/{job_id}/{filename}` | Serve output file for download |

---

## Pipeline

```
Upload → Validate → FFmpeg audio extraction → faster-whisper transcription
→ IBM Granite (correction + genre + style) → SRT generation
→ SSE progress → Interactive editor → POST /export → FFmpeg burn-in → Download
```

---

## Style Presets

| Preset | Auto-selected for genre | Manual only |
|--------|------------------------|-------------|
| `education` | `study` | — |
| `minimal` | `talk` | — |
| `cinematic` | `song` | — |
| `social` | `vlog` | — |
| `karaoke` | — | ✓ (manual selection only) |

---

*Powered by IBM Granite on watsonx*
