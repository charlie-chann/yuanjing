"""小动物交情：湖心小寺里的猫狗记住每个人

Revision ID: 5c8e3f0d2b41
Revises: 4b7d2e9c1a30
Create Date: 2026-11-15 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5c8e3f0d2b41'
down_revision: Union[str, Sequence[str], None] = '4b7d2e9c1a30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('pet_bonds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('pet', sa.String(length=16), nullable=False),
    sa.Column('affinity', sa.Integer(), nullable=False),
    sa.Column('day', sa.Date(), nullable=True),
    sa.Column('pets_today', sa.Integer(), nullable=False),
    sa.Column('feeds_today', sa.Integer(), nullable=False),
    sa.Column('gift_day', sa.Date(), nullable=True),
    sa.Column('greet_day', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'pet', name='uq_pet_bonds_user_pet')
    )
    op.create_index(op.f('ix_pet_bonds_user_id'), 'pet_bonds', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pet_bonds_user_id'), table_name='pet_bonds')
    op.drop_table('pet_bonds')
