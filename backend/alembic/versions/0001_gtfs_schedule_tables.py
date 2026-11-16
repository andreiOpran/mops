"""GTFS schedule tables (US-01).

Versioned timetable: every imported GTFS archive is one feed_versions row and
all schedule rows cascade-delete with it. See docs/model-date.md, section 2.1.

Revision ID: 0001
Revises: 
Create Date: 2026-11-16 12:25:42.079001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('feed_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('feed_version', sa.Text(), nullable=False),
    sa.Column('sha256', sa.CHAR(length=64), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_to', sa.Date(), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sha256')
    )
    op.create_table('agencies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('feed_version_id', sa.Integer(), nullable=False),
    sa.Column('agency_id', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['feed_version_id'], ['feed_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_version_id', 'agency_id')
    )
    op.create_table('services',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('feed_version_id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.Text(), nullable=False),
    sa.Column('monday', sa.Boolean(), nullable=False),
    sa.Column('tuesday', sa.Boolean(), nullable=False),
    sa.Column('wednesday', sa.Boolean(), nullable=False),
    sa.Column('thursday', sa.Boolean(), nullable=False),
    sa.Column('friday', sa.Boolean(), nullable=False),
    sa.Column('saturday', sa.Boolean(), nullable=False),
    sa.Column('sunday', sa.Boolean(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.ForeignKeyConstraint(['feed_version_id'], ['feed_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_version_id', 'service_id')
    )
    op.create_table('stops',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('feed_version_id', sa.Integer(), nullable=False),
    sa.Column('stop_id', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lon', sa.Float(), nullable=False),
    sa.Column('parent_stop_pk', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['feed_version_id'], ['feed_versions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_stop_pk'], ['stops.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_version_id', 'stop_id')
    )
    op.create_table('routes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('feed_version_id', sa.Integer(), nullable=False),
    sa.Column('agency_pk', sa.Integer(), nullable=False),
    sa.Column('route_id', sa.Text(), nullable=False),
    sa.Column('short_name', sa.Text(), nullable=False),
    sa.Column('long_name', sa.Text(), nullable=True),
    sa.Column('route_type', sa.SmallInteger(), nullable=False),
    sa.Column('color', sa.CHAR(length=6), nullable=True),
    sa.ForeignKeyConstraint(['agency_pk'], ['agencies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['feed_version_id'], ['feed_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_version_id', 'route_id')
    )
    op.create_index(op.f('ix_routes_short_name'), 'routes', ['short_name'], unique=False)
    op.create_table('service_exceptions',
    sa.Column('service_pk', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('exception_type', sa.SmallInteger(), nullable=False),
    sa.ForeignKeyConstraint(['service_pk'], ['services.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('service_pk', 'date')
    )
    op.create_table('trips',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('feed_version_id', sa.Integer(), nullable=False),
    sa.Column('trip_id', sa.Text(), nullable=False),
    sa.Column('route_pk', sa.Integer(), nullable=False),
    sa.Column('service_pk', sa.Integer(), nullable=False),
    sa.Column('headsign', sa.Text(), nullable=True),
    sa.Column('direction_id', sa.SmallInteger(), nullable=True),
    sa.ForeignKeyConstraint(['feed_version_id'], ['feed_versions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['route_pk'], ['routes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['service_pk'], ['services.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_version_id', 'trip_id')
    )
    op.create_table('stop_times',
    sa.Column('trip_pk', sa.Integer(), nullable=False),
    sa.Column('stop_sequence', sa.SmallInteger(), nullable=False),
    sa.Column('stop_pk', sa.Integer(), nullable=False),
    sa.Column('arrival_seconds', sa.Integer(), nullable=True),
    sa.Column('departure_seconds', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['stop_pk'], ['stops.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['trip_pk'], ['trips.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('trip_pk', 'stop_sequence')
    )
    op.create_index(op.f('ix_stop_times_stop_pk'), 'stop_times', ['stop_pk'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_stop_times_stop_pk'), table_name='stop_times')
    op.drop_table('stop_times')
    op.drop_table('trips')
    op.drop_table('service_exceptions')
    op.drop_index(op.f('ix_routes_short_name'), table_name='routes')
    op.drop_table('routes')
    op.drop_table('stops')
    op.drop_table('services')
    op.drop_table('agencies')
    op.drop_table('feed_versions')
