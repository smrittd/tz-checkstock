"""Allow casefold expansion of valid Unicode warehouse names."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("warehouses", "name_key", existing_type=sa.String(120), type_=sa.String(360))


def downgrade():
    op.alter_column("warehouses", "name_key", existing_type=sa.String(360), type_=sa.String(120))
