# src/services/hunter/investment_scorer.py

"""
Investment Scorer - Движок оценки инвестиционной привлекательности
Инверсия AntifraudEngine: находим алмазы, а не мусор
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta

from .models import (
    InvestmentScore, 
    InvestmentFactor, 
    InvestmentFactorType,
    DealScore,
    DealRecommendation
)

logger = logging.getLogger(__name__)


class InvestmentScorer:
    """
    Оценивает инвестиционную привлекательность лота
    
    Компоненты оценки:
    1. Geography (0-30): Приоритет районов
    2. Discount (0-50): Дисконт к рынку (чем больше, тем лучше!)
    3. Liquidity (0-35): Тип актива (МКД/Земля > Офис > Склад)
    4. Timing (0-20): Стадия торгов (Публичное предложение = выгоднее)
    5. Early Bird (0-25): Бонус за раннюю стадию (Инвентаризация)
    """
    
    # Константы для скоринга
    GEOGRAPHY_WEIGHTS = {
        "GARDEN_RING": 30,
        "TTK": 20,
        "OUTSIDE": 5,
        "UNKNOWN": 10
    }
    
    ASSET_TYPE_SCORES = {
        # Целевые активы (высоколиквидные)
        "земля_ижс": 35,
        "мкд": 30,
        "офис": 25,
        "торговое": 25,
        
        # Средняя ликвидность
        "жилое": 20,
        "производство": 15,
        
        # Низкая ликвидность
        "склад": 10,
        "гараж": 5,
        "доля": 5
    }
    
    def __init__(self, market_benchmark_service=None):
        """
        Args:
            market_benchmark_service: Сервис для получения рыночных цен
        """
        self.market_service = market_benchmark_service
    
    async def calculate_investment_score(
        self,
        lot_price: float,
        lot_area: float,
        district: str,
        description: str,
        cadastral_numbers: List[str],
        zone: Optional[str] = None,
        stage: Optional[str] = None,
        days_until_next_period: Optional[int] = None,
        market_price_per_sqm: Optional[float] = None
    ) -> InvestmentScore:
        """
        Рассчитывает investment_score [0-100]
        
        Args:
            lot_price: Цена лота (₽)
            lot_area: Площадь (м²)
            district: Район (для бенчмарка)
            description: Текст описания
            cadastral_numbers: Кадастровые номера
            zone: Зона (GARDEN_RING/TTK/OUTSIDE)
            stage: Стадия (InventoryResult/Auction/PublicOffer)
            days_until_next_period: Дней до снижения цены
            market_price_per_sqm: Рыночная цена/м² (если уже известна)
            
        Returns:
            InvestmentScore с детализацией
        """
        
        score = 0
        factors: List[InvestmentFactor] = []
        
        # === КОМПОНЕНТ 1: География ===
        geo_score, geo_reason = self._geography_score(district, zone)
        if geo_score > 0:
            factors.append(InvestmentFactor(
                type=InvestmentFactorType.GEOGRAPHY,
                score=geo_score,
                reason=geo_reason,
                details={"district": district, "zone": zone}
            ))
            score += geo_score
        
        # === КОМПОНЕНТ 2: Дисконт (КЛЮЧЕВОЙ!) ===
        # Получаем рыночную цену если не передали
        if market_price_per_sqm is None and self.market_service:
            try:
                benchmark = await self.market_service.get_benchmark(district)
                if benchmark:
                    market_price_per_sqm = benchmark.median_price_per_sqm
            except Exception as e:
                logger.warning(f"Failed to get market benchmark: {e}")
        
        discount_score = 0
        discount_percent = None
        
        if market_price_per_sqm and lot_area > 0:
            lot_price_per_sqm = lot_price / lot_area
            
            # Расчёт отклонения
            discount_percent = ((lot_price_per_sqm - market_price_per_sqm) / market_price_per_sqm) * 100
            
            # ИНВЕРСИЯ: Большой минус = хорошо!
            if discount_percent < -50:
                discount_score = 50
                reason = f"🔥 СУПЕР СКИДКА: {abs(discount_percent):.1f}% ниже рынка!"
            elif discount_percent < -40:
                discount_score = 40
                reason = f"🔥 Большая скидка: {abs(discount_percent):.1f}% ниже рынка"
            elif discount_percent < -30:
                discount_score = 30
                reason = f"✅ Хорошая скидка: {abs(discount_percent):.1f}% ниже рынка"
            elif discount_percent < -20:
                discount_score = 20
                reason = f"✅ Скидка: {abs(discount_percent):.1f}% ниже рынка"
            elif discount_percent < -10:
                discount_score = 10
                reason = f"Небольшая скидка: {abs(discount_percent):.1f}%"
            else:
                discount_score = 0
                reason = f"Цена близка к рынку ({discount_percent:+.1f}%)"
            
            factors.append(InvestmentFactor(
                type=InvestmentFactorType.DISCOUNT,
                score=discount_score,
                reason=reason,
                details={
                    "lot_price_per_sqm": lot_price_per_sqm,
                    "market_price_per_sqm": market_price_per_sqm,
                    "discount_percent": discount_percent
                }
            ))
            score += discount_score
        
        # === КОМПОНЕНТ 3: Ликвидность ===
        liquidity_score, liquidity_reason, asset_type = self._liquidity_score(
            description, 
            cadastral_numbers
        )
        if liquidity_score > 0:
            factors.append(InvestmentFactor(
                type=InvestmentFactorType.LIQUIDITY,
                score=liquidity_score,
                reason=liquidity_reason,
                details={"asset_type": asset_type}
            ))
            score += liquidity_score
        
        # === КОМПОНЕНТ 4: Timing (стадия торгов) ===
        if stage:
            timing_score, timing_reason = self._timing_score(stage, days_until_next_period)
            if timing_score > 0:
                factors.append(InvestmentFactor(
                    type=InvestmentFactorType.TIMING,
                    score=timing_score,
                    reason=timing_reason,
                    details={
                        "stage": stage,
                        "days_until_next": days_until_next_period
                    }
                ))
                score += timing_score
        
        # === КОМПОНЕНТ 5: Early Bird (Shift Left!) ===
        if stage in ["InventoryResult", "AppraiserReport"]:
            early_bird_score = 25
            factors.append(InvestmentFactor(
                type=InvestmentFactorType.EARLY_BIRD,
                score=early_bird_score,
                reason="🎯 РАННЯЯ СТАДИЯ — Инвентаризация (торги через 3-6 месяцев)",
                details={"stage": stage}
            ))
            score += early_bird_score
        
        # Ограничиваем [0, 100]
        final_score = min(100, max(0, score))
        
        return InvestmentScore(
            investment_score=final_score,
            factors=factors,
            discount_percent=discount_percent,
            district=district,
            zone=zone,
            asset_type=asset_type,
            liquidity_category=self._get_liquidity_category(liquidity_score)
        )
    
    def _geography_score(self, district: str, zone: Optional[str] = None) -> tuple[int, str]:
        """
        Оценка приоритета района
        
        Returns:
            (score, reason)
        """
        # Используем зону если есть
        if zone:
            score = self.GEOGRAPHY_WEIGHTS.get(zone, 10)
            reason = f"📍 {district} ({zone})"
        else:
            # Fallback: пытаемся определить по названию района
            district_lower = district.lower()
            
            # Премиальные районы (Garden Ring)
            if any(name in district_lower for name in [
                "хамовники", "арбат", "пресненский", "тверской",
                "басманный", "таганский", "замоскворечье"
            ]):
                score = 30
                reason = f"📍 {district} (центр Москвы)"
            
            # ТТК
            elif any(name in district_lower for name in [
                "марьино", "кунцево", "тушино", "бабушкинский"
            ]):
                score = 20
                reason = f"📍 {district} (в пределах ТТК)"
            
            # За пределами ТТК
            else:
                score = 10
                reason = f"📍 {district}"
        
        return score, reason
    
    def _liquidity_score(
        self, 
        description: str, 
        cadastral_numbers: List[str]
    ) -> tuple[int, str, str]:
        """
        Оценка ликвидности актива
        
        Returns:
            (score, reason, asset_type)
        """
        desc_lower = description.lower()
        
        # Земля под застройку (ГЛАВНЫЙ АКТИВ!)
        if "земельный участок" in desc_lower:
            if "ижс" in desc_lower or "индивидуальн" in desc_lower:
                return (35, "🏆 ЗЕМЛЯ ИЖС — высоколиквидный актив", "земля_ижс")
            elif "мкд" in desc_lower or "многоквартирн" in desc_lower:
                return (35, "🏆 ЗЕМЛЯ ПОД МКД — целевой актив!", "земля_мкд")
            else:
                return (25, "✅ Земельный участок", "земля")
        
        # МКД (целевой тип!)
        if any(word in desc_lower for word in ["мкд", "многоквартирный дом", "жилой дом"]):
            return (30, "🏆 МКД — высоколиквидный актив", "мкд")
        
        # Коммерческая недвижимость
        if "офис" in desc_lower or "офисное помещение" in desc_lower:
            return (25, "✅ Офис — ликвидный актив", "офис")
        
        if any(word in desc_lower for word in ["торговое помещение", "магазин", "ритейл"]):
            return (25, "✅ Торговое помещение — ликвидный актив", "торговое")
        
        # Жилая недвижимость
        if "квартира" in desc_lower or "жилое помещение" in desc_lower:
            return (20, "Жилая недвижимость", "жилое")
        
        # Производство
        if any(word in desc_lower for word in ["производственное", "завод", "цех"]):
            return (15, "Производственная недвижимость", "производство")
        
        # Низколиквидные
        if "склад" in desc_lower:
            return (10, "⚠️ Склад — низкая ликвидность", "склад")
        
        if "гараж" in desc_lower or "машиноместо" in desc_lower:
            return (5, "⚠️ Гараж/Машиноместо — низкая ликвидность", "гараж")
        
        if "доля" in desc_lower:
            return (5, "⚠️ Доля в праве — очень низкая ликвидность", "доля")
        
        # Неизвестный тип
        return (10, "Тип недвижимости не определён", "unknown")
    
    def _timing_score(
        self, 
        stage: str, 
        days_until_next: Optional[int]
    ) -> tuple[int, str]:
        """
        Оценка момента входа
        
        Returns:
            (score, reason)
        """
        if stage == "PublicOffer":
            if days_until_next and days_until_next <= 3:
                return (20, f"⏰ СРОЧНО: Цена упадёт через {days_until_next} дней!")
            elif days_until_next and days_until_next <= 7:
                return (15, f"⏰ Публичное предложение (цена упадёт через {days_until_next} дней)")
            else:
                return (10, "Публичное предложение (отслеживаем снижение цены)")
        
        if stage == "Auction":
            return (5, "Обычные торги")
        
        return (0, "")
    
    @staticmethod
    def _get_liquidity_category(liquidity_score: int) -> str:
        """Категория ликвидности по баллам"""
        if liquidity_score >= 30:
            return "HIGH"
        elif liquidity_score >= 20:
            return "MEDIUM"
        elif liquidity_score >= 10:
            return "LOW"
        else:
            return "VERY_LOW"
    
    @staticmethod
    def calculate_deal_score(
        investment_score: int,
        fraud_risk_score: int
    ) -> DealScore:
        """
        Комбинирует Investment Score и Fraud Risk в финальный Deal Score
        
        Formula: deal_score = investment_score - (fraud_risk * 0.6)
        
        Логика: Антифрод штрафует, но не полностью убивает сделку.
        Пример:
        - Investment 80, Fraud 20 → Deal 68 (🔥 HOT)
        - Investment 60, Fraud 60 → Deal 24 (⛔ PASS)
        
        Args:
            investment_score: Привлекательность [0-100]
            fraud_risk_score: Риск мошенничества [0-100]
            
        Returns:
            DealScore с рекомендацией
        """
        
        # Fraud penalty с коэффициентом 0.6 (не убиваем сделку полностью)
        fraud_penalty = int(fraud_risk_score * 0.6)
        
        # Финальный скор
        deal_score = max(0, investment_score - fraud_penalty)
        
        # Рекомендация
        if deal_score >= 70:
            recommendation = DealRecommendation.HOT_DEAL
            explanation = "🔥 ГОРЯЧАЯ СДЕЛКА! Высокая привлекательность, низкие риски."
        elif deal_score >= 50:
            recommendation = DealRecommendation.GOOD_OPPORTUNITY
            explanation = "✅ Хорошая возможность. Рекомендуется детальная проверка."
        elif deal_score >= 30:
            recommendation = DealRecommendation.CONSIDER
            explanation = "🤔 Сделка требует осторожности. Есть риски или невысокая привлекательность."
        else:
            recommendation = DealRecommendation.PASS
            explanation = "⛔ Не рекомендуется. Слишком высокие риски или низкая привлекательность."
        
        return DealScore(
            deal_score=deal_score,
            recommendation=recommendation,
            investment_score=investment_score,
            fraud_risk_score=fraud_risk_score,
            fraud_penalty=fraud_penalty,
            investment_factors=[],  # Будет заполнено позже
            explanation=explanation
        )
