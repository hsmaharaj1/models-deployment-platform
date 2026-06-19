import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, BigInteger, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class ModelFramework(str, PyEnum):
    sklearn = "sklearn"
    pytorch = "pytorch"


class ModelStatus(str, PyEnum):
    uploaded = "uploaded"
    ready = "ready"
    deprecated = "deprecated"


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_tag: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "v1.0"
    framework: Mapped[ModelFramework] = mapped_column(
        Enum(ModelFramework, name="model_framework"), nullable=False
    )
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # hyperparams, metrics, etc.
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus, name="model_status"), nullable=False, default=ModelStatus.ready
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="model_versions")  # noqa: F821
    deployments: Mapped[list["Deployment"]] = relationship(  # noqa: F821
        "Deployment", back_populates="model_version", cascade="all, delete-orphan"
    )
