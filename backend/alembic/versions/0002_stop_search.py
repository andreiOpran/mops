"""Stop search: stop description and accent-insensitive name index.

Adds stops.description (GTFS stop_desc, the street) to tell apart the many
stops that share a name (e.g. 7 x "Piata Unirii"), and a trigram index on
f_unaccent(lower(name)) so partial names match with or without diacritics.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-16 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('stops', sa.Column('description', sa.Text(), nullable=True))

    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # unaccent() is only STABLE (its dictionary is looked up through
    # search_path), so it cannot be used in an index. Naming the dictionary
    # explicitly makes this wrapper safe to declare IMMUTABLE.
    op.execute(
        """
        CREATE FUNCTION f_unaccent(text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
        """
    )
    op.create_index(
        'ix_stops_name_search',
        'stops',
        [sa.literal_column('f_unaccent(lower(name)) gin_trgm_ops')],
        postgresql_using='gin',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_stops_name_search', table_name='stops', postgresql_using='gin')
    op.execute("DROP FUNCTION f_unaccent(text)")
    op.drop_column('stops', 'description')
