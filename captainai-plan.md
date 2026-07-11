# CaptainAI — Implementation Plan

> **Scope decisions applied:**
> - Sub-task 8 (Integration & Demo Polish) removed as a formal sub-task. Integration testing is folded into each sub-task's own todo list.
> - Sub-task 5 (Subtitle Composer) simplified: ASS file generation removed. Burn-in uses SRT + FFmpeg `force_style` string. Lower style fidelity than ASS, but sufficient for MVP and saves ~1 day of build time.

## Top-Level Overview

**Goal:** Build CaptainAI, an AI-powered subtitle intelligence platform that transforms raw MP4/MP3 videos into publish-ready videos with accurate, styled, and burned-in subtitles — without any manual transcription work.

**Scope:** A stateless, single-session web application. No auth, no database, no deployment infrastructure. Files exist only during processing and are cleaned up after download.

**Core differentiator:** IBM Granite reads the video's *intent* (genre, language pattern, quality signals), not just its words. Whisper provides the raw transcript. Granite makes it publish-ready and intelligently styled.

**Stack:**
- Frontend: React + Vite + Tailwind CSS
- Backend: Python + FastAPI
- AI: faster-whisper (local, CUDA GPU), IBM Granite via watsonx SDK
- Video: FFmpeg
- Preview: CSS overlay on HTML5 video player (no server round-trip)

**Pipeline:**
```
Upload -> Validate -> FFmpeg audio extraction -> faster-whisper transcription
-> IBM Granite processing (correction + genre + style recommendation)
-> Subtitle Composer (SRT generation) -> SSE progress to frontend
-> Interactive editor (text + style, CSS preview)
-> POST /export -> FFmpeg burn-in -> Download MP4 / SRT / TXT
```

**Architecture decisions locked in:**
- Job identity: UUID generated at upload, all files in `/tmp/captainai/{job_id}/`
- Progress feedback: Server-Sent Events (SSE) on `GET /status/{job_id}`
- Style system: Named presets (5 options) mapped to FFmpeg `force_style` strings
- Granite call strategy: Single structured JSON call per job (minimises token cost)
- Subtitle preview: CSS-overlay div synced to `video.currentTime` in React
- Timestamp ownership: Whisper owns all timestamps. Granite only edits display text.
- Granite model: `ibm/granite-3-3-8b-instruct` on watsonx

---

## Sub-Task 1: Project Scaffold & Configuration

**Status:** [ ] pending

### Intent
Create the complete folder structure for both frontend and backend, set up dependency files, and configure environment variables. This is the foundation every other sub-task builds on.

### Expected Outcomes
- `backend/` folder exists with `main.py`, router stubs, service stubs, and `requirements.txt`
- `frontend/` folder exists with Vite + React + Tailwind bootstrapped and running on `localhost:5173`
- `.env.example` documents all required environment variables
- FastAPI backend starts on `localhost:8000` with CORS enabled for the frontend origin
- A single `GET /health` endpoint returns `{ "status": "ok" }` — proves the stack is wired together

### Todo List
1. Create `backend/` folder with the structure defined in the folder layout section
2. Create `backend/requirements.txt` with: `fastapi`, `uvicorn[standard]`, `python-multipart`, `faster-whisper`, `ibm-watsonx-ai`, `pydantic`, `python-dotenv`, `aiofiles`
3. Create `backend/config.py` — reads env vars: `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID` (default: `ibm/granite-3-3-8b-instruct`), `TMP_DIR` (default: `/tmp/captainai`), `MAX_FILE_SIZE_MB` (default: 500), `WHISPER_MODEL_SIZE` (default: `small`)
4. Create `backend/main.py` — FastAPI app with CORS middleware (allow `http://localhost:5173`), register all routers, include `GET /health`
5. Create stub router files: `routers/upload.py`, `routers/process.py`, `routers/status.py`, `routers/export.py` — each returns a `501 Not Implemented` response for now
6. Create stub service files: `services/validator.py`, `services/audio_extractor.py`, `services/transcriber.py`, `services/granite_processor.py`, `services/subtitle_composer.py`, `services/style_engine.py`, `services/burner.py`
7. Create `backend/models/schemas.py` with all Pydantic models (see Relevant Context below)
8. Scaffold frontend: `npm create vite@latest frontend -- --template react`, then `npm install tailwindcss @tailwindcss/vite`
9. Configure Tailwind in `frontend/vite.config.js` and `frontend/src/index.css`
10. Create `.env.example` at project root with all variable names and placeholder values
11. Create `README.md` with local dev setup instructions (how to start backend, how to start frontend)

