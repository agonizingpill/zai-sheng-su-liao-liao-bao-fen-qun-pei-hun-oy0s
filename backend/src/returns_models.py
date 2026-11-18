"""Customer returns, restocked return packs and their shipment links have independent lifecycles."""
from decimal import Decimal
from sqlalchemy import String,Numeric,ForeignKey,JSON,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class PackReturn(Base):
    __tablename__='pack_returns'
    __table_args__=(CheckConstraint('kg > 0'),CheckConstraint('(pack_id IS NULL) <> (return_pack_id IS NULL)'))
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(60),unique=True)
    request_key:Mapped[str]=mapped_column(String(80),unique=True)
    pack_id:Mapped[int|None]=mapped_column(ForeignKey('pellet_packs.id'),nullable=True)
    return_pack_id:Mapped[int|None]=mapped_column(ForeignKey('return_packs.id'),nullable=True)
    kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    reason:Mapped[str]=mapped_column(String(600))
    state:Mapped[str]=mapped_column(String(20),default='quarantine')
    source_snapshot:Mapped[dict]=mapped_column(JSON)
    inspections:Mapped[list]=mapped_column(JSON)
    created_by:Mapped[str]=mapped_column(String(120))
    created_at:Mapped[str]=mapped_column(String(40))
class ReturnPack(Base):
    __tablename__='return_packs'
    __table_args__=(CheckConstraint('kg > 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(80),unique=True)
    return_id:Mapped[int]=mapped_column(ForeignKey('pack_returns.id'),unique=True)
    kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    state:Mapped[str]=mapped_column(String(20),default='saleable')
    lineage_snapshot:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]=mapped_column(String(40))
class ShipmentReturnPack(Base):
    __tablename__='shipment_return_packs'
    id:Mapped[int]=mapped_column(primary_key=True)
    shipment_id:Mapped[int]=mapped_column(ForeignKey('blend_shipments.id'))
    return_pack_id:Mapped[int]=mapped_column(ForeignKey('return_packs.id'),unique=True)
    pack_snapshot:Mapped[dict]=mapped_column(JSON)
