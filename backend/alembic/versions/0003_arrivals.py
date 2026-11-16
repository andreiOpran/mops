"""Arrivals table and feed_versions.retrieved_at (US-02a, US-03).

- arrivals: one row per (service_date, trip_id, stop_sequence); not
  partitioned for now (decision 2 in docs/model-date.md, section 5).
- feed_versions.retrieved_at: when the collector downloaded the archive;
  picks the schedule version valid on a given day (decision 5).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16 18:22:04.038146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('arrivals',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('service_date', sa.Date(), nullable=False),
    sa.Column('trip_id', sa.Text(), nullable=False),
    sa.Column('route_id', sa.Text(), nullable=False),
    sa.Column('stop_id', sa.Text(), nullable=False),
    sa.Column('stop_sequence', sa.SmallInteger(), nullable=False),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('method', sa.Enum('stopped_at', 'sequence_advance', 'trip_update_estimate', name='arrival_method'), nullable=False),
    sa.Column('vehicle_id', sa.Text(), nullable=True),
    sa.Column('feed_version_id', sa.Integer(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delay_seconds', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['feed_version_id'], ['feed_versions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('service_date', 'trip_id', 'stop_sequence')
    )
    op.create_index('ix_arrivals_route_day', 'arrivals', ['route_id', 'service_date'], unique=False)
    op.create_index('ix_arrivals_stop_day', 'arrivals', ['stop_id', 'service_date'], unique=False)
    op.add_column('feed_versions', sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_feed_versions_retrieved_at'), 'feed_versions', ['retrieved_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_feed_versions_retrieved_at'), table_name='feed_versions')
    op.drop_column('feed_versions', 'retrieved_at')
    op.drop_index('ix_arrivals_stop_day', table_name='arrivals')
    op.drop_index('ix_arrivals_route_day', table_name='arrivals')
    op.drop_table('arrivals')
    sa.Enum(name='arrival_method').drop(op.get_bind(), checkfirst=True)
