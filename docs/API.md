# CaptainAI — API Reference

Base URL: `http://localhost:8000`

---

## `GET /health`

Health check. Returns `200 OK` when the server is running.

### Response

```json
{ "status": "ok" }
```

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

_(Sub-task 3 — not yet implemented)_

Returns **501 Not Implemented**.

---

## `GET /status/{job_id}`

_(Sub-task 3 — not yet implemented)_

Returns **501 Not Implemented**.

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

Uploaded files are stored at:

```
{TMP_DIR}/{job_id}/original.{ext}
```

Default `TMP_DIR`: `/tmp/captainai`

Job directories are automatically cleaned up after 30 minutes (implemented in Sub-task 7).
