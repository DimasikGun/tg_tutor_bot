"""change length of course_name and add datetime to publlishing

Revision ID: d4ef7cf989a2
Revises: 621fa28379e9
Create Date: 2023-10-24 16:32:52.640720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4ef7cf989a2'
down_revision: Union[str, None] = '621fa28379e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('courses', 'name',
               existing_type=sa.VARCHAR(length=60),
               type_=sa.String(length=30),
               existing_nullable=False)
    op.add_column('publications', sa.Column('add_date', sa.DateTime(), nullable=True))
    op.add_column('publications', sa.Column('finish_date', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('publications', 'finish_date')
    op.drop_column('publications', 'add_date')
    op.alter_column('courses', 'name',
               existing_type=sa.String(length=30),
               type_=sa.VARCHAR(length=60),
               existing_nullable=False)
    # ### end Alembic commands ###
