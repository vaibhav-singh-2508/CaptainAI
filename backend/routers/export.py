from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/export/{job_id}")
async def export(job_id: str):
    return JSONResponse(status_code=501, content={"detail": "Not Implemented"})


@router.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    return JSONResponse(status_code=501, content={"detail": "Not Implemented"})
