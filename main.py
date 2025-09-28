from fastapi import FastAPI, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, Boolean, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from datetime import date, datetime
import os
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import base64

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
        ports = ["Порт1", "Порт2", "Порт3"]
        for name in ports:
            db.add(Port(name=name))
    
    if db.query(Contractor).count() == 0:
        contractors = ["Контрагент1", "Контрагент2", "Контрагент3"]
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
async def list_operations(
    request: Request,
    ship_ids: str = None,
    start_date: str = None,
    end_date: str = None,
    port_id: int = None,
    sort_order: str = "desc",  # По умолчанию DESC
    db: Session = Depends(get_db)
):
    query = db.query(Operation)
    
    # Фильтр по судам
    if ship_ids:
        try:
            ship_ids_list = [int(id) for id in ship_ids.split(",") if id]
            query = query.filter(Operation.ship_id.in_(ship_ids_list))
        except ValueError:
            pass
    
    # Фильтр по датам
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Operation.date >= start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Operation.date <= end_date_obj)
        except ValueError:
            pass
    
    # Фильтр по порту
    if port_id:
        query = query.filter(Operation.port_id == port_id)
    
    # Сортировка по дате
    if sort_order.lower() == "asc":
        query = query.order_by(Operation.date.asc())
    else:
        query = query.order_by(Operation.date.desc())
    
    operations = query.all()
    
    # Итоговая стоимость
    total_costs = {}
    for op in operations:
        total_cost = db.query(func.sum(OperationPollutant.cost)).filter(OperationPollutant.operation_id == op.id).scalar() or 0.0
        total_costs[op.id] = total_cost
    
    # Данные для фильтров
    ships = db.query(Ship).order_by(Ship.name).all()
    ports = db.query(Port).order_by(Port.name).all()
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "operations": operations,
        "total_costs": total_costs,
        "ships": ships,
        "ports": ports,
        "selected_ship_ids": ship_ids.split(",") if ship_ids else [],
        "selected_start_date": start_date,
        "selected_end_date": end_date,
        "selected_port_id": port_id,
        "sort_order": sort_order
    })

