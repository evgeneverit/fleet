from fastapi import APIRouter, Depends, Form, HTTPException, Request, File, UploadFile, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.database import get_db
from models.schemas import Operation, Ship, Port, Contractor, Pollutant, OperationPollutant
from datetime import datetime, date
import os
import shutil

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def list_operations(
    request: Request,
    ship_ids: list[int] = Query(None),
    start_date: str = None,
    end_date: str = None,
    port_ids: list[int] = Query(None),
    contractor_ids: list[int] = Query(None),
    sort_order: str = "desc",
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db)
):
    """
    Отображает список операций с гибкой фильтрацией.
    """
    query = db.query(Operation)
    
    # Фильтр по судам (множественный, опциональный)
    if ship_ids:
        query = query.filter(Operation.ship_id.in_(ship_ids))
    
    # Фильтр по датам (опциональный)
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
    
    # Фильтр по портам (множественный, опциональный)
    if port_ids:
        query = query.filter(Operation.port_id.in_(port_ids))
    
    # Фильтр по контрагентам (множественный, опциональный)
    if contractor_ids:
        query = query.filter(Operation.contractor_id.in_(contractor_ids))
    
    # Сортировка
    if sort_order.lower() == "asc":
        query = query.order_by(Operation.date.asc())
    else:
        query = query.order_by(Operation.date.desc())
    
    # Пагинация
    total = query.count()
    operations = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Расчет итоговой стоимости
    total_costs = {}
    for op in operations:
        total_cost = db.query(func.sum(OperationPollutant.cost)).filter(
            OperationPollutant.operation_id == op.id
        ).scalar() or 0.0
        total_costs[op.id] = total_cost
    
    # Данные для фильтров (selected как list[str] для Jinja2)
    selected_ship_ids = [str(id) for id in ship_ids or []]
    selected_port_ids = [str(id) for id in port_ids or []]
    selected_contractor_ids = [str(id) for id in contractor_ids or []]
    
    ships = db.query(Ship).order_by(Ship.name).all()
    ports = db.query(Port).order_by(Port.name).all()
    contractors = db.query(Contractor).order_by(Contractor.name).all()
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "operations": operations,
        "total_costs": total_costs,
        "ships": ships,
        "ports": ports,
        "contractors": contractors,
        "selected_ship_ids": selected_ship_ids,
        "selected_start_date": start_date,
        "selected_end_date": end_date,
        "selected_port_ids": selected_port_ids,
        "selected_contractor_ids": selected_contractor_ids,
        "sort_order": sort_order,
        "total_pages": (total // per_page) + (1 if total % per_page else 0),
        "current_page": page,
        "per_page": per_page
    })

# Остальные роуты (без изменений, для полноты)
@router.get("/operation/{operation_id}", response_class=JSONResponse)
async def get_operation(operation_id: int, db: Session = Depends(get_db)):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    pollutants = [
        {"name": op.pollutant.name, "volume": op.volume, "cost": op.cost}
        for op in operation.pollutants
    ]
    total_cost = db.query(func.sum(OperationPollutant.cost)).filter(
        OperationPollutant.operation_id == operation.id
    ).scalar() or 0.0
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

@router.get("/create", response_class=HTMLResponse)
async def create_form(request: Request, db: Session = Depends(get_db)):
    ships = db.query(Ship).all()
    ports = db.query(Port).all()
    contractors = db.query(Contractor).all()
    pollutants = db.query(Pollutant).all()
    return templates.TemplateResponse("create.html", {
        "request": request,
        "ships": ships,
        "ports": ports,
        "contractors": contractors,
        "pollutants": pollutants
    })

@router.post("/create")
async def create_operation(
    ship_id: int = Form(...),
    port_id: int = Form(...),
    contractor_id: int = Form(...),
    date: date = Form(...),
    document: UploadFile = File(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    if not db.query(Ship).filter(Ship.id == ship_id).first():
        raise HTTPException(status_code=400, detail="Судно не найдено")
    if not db.query(Port).filter(Port.id == port_id).first():
        raise HTTPException(status_code=400, detail="Порт не найден")
    if not db.query(Contractor).filter(Contractor.id == contractor_id).first():
        raise HTTPException(status_code=400, detail="Контрагент не найден")

    operation = Operation(
        ship_id=ship_id,
        port_id=port_id,
        contractor_id=contractor_id,
        date=date,
        has_documents=bool(document)
    )
    db.add(operation)
    db.flush()

    if document:
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/op_{operation.id}_{document.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(document.file, buffer)
        operation.document_path = file_path

    form_data = await request.form()
    pollutants = db.query(Pollutant).all()
    for pollutant in pollutants:
        volume_key = f"volume_{pollutant.id}"
        cost_key = f"cost_{pollutant.id}"
        if volume_key in form_data and cost_key in form_data:
            try:
                volume = float(form_data.get(volume_key, 0.0))
                cost = float(form_data.get(cost_key, 0.0))
                if volume < 0 or cost < 0:
                    raise ValueError("Объём и стоимость должны быть неотрицательными")
                if volume > 0 or cost > 0:
                    operation_pollutant = OperationPollutant(
                        operation_id=operation.id,
                        pollutant_id=pollutant.id,
                        volume=volume,
                        cost=cost
                    )
                    db.add(operation_pollutant)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ошибка для загрязнителя {pollutant.name}: {str(e)}"
                )
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@router.get("/edit/{operation_id}", response_class=HTMLResponse)
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
        "request": request,
        "operation": operation,
        "ships": ships,
        "ports": ports,
        "contractors": contractors,
        "pollutants": pollutants,
        "operation_pollutants": operation_pollutants
    })

@router.post("/edit/{operation_id}")
async def update_operation(
    operation_id: int,
    request: Request,
    ship_id: int = Form(...),
    port_id: int = Form(...),
    contractor_id: int = Form(...),
    date: date = Form(...),
    document: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    
    if not db.query(Ship).filter(Ship.id == ship_id).first():
        raise HTTPException(status_code=400, detail="Судно не найдено")
    if not db.query(Port).filter(Port.id == port_id).first():
        raise HTTPException(status_code=400, detail="Порт не найден")
    if not db.query(Contractor).filter(Contractor.id == contractor_id).first():
        raise HTTPException(status_code=400, detail="Контрагент не найден")

    operation.ship_id = ship_id
    operation.port_id = port_id
    operation.contractor_id = contractor_id
    operation.date = date
    
    if document:
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/op_{operation.id}_{document.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(document.file, buffer)
        operation.document_path = file_path
        operation.has_documents = True
    else:
        operation.has_documents = bool(operation.document_path)

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
                if volume < 0 or cost < 0:
                    raise ValueError("Объём и стоимость должны быть неотрицательными")
                if volume > 0 or cost > 0:
                    operation_pollutant = OperationPollutant(
                        operation_id=operation.id,
                        pollutant_id=pollutant.id,
                        volume=volume,
                        cost=cost
                    )
                    db.add(operation_pollutant)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ошибка для загрязнителя {pollutant.name}: {str(e)}"
                )
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@router.post("/delete/{operation_id}")
async def delete_operation(operation_id: int, db: Session = Depends(get_db)):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    db.delete(operation)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@router.get("/download/{operation_id}")
async def download_document(operation_id: int, db: Session = Depends(get_db)):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation or not operation.document_path:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return FileResponse(operation.document_path, filename=os.path.basename(operation.document_path))