### Relevant Context
Pydantic models needed in `schemas.py`:
- `JobStatus`: `job_id: str`, `stage: str`, `pct: int`, `error: str | None`
- `Segment`: `id: int`, `start: float`, `end: float`, `text: str`, `corrected_text: str`, `language: str` (values: `"en"`, `"hi"`, `"hi-en"`)
- `StylePreset`: `preset_name: str`, `font_name: str`, `font_size: int`, `primary_color: str`, `outline_color: str`, `position: str`, `background_box: bool`, `bold: bool`
- `ProcessedResult`: `segments: list[Segment]`, `genre: str`, `keywords: list[str]`, `style_recommendation: StylePreset`, `granite_summary: str`
- `ExportRequest`: `segments: list[Segment]`, `style: StylePreset`, `formats: list[str]`

---

## Sub-Task 2: Upload & Validation

**Status:** [ ] pending

### Intent
Implement `POST /upload` — the entry point for all files. This stage must reject bad files with clear errors and accept valid files without failure.

### Expected Outcomes
- Valid MP4 and MP3 files are accepted; a `job_id` UUID and file duration are returned
- Files larger than `MAX_FILE_SIZE_MB` are rejected with `422` and a readable error
- Non-video/audio MIME types are rejected
- Corrupted/truncated files (that pass MIME check but fail FFprobe) are rejected with a clear error
- Accepted files are saved to `/tmp/captainai/{job_id}/original.{ext}`

### Todo List
1. Implement `services/validator.py`:
   - Check file extension against allowlist: `.mp4`, `.mp3`, `.mov`, `.webm`
   - Check file size against `MAX_FILE_SIZE_MB`
   - Run `ffprobe -v quiet -print_format json -show_format` as a subprocess on the saved file — parse duration from output. If ffprobe fails or duration is 0, raise a validation error.
   - Return `{ "valid": True, "duration_seconds": float }` or raise `ValueError` with a message
2. Implement `POST /upload` in `routers/upload.py`:
   - Accept `multipart/form-data` with `file` field
   - Generate UUID for `job_id`
   - Create directory `/tmp/captainai/{job_id}/`
   - Save uploaded file to `original.{ext}`
   - Call `validator.validate(filepath)` — return `422` with detail on failure
   - On success, return `{ "job_id": ..., "filename": ..., "duration_seconds": ... }`
3. Register route in `main.py`

### Relevant Context
- Use Python's `subprocess.run` for ffprobe — do not add a Python ffprobe library, it is unnecessary
- FFprobe is bundled with FFmpeg — if FFmpeg is installed, ffprobe is available
- Keep the validator as a pure function that takes a file path — makes it testable without HTTP

---

## Sub-Task 3: Audio Extraction & Transcription

**Status:** [ ] pending

### Intent
Implement the FFmpeg audio extraction step and faster-whisper transcription. This stage produces the raw timestamped segments that everything downstream depends on.

### Expected Outcomes
- `POST /process/{job_id}` triggers the pipeline asynchronously and returns immediately
- `GET /status/{job_id}` begins emitting SSE events
- Audio is extracted from the video to `/{job_id}/audio.wav` (16kHz mono — required by Whisper)
- faster-whisper produces a list of segments with `start`, `end`, and `text`
- Segments are saved to `/{job_id}/whisper_segments.json`
- SSE events are emitted for `extracting_audio` (pct: 10) and `transcribing` (pct: 30) stages

### Todo List
1. Implement `services/audio_extractor.py`:
   - Run: `ffmpeg -i {input} -vn -acodec pcm_s16le -ar 16000 -ac 1 {output}.wav`
   - Raise `RuntimeError` if ffmpeg exits non-zero, include stderr in the message
