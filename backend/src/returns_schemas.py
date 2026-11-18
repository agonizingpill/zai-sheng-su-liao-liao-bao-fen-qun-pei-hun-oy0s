from decimal import Decimal
from pydantic import BaseModel,Field,ConfigDict,model_validator
class Clean(BaseModel):model_config=ConfigDict(str_strip_whitespace=True)
class ReturnInput(Clean):
    code:str=Field(min_length=2,max_length=60)
    request_key:str=Field(min_length=8,max_length=80)
    pack_id:int|None=Field(default=None,gt=0)
    return_pack_id:int|None=Field(default=None,gt=0)
    kg:Decimal=Field(gt=0,le=100000,max_digits=12,decimal_places=3)
    reason:str=Field(min_length=8,max_length=600)
    @model_validator(mode='after')
    def one_source(self):
        if (self.pack_id is None)==(self.return_pack_id is None):raise ValueError('退货须且只须指定一个来源箱码')
        return self
class ReturnRetest(Clean):
    melt_index:Decimal=Field(gt=0,le=200,max_digits=9,decimal_places=3)
    pvc_ppm:Decimal=Field(ge=0,le=10000,max_digits=9,decimal_places=3)
    decision:str=Field(pattern='^(restocked|rejected)$')
    note:str=Field(min_length=8,max_length=600)
class LoadReturnPack(Clean):return_pack_id:int=Field(gt=0)
