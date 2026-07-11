from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import upload, process, status, export

app = FastAPI(title="CaptainAI", version="0.1.0")

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
    return {"status": "ok"}
