from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/upload")
async def upload():
    return JSONResponse(status_code=501, content={"detail": "Not Implemented"})
