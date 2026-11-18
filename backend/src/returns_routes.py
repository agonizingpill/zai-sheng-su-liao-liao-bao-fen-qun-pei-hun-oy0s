from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .database import Session
from .security import current,allow
from .returns_models import PackReturn,ReturnPack
from .returns_schemas import ReturnInput,ReturnRetest,LoadReturnPack
from . import returns_service as svc
router=APIRouter()
@router.get('/pack-returns')
def returns(u=Depends(current)):
    with Session()as s:return [svc.return_view(s,x)for x in s.scalars(select(PackReturn).order_by(PackReturn.id.desc()))]
@router.post('/pack-returns')
def register(p:ReturnInput,u=Depends(current)):
    allow(u,'admin','blender')
    try:
        with Session.begin()as s:return svc.create_return(s,p,u)
    except IntegrityError:
        with Session()as s:
            hit=s.scalar(select(PackReturn).where(PackReturn.request_key==p.request_key))
            if hit:return svc.return_view(s,hit)
        raise HTTPException(409,'退货单号已存在或关联数据不合法')
@router.post('/pack-returns/{id}/retest')
def retest(id:int,p:ReturnRetest,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.retest_return(s,id,p,u)
@router.get('/return-packs')
def return_packs(u=Depends(current)):
    with Session()as s:return [svc.return_pack_view(s,x)for x in s.scalars(select(ReturnPack).order_by(ReturnPack.id.desc()))]
@router.post('/blend-shipments/{id}/return-packs')
def load(id:int,p:LoadReturnPack,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.load_return_pack(s,id,p,u)
@router.get('/returns-summary')
def returns_summary(u=Depends(current)):
    with Session()as s:return svc.summary(s)
