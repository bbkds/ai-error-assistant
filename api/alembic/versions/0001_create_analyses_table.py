"""create analyses table

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # # Версионирование: создание таблицы analyses
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(100), default="unknown"),
        sa.Column("category", sa.String(100)),
        sa.Column("severity", sa.String(50)),
        sa.Column("confidence", sa.Float()),
        sa.Column("explanation", sa.Text()),
        sa.Column("recommendations", sa.Text()),
        sa.Column("task_id", sa.String(200), index=True, nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
    )


def downgrade() -> None:
    op.drop_table("analyses")
