from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from models.database import Base, engine, SessionLocal
from utils.init_data import init_data
from routers import operations, analytics

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Инициализация данных
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    init_data(db)
    db.close()

# Подключение роутеров
app.include_router(operations.router)
app.include_router(analytics.router)