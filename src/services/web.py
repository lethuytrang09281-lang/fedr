import asyncio
from fastapi import FastAPI
from sqladmin import Admin, ModelView
from src.database.session import engine
from src.database.models import Lot, Auction, Manager
from src.services.orchestrator import Orchestrator
from src.core.logger import logger

app = FastAPI(title="Fedresurs Pro Admin")

# --- Настройка Админки ---
class LotAdmin(ModelView, model=Lot):
    name = "Лот"
    name_plural = "Лоты"
    icon = "fa-solid fa-gavel"
    column_list = [Lot.id, Lot.lot_number, Lot.price_start, Lot.status, Lot.yara_score]
    column_searchable_list = [Lot.description]
    column_default_sort = ("created_at", True)

class AuctionAdmin(ModelView, model=Auction):
    name = "Торги"
    name_plural = "Торги"
    icon = "fa-solid fa-file-contract"
    column_list = [Auction.guid, Auction.number, Auction.last_updated]

class ManagerAdmin(ModelView, model=Manager):
    name = "АУ"
    name_plural = "Управляющие"
    icon = "fa-solid fa-user-tie"
    column_list = [Manager.inn, Manager.full_name, Manager.trust_score]

# --- Фоновый процесс ---
async def background_parser():
    orchestrator = Orchestrator()
    while True:
        try:
            await orchestrator.run_parsing_cycle()
        except Exception as e:
            logger.error(f"Background task error: {e}")
        await asyncio.sleep(60) # Запуск раз в минуту

@app.on_event("startup")
async def startup():
    logger.info("🚀 Web Server Starting...")
    
    # 1. Подключаем SQLAdmin
    admin = Admin(app, engine)
    admin.add_view(LotAdmin)
    admin.add_view(AuctionAdmin)
    admin.add_view(ManagerAdmin)
    
    # 2. Запускаем парсер в фоне
    asyncio.create_task(background_parser())

@app.get("/")
async def index():
    return {"status": "ok", "message": "Go to /admin"}