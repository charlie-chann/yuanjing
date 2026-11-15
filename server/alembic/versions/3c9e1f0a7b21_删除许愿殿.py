"""删除许愿殿

Revision ID: 3c9e1f0a7b21
Revises: ff5a00b6d1c6
Create Date: 2026-11-15 12:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = '3c9e1f0a7b21'
down_revision: Union[str, Sequence[str], None] = 'ff5a00b6d1c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_sanctuary_presence_scene', table_name='sanctuary_presence')
    op.drop_index('ix_sanctuary_presence_last_seen', table_name='sanctuary_presence')
    op.drop_table('sanctuary_presence')
    op.drop_index('ix_sanctuary_offerings_user_id', table_name='sanctuary_offerings')
    op.drop_index('ix_sanctuary_offerings_scene_id', table_name='sanctuary_offerings')
    op.drop_table('sanctuary_offerings')


def downgrade() -> None:
    raise NotImplementedError("许愿殿已删除，不再回退")
