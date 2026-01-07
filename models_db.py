from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from db import Base


class Category(Base):
    __tablename__ = "category"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)


class Product(Base):
    __tablename__ = "product"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    pic_url = Column(Text, nullable=True)
    price = Column(Float, nullable=False, default=0.0)
    category_id = Column(Integer, ForeignKey("category.id"), nullable=True)

    category = relationship("Category", backref="products")

class Request(Base):
    __tablename__ = "request"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    product_list = Column(Text, nullable=False)

