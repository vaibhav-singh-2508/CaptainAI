"""
CaptainAI — FastAPI application entry point.

Lifespan:
- On startup: probe for CUDA (live runtime test), load WhisperModel once,
  inject into transcriber.
- On shutdown: nothing special needed (process exit cleans up threads).

CUDA note for Windows:
  Python 3.8+ no longer includes PATH entries in the DLL search path for
  security reasons.  os.add_dll_directory() must be called explicitly to
  make CUDA runtime DLLs (cublas64_12.dll, cudart64_12.dll, …) findable
  before ctranslate2 tries to load them.  The CUDA bin path is derived from
  the environment variable CUDA_PATH (set by the CUDA Toolkit installer) with
  a hard-coded fallback.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from routers import upload, process, status, export
from services import transcriber

logger = logging.getLogger(__name__)

# ── CUDA DLL directory registration (Windows only) ───────────────────────────
# On Windows, Python 3.8+ does not include PATH entries in the DLL search path.
# We must explicitly register the CUDA bin directory so ctranslate2 can load
# cublas64_12.dll, cudart64_12.dll, etc.
def _register_cuda_dll_directory() -> str | None:
    """
    Register the CUDA Toolkit bin directory with os.add_dll_directory().

    Returns the path that was registered, or None if not on Windows / not found.
    """
    if os.name != "nt":
        return None  # Linux/macOS: PATH is sufficient

    # Prefer the CUDA_PATH env var set by the CUDA Toolkit installer
    cuda_root = os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
    if not cuda_root:
        # Hard-coded fallback for the known installation location
        cuda_root = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5"

    cuda_bin = Path(cuda_root) / "bin"
    if cuda_bin.exists():
        try:
            os.add_dll_directory(str(cuda_bin))
            logger.info("Registered CUDA DLL directory: %s", cuda_bin)
            return str(cuda_bin)
        except Exception as exc:
            logger.warning("Could not register CUDA DLL directory %s: %s", cuda_bin, exc)
    else:
        logger.warning("CUDA bin directory not found at %s", cuda_bin)

    return None


# ── WhisperModel loader with live runtime CUDA test ───────────────────────────

def _try_load_cuda_model(model_size: str):
    """
    Attempt to load the WhisperModel on CUDA.

    Performs a live runtime inference test on a 1-second silent clip
    to confirm the GPU and its runtime libraries are fully functional.

    Returns the model if successful, or raises RuntimeError with details.
    """
    import ctranslate2
    import subprocess
    import tempfile

    # Fast capability check first — avoids importing WhisperModel
    # if the driver itself doesn't support CUDA at all
    cuda_types = ctranslate2.get_supported_compute_types("cuda")
    if "float16" not in cuda_types:
        raise RuntimeError(
            f"CUDA driver does not support float16. "
            f"Supported types: {cuda_types}"
        )

    from faster_whisper import WhisperModel

    logger.info(
        "CUDA capable — attempting to load '%s' on GPU (float16)…", model_size
    )
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    # ── Live inference smoke-test ─────────────────────────────────────────
    # Generate a 1-second silent 16 kHz mono WAV in a temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_wav = f.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                "-t", "1",
                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                tmp_wav,
            ],
            capture_output=True,
            check=True,
        )
        # Run a real transcription pass — this will throw if cuBLAS etc. is missing
        segs_iter, _ = model.transcribe(
            tmp_wav,
            language=None,
            task="transcribe",
            word_timestamps=False,
        )
        list(segs_iter)  # consume the iterator to force actual inference
    finally:
        try:
            os.unlink(tmp_wav)
        except OSError:
            pass

    logger.info("CUDA smoke-test passed — GPU inference is working.")
    return model


def _load_whisper_model() -> tuple:
    """
    Load the WhisperModel, using CUDA if the runtime is fully functional.

    Strategy:
    1. Register CUDA DLL directory (Windows).
    2. Try CUDA + float16 with a live inference test.
    3. On any failure, log the reason and fall back to CPU + int8.

    Returns:
        (model, device, compute_type)
    """
    _register_cuda_dll_directory()

    # ── Attempt GPU ──────────────────────────────────────────────────────
    try:
        model = _try_load_cuda_model(config.WHISPER_MODEL_SIZE)
        logger.info(
            "WhisperModel ready: size=%s  device=cuda  compute_type=float16",
            config.WHISPER_MODEL_SIZE,
        )
        return model, "cuda", "float16"
    except Exception as exc:
        logger.warning(
            "GPU load failed (%s) — falling back to CPU.", exc
        )

    # ── CPU fallback ─────────────────────────────────────────────────────
    from faster_whisper import WhisperModel

    logger.info(
        "Loading WhisperModel '%s' on CPU (int8)…", config.WHISPER_MODEL_SIZE
    )
    model = WhisperModel(
        config.WHISPER_MODEL_SIZE,
        device="cpu",
        compute_type="int8",
    )
    logger.info(
        "WhisperModel ready: size=%s  device=cpu  compute_type=int8",
        config.WHISPER_MODEL_SIZE,
    )
    return model, "cpu", "int8"


# ── FastAPI lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    app.state.jobs = {}

    logger.info("CaptainAI startup: loading Whisper model…")
    model, device, compute_type = _load_whisper_model()
    transcriber.set_model(model)

    # Expose for /health and diagnostics
    app.state.whisper_device = device
    app.state.whisper_compute_type = compute_type

    logger.info(
        "CaptainAI startup complete.  Whisper: size=%s device=%s compute=%s",
        config.WHISPER_MODEL_SIZE, device, compute_type,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("CaptainAI shutdown.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="CaptainAI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(process.router)
app.include_router(status.router)
app.include_router(export.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "whisper_device": getattr(app.state, "whisper_device", "unknown"),
        "whisper_compute_type": getattr(app.state, "whisper_compute_type", "unknown"),
    }
