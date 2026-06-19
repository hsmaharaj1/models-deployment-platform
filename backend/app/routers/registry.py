import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.model_version import ModelVersion, ModelFramework
from app.schemas.model_version import ModelVersionResponse, ModelVersionUpdate
from app.core.auth import get_current_user
from app.core.storage import get_storage, build_artifact_path, StorageBackend

router = APIRouter(tags=["registry"])

ALLOWED_EXTENSIONS = {
    ModelFramework.sklearn: [".pkl", ".joblib"],
    ModelFramework.pytorch: [".pt", ".pth"],
}


def validate_file_extension(filename: str, framework: ModelFramework) -> None:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = ALLOWED_EXTENSIONS[framework]
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}' for framework '{framework.value}'. Allowed: {allowed}",
        )


@router.post("/projects/{project_id}/models", response_model=ModelVersionResponse, status_code=201)
async def upload_model(
    project_id: uuid.UUID,
    version_tag: str = Form(...),
    framework: ModelFramework = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    _: User = Depends(get_current_user),
):
    # Validate project exists
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file extension matches framework
    validate_file_extension(file.filename or "model.pkl", framework)

    # Check version tag is unique within project
    existing = await db.execute(
        select(ModelVersion).where(
            ModelVersion.project_id == project_id,
            ModelVersion.version_tag == version_tag,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Version tag '{version_tag}' already exists in this project",
        )

    # Generate model ID for path building
    model_id = uuid.uuid4()
    dest_path = build_artifact_path(project_id, model_id, file.filename or "model")

    # Save artifact
    artifact_path, file_size = await storage.save(file, dest_path)

    # Create DB record
    model = ModelVersion(
        id=model_id,
        project_id=project_id,
        version_tag=version_tag,
        framework=framework,
        artifact_path=artifact_path,
        original_filename=file.filename or "model",
        file_size_bytes=file_size,
        description=description,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)

    return ModelVersionResponse(
        id=str(model.id),
        project_id=str(model.project_id),
        version_tag=model.version_tag,
        framework=model.framework,
        original_filename=model.original_filename,
        file_size_bytes=model.file_size_bytes,
        description=model.description,
        metadata_json=model.metadata_json,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("/projects/{project_id}/models", response_model=list[ModelVersionResponse])
async def list_models(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.project_id == project_id)
        .order_by(ModelVersion.created_at.desc())
    )
    models = result.scalars().all()
    return [
        ModelVersionResponse(
            id=str(m.id),
            project_id=str(m.project_id),
            version_tag=m.version_tag,
            framework=m.framework,
            original_filename=m.original_filename,
            file_size_bytes=m.file_size_bytes,
            description=m.description,
            metadata_json=m.metadata_json,
            status=m.status,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in models
    ]


@router.get("/models/{model_id}", response_model=ModelVersionResponse)
async def get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")

    return ModelVersionResponse(
        id=str(model.id),
        project_id=str(model.project_id),
        version_tag=model.version_tag,
        framework=model.framework,
        original_filename=model.original_filename,
        file_size_bytes=model.file_size_bytes,
        description=model.description,
        metadata_json=model.metadata_json,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.patch("/models/{model_id}", response_model=ModelVersionResponse)
async def update_model(
    model_id: uuid.UUID,
    payload: ModelVersionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")

    if payload.description is not None:
        model.description = payload.description
    if payload.status is not None:
        model.status = payload.status
    if payload.metadata_json is not None:
        model.metadata_json = payload.metadata_json

    await db.flush()
    await db.refresh(model)

    return ModelVersionResponse(
        id=str(model.id),
        project_id=str(model.project_id),
        version_tag=model.version_tag,
        framework=model.framework,
        original_filename=model.original_filename,
        file_size_bytes=model.file_size_bytes,
        description=model.description,
        metadata_json=model.metadata_json,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")

    # Delete artifact from storage
    await storage.delete(model.artifact_path)

    # Delete DB record
    await db.delete(model)
    await db.commit()
