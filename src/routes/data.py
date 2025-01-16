from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os

from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController, ProcessController

import aiofiles
from models import ResponseSignal
import logging
from .schemes.data import ProcessResquest

from models.ProjectModel import ProjectModel
from models.db_schemes import DataChunk
from models.ChunkModel import ChunkModel

logger = logging.getLogger("uvicorn.error")
data_router = APIRouter(prefix="/api/v1/data", tags=["apiv1", "data"])


@data_router.post("/upload/{project_id}")
async def upload_data(
    request: Request,
    project_id: str,
    file: UploadFile,
    app_settings: Settings = Depends(get_settings),
):

    data_controller = DataController()
    project_model = ProjectModel(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)
    # validate the file properties
    is_valid, signal = data_controller.validate_uploaded_file(file=file)
    # return {"is_valid": is_valid, "response signal": signal}
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"signal": signal}
        )
    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_path, file_id = data_controller.generate_unique_filepath(
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

    return JSONResponse(
        content={
            "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
            "file_id": file_id,
            "pro_id": str(project.id),
        }
    )


@data_router.post("/process/{project_id}")
async def process_endpoint(
    request: Request, project_id: str, process_request: ProcessResquest
):
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size

    do_reset = process_request.do_reset
    project_model = ProjectModel(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)

    chunk_model = ChunkModel(db_client=request.app.db_client)

    process_controller = ProcessController(project_id=project_id)
    file_content = process_controller.get_file_content(file_id=file_id)
    file_chunks = process_controller.process_file_content(
        file_content=file_content,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        file_id=file_id,
    )
    if file_chunks is None or len(file_chunks) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROCESSING_FAILED.value},
        )
    file_cuknks_records = [
        DataChunk(
            chunk_text=chunk.page_content,
            chunk_metadata=chunk.metadata,
            chunk_order=i + 1,
            chunk_project_id=project.id,
        )
        for i, chunk in enumerate(file_chunks)
    ]

    if do_reset == 1:
        _ = await chunk_model.delete_chunks_by_project_id(project_id=project_id)

    no_recordes = await chunk_model.insert_many_chunks(chunks=file_cuknks_records)
    return JSONResponse(
        content={
            "signal": ResponseSignal.PROCESSING_SUCCESS.value,
            "inserted_chunks": no_recordes,
        },
    )
