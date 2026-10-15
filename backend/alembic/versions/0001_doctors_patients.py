"""create doctors and patients

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("specialty", sa.String(80), nullable=False),
        sa.Column("room", sa.String(20)),
        sa.Column("slot_minutes", sa.SmallInteger(), nullable=False, server_default="15"),
        sa.Column("work_start", sa.Time(), nullable=False, server_default="09:00"),
        sa.Column("work_end", sa.Time(), nullable=False, server_default="17:00"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("slot_minutes BETWEEN 5 AND 120", name="ck_doctors_slot_minutes"),
        sa.CheckConstraint("work_end > work_start", name="ck_doctors_work_hours"),
    )
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, unique=True),
        sa.Column("email", sa.String(254)),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("date_of_birth <= current_date", name="ck_patients_dob"),
    )


def downgrade() -> None:
    op.drop_table("patients")
    op.drop_table("doctors")
