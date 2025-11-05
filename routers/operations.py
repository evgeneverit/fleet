from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.database import get_db
from models.schemas import Operation, Ship, Port, Contractor, Item, OperationItem
from datetime import datetime, date


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
    
    if ship_ids:
        query = query.filter(Operation.ship_id.in_(ship_ids))
    
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
    
    if port_ids:
        query = query.filter(Operation.port_id.in_(port_ids))
    
    if contractor_ids:
        query = query.filter(Operation.contractor_id.in_(contractor_ids))
    
    if sort_order.lower() == "asc":
        query = query.order_by(Operation.date.asc())
    else:
        query = query.order_by(Operation.date.desc())
    
    total = query.count()
    operations = query.offset((page - 1) * per_page).limit(per_page).all()
    
    total_costs = {}
    for op in operations:
        total_cost = db.query(func.sum(OperationItem.cost)).filter(
            OperationItem.operation_id == op.id
        ).scalar() or 0.0
        total_costs[op.id] = total_cost
    
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

@router.get("/operation/{operation_id}", response_class=JSONResponse)
async def get_operation(operation_id: int, db: Session = Depends(get_db)):
    operation = db.query(Operation).filter(Operation.id == operation_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    items = [
        {"name": op.item.name, "volume": op.volume, "cost": op.cost}
        for op in operation.items
    ]
    total_cost = db.query(func.sum(OperationItem.cost)).filter(
        OperationItem.operation_id == operation.id
    ).scalar() or 0.0
    return {
        "id": operation.id,
        "ship": operation.ship.name,
        "port": operation.port.name,
        "contractor": operation.contractor.name,
        "date": str(operation.date),
        "has_documents": operation.has_documents,
        "items": items,
        "total_cost": total_cost
    }

@router.get("/create", response_class=HTMLResponse)
async def create_form(request: Request, db: Session = Depends(get_db)):
    ships = db.query(Ship).all()
    ports = db.query(Port).all()
    contractors = db.query(Contractor).all()
    items = db.query(Item).all()
    items_dict = [{"id": item.id, "name": item.name} for item in items]
    return templates.TemplateResponse("create.html", {
        "request": request,
        "ships": ships,
        "ports": ports,
        "contractors": contractors,
        "items": items_dict
    })

@router.post("/create")
async def create_operation(
    ship_id: int = Form(...),
    port_id: int = Form(...),
    contractor_id: int = Form(...),
    date: date = Form(...),
    has_documents: bool = Form(False),
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
        has_documents=has_documents
    )
    db.add(operation)
    db.flush()

    form_data = await request.form()
    items = db.query(Item).all()
    for item in items:
        volume_key = f"volume_{item.id}"
        cost_key = f"cost_{item.id}"
        if volume_key in form_data and cost_key in form_data:
            try:
                volume = float(form_data.get(volume_key, 0.0))
                cost = float(form_data.get(cost_key, 0.0))
                if volume < 0 or cost < 0:
                    raise ValueError("Объём и стоимость должны быть неотрицательными")
                if volume > 0 or cost > 0:
                    operation_item = OperationItem(
                        operation_id=operation.id,
                        item_id=item.id,
                        volume=volume,
                        cost=cost
                    )
                    db.add(operation_item)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ошибка для элемента {item.name}: {str(e)}"
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
    items = db.query(Item).all()
    items_dict = [{"id": item.id, "name": item.name} for item in items]
    today = date.today().isoformat()  # Формат YYYY-MM-DD
    item_assocs = [
        {"item_id": op.item_id, "name": op.item.name, "volume": op.volume, "cost": op.cost}
        for op in operation.items
    ]
    return templates.TemplateResponse("edit.html", {
        "request": request,
        "operation": operation,
        "ships": ships,
        "ports": ports,
        "contractors": contractors,
        "items": items_dict,
        "today": today,
        "item_assocs": item_assocs
    })

@router.post("/edit/{operation_id}")
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
    operation.has_documents = has_documents

    db.query(OperationItem).filter(OperationItem.operation_id == operation_id).delete()

    form_data = await request.form()
    items = db.query(Item).all()
    for item in items:
        volume_key = f"volume_{item.id}"
        cost_key = f"cost_{item.id}"
        if volume_key in form_data and cost_key in form_data:
            try:
                volume = float(form_data.get(volume_key, 0.0))
                cost = float(form_data.get(cost_key, 0.0))
                if volume < 0 or cost < 0:
                    raise ValueError("Объём и стоимость должны быть неотрицательными")
                if volume > 0 or cost > 0:
                    operation_item = OperationItem(
                        operation_id=operation.id,
                        item_id=item.id,
                        volume=volume,
                        cost=cost
                    )
                    db.add(operation_item)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ошибка для элемента {item.name}: {str(e)}"
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

