from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/process/{job_id}")
async def process(job_id: str):
    return JSONResponse(status_code=501, content={"detail": "Not Implemented"})