2. Implement `services/transcriber.py`:
   - Load `faster_whisper.WhisperModel` with `model_size_or_path=config.WHISPER_MODEL_SIZE`, `device="cuda"`, `compute_type="float16"`
   - Call `model.transcribe(audio_path, language=None, task="transcribe", word_timestamps=False)` — language=None forces auto-detection, handles Hinglish
   - Collect segments into `list[dict]` with `id`, `start`, `end`, `text`
   - Save to `whisper_segments.json` in the job directory
   - Return the segment list
3. Implement `POST /process/{job_id}` in `routers/process.py`:
   - Start the pipeline as a `asyncio.create_task` (background task)
   - Store a `JobState` in `app.state.jobs[job_id]` with stage and pct fields
   - Return `{ "job_id": ..., "status": "processing" }` immediately
4. Implement `GET /status/{job_id}` SSE in `routers/status.py`:
   - Use `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"`
   - Poll `app.state.jobs[job_id]` every 500ms and emit the current state as SSE `data:` lines
   - When `stage == "ready"` or `stage == "error"`, emit the final event and close the stream
5. The background pipeline task calls `audio_extractor` then `transcriber`, updating `app.state.jobs[job_id]` at each step

### Relevant Context
- `faster-whisper` with `device="cuda"` and `compute_type="float16"` on an NVIDIA GPU should process a 3-minute clip in under 30 seconds using `small` model
- The WhisperModel should be loaded once at application startup (in `main.py` lifespan), not on each request — loading the model per request would cause a 10-30 second delay on every call
- `language=None` (auto-detect) is essential for Hinglish — forcing `language="en"` will cause Whisper to transliterate Hindi phonetically rather than recognising the code-switching
- `word_timestamps=False` is intentional — segment-level timestamps are sufficient and faster. Word timestamps are a stretch feature.

---

## Sub-Task 4: IBM Granite Processing

**Status:** [ ] pending

### Intent
Implement the Granite processing step. This is the AI intelligence layer that transforms raw Whisper output into publisher-ready, semantically understood content. This is the primary differentiator for hackathon judging.

### Expected Outcomes
- watsonx SDK is configured and authenticated from environment variables
- A single structured Granite API call processes the full transcript
- Granite returns: corrected segments, detected genre, keywords, style recommendation, and a one-sentence summary
- Raw Whisper text and Granite-corrected text are both preserved (for side-by-side demo display)
- If Granite returns unparseable output, the pipeline falls back gracefully to raw Whisper text + a default style
- Granite output is saved to `/{job_id}/granite_result.json`
- SSE event is emitted for `granite_processing` (pct: 60)

### Todo List
1. Set up watsonx account and obtain `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`. Region URL is typically `https://us-south.ml.cloud.ibm.com`. Document in `.env.example`.
2. Implement `services/granite_processor.py`:
   - Instantiate `ibm_watsonx_ai.ModelInference` using model ID string `ibm/granite-3-3-8b-instruct`, credentials from `config.py`
   - Build the prompt (see Prompt Design below)
   - Call `model.generate_text(prompt=..., params=TextGenParameters(max_new_tokens=2000, temperature=0.1))`
   - Parse the JSON response with `json.loads()` inside a try/except
   - On parse failure: log the raw response, return a fallback `ProcessedResult` using raw Whisper segments and `style_engine.get_default_style()`
   - On success: map the parsed output to `ProcessedResult` Pydantic model
3. Implement `services/style_engine.py`:
   - Define 5 `StylePreset` presets: `cinematic`, `social`, `education`, `minimal`, `karaoke`
   - `get_preset_for_genre(genre: str) -> StylePreset` — maps genre strings to presets
   - `get_default_style() -> StylePreset` — returns the `minimal` preset
4. Wire the Granite step into the background pipeline task after transcription

### Relevant Context

**Prompt Design (single-call, structured output):**

The prompt should be a system + user message. System: "You are a subtitle intelligence assistant. You must respond with valid JSON only. Do not include any explanation or markdown."

User message structure:
```
Analyse the following video transcript segments and return a JSON object with these exact keys:
- "corrected_segments": array of objects, each with "id", "corrected_text", "language" ("en", "hi", or "hi-en")
- "genre": one of "study", "talk", "song", "vlog"
- "keywords": array of 5 to 8 strings
- "style_preset": one of "cinematic", "social", "education", "minimal"
- "summary": one sentence describing the video content

Rules:
- For corrected_text: fix grammar, remove filler words (um, uh, like), complete broken sentences. Do not change meaning.
- For language: tag each segment based on the dominant language used in that segment.
- Preserve the original "id" for each segment.

Transcript segments:
[segments as JSON]
```

