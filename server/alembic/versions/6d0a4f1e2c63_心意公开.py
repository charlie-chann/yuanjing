"""心意公开：红布条、木牌上的字给不给别人看，按写的时候界面上怎么说的记下来

Revision ID: 6d0a4f1e2c63
Revises: 5c8e3f0d2b41
Create Date: 2026-11-17 09:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6d0a4f1e2c63'
down_revision: Union[str, Sequence[str], None] = '5c8e3f0d2b41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 已经写下的都是老版本写的（当时说的是「只有你自己看得到」）：一律不公开
    with op.batch_alter_table('sanctuary_offerings') as batch:
        batch.add_column(sa.Column('public', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('sanctuary_offerings') as batch:
        batch.drop_column('public')
