# CaptainAI — API Reference

Base URL: `http://localhost:8000`

---

## `GET /health`

Health check. Returns `200 OK` when the server is running.
Also reports the Whisper inference device selected at startup.

### Response

```json
{
  "status": "ok",
  "whisper_device": "cuda",
  "whisper_compute_type": "float16"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"ok"` when the server is up |
| `whisper_device` | string | `"cuda"` (GPU) or `"cpu"` (fallback) |
| `whisper_compute_type` | string | `"float16"` (CUDA) or `"int8"` (CPU) |

---

## `POST /upload`

Upload a media file. Validates the file and stores it in the job directory.
Returns a `job_id` that is used in all subsequent pipeline requests.

### Request

- **Content-Type:** `multipart/form-data`
- **Field:** `file` — the media file to upload

**Supported extensions:** `.mp4`, `.mp3`, `.mov`, `.webm`

### Success Response

**HTTP 200 OK**

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "my-video.mp4",
  "duration_seconds": 183.42
}
```

| Field | Type | Description |
|---|---|---|
| `job_id` | string (UUID) | Unique job identifier used in all downstream requests |
| `filename` | string | Original filename as uploaded by the client |
| `duration_seconds` | number | Media duration in seconds, parsed by ffprobe |

### Error Responses

All error responses use HTTP **422 Unprocessable Entity** with a JSON body:

```json
{ "detail": "<human-readable message>" }
```

#### Error cases

| Condition | HTTP | `detail` example |
|---|---|---|
| Unsupported file extension | 422 | `"Unsupported file type '.txt'. Allowed extensions: .mp3, .mov, .mp4, .webm."` |
| File too large | 422 | `"File size exceeds the 500 MB limit. Please upload a smaller file."` |
| ffprobe not installed | 422 | `"ffprobe not found. Please ensure FFmpeg is installed and on PATH."` |
| Corrupted or unreadable file | 422 | `"File could not be read by ffprobe — it may be corrupted or unsupported. Details: …"` |
| Zero-duration file | 422 | `"File appears to be corrupted or has zero duration. Please upload a valid media file."` |
| Unexpected server error | 500 | `"Failed to save file: <details>"` |

---

## `POST /process/{job_id}`

Start the processing pipeline for an uploaded job.
Returns immediately — the pipeline runs in the background.
Progress is streamed via `GET /status/{job_id}`.

### Path parameter

| Parameter | Description |
|---|---|
| `job_id` | UUID returned by `POST /upload` |

### Success Response

**HTTP 200 OK**

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "processing"
}
```

### Error Responses

| Condition | HTTP | `detail` example |
|---|---|---|
| Job directory not found (not uploaded first) | 404 | `"Job '…' not found. Upload a file first."` |
| Job already being processed | 409 | `"Job '…' is already being processed (stage: transcribing)."` |

---

## `GET /status/{job_id}`

Stream pipeline progress as **Server-Sent Events (SSE)**.

- **Content-Type:** `text/event-stream`
- Events are emitted every **500 ms**.
- The stream closes automatically when `stage` is `"ready"` or `"error"`.
- The stream closes after **10 minutes** if the pipeline never resolves (guard against crashed jobs).

### Usage

```js
const source = new EventSource(`http://localhost:8000/status/${jobId}`)
source.onmessage = (e) => {
  const state = JSON.parse(e.data)
  // state.stage, state.pct, state.error, state.segments (when ready)
}
```

### SSE event format

Each event is a single `data:` line containing a JSON object:

```
data: {"stage": "transcribing", "pct": 30, "error": null}

```

_(Note the required blank line after each event per the SSE specification.)_

#### Event fields

| Field | Type | Present | Description |
|---|---|---|---|
| `stage` | string | always | Current pipeline stage (see table below) |
| `pct` | integer | always | Progress percentage 0–100 |
| `error` | string \| null | always | Error message, or `null` if no error |
| `segments` | array | only when `stage == "ready"` | Raw Whisper transcript segments (see schema below) |

#### Pipeline stages

| `stage` | `pct` | Description |
|---|---|---|
| `waiting` | 0 | Job state not yet seeded (brief race window between POST and SSE open) |
| `queued` | 0 | Job accepted, pipeline not yet started |
| `extracting_audio` | 10 | FFmpeg extracting / normalising audio to 16 kHz mono WAV |
| `transcribing` | 30 | faster-whisper transcribing audio |
| `ready` | 100 | Pipeline complete; `segments` array included in this event |
| `error` | 0 | Pipeline failed; `error` field contains the reason |

---

## `whisper_segments.json` — schema

Saved to `{TMP_DIR}/{job_id}/whisper_segments.json` after transcription.
Also delivered inline in the SSE `ready` event as the `segments` field.

```json
[
  {
    "id": 1,
    "start": 0.0,
    "end": 4.96,
    "text": "Hello and welcome to the show."
  },
  {
    "id": 2,
    "start": 4.96,
    "end": 9.12,
    "text": "Aaj hum baat karenge AI ke baare mein."
  }
]
```

#### Segment fields

| Field | Type | Description |
|---|---|---|
| `id` | integer | 1-based segment index assigned by Whisper |
| `start` | number | Segment start time in seconds (rounded to 3 decimal places) |
| `end` | number | Segment end time in seconds (rounded to 3 decimal places) |
| `text` | string | Raw Whisper transcript — no grammar correction applied at this stage |

**Language detection:** Whisper uses `language=None` (auto-detect). For Hinglish / code-switched audio the model will produce mixed-script text directly in `text`. Granite processing (Sub-task 4) adds the per-segment `language` tag (`"en"`, `"hi"`, or `"hi-en"`) and a `corrected_text` field.

---

## `POST /export/{job_id}`

_(Sub-task 7 — not yet implemented)_

Returns **501 Not Implemented**.

---

## `GET /download/{job_id}/{filename}`

_(Sub-task 7 — not yet implemented)_

Returns **501 Not Implemented**.

---

## File Storage

All job files live under one directory per job:

```
{TMP_DIR}/{job_id}/
  original.{ext}          — uploaded source file (mp4, mp3, mov, webm)
  audio.wav               — 16 kHz mono PCM WAV extracted by FFmpeg (Sub-task 3)
  whisper_segments.json   — raw Whisper transcript (Sub-task 3)
  granite_result.json     — Granite-corrected segments + metadata (Sub-task 4)
  subtitles.srt           — generated SRT file (Sub-task 5)
  transcript.txt          — plain-text transcript (Sub-task 5)
  output.mp4              — burned-in video (Sub-task 7)
```

Default `TMP_DIR`: `/tmp/captainai` (override via `TMP_DIR` env var)

Job directories are automatically cleaned up after 30 minutes (implemented in Sub-task 7).
