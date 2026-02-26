# Файл: /home/quser/SOFT/FEDR/fedr/src/services/antifraud/velocity.py

"""
Velocity Analyzer - детекция подозрительных изменений цены
"""

from typing import List, Dict, Optional
import asyncpg


class VelocityAnalyzer:
    """Анализатор скорости и характера изменения цены"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        
    async def analyze_price_schedule(self, price_history: List[Dict]) -> Dict:
        """
        Анализирует график снижения цены
        
        Args:
            price_history: Список периодов с ценами [{"period_number": 1, "price": 1000}, ...]
            
        Returns:
            Словарь с результатами анализа
        """
        if not price_history or len(price_history) < 2:
            return {
                "has_suspicious_drops": False,
                "max_drop_percent": 0,
                "reason": "Недостаточно данных для анализа"
            }
            
        # Сортируем по номеру периода
        sorted_history = sorted(price_history, key=lambda x: x.get("period_number", 0))
        
        max_drop_percent = 0
        has_suspicious_drops = False
        drops = []
        
        for i in range(1, len(sorted_history)):
            prev_price = float(sorted_history[i-1]["price"])
            curr_price = float(sorted_history[i]["price"])
            
            if prev_price > 0:
                drop_percent = ((prev_price - curr_price) / prev_price) * 100
                drops.append(drop_percent)
                
                if drop_percent > max_drop_percent:
                    max_drop_percent = drop_percent
                    
                # Если цена падает более чем на 50% за один шаг - это подозрительно
                if drop_percent > 50:
                    has_suspicious_drops = True
                    
        return {
            "has_suspicious_drops": has_suspicious_drops,
            "max_drop_percent": max_drop_percent,
            "drops_count": len(drops),
            "average_drop": sum(drops) / len(drops) if drops else 0
        }
