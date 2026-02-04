"""
Админ-панель для Fedresurs Pro.
Временно отключаем парсер для отладки веб-интерфейса.
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from src.core.logger import logger
from src.database.session import get_session
from src.database.models import Auction, Lot, MessageHistory, SystemState, LotStatus
from src.core.config import settings

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

# Временно отключаем парсер для отладки
async def run_parser_background():
    """Фоновая задача парсера - временно отключена для отладки"""
    logger.info("🚫 Парсер временно отключен для отладки админ-панели.")
    # await main_loop()  # Закомментировано по требованию
    # Вместо этого просто спим, чтобы не мешать
    while True:
        logger.debug("💓 Система жива (парсер отключен)")
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    """Действия при старте приложения"""
    logger.info("🚀 Запуск админ-панели Fedresurs Pro...")
    
    # Запускаем отключенный парсер в фоне
    asyncio.create_task(run_parser_background())
    
    logger.info("✅ Админ-панель запущена. Парсер временно отключен.")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Корневая страница с информацией о системе"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fedresurs Pro Admin Panel</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .card { background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .endpoint { background: #e9ecef; padding: 10px; border-radius: 4px; font-family: monospace; }
            a { color: #007bff; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>🚀 Fedresurs Pro Admin Panel</h1>
        <div class="card">
            <h2>📊 Система мониторинга торгов</h2>
            <p>Парсер временно отключен для отладки админ-панели.</p>
            <p>Используйте следующие эндпоинты для работы с данными:</p>
            <ul>
                <li><a href="/docs">📚 Swagger UI документация</a></li>
                <li><a href="/redoc">📖 ReDoc документация</a></li>
                <li><a href="/api/health">🩺 Проверка здоровья системы</a></li>
                <li><a href="/api/auctions">🏛️ Список торгов</a></li>
                <li><a href="/api/lots">📦 Список лотов</a></li>
                <li><a href="/api/stats">📈 Статистика</a></li>
            </ul>
        </div>
        <div class="card">
            <h3>Примеры запросов:</h3>
            <div class="endpoint">GET /api/auctions?limit=10&offset=0</div>
            <div class="endpoint">GET /api/lots?status=Active&min_price=1000000</div>
            <div class="endpoint">GET /api/stats</div>
        </div>
    </body>
    </html>
    """

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
            "parser": "temporarily_disabled"
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
                "lots_without_cadastral": lot_count - lots_with_cadastral
            },
            "status_distribution": status_stats,
            "recent_activity": {
                "last_auction_time": last_auction.last_updated.isoformat() if last_auction else None,
                "last_auction_number": last_auction.number if last_auction else None
            },
            "system": {
                "parser_status": "temporarily_disabled",
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