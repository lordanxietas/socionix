"""func12

Revision ID: 30ab132966bd
Revises: 8b296bf68af0
Create Date: 2023-09-28 23:30:08.797011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30ab132966bd'
down_revision: Union[str, None] = '8b296bf68af0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('questions', 'text',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.TEXT(),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('questions', 'text',
               existing_type=sa.TEXT(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
    # ### end Alembic commands ###
