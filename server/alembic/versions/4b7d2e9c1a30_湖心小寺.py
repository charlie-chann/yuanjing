"""湖心小寺：重新建回在场和心意两张表（上一版随许愿殿一起删了）

Revision ID: 4b7d2e9c1a30
Revises: 3c9e1f0a7b21
Create Date: 2026-11-15 15:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4b7d2e9c1a30'
down_revision: Union[str, Sequence[str], None] = '3c9e1f0a7b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sanctuary_offerings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('scene', sa.String(length=12), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('slot', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sanctuary_offerings_scene_id', 'sanctuary_offerings', ['scene', 'id'], unique=False)
    op.create_index(op.f('ix_sanctuary_offerings_user_id'), 'sanctuary_offerings', ['user_id'], unique=False)
    op.create_table('sanctuary_presence',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('scene', sa.String(length=12), nullable=False),
    sa.Column('seat', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=12), nullable=True),
    sa.Column('action_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_sanctuary_presence_last_seen'), 'sanctuary_presence', ['last_seen'], unique=False)
    op.create_index(op.f('ix_sanctuary_presence_scene'), 'sanctuary_presence', ['scene'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sanctuary_presence_scene'), table_name='sanctuary_presence')
    op.drop_index(op.f('ix_sanctuary_presence_last_seen'), table_name='sanctuary_presence')
    op.drop_table('sanctuary_presence')
    op.drop_index(op.f('ix_sanctuary_offerings_user_id'), table_name='sanctuary_offerings')
    op.drop_index('ix_sanctuary_offerings_scene_id', table_name='sanctuary_offerings')
    op.drop_table('sanctuary_offerings')
