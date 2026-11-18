from decimal import Decimal
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select,func
from .production_models import PelletPack,BlendShipment,ShipmentPack
from .returns_models import PackReturn,ReturnPack,ShipmentReturnPack
from .production_service import ship_view
from .blending import obj,get,audit

def now():return datetime.now(timezone.utc).isoformat()
def returned_kg(s,pack_id=None,return_pack_id=None):
    q=select(func.coalesce(func.sum(PackReturn.kg),0))
    q=q.where(PackReturn.pack_id==pack_id) if pack_id else q.where(PackReturn.return_pack_id==return_pack_id)
    return s.scalar(q)
def return_pack_view(s,rp):
    link=s.scalar(select(ShipmentReturnPack).where(ShipmentReturnPack.return_pack_id==rp.id))
    return {**obj(rp),'source_return_code':s.get(PackReturn,rp.return_id).code,'shipment_code':s.get(BlendShipment,link.shipment_id).code if link else None,'returned_kg':float(returned_kg(s,return_pack_id=rp.id))}
def return_view(s,x):
    child=s.scalar(select(ReturnPack).where(ReturnPack.return_id==x.id))
    return {**obj(x),'source_kind':'pack' if x.pack_id else 'return_pack','source_code':x.source_snapshot['source_code'],'shipment_code':x.source_snapshot['shipment']['code'],'return_pack':return_pack_view(s,child) if child else None}
def create_return(s,p,u):
    hit=s.scalar(select(PackReturn).where(PackReturn.request_key==p.request_key))
    if hit:return return_view(s,hit)
    if p.pack_id:
        pack=get(s,PelletPack,p.pack_id,True)
        link=s.scalar(select(ShipmentPack).where(ShipmentPack.pack_id==pack.id))
        if not link:raise HTTPException(409,'箱码尚未装车，没有可退的客户签收记录')
        sh=get(s,BlendShipment,link.shipment_id)
        if sh.state!='received':raise HTTPException(409,'仅客户已签收的箱码可登记退货')
        before=returned_kg(s,pack_id=pack.id)
        if before+p.kg>pack.kg:raise HTTPException(409,f'累计退货{before+p.kg}kg将超过原箱重{pack.kg}kg，本次未登记')
        cert=pack.certificate_snapshot
        snapshot={'kind':'pack','source_code':pack.code,'pack':{'id':pack.id,'code':pack.code,'kg':float(pack.kg)},'certificate':cert,'shipment':{'code':sh.code,'customer':sh.customer,'receipt':sh.receipt_snapshot},'max_pvc':float(cert['input']['max_pvc']),'chain':[{'kind':'pack','code':pack.code,'certificate':cert['code'],'blend':cert['input']['code']}],'returned_before_kg':float(before),'at':now(),'registered_by':u['email']}
    else:
        rp=get(s,ReturnPack,p.return_pack_id,True)
        if rp.state!='sold':raise HTTPException(409,'退货箱须再次售出并由客户签收后才能登记退货')
        link=s.scalar(select(ShipmentReturnPack).where(ShipmentReturnPack.return_pack_id==rp.id))
        sh=get(s,BlendShipment,link.shipment_id)
        before=returned_kg(s,return_pack_id=rp.id)
        if before+p.kg>rp.kg:raise HTTPException(409,f'累计退货{before+p.kg}kg将超过退货箱重{rp.kg}kg，本次未登记')
        parent=rp.lineage_snapshot
        snapshot={'kind':'return_pack','source_code':rp.code,'return_pack':{'id':rp.id,'code':rp.code,'kg':float(rp.kg)},'certificate':parent.get('certificate'),'shipment':{'code':sh.code,'customer':sh.customer,'receipt':sh.receipt_snapshot},'max_pvc':parent['max_pvc'],'chain':parent['chain'],'returned_before_kg':float(before),'at':now(),'registered_by':u['email']}
    x=PackReturn(code=p.code,request_key=p.request_key,pack_id=p.pack_id,return_pack_id=p.return_pack_id,kg=p.kg,reason=p.reason,state='quarantine',source_snapshot=snapshot,inspections=[],created_by=u['email'],created_at=now())
    s.add(x);s.flush();audit(s,u,'return_registered',x.code+' / '+str(p.kg)+'kg ← '+snapshot['source_code']);return return_view(s,x)
