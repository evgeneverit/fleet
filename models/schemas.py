from sqlalchemy import Column, Integer, String, Date, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Ship(Base):
    __tablename__ = "ships"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class Port(Base):
    __tablename__ = "ports"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class Operation(Base):
    __tablename__ = "operations"
    id = Column(Integer, primary_key=True, index=True)
    ship_id = Column(Integer, ForeignKey("ships.id"))
    port_id = Column(Integer, ForeignKey("ports.id"))
    contractor_id = Column(Integer, ForeignKey("contractors.id"))
    date = Column(Date)
    has_documents = Column(Boolean, default=False)
    document_path = Column(String, nullable=True)

    ship = relationship("Ship")
    port = relationship("Port")
    contractor = relationship("Contractor")
    items = relationship("OperationItem", back_populates="operation", cascade="all, delete-orphan")

class OperationItem(Base):
    __tablename__ = "operation_items"
    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(Integer, ForeignKey("operations.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    volume = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)

    operation = relationship("Operation", back_populates="items")
    item = relationship("Item")