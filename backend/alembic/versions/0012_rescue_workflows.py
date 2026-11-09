"""Add rescue appointments, participation, evidence, supplies and contributions. No grants."""

from pathlib import Path

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE rescue_animals SET publication=NULL WHERE publication='null'::jsonb")
    op.execute("UPDATE rescue_funds SET public_report=NULL WHERE public_report='null'::jsonb")
    op.execute("ALTER TABLE rescue_animals ADD COLUMN profile JSONB NOT NULL DEFAULT '{}'::jsonb")
    for statement in Path(__file__).with_suffix(".sql").read_text(encoding="utf-8-sig").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in (
        "rescue_visit_slots",
        "rescue_messages",
        "rescue_refunds",
        "rescue_donation_events",
        "rescue_donation_intents",
        "rescue_campaigns",
        "rescue_supply_pledges",
        "rescue_supply_needs",
        "rescue_supply_movements",
        "rescue_subscriptions",
        "rescue_assets",
        "rescue_reminders",
        "rescue_care_schedules",
        "rescue_shifts",
        "rescue_partners",
        "rescue_consents",
        "rescue_application_checks",
        "rescue_appointments",
    ):
        op.drop_table(table)
    op.drop_column("rescue_animals", "profile")
