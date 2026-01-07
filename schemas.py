from pydantic import BaseModel
from typing import Optional
from typing import List
import datetime


class CategorySchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    pic_url: Optional[str] = None
    price: float
    category_id: Optional[int] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    pic_url: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[int] = None


class ProductSchema(ProductBase):
    id: int
    category: Optional[CategorySchema] = None

    class Config:
        orm_mode = True


class Contact(BaseModel):
    name: str
    phone: str


class AdminRequest(BaseModel):
    items: List[ProductSchema]
    contact: Contact

    class Config:
        orm_mode = True


class RequestSchema(BaseModel):
    id: int
    customer_name: str
    customer_phone: str
    product_list: List[ProductSchema]

    class Config:
        orm_mode = True