**Why this works for judging:** The side-by-side of raw Whisper text vs Granite-corrected text is visually compelling and immediately demonstrates value. The genre badge and auto-selected style show that Granite understands the video's purpose, not just its words. This is the story judges need to see.

**Granite model note:** `ibm/granite-3-3-8b-instruct` is available on watsonx Lite/Essentials plans and is well-suited to structured JSON instruction-following. It is significantly cheaper per token than larger models and fast enough for interactive demo use.

---

## Sub-Task 5: Subtitle Composer & SRT Generation

**Status:** [ ] pending

### Intent
Transform the processed segments into a valid SRT file and a plain TXT transcript. This stage has no AI — it is pure text formatting logic. ASS generation is omitted; burn-in uses SRT + FFmpeg `force_style` to keep implementation simple.

### Expected Outcomes
- `services/subtitle_composer.py` generates a valid SRT file from corrected segments
- SRT is saved to `/{job_id}/subtitles.srt`
- A plain TXT file (transcript only, no timestamps) is saved to `/{job_id}/transcript.txt`
- SRT format is valid: sequential index, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, text, blank line
- TXT file is the corrected text of all segments joined by newlines

### Todo List
1. Implement `services/subtitle_composer.py`:
   - `generate_srt(segments: list[Segment], output_path: str) -> None`
     - Convert float seconds to `HH:MM:SS,mmm` format (comma as decimal separator, not period)
     - Write SRT blocks: index, timestamp line, corrected_text, blank line
     - Index starts at 1
   - `generate_txt(segments: list[Segment], output_path: str) -> None`
     - Write `segment.corrected_text` lines joined by newline
2. Call `generate_srt` and `generate_txt` in the background pipeline task after Granite processing
3. Update SSE to emit `composing_subtitles` (pct: 75) and `ready` (pct: 100) with `ProcessedResult` payload
4. End-to-end check: open the generated SRT in VLC or a text editor and confirm format is valid before moving to Sub-task 6

### Relevant Context
- SRT index starts at 1, not 0
- Timestamp format uses comma as decimal separator (`,`), not period — this is a common mistake
- ASS generation is intentionally excluded. Style is applied at burn-in time via `services/style_engine.py` which builds a `force_style` string from the `StylePreset` (see Sub-task 7).
- At this point `GET /status/{job_id}` emits the `ready` event with the full `ProcessedResult` — the frontend unblocks here and renders the editor

---

## Sub-Task 6: React Frontend — Core UI

**Status:** [ ] pending

### Intent
Build the complete React frontend: upload flow, SSE-driven progress tracker, subtitle editor with CSS-overlay preview, style panel, and export buttons.

### Expected Outcomes
- User can drag-and-drop or click to upload an MP4/MP3
- A multi-stage progress bar shows live pipeline status via SSE
- After `ready`, the subtitle editor renders all segments as editable text fields
- The HTML5 video player shows the original video with a CSS-overlay subtitle div synced to `video.currentTime`
- The style panel shows the AI-recommended preset and allows overriding font, color, and position
- Style changes update the CSS overlay in real time — no server round-trip for preview
- Export buttons trigger `POST /export/{job_id}` and then download the returned files
- A side-by-side diff view shows raw Whisper text vs Granite-corrected text (demo highlight)
- Genre badge and keyword tags are shown in the UI

### Todo List
1. `components/Uploader.jsx` — drag-and-drop zone, calls `POST /upload`, navigates to editor on success
2. `hooks/useJobStatus.js` — SSE hook: opens `EventSource` to `GET /status/{job_id}`, returns `{ stage, pct, result, error }`
3. `components/ProgressTracker.jsx` — displays pipeline stages as a step indicator, animates based on SSE `pct`
4. `components/SubtitleEditor.jsx`:
   - Renders a scrollable list of segments, each with an editable textarea for `corrected_text`
   - Shows a small language badge (`EN`, `HI`, `HI-EN`) per segment
   - Shows original Whisper text as greyed-out below each editable field (the side-by-side diff)
   - Clicking a segment seeks the video player to `segment.start`
