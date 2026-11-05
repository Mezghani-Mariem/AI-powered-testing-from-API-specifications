from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)


class ItemUpdate(BaseModel):
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)


class ItemOut(ItemCreate):
    id: int