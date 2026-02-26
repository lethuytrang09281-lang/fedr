# Файл: /home/quser/SOFT/FEDR/fedr/src/services/antifraud/engine.py

"""
AntiFraud Engine - Центральный движок объединяющий все метрики
"""

from typing import Optional, List, Dict
import asyncpg
from .models import (
    AntiFraudResult, FraudFactor, RiskLevel,
    PriceDeviation, ManagerKarmaResult
)
from .benchmark import MarketBenchmarkService
from .velocity import VelocityAnalyzer
from .nlp import NLPRedFlagDetector
from .manager_karma import ManagerKarmaService


class AntiFraudEngine:
    """
    Главный движок антифрод анализа
    Объединяет 4 метрики:
    1. Market Benchmark (отклонение от рынка)
    2. Velocity (подозрительные изменения цены)
    3. NLP Red Flags (мошеннические паттерны в описании)
    4. Manager Karma (надёжность управляющего)
    """
    
    def __init__(self, db_pool: asyncpg.Pool, config: dict = None):
        self.db = db_pool
        self.config = config or {}
        
        # Инициализация сервисов
        self.benchmark_service = MarketBenchmarkService(db_pool)
        self.velocity_analyzer = VelocityAnalyzer(db_pool)
        self.nlp_detector = NLPRedFlagDetector()
        self.manager_karma_service = ManagerKarmaService(
            db_pool,
            parser_api_key=self.config.get("parser_api_key"),
            checko_api_key=self.config.get("checko_api_key")
        )
    
    async def analyze_lot(
        self,
        lot_id: int,
        lot_price: float,
        lot_area: float,
        district: str,
        description: str,
        manager_inn: Optional[str] = None,
        price_history: Optional[list] = None
    ) -> AntiFraudResult:
        """
        Комплексный антифрод анализ лота
        """
        
        factors: list[FraudFactor] = []
        total_risk_score = 0
        
        # --- МЕТРИКА 1: Market Benchmark ---
        market_result = None
        try:
            market_result = await self.benchmark_service.analyze_lot(
                lot_price, lot_area, district
            )
            
            if market_result.risk_score > 0:
                factors.append(FraudFactor(
                    type="market_benchmark",
                    score=market_result.risk_score,
                    reason=f"Отклонение от рынка: {market_result.deviation_percent:.1f}%",
                    details={
                        "lot_price_per_sqm": market_result.lot_price_per_sqm,
                        "market_price_per_sqm": market_result.market_price_per_sqm,
                        "deviation_percent": market_result.deviation_percent,
                        "risk_level": market_result.risk_level.value
                    }
                ))
                total_risk_score += market_result.risk_score
        except Exception as e:
            print(f"Market Benchmark error: {e}")
        
        # --- МЕТРИКА 2: Velocity Analysis ---
        velocity_result = None
        if price_history and len(price_history) > 1:
            try:
                velocity_result = await self.velocity_analyzer.analyze_price_schedule(
                    price_history
                )
                
                if velocity_result.get("has_suspicious_drops"):
                    risk_score = 15  # Фиксированный score для velocity
                    factors.append(FraudFactor(
                        type="velocity",
                        score=risk_score,
                        reason=f"Подозрительное снижение цены: {velocity_result.get('max_drop_percent', 0):.1f}%",
                        details=velocity_result
                    ))
                    total_risk_score += risk_score
            except Exception as e:
                print(f"Velocity analysis error: {e}")
        
        # --- МЕТРИКА 3: NLP Red Flags ---
        nlp_red_flags = []
        try:
            nlp_red_flags = await self.nlp_detector.detect_red_flags(description)
            
            if nlp_red_flags:
                risk_score = len(nlp_red_flags) * 5  # 5 баллов за каждый флаг
                factors.append(FraudFactor(
                    type="nlp",
                    score=risk_score,
                    reason=f"Найдено {len(nlp_red_flags)} подозрительных паттернов",
                    details={"red_flags": nlp_red_flags}
                ))
                total_risk_score += risk_score
        except Exception as e:
            print(f"NLP detection error: {e}")
        
        # --- МЕТРИКА 4: Manager Karma ---
        manager_karma_result = None
        if manager_inn:
            try:
                manager_karma_result = await self.manager_karma_service.calculate_karma(
                    manager_inn
                )
                
                if manager_karma_result.risk_score > 0:
                    factors.append(FraudFactor(
                        type="manager_karma",
                        score=manager_karma_result.risk_score,
                        reason=f"Низкая карма управляющего: {manager_karma_result.trust_score}/100",
                        details={
                            "trust_score": manager_karma_result.trust_score,
                            "manager_name": manager_karma_result.manager_name,
                            "success_rate": manager_karma_result.success_rate,
                            "has_red_flags": manager_karma_result.has_red_flags,
                            "factors": manager_karma_result.factors
                        }
                    ))
                    total_risk_score += manager_karma_result.risk_score
            except Exception as e:
                print(f"Manager karma error: {e}")
        
        # --- ФИНАЛЬНАЯ ОЦЕНКА ---
        
        # Ограничить risk_score [0, 100]
        final_risk_score = min(100, total_risk_score)
        
        # Определить risk_level
        if final_risk_score >= 60:
            fraud_risk_level = RiskLevel.CRITICAL
            recommendation = "DO_NOT_BID"
            explanation = "КРИТИЧЕСКИЙ риск мошенничества! Не рекомендуется участвовать в торгах."
        elif final_risk_score >= 40:
            fraud_risk_level = RiskLevel.HIGH
            recommendation = "HIGH_RISK"
            explanation = "Высокий риск. Требуется детальная проверка перед участием."
        elif final_risk_score >= 20:
            fraud_risk_level = RiskLevel.MEDIUM
            recommendation = "REVIEW"
            explanation = "Средний риск. Рекомендуется дополнительная проверка документов."
        else:
            fraud_risk_level = RiskLevel.LOW
            recommendation = "SAFE"
            explanation = "Низкий риск. Лот выглядит безопасным для участия."
        
        return AntiFraudResult(
            lot_id=lot_id,
            fraud_risk_score=final_risk_score,
            fraud_risk_level=fraud_risk_level,
            market_benchmark=market_result,
            velocity_analysis=velocity_result,
            nlp_red_flags=nlp_red_flags,
            manager_karma=manager_karma_result,
            factors=factors,
            recommendation=recommendation,
            explanation=explanation
        )
    
    async def batch_analyze(
        self,
        lot_ids: list[int],
        batch_size: int = 10
    ) -> dict[int, AntiFraudResult]:
        """
        Пакетный анализ нескольких лотов
        """
        results = {}
        
        for i in range(0, len(lot_ids), batch_size):
            batch = lot_ids[i:i+batch_size]
            
            for lot_id in batch:
                # Получить данные лота из БД
                lot_data = await self.db.fetchrow("""
                    SELECT 
                        id,
                        start_price,
                        area,
                        district,
                        description,
                        manager_inn
                    FROM lots
                    WHERE id = $1
                """, lot_id)
                
                if lot_data:
                    # Получить историю цен
                    price_history = await self.db.fetch("""
                        SELECT period_number, price
                        FROM price_schedules
                        WHERE lot_id = $1
                        ORDER BY period_number
                    """, lot_id)
                    
                    # Анализ
                    result = await self.analyze_lot(
                        lot_id=lot_data["id"],
                        lot_price=float(lot_data["start_price"]),
                        lot_area=float(lot_data["area"]),
                        district=lot_data["district"],
                        description=lot_data["description"] or "",
                        manager_inn=lot_data.get("manager_inn"),
                        price_history=[dict(p) for p in price_history] if price_history else None
                    )
                    
                    results[lot_id] = result
        
        return results