5. `components/PreviewPlayer.jsx`:
   - HTML5 video element
   - Overlaid div absolutely positioned over the video
   - On each `timeupdate` event, find the active segment (where `currentTime >= start && currentTime < end`) and render its `corrected_text` as a styled div
   - Apply `StylePreset` fields as inline CSS (font-family, font-size, color, position classes via Tailwind)
6. `components/StylePanel.jsx`:
   - Shows genre badge and Granite's one-sentence summary
   - Shows keyword tags
   - Preset selector (5 buttons: cinematic, social, education, minimal, karaoke)
   - Manual overrides: font size slider, color pickers for text and outline, position selector (top/center/bottom)
   - All changes update a shared `styleState` which is passed to `PreviewPlayer` and sent in `POST /export`
7. `components/ExportButtons.jsx`:
   - Three buttons: "Export MP4", "Export SRT", "Export TXT"
   - Calls `POST /export/{job_id}` with current segments and style
   - Shows loading spinner while export is running (MP4 burn-in can take 30-60 seconds)
   - On response, triggers browser download via URL
8. `hooks/useSubtitleEditor.js` — manages local state for all segment text edits and the current style
9. Add a "Reset / Upload New Video" button in `App.jsx` that clears all state and returns to the upload screen
10. Add the app title, CaptainAI branding, and IBM watsonx logo attribution (required for IBM challenge submissions)

### Relevant Context
- The CSS overlay approach for preview means the style the user sees is an approximation, not pixel-perfect to FFmpeg output. This is acceptable and standard for subtitle editors.
- For `PreviewPlayer`, the video source URL is `GET /download/{job_id}/original.{ext}` — the backend needs a static file serving route for the original video (add to `export.py`)
- Tailwind position classes: use `absolute bottom-4 left-0 right-0 text-center` for bottom-center, `absolute top-4 ...` for top
- State management: use React `useState` and `useReducer` only — no Redux, no Zustand. The state is: `segments[]`, `style`, `jobId`. Simple enough for local state.
- Demo script: upload -> watch pipeline complete -> show the Whisper vs Granite diff -> accept the AI style recommendation -> click Export -> download and play the MP4

---

## Sub-Task 7: Export, Burn-in & Download

**Status:** [ ] pending

### Intent
Implement `POST /export/{job_id}` — accepts the user's final segments and style, runs FFmpeg burn-in, and serves the output files for download.

### Expected Outcomes
- `POST /export/{job_id}` accepts `ExportRequest` (segments + style + formats list)
- Backend regenerates SRT/TXT from the user-edited segments
- If `"mp4"` is in formats: FFmpeg burns the SRT subtitles (with `force_style`) into the video and saves `/{job_id}/output.mp4`
- If `"srt"` is in formats: returns the SRT file path
- If `"txt"` is in formats: returns the TXT file path
- All requested file download URLs are returned
- `GET /download/{job_id}/{filename}` serves any file from the job's tmp directory as a streaming response
- After a 30-minute TTL, the job directory is deleted
- Final MP4 plays correctly with legible subtitles; SRT and TXT exports are valid files

### Todo List
1. Implement `services/style_engine.py` (complete the stub from Sub-task 4):
   - `to_force_style_string(style: StylePreset) -> str` — builds FFmpeg `force_style` value, e.g. `FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2`
   - Note: FFmpeg `force_style` colours use BGR hex in the format `&HAABBGGRR` — not standard HTML hex. White is `&H00FFFFFF`. This is the most common FFmpeg subtitle colouring mistake.
2. Implement `services/burner.py`:
   - `burn_subtitles(video_path: str, srt_path: str, force_style: str, output_path: str) -> None`
   - FFmpeg command: `ffmpeg -i {video} -vf "subtitles={srt_path}:force_style='{force_style}'" -c:a copy {output}`
   - On Windows: replace backslashes in `srt_path` with forward slashes before passing to FFmpeg
   - Raise `RuntimeError` on non-zero exit, include stderr in the message
