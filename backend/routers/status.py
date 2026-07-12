"""
Status router — Sub-task 3.

GET /status/{job_id}
  Streams Server-Sent Events (SSE) reporting pipeline progress.

  Each event is a JSON-encoded JobState object:
    data: {"stage": "extracting_audio", "pct": 10, "error": null}

  The stream closes when stage == "ready" or stage == "error".

  Polling interval: 500 ms — fast enough for a responsive progress bar
  without hammering the event loop.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_POLL_INTERVAL = 0.5   # seconds between SSE events
_TERMINAL_STAGES = {"ready", "error"}
# Stop streaming after this many seconds even if stage never resolves
# (guards against stale jobs from crashed pipelines)
_STREAM_TIMEOUT = 600  # 10 minutes


@router.get("/status/{job_id}")
async def stream_status(job_id: str, request: Request):
    """
    SSE endpoint — stream job progress until complete or error.

    The client opens an EventSource to this URL.  Events are emitted
    every 500 ms; the stream closes on "ready" or "error".
    """
    async def event_generator():
        elapsed = 0.0

        # If the job doesn't exist yet, emit a single "pending" event and
        # then start polling so the client doesn't have to retry.
        while True:
            # Respect client disconnect
            if await request.is_disconnected():
                logger.debug("[%s] SSE client disconnected", job_id)
                return

            state = request.app.state.jobs.get(job_id)

            if state is None:
                # Job not yet seeded (race between POST /process response
                # and the client opening SSE) — send a waiting event
                payload = json.dumps({"stage": "waiting", "pct": 0, "error": None})
            else:
                payload = json.dumps({
                    "stage": state.get("stage", "unknown"),
                    "pct": state.get("pct", 0),
                    "error": state.get("error"),
                    # Include composed subtitles when ready (Sub-task 5)
                    **({"subtitles": state["subtitles"]} if "subtitles" in state else {}),
                    # Include Granite result when ready (Sub-task 4)
                    **({"granite_result": state["granite_result"]} if "granite_result" in state else {}),
                })

            yield f"data: {payload}\n\n"

            stage = (state or {}).get("stage")
            if stage in _TERMINAL_STAGES:
                return

            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

            if elapsed >= _STREAM_TIMEOUT:
                timeout_payload = json.dumps({
                    "stage": "error",
                    "pct": 0,
                    "error": "Pipeline timed out after 10 minutes.",
                })
                yield f"data: {timeout_payload}\n\n"
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering in production
        },
    )
