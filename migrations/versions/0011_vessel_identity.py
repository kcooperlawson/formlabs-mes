"""a vessel on the screen should be the vessel on the floor

The reactor page drew every tank as one of three shapes picked from its
capacity, on the assumption that a bigger number means a bigger tank of the
same kind. On this floor it does not. M-205 is a 5,000 L straight-sided
vertical with litre graduations up the side and a flat bottom; the Black V5
vessel beside it is comparably large, flat-bottomed, with an agitator on top;
M-101 is a squat cone-bottom mixer sitting in a steel frame; and the smallest
is not a fabricated tank at all but a caged IBC tote on a pallet. Capacity
cannot tell those apart, and no arithmetic on it ever will - the shape is a
fact about the vessel, so it has to be stored as one.

The two identifier columns are the same argument. Every vessel out there
carries an asset tag stencilled on it (M-101, M-205) and an orange bay marker
on the bollard beside it (E2, E3, F3, H1), and those are what people say to
each other on the floor. The application called them Reactor 1, 2 and 3,
which is a name only the application uses. Carrying the real ones means the
tank on the screen can be matched to the tank in front of you without anybody
translating.

All three are optional and all three default to empty or to the capacity
band, so an existing fleet keeps drawing exactly as it did until somebody
sets them.

Revision ID: 0011_vessel_identity
Revises: 0010_drop_handover_emails
Create Date: 2026-09-05
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_vessel_identity"
down_revision = "0010_drop_handover_emails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reactors", sa.Column("vessel_type", sa.String(20), nullable=True))
    op.add_column("reactors", sa.Column("asset_tag", sa.String(30), nullable=True))
    op.add_column("reactors", sa.Column("bay_marker", sa.String(10), nullable=True))

    # Seed the shape from capacity so nothing has to be set by hand before the
    # fleet looks right. These are the bands the page used to hard-code, now
    # written down once as a starting point a manager corrects rather than as
    # a rule the drawing keeps re-deriving.
    op.execute("""
        UPDATE reactors SET vessel_type = CASE
            WHEN max_capacity_l >= 3500 THEN 'bulk_vertical'
            WHEN max_capacity_l >= 1500 THEN 'cone_mixer'
            ELSE 'ibc_tote'
        END
        WHERE vessel_type IS NULL
    """)


def downgrade() -> None:
    op.drop_column("reactors", "bay_marker")
    op.drop_column("reactors", "asset_tag")
    op.drop_column("reactors", "vessel_type")
