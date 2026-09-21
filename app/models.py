from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship
Base = declarative_base()

class Student(Base):
    __tablename__ = "students"
    id=Column(Integer,primary_key=True)
    name=Column(String,nullable=False)
    email=Column(String,unique=True,nullable=False)
    wallet_balance=Column(Float,nullable=False,default=0)
    orders=relationship("Order",back_populates="student")

class MenuItem(Base):
    __tablename__="menu_items"
    id=Column(Integer,primary_key=True)
    name=Column(String,unique=True,nullable=False)
    category=Column(String,nullable=False)
    price=Column(Float,nullable=False)
    portions_available=Column(Integer,nullable=False)
    active=Column(Boolean,default=True,nullable=False)
    order_items=relationship("OrderItem",back_populates="menu_item")

class Order(Base):
    __tablename__="orders"
    id=Column(Integer,primary_key=True)
    student_id=Column(Integer,ForeignKey("students.id"),nullable=False)
    total=Column(Float,nullable=False)
    status=Column(String,default="confirmed",nullable=False)
    idempotency_key=Column(String,unique=True,nullable=False)
    student=relationship("Student",back_populates="orders")
    items=relationship("OrderItem",back_populates="order",cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__="order_items"
    id=Column(Integer,primary_key=True)
    order_id=Column(Integer,ForeignKey("orders.id"),nullable=False)
    menu_item_id=Column(Integer,ForeignKey("menu_items.id"),nullable=False)
    quantity=Column(Integer,nullable=False)
    unit_price=Column(Float,nullable=False)
    order=relationship("Order",back_populates="items")
    menu_item=relationship("MenuItem",back_populates="order_items")
