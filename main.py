from fastapi import FastAPI, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from datetime import date
import os

# Настройка базы данных
SQLALCHEMY_DATABASE_URL = "sqlite:///./fleet.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модели
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

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Зависимость для работы с базой данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Приложение FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Инициализация тестовых данных
def init_data(db: Session):
    if db.query(Ship).count() == 0:
        ships = ["Теплоход1", "Теплоход2", "Теплоход3", "Теплоход4", "Теплоход5",
                 "Теплоход6", "Теплоход7", "Теплоход8", "Теплоход9", "Теплоход10",
                 "Теплоход11", "Теплоход12"]
        for name in ships:
            db.add(Ship(name=name))
    
    if db.query(Port).count() == 0:
        ports = ["Порт1", "Порт2", "Порт3"]  # Замените на реальные порты
        for name in ports:
            db.add(Port(name=name))
    
    if db.query(Contractor).count() == 0:
        contractors = ["Контрагент1", "Контрагент2", "Контрагент3"]  # Замените на реальных
        for name in contractors:
            db.add(Contractor(name=name))
    
    if db.query(Pollutant).count() == 0:
        pollutants = ["Питьевая вода", "Хозфекальные воды", "Шлам", "Бытовой мусор"]
        for name in pollutants:
            db.add(Pollutant(name=name))
    
    db.commit()

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    init_data(db)
    db.close()

# Маршруты
@app.get("/", response_class=HTMLResponse)
async def list_operations(request: Request, db: Session = Depends(get_db)):
    operations = db.query(Operation).all()
    return templates.TemplateResponse("list.html", {"request": request, "operations": operations})

@app.get("/create", response_class=HTMLResponse)
async def create_form(request: Request, db: Session = Depends(get_db)):
    ships = db.query(Ship).all()
    ports = db.query(Port).all()
    contractors = db.query(Contractor).all()
    pollutants = db.query(Pollutant).all()
    return templates.TemplateResponse("create.html", {"request": request, "ships": ships, "ports": ports, "contractors": contractors, "pollutants": pollutants})

@app.post("/create")
async def create_operation(
    request: Request,
    ship_id: int = Form(...),
    port_id: int = Form(...),
    contractor_id: int = Form(...),
    date: date = Form(...),
    db: Session = Depends(get_db)
):
    # Создаём операцию
    operation = Operation(
        ship_id=ship_id, port_id=port_id, contractor_id=contractor_id, date=date
    )
    db.add(operation)
    db.flush()  # Получаем operation.id без коммита

    # Получаем данные о загрязнителях из формы
    form_data = await request.form()
    pollutants = db.query(Pollutant).all()
    for pollutant in pollutants:
        volume_key = f"volume_{pollutant.id}"
        cost_key = f"cost_{pollutant.id}"
        volume = float(form_data.get(volume_key, 0.0))
        cost = float(form_data.get(cost_key, 0.0))
        if volume > 0 or cost > 0:
            operation_pollutant = OperationPollutant(
                operation_id=operation.id, pollutant_id=pollutant.id, volume=volume, cost=cost
            )
            db.add(operation_pollutant)
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/edit/{operation_id}", response_class=HTMLResponse)
async def edit_form(operation_id: int, request: Request, db: Session = Depends(get_db)):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    ships = db.query(Ship).all()
    ports = db.query(Port).all()
    contractors = db.query(Contractor).all()
    pollutants = db.query(Pollutant).all()
    operation_pollutants = {op.pollutant_id: op for op in operation.pollutants}
    return templates.TemplateResponse("edit.html", {
        "request": request, "operation": operation, "ships": ships, "ports": ports,
        "contractors": contractors, "pollutants": pollutants, "operation_pollutants": operation_pollutants
    })

@app.post("/edit/{operation_id}")
async def update_operation(
    operation_id: int,
    request: Request,
    ship_id: int = Form(...),
    port_id: int = Form(...),
    contractor_id: int = Form(...),
    date: date = Form(...),
    has_documents: bool = Form(False),
    db: Session = Depends(get_db)
):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    
    # Обновляем основную информацию
    operation.ship_id = ship_id
    operation.port_id = port_id
    operation.contractor_id = contractor_id
    operation.date = date
    operation.has_documents = has_documents

    # Удаляем старые записи о загрязнителях
    db.query(OperationPollutant).filter(OperationPollutant.operation_id == operation_id).delete()

    # Получаем данные о загрязнителях из формы
    form_data = await request.form()
    pollutants = db.query(Pollutant).all()
    for pollutant in pollutants:
        volume_key = f"volume_{pollutant.id}"
        cost_key = f"cost_{pollutant.id}"
        volume = float(form_data.get(volume_key, 0.0))
        cost = float(form_data.get(cost_key, 0.0))
        if volume > 0 or cost > 0:
            operation_pollutant = OperationPollutant(
                operation_id=operation.id, pollutant_id=pollutant.id, volume=volume, cost=cost
            )
            db.add(operation_pollutant)
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete/{operation_id}")
async def delete_operation(operation_id: int, db: Session = Depends(get_db)):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    db.delete(operation)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, db: Session = Depends(get_db)):
    operations = db.query(Operation).all()
    return templates.TemplateResponse("analytics.html", {"request": request, "operations": operations})