def retest_return(s,id,p,u):
    x=get(s,PackReturn,id,True)
    if x.state!='quarantine':raise HTTPException(409,'退货已完成复检处置，结果冻结不可改写')
    if p.decision=='restocked' and p.pvc_ppm>Decimal(str(x.source_snapshot['max_pvc'])):raise HTTPException(409,f"实测PVC超过原配方上限{x.source_snapshot['max_pvc']}ppm，不能转为可售退货箱")
    record={'melt_index':float(p.melt_index),'pvc_ppm':float(p.pvc_ppm),'decision':p.decision,'note':p.note,'actor':u['email'],'at':now()}
    x.inspections=[*(x.inspections or []),record]
    if p.decision=='restocked':
        code=f'RTP-{x.id:06d}'
        lineage={'chain':[*x.source_snapshot['chain'],{'kind':'return','code':x.code,'kg':float(x.kg)},{'kind':'return_pack','code':code,'kg':float(x.kg)}],'max_pvc':x.source_snapshot['max_pvc'],'certificate':x.source_snapshot.get('certificate'),'retest':record}
        s.add(ReturnPack(code=code,return_id=x.id,kg=x.kg,state='saleable',lineage_snapshot=lineage,created_at=now()));x.state='restocked'
    else:x.state='rejected'
    s.flush();audit(s,u,'return_retested',x.code+' / '+p.decision);return return_view(s,x)
def load_return_pack(s,shipment_id,p,u):
    sh=get(s,BlendShipment,shipment_id,True)
    if sh.state!='loading':raise HTTPException(409,'发车后清单冻结，不能继续装车')
    rp=get(s,ReturnPack,p.return_pack_id,True)
    if rp.state!='saleable':raise HTTPException(409,'仅复检合格的可售退货箱可装车，在途或已售出不可重复出库')
    if s.scalar(select(ShipmentReturnPack.id).where(ShipmentReturnPack.return_pack_id==rp.id)):raise HTTPException(409,'退货箱已装车，不得重复出库')
    s.add(ShipmentReturnPack(shipment_id=sh.id,return_pack_id=rp.id,pack_snapshot=return_pack_view(s,rp)));rp.state='loaded';s.flush()
    audit(s,u,'return_pack_loaded',sh.code+' / '+rp.code);return ship_view(s,sh)
def summary(s):
    transit_orig=transit_ret=Decimal(0)
    for sid in s.scalars(select(BlendShipment.id).where(BlendShipment.state=='dispatched')):
        for link in s.scalars(select(ShipmentPack).where(ShipmentPack.shipment_id==sid)):transit_orig+=Decimal(str(link.pack_snapshot['kg']))
        for link in s.scalars(select(ShipmentReturnPack).where(ShipmentReturnPack.shipment_id==sid)):transit_ret+=Decimal(str(link.pack_snapshot['kg']))
    quarantine=s.scalar(select(func.coalesce(func.sum(PackReturn.kg),0)).where(PackReturn.state=='quarantine'))
    rejected=s.scalar(select(func.coalesce(func.sum(PackReturn.kg),0)).where(PackReturn.state=='rejected'))
    saleable_orig=s.scalar(select(func.coalesce(func.sum(PelletPack.kg),0)).where(PelletPack.state=='sealed'))
    saleable_ret=s.scalar(select(func.coalesce(func.sum(ReturnPack.kg),0)).where(ReturnPack.state=='saleable'))
    return {'in_transit_kg':float(transit_orig+transit_ret),'in_transit_original_kg':float(transit_orig),'in_transit_return_kg':float(transit_ret),'quarantine_kg':float(quarantine),'rejected_kg':float(rejected),'saleable_kg':float(saleable_orig+saleable_ret),'saleable_original_kg':float(saleable_orig),'saleable_return_kg':float(saleable_ret)}
