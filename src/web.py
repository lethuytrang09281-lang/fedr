"""
Админ-панель для Fedresurs Pro.
Включает FastAPI + SQLAdmin для управления данными + красивый Dashboard.
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from sqladmin import Admin, ModelView

from src.core.logger import logger
from src.database.session import get_session, engine
from src.database.models import Auction, Lot, MessageHistory, SystemState, LotStatus
from src.core.config import settings
from src.services.orchestrator import orchestrator

app = FastAPI(
    title="Fedresurs Pro Admin Panel",
    description="Административная панель для мониторинга торгов и лотов",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLAdmin интеграция
admin = Admin(app, engine, title="Fedresurs Pro Admin")


# Admin Views для моделей
class AuctionAdmin(ModelView, model=Auction):
    """Административная панель для торгов"""
    column_list = [Auction.guid, Auction.number, Auction.etp_id, Auction.organizer_inn, Auction.last_updated]
    column_searchable_list = [Auction.number, Auction.organizer_inn]
    column_sortable_list = [Auction.number, Auction.last_updated]
    column_default_sort = [(Auction.last_updated, True)]
    can_create = False  # Только чтение (создаются парсером)
    can_edit = True
    can_delete = True
    page_size = 50


class LotAdmin(ModelView, model=Lot):
    """Административная панель для лотов"""
    column_list = [
        Lot.id, Lot.lot_number, Lot.description, Lot.start_price,
        Lot.status, Lot.category_code, Lot.is_restricted
    ]
    column_searchable_list = [Lot.description, Lot.category_code]
    column_sortable_list = [Lot.id, Lot.start_price, Lot.status]
    column_filters = [Lot.status, Lot.category_code, Lot.is_restricted]
    column_default_sort = [(Lot.id, True)]
    can_create = False
    can_edit = True
    can_delete = True
    page_size = 100


class MessageHistoryAdmin(ModelView, model=MessageHistory):
    """Административная панель для истории сообщений"""
    column_list = [MessageHistory.guid, MessageHistory.type, MessageHistory.date_publish]
    column_searchable_list = [MessageHistory.type]
    column_sortable_list = [MessageHistory.date_publish]
    column_default_sort = [(MessageHistory.date_publish, True)]
    can_create = False
    can_edit = False
    can_delete = True
    page_size = 50


class SystemStateAdmin(ModelView, model=SystemState):
    """Административная панель для системного состояния"""
    column_list = [SystemState.task_key, SystemState.last_processed_date]
    can_create = True
    can_edit = True
    can_delete = True


# Регистрация админ-панелей
admin.add_view(AuctionAdmin)
admin.add_view(LotAdmin)
admin.add_view(MessageHistoryAdmin)
admin.add_view(SystemStateAdmin)

@app.on_event("startup")
async def startup_event():
    """Действия при старте приложения"""
    logger.info("🚀 Запуск админ-панели Fedresurs Pro...")

    # Запускаем оркестратор в фоновом режиме
    asyncio.create_task(orchestrator.start_monitoring())

    logger.info("✅ Админ-панель запущена. Оркестратор работает в фоне.")


@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения"""
    logger.info("🛑 Остановка админ-панели...")
    await orchestrator.stop()
    logger.info("✅ Приложение остановлено.")

