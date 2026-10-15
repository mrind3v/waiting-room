"""create appointments with no-overlap exclusion constraint

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey("doctors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="BOOKED"),
        sa.Column("checked_in_at", sa.DateTime(timezone=True)),
        sa.Column("consultation_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_appointments_range"),
        sa.CheckConstraint(
            "status IN ('BOOKED','CHECKED_IN','IN_CONSULTATION','DONE','CANCELLED')",
            name="ck_appointments_status",
        ),
    )
    op.create_index("ix_appointments_doctor_starts", "appointments", ["doctor_id", "starts_at"])
    op.create_index("ix_appointments_starts", "appointments", ["starts_at"])
    op.create_index("ix_appointments_patient", "appointments", ["patient_id"])
    # A doctor can never have two non-cancelled appointments whose time ranges overlap.
    # Half-open [) ranges let back-to-back slots coexist; enforced atomically by Postgres.
    op.execute(
        """
        ALTER TABLE appointments ADD CONSTRAINT appointments_no_doctor_overlap
        EXCLUDE USING gist (doctor_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)
        WHERE (status <> 'CANCELLED')
        """
    )


def downgrade() -> None:
    op.drop_table("appointments")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