3. Implement `POST /export/{job_id}` in `routers/export.py`:
   - Accept `ExportRequest` body
   - Regenerate SRT and TXT using `subtitle_composer` with user-edited segments
   - Build `force_style` string from `style_engine.to_force_style_string(request.style)`
   - If `"mp4"` requested: call `burner.burn_subtitles()`
   - Build `download_urls` dict: `{ "mp4": "/download/{job_id}/output.mp4", ... }`
   - Return the dict
4. Implement `GET /download/{job_id}/{filename}` in `routers/export.py`:
   - Use `fastapi.responses.FileResponse` with appropriate `media_type`
   - Security: validate `filename` is in the known output file list (`output.mp4`, `subtitles.srt`, `transcript.txt`, `original.*`) — prevent path traversal
5. Implement a background cleanup task in `main.py`:
   - On app startup, schedule a task that runs every 5 minutes
   - Delete any `/tmp/captainai/{job_id}/` directories older than 30 minutes
   - Use `asyncio.create_task` + `asyncio.sleep` loop — no Celery, no scheduler library
6. Integration checks for this sub-task:
   - Export MP4 with each of the 5 style presets and confirm subtitles are visible and correctly positioned
   - Export SRT and open in VLC or a subtitle validator — confirm format is valid
   - Test path-with-spaces scenario on Windows — confirm FFmpeg does not fail
   - Test with a wrong API key to simulate Granite failure: confirm the exported video still has subtitles (fallback path works)
   - Test with a corrupted/invalid upload file: confirm the error message is shown in the UI

### Relevant Context
- `force_style` colour format in FFmpeg is `&HAABBGGRR` (Alpha-Blue-Green-Red), not HTML `#RRGGBB`. White is `&H00FFFFFF`. This is the most common FFmpeg subtitle colouring mistake.
- On Windows, the `subtitles=` filter path must use forward slashes: `C:/tmp/captainai/{job_id}/subtitles.srt`
- `FileResponse` from FastAPI handles `Content-Disposition: attachment` headers automatically when `filename` is provided
- The cleanup task uses `asyncio.create_task` + `asyncio.sleep` in a loop — no Celery, no scheduler library needed

---

## Optional / Stretch Features (Do Not Implement Unless Core is Complete)

These are explicitly flagged as out-of-scope for the one-month deadline:

- STRETCH: Word-level karaoke highlighting — requires `word_timestamps=True` in Whisper, ASS karaoke tags, and a more complex subtitle composer. High implementation cost for moderate demo impact.
- STRETCH: Granite translation — add a second Granite call to translate corrected subtitles to a target language (e.g., English-only subtitles from a Hindi video). Costs extra tokens per job.
- STRETCH: Thumbnail moment extraction — use Granite to identify the most quotable line, extract that video frame with FFmpeg, serve it as a suggested social thumbnail.
- STRETCH: Sentiment-based colour shift — tag segments as positive/negative/neutral and change subtitle colour accordingly. Requires additional Granite output field and more complex style handling.
- STRETCH: Waveform visualiser in the editor — would require a separate audio processing library (e.g., pydub or wavesurfer.js). Not worth the build time for MVP.

---

## Folder Layout Reference

```
captainai/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   │   ├── upload.py
│   │   ├── process.py
│   │   ├── status.py
│   │   └── export.py
│   ├── services/
│   │   ├── validator.py
│   │   ├── audio_extractor.py
│   │   ├── transcriber.py
│   │   ├── granite_processor.py
│   │   ├── subtitle_composer.py
│   │   ├── style_engine.py
│   │   └── burner.py
│   ├── models/
│   │   └── schemas.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Uploader.jsx
│   │   │   ├── ProgressTracker.jsx
│   │   │   ├── SubtitleEditor.jsx
│   │   │   ├── StylePanel.jsx
│   │   │   ├── PreviewPlayer.jsx
│   │   │   └── ExportButtons.jsx
│   │   ├── hooks/
│   │   │   ├── useJobStatus.js
│   │   │   └── useSubtitleEditor.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── .env.example
├── captainai-plan.md
└── README.md
```

---

## API Summary Reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/upload` | Upload and validate file, get job_id |
| POST | `/process/{job_id}` | Start async pipeline |
| GET | `/status/{job_id}` | SSE stream of pipeline progress + final result |
| POST | `/export/{job_id}` | Burn subtitles, generate output files |
| GET | `/download/{job_id}/{filename}` | Serve output file for download |
