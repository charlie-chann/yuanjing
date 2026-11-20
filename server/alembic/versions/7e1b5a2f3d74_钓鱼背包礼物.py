"""钓鱼、背包、小动物的礼物：inventory、fish_dex、fishing_days、pet_memos

Revision ID: 7e1b5a2f3d74
Revises: 6d0a4f1e2c63
Create Date: 2026-11-19 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7e1b5a2f3d74'
down_revision: Union[str, Sequence[str], None] = '6d0a4f1e2c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('inventory', 'fish_dex', 'fishing_days', 'pet_memos')


def upgrade() -> None:
    # 四张都是新表、没有给老表加列。本地的 SQLite 启动时 create_all 可能已经把它们建出来了：已有的就跳过
    has = set(sa.inspect(op.get_bind()).get_table_names())
    if 'inventory' not in has:
        op.create_table('inventory',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.String(length=24), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'item_id')
        )
    if 'fish_dex' not in has:
        op.create_table('fish_dex',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('fish_id', sa.String(length=16), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('best_mm', sa.Integer(), nullable=False),
        sa.Column('first_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'fish_id')
        )
    if 'fishing_days' not in has:
        op.create_table('fishing_days',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=True),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
        )
    if 'pet_memos' not in has:
        op.create_table('pet_memos',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('pet', sa.String(length=16), nullable=False),
        sa.Column('milestones', sa.Integer(), nullable=False),
        sa.Column('favs', sa.String(length=120), nullable=False),
        sa.Column('gifts_seen', sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'pet')
        )


def downgrade() -> None:
    for t in reversed(TABLES):
        op.drop_table(t)
