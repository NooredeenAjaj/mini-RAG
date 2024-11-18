from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os

from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController

import aiofiles
from models import ResponseSignal
import logging

logger = logging.getLogger("uvicorn.error")
data_router = APIRouter(prefix="/api/v1/data", tags=["apiv1", "data"])


@data_router.post("/upload/{project_id}")
async def upload_data(
    project_id: str, file: UploadFile, app_settings: Settings = Depends(get_settings)
):
    data_controller = DataController()
    # validate the file properties
    is_valid, signal = data_controller.validate_uploaded_file(file=file)
    # return {"is_valid": is_valid, "response signal": signal}
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"signal": signal}
        )
    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_path = data_controller.generate_unique_filepath(
        orig_file_name=file.filename, project_id=project_id
    )
    try:
        async with aiofiles.open(file_path, "wb") as f:

            #:= för att både läsa en "chunk" av data från filen och samtidigt kontrollera om den är tom:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)

    except Exception as e:
        logger.error(f"Error while upploding file : {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value},
        )

    return JSONResponse(content={"signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value})
