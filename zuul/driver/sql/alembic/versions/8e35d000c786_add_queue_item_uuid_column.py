# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Add QueueItem UUID column

Revision ID: 8e35d000c786
Revises: 6c1582c1d08c
Create Date: 2025-11-24 10:17:28.428121

"""

# revision identifiers, used by Alembic.
revision = '8e35d000c786'
down_revision = '6c1582c1d08c'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade(table_prefix=''):
    op.add_column(
        table_prefix + 'zuul_buildset',
        sa.Column('queue_item_uuid', sa.String(255), nullable=True)
    )


def downgrade():
    raise Exception("Downgrades not supported")
