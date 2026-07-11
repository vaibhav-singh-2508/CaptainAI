from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/status/{job_id}")
async def status(job_id: str):
    return JSONResponse(status_code=501, content={"detail": "Not Implemented"})
