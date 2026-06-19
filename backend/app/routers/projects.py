import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.project import Project
from app.models.model_version import ModelVersion
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.core.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    try:
        await db.flush()
        await db.refresh(project)
    except Exception as e:
        await db.rollback()
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A project named '{payload.name}' already exists",
            )
        raise
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        model_count=0,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # Subquery: count model versions per project
    count_subq = (
        select(ModelVersion.project_id, func.count(ModelVersion.id).label("model_count"))
        .group_by(ModelVersion.project_id)
        .subquery()
    )
    result = await db.execute(
        select(Project, func.coalesce(count_subq.c.model_count, 0).label("model_count"))
        .outerjoin(count_subq, Project.id == count_subq.c.project_id)
        .order_by(Project.created_at.desc())
    )
    rows = result.all()
    return [
        ProjectResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            created_at=p.created_at,
            updated_at=p.updated_at,
            model_count=mc,
        )
        for p, mc in rows
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, db)

    count_result = await db.execute(
        select(func.count(ModelVersion.id)).where(ModelVersion.project_id == project_id)
    )
    model_count = count_result.scalar_one()

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        model_count=model_count,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, db)
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    await db.flush()
    await db.refresh(project)

    count_result = await db.execute(
        select(func.count(ModelVersion.id)).where(ModelVersion.project_id == project_id)
    )
    model_count = count_result.scalar_one()

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        model_count=model_count,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, db)
    await db.delete(project)
    await db.commit()