@app.get("/")
async def root():
    """Redirect to dashboard"""
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Красивая панель управления с real-time мониторингом"""
    dashboard_path = Path(__file__).parent / "static" / "dashboard.html"

    if not dashboard_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")

    with open(dashboard_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Проверка здоровья системы и подключения к БД"""
    try:
        # Проверяем подключение к БД
        result = await session.execute(select(func.count()).select_from(Auction))
        auction_count = result.scalar()
        
        result = await session.execute(select(func.count()).select_from(Lot))
        lot_count = result.scalar()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected",
            "counts": {
                "auctions": auction_count,
                "lots": lot_count
            },
            "orchestrator": {
                "status": "running" if orchestrator.is_running else "stopped",
                "mode": "simulation" if not settings.CHECKO_API_KEY else "production"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")

@app.get("/api/auctions")
async def get_auctions(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    organizer_inn: Optional[str] = None,
    search: Optional[str] = None
):
    """Получить список торгов с пагинацией"""
    try:
        query = select(Auction).order_by(desc(Auction.last_updated))
        
        if organizer_inn:
            query = query.where(Auction.organizer_inn == organizer_inn)
        
        if search:
            query = query.where(Auction.number.ilike(f"%{search}%"))
        
        query = query.offset(offset).limit(limit).options(selectinload(Auction.lots))
        
        result = await session.execute(query)
        auctions = result.scalars().all()
        
        return {
            "auctions": [
                {
                    "guid": str(a.guid),
                    "number": a.number,
                    "etp_id": a.etp_id,
                    "organizer_inn": a.organizer_inn,
                    "last_updated": a.last_updated.isoformat() if a.last_updated else None,
                    "lot_count": len(a.lots)
                }
                for a in auctions
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(auctions)
            }
        }
    except Exception as e:
        logger.error(f"Error fetching auctions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/api/lots/filter")
async def filter_lots(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    zone: Optional[str] = Query(None, description="Фильтр по зоне: GARDEN_RING, TTK, TPU, OUTSIDE"),
    is_relevant: Optional[bool] = Query(None, description="Только релевантные лоты"),
    tags: Optional[str] = Query(None, description="Теги через запятую (например: мкд,офисный_центр)"),
    exclude_red_flags: Optional[bool] = Query(False, description="Исключить лоты с красными флагами"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0)
):
    """
    Фильтрация лотов по критериям классификации (Sprint 1).

    Примеры:
    - /api/lots/filter?zone=GARDEN_RING&is_relevant=true
    - /api/lots/filter?tags=мкд,офисный_центр&exclude_red_flags=true
    - /api/lots/filter?is_relevant=true&min_price=1000000
    """
    try:
        query = select(Lot).join(Auction).order_by(desc(Lot.id))

        # Фильтр по зоне
        if zone:
            query = query.where(Lot.location_zone == zone)

        # Фильтр по релевантности
        if is_relevant is not None:
            query = query.where(Lot.is_relevant == is_relevant)

        # Фильтр по тегам (поддержка нескольких через запятую)
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            # Ищем лоты, у которых есть хотя бы один из указанных тегов
            query = query.where(Lot.semantic_tags.overlap(tag_list))

        # Исключение лотов с красными флагами
        if exclude_red_flags:
            query = query.where(Lot.red_flags == [])

        # Фильтр по цене
        if min_price is not None:
            query = query.where(Lot.start_price >= min_price)

        if max_price is not None:
            query = query.where(Lot.start_price <= max_price)

        # Применяем пагинацию
        query = query.offset(offset).limit(limit).options(
            selectinload(Lot.auction),
            selectinload(Lot.price_schedules)
        )

        result = await session.execute(query)
        lots = result.scalars().all()

        return {
            "lots": [
                {
                    "id": lot.id,
                    "guid": str(lot.guid) if lot.guid else None,
                    "auction_id": str(lot.auction_id),
                    "auction_number": lot.auction.number if lot.auction else None,
                    "lot_number": lot.lot_number,
                    "description": lot.description[:200] + "..." if len(lot.description) > 200 else lot.description,
                    "start_price": float(lot.start_price) if lot.start_price else None,
                    "status": lot.status,
                    "category_code": lot.category_code,
                    "cadastral_numbers": lot.cadastral_numbers,
                    "is_restricted": lot.is_restricted,
                    # Поля классификации (Sprint 1)
                    "location_zone": lot.location_zone,
                    "is_relevant": lot.is_relevant,
                    "semantic_tags": lot.semantic_tags,
                    "red_flags": lot.red_flags,
                    "needs_enrichment": lot.needs_enrichment,
                    "created_at": lot.auction.last_updated.isoformat() if lot.auction and lot.auction.last_updated else None
                }
                for lot in lots
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(lots)
            }
        }
    except Exception as e:
        logger.error(f"Error filtering lots: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/api/lots")
async def get_lots(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    auction_guid: Optional[str] = None,
    has_cadastral: Optional[bool] = None
):
    """Получить список лотов с фильтрацией"""
    try:
        query = select(Lot).join(Auction).order_by(desc(Lot.id))
        
        if status:
            query = query.where(Lot.status == status)
        
        if min_price is not None:
            query = query.where(Lot.start_price >= min_price)
        
        if max_price is not None:
            query = query.where(Lot.start_price <= max_price)
        
        if auction_guid:
            query = query.where(Auction.guid == auction_guid)
        
        if has_cadastral is not None:
            if has_cadastral:
                query = query.where(Lot.cadastral_numbers != [])
            else:
                query = query.where(Lot.cadastral_numbers == [])
        
        query = query.offset(offset).limit(limit).options(
            selectinload(Lot.auction),
            selectinload(Lot.price_schedules)
        )
        
        result = await session.execute(query)
        lots = result.scalars().all()
        
        return {
            "lots": [
                {
                    "id": lot.id,
                    "guid": str(lot.guid) if lot.guid else None,
                    "auction_id": str(lot.auction_id),
                    "auction_number": lot.auction.number if lot.auction else None,
                    "lot_number": lot.lot_number,
                    "description": lot.description[:200] + "..." if len(lot.description) > 200 else lot.description,
                    "start_price": float(lot.start_price) if lot.start_price else None,
                    "status": lot.status,
                    "category_code": lot.category_code,
                    "cadastral_numbers": lot.cadastral_numbers,
                    "is_restricted": lot.is_restricted,
                    # Поля классификации (Sprint 1)
                    "location_zone": getattr(lot, "location_zone", "OUTSIDE"),
                    "is_relevant": getattr(lot, "is_relevant", False),
                    "semantic_tags": getattr(lot, "semantic_tags", []),
                    "red_flags": getattr(lot, "red_flags", []),
                    "needs_enrichment": getattr(lot, "needs_enrichment", False),
                    "created_at": lot.auction.last_updated.isoformat() if lot.auction and lot.auction.last_updated else None
                }
                for lot in lots
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(lots)
            }
        }
    except Exception as e:
        logger.error(f"Error fetching lots: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/api/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Получить статистику системы"""
    try:
        # Статистика по аукционам
        auctions_query = select(func.count()).select_from(Auction)
        result = await session.execute(auctions_query)
        auction_count = result.scalar()
        
        # Статистика по лотам
        lots_query = select(func.count()).select_from(Lot)
        result = await session.execute(lots_query)
        lot_count = result.scalar()
        
        # Статистика по статусам лотов
        status_query = select(Lot.status, func.count(Lot.status)).group_by(Lot.status)
        result = await session.execute(status_query)
        status_stats = {row[0]: row[1] for row in result.all()}
        
        # Лоты с кадастровыми номерами
        cadastral_query = select(func.count()).select_from(Lot).where(Lot.cadastral_numbers != [])
        result = await session.execute(cadastral_query)
        lots_with_cadastral = result.scalar()
        
        # Статистика по зонам
        zone_query = select(Lot.location_zone, func.count(Lot.location_zone)).group_by(Lot.location_zone)
        result = await session.execute(zone_query)
        zone_stats = {row[0]: row[1] for row in result.all()}

        # Целевые лоты (is_relevant=true)
        target_query = select(func.count()).select_from(Lot).where(Lot.is_relevant == True)
        result = await session.execute(target_query)
        target_count = result.scalar()

        # Лоты с red_flags
        red_flags_query = select(func.count()).select_from(Lot).where(Lot.red_flags != [])
        result = await session.execute(red_flags_query)
        red_flags_count = result.scalar()

        # Последние обновления
        last_auction_query = select(Auction).order_by(desc(Auction.last_updated)).limit(1)
        result = await session.execute(last_auction_query)
        last_auction = result.scalar_one_or_none()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "auctions": auction_count,
                "lots": lot_count,
                "lots_with_cadastral": lots_with_cadastral,
                "lots_without_cadastral": lot_count - lots_with_cadastral,
                "target_lots": target_count,
                "red_flags_lots": red_flags_count
            },
            "zone_distribution": zone_stats,
            "status_distribution": status_stats,
            "recent_activity": {
                "last_auction_time": last_auction.last_updated.isoformat() if last_auction else None,
                "last_auction_number": last_auction.number if last_auction else None
            },
            "system": {
                "orchestrator_status": "running" if orchestrator.is_running else "stopped",
                "orchestrator_mode": "simulation" if not settings.CHECKO_API_KEY else "production",
                "database": "connected",
                "environment": settings.APP_ENV
            }
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/api/auctions/{auction_guid}")
async def get_auction_detail(
    auction_guid: str,
    session: AsyncSession = Depends(get_session)
):
    """Получить детальную информацию о торгах"""
    try:
        query = select(Auction).where(Auction.guid == auction_guid).options(
            selectinload(Auction.lots),
            selectinload(Auction.messages)
        )
        result = await session.execute(query)
        auction = result.scalar_one_or_none()
        
        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")
        
        return {
            "auction": {
                "guid": str(auction.guid),
                "number": auction.number,
                "etp_id": auction.etp_id,
                "organizer_inn": auction.organizer_inn,
                "last_updated": auction.last_updated.isoformat() if auction.last_updated else None
            },
            "lots": [
                {
                    "id": lot.id,
                    "lot_number": lot.lot_number,
                    "description": lot.description,
                    "start_price": float(lot.start_price) if lot.start_price else None,
                    "status": lot.status,
                    "cadastral_numbers": lot.cadastral_numbers,
                    "is_restricted": lot.is_restricted
                }
                for lot in auction.lots
            ],
            "messages": [
                {
                    "guid": str(msg.guid),
                    "type": msg.type,
                    "date_publish": msg.date_publish.isoformat() if msg.date_publish else None
                }
                for msg in auction.messages
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching auction detail: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/api/orchestrator/status")
async def get_orchestrator_status(session: AsyncSession = Depends(get_session)):
    """Получить детальный статус оркестратора с реальными метриками"""
    try:
        # Получаем состояние из базы данных
        state_query = select(SystemState).where(SystemState.task_key == "trade_monitor")
        result = await session.execute(state_query)
        state = result.scalar_one_or_none()

        # Получаем последние сообщения
        recent_messages_query = (
            select(MessageHistory)
            .order_by(desc(MessageHistory.date_publish))
            .limit(10)
        )
        result = await session.execute(recent_messages_query)
        recent_messages = result.scalars().all()

        # Вычисляем разницу между текущей датой и последней обработанной
        now = datetime.now(timezone.utc)
        if state and state.last_processed_date:
            time_behind = (now - state.last_processed_date).total_seconds()
            days_behind = time_behind / 86400  # секунды в днях
        else:
            time_behind = 0
            days_behind = 0

        return {
            "timestamp": now.isoformat(),
            "orchestrator": {
                "is_running": orchestrator.is_running,
                "mode": "production" if settings.CHECKO_API_KEY else "simulation",
                "last_processed_date": state.last_processed_date.isoformat() if state and state.last_processed_date else None,
                "current_date": now.isoformat(),
                "time_behind_seconds": round(time_behind),
                "days_behind": round(days_behind, 2),
            },
            "recent_activity": [
                {
                    "guid": str(msg.guid),
                    "type": msg.type,
                    "date_publish": msg.date_publish.isoformat() if msg.date_publish else None,
                    "auction_id": str(msg.auction_id) if msg.auction_id else None
                }
                for msg in recent_messages
            ],
            "api": {
                "base_url": settings.EFRSB_BASE_URL,
                "login": settings.EFRSB_LOGIN,
            }
        }
    except Exception as e:
        logger.error(f"Error fetching orchestrator status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server on http://0.0.0.0:8000")
    uvicorn.run(
        "src.web:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )