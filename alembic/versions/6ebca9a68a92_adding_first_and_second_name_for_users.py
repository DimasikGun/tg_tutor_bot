"""adding first and second name for users

Revision ID: 6ebca9a68a92
Revises: 013dccba6cca
Create Date: 2023-11-01 15:12:58.025422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ebca9a68a92'
down_revision: Union[str, None] = '013dccba6cca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('first_name', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('second_name', sa.String(length=64), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'second_name')
    op.drop_column('users', 'first_name')
    # ### end Alembic commands ###
