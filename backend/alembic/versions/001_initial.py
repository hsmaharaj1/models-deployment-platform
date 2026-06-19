"""initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── projects ───────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── model_framework enum ───────────────────────────────
    model_framework = postgresql.ENUM("sklearn", "pytorch", name="model_framework")
    model_framework.create(op.get_bind())

    # ── model_status enum ─────────────────────────────────
    model_status = postgresql.ENUM("uploaded", "ready", "deprecated", name="model_status")
    model_status.create(op.get_bind())

    # ── model_versions ────────────────────────────────────
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_tag", sa.String(50), nullable=False),
        sa.Column("framework", postgresql.ENUM("sklearn", "pytorch", name="model_framework", create_type=False), nullable=False),
        sa.Column("artifact_path", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", postgresql.ENUM("uploaded", "ready", "deprecated", name="model_status", create_type=False), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_versions_project_id", "model_versions", ["project_id"])

    # ── deployment_status enum ────────────────────────────
    deployment_status = postgresql.ENUM("pending", "starting", "running", "stopped", "failed", name="deployment_status")
    deployment_status.create(op.get_bind())

    # ── deployments ───────────────────────────────────────
    op.create_table(
        "deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("container_id", sa.String(255), nullable=True),
        sa.Column("endpoint_url", sa.String(512), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("status", postgresql.ENUM("pending", "starting", "running", "stopped", "failed", name="deployment_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deployments_model_version_id", "deployments", ["model_version_id"])

    # ── job_status enum ───────────────────────────────────
    job_status = postgresql.ENUM("queued", "processing", "completed", "failed", name="job_status")
    job_status.create(op.get_bind())

    # ── inference_jobs ────────────────────────────────────
    op.create_table(
        "inference_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deployment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("input_payload", postgresql.JSONB(), nullable=True),
        sa.Column("output_payload", postgresql.JSONB(), nullable=True),
        sa.Column("status", postgresql.ENUM("queued", "processing", "completed", "failed", name="job_status", create_type=False), nullable=False, server_default="queued"),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inference_jobs_deployment_id", "inference_jobs", ["deployment_id"])


def downgrade() -> None:
    op.drop_table("inference_jobs")
    op.drop_table("deployments")
    op.drop_table("model_versions")
    op.drop_table("projects")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS deployment_status")
    op.execute("DROP TYPE IF EXISTS model_status")
    op.execute("DROP TYPE IF EXISTS model_framework")
