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

class Pollutant(Base):
    __tablename__ = "pollutants"
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
    document_path = Column(String, nullable=True)  # Добавляем для файлов

    ship = relationship("Ship")
    port = relationship("Port")
    contractor = relationship("Contractor")
    pollutants = relationship("OperationPollutant", back_populates="operation", cascade="all, delete-orphan")

class OperationPollutant(Base):
    __tablename__ = "operation_pollutants"
    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(Integer, ForeignKey("operations.id"))
    pollutant_id = Column(Integer, ForeignKey("pollutants.id"))
    volume = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)

    operation = relationship("Operation", back_populates="pollutants")
    pollutant = relationship("Pollutant")