@app.get("/operation/{operation_id}", response_class=JSONResponse)
async def get_operation(operation_id: int, db: Session = Depends(get_db)):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    pollutants = [
        {"name": op.pollutant.name, "volume": op.volume, "cost": op.cost}
        for op in operation.pollutants
    ]
    total_cost = db.query(func.sum(OperationPollutant.cost)).filter(OperationPollutant.operation_id == operation.id).scalar() or 0.0
    return {
        "id": operation.id,
        "ship": operation.ship.name,
        "port": operation.port.name,
        "contractor": operation.contractor.name,
        "date": str(operation.date),
        "has_documents": operation.has_documents,
        "pollutants": pollutants,
        "total_cost": total_cost
    }

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
    operation = Operation(
        ship_id=ship_id, port_id=port_id, contractor_id=contractor_id, date=date
    )
    db.add(operation)
    db.flush()

    form_data = await request.form()
    pollutants = db.query(Pollutant).all()
    for pollutant in pollutants:
        volume_key = f"volume_{pollutant.id}"
        cost_key = f"cost_{pollutant.id}"
        if volume_key in form_data and cost_key in form_data:
            try:
                volume = float(form_data.get(volume_key, 0.0))
                cost = float(form_data.get(cost_key, 0.0))
                if volume > 0 or cost > 0:
                    operation_pollutant = OperationPollutant(
                        operation_id=operation.id, pollutant_id=pollutant.id, volume=volume, cost=cost
                    )
                    db.add(operation_pollutant)
            except ValueError as e:
                print(f"Ошибка преобразования для pollutant {pollutant.id}: {e}")
                continue
    
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
    operation_pollutants = {op.pollutant_id: op for op in operation.pollutants} if operation.pollutants else {}
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
    
    operation.ship_id = ship_id
    operation.port_id = port_id
    operation.contractor_id = contractor_id
    operation.date = date
    operation.has_documents = has_documents

    db.query(OperationPollutant).filter(OperationPollutant.operation_id == operation_id).delete()

    form_data = await request.form()
    pollutants = db.query(Pollutant).all()
    for pollutant in pollutants:
        volume_key = f"volume_{pollutant.id}"
        cost_key = f"cost_{pollutant.id}"
        if volume_key in form_data and cost_key in form_data:
            try:
                volume = float(form_data.get(volume_key, 0.0))
                cost = float(form_data.get(cost_key, 0.0))
                if volume > 0 or cost > 0:
                    operation_pollutant = OperationPollutant(
                        operation_id=operation.id, pollutant_id=pollutant.id, volume=volume, cost=cost
                    )
                    db.add(operation_pollutant)
            except ValueError as e:
                print(f"Ошибка преобразования для pollutant {pollutant.id}: {e}")
                continue
    
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
    current_date = date(2025, 9, 28)
    summary_query = (
        db.query(
            Ship.name.label("ship_name"),
            func.count(Operation.id).label("operation_count"),
            func.sum(OperationPollutant.volume).label("total_volume"),
            func.sum(OperationPollutant.cost).label("total_cost"),
            func.group_concat(Pollutant.name.distinct()).label("pollutant_types"),
            func.min(Operation.date).label("first_operation"),
            func.max(Operation.date).label("last_operation")
        )
        .outerjoin(Operation, Ship.id == Operation.ship_id)
        .outerjoin(OperationPollutant, Operation.id == OperationPollutant.operation_id)
        .outerjoin(Pollutant, OperationPollutant.pollutant_id == Pollutant.id)
        .filter(Operation.date <= current_date)
        .group_by(Ship.id)
        .order_by(Ship.name)
    )
    summary_results = summary_query.all()

    pollutants_query = (
        db.query(
            Ship.name.label("ship_name"),
            Pollutant.name.label("pollutant_name"),
            func.sum(OperationPollutant.volume).label("total_volume"),
            func.sum(OperationPollutant.cost).label("total_cost")
        )
        .outerjoin(Operation, Ship.id == Operation.ship_id)
        .outerjoin(OperationPollutant, Operation.id == OperationPollutant.operation_id)
        .outerjoin(Pollutant, OperationPollutant.pollutant_id == Pollutant.id)
        .filter(Operation.date <= current_date)
        .filter((OperationPollutant.volume > 0) | (OperationPollutant.cost > 0))
        .group_by(Ship.name, Pollutant.name)
        .order_by(Ship.name, Pollutant.name)
    )
    pollutants_results = pollutants_query.all()

    ship_names = [row.ship_name for row in summary_results]
    total_volumes = [row.total_volume or 0 for row in summary_results]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(ship_names, total_volumes)
    ax.set_xlabel('Судно')
    ax.set_ylabel('Общий объём (куб.м)')
    ax.set_title('Общий объём загрязнителей/воды по судам')
    ax.tick_params(axis='x', rotation=45)
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    volume_chart_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)

    pie_charts = {}
    ships = db.query(Ship).order_by(Ship.name).all()
    for ship in ships:
        ship_pollutants = [
            row for row in pollutants_results if row.ship_name == ship.name
        ]
        if ship_pollutants:
            poll_names = [row.pollutant_name for row in ship_pollutants]
            poll_costs = [row.total_cost or 0 for row in ship_pollutants]
            fig_pie, ax_pie = plt.subplots(figsize=(8, 6))
            ax_pie.pie(poll_costs, labels=poll_names, autopct='%1.1f%%', startangle=90)
            ax_pie.set_title(f'Распределение стоимости по загрязнителям для {ship.name}')
            buffer_pie = BytesIO()
            plt.savefig(buffer_pie, format='png', bbox_inches='tight')
            buffer_pie.seek(0)
            pie_charts[ship.name] = base64.b64encode(buffer_pie.read()).decode('utf-8')
            plt.close(fig_pie)

    operations = db.query(Operation).filter(Operation.date <= current_date).all()
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "operations": operations,
        "summary_results": summary_results,
        "pollutants_results": pollutants_results,
        "volume_chart_base64": volume_chart_base64,
        "pie_charts": pie_charts
    })