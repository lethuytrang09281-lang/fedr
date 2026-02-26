# src/services/hunter/strategies/conflict_analyzer.py

"""
Conflict Analyzer - Стратегия "Конфликт АУ ↔ Должник"

Цель: Найти "чистые" активы через анализ арбитражных дел
Логика: Если должник активно жалуется на управляющего = управляющий работает честно

Гипотеза:
- Управляющий честный → Должник недоволен (актив продают реально)
- Управляющий мошенник → Должник молчит (актив продают "своим")

Показатели конфликта:
1. Жалобы должника на действия АУ
2. Жалобы кредиторов на АУ
3. Судебные споры по оценке имущества
4. Оспаривание сделок АУ

Парадокс: Много жалоб = Хороший знак для инвестора!
"""

import logging
from typing import Optional, List, Dict
import asyncpg

logger = logging.getLogger(__name__)


class ConflictAnalyzer:
    """
    Анализатор конфликтов в банкротном деле
    
    Источник данных: КАД.АРБИТР (через parser-api.com)
    
    Метрики:
    - Количество жалоб должника
    - Количество оспариваний сделок
    - Количество жалоб кредиторов
    - Успешность жалоб (удовлетворены/отклонены)
    """
    
    # Типы документов которые нас интересуют
    CONFLICT_DOCUMENT_TYPES = {
        "complaint": "Жалоба",
        "objection": "Возражение",
        "dispute": "Оспаривание",
        "motion": "Ходатайство об отстранении АУ"
    }
    
    # Пороги для оценки
    HIGH_CONFLICT_THRESHOLD = 5    # 5+ жалоб = высокий конфликт
    TRUST_BONUS_THRESHOLD = 3      # 3+ жалоб = бонус к доверию
    
    def __init__(self, db_pool: asyncpg.Pool, parser_api_client=None):
        self.db = db_pool
        self.parser_api = parser_api_client  # Клиент для КАД.АРБИТР
    
    async def analyze_bankruptcy_case(
        self,
        case_number: str,
        manager_inn: Optional[str] = None
    ) -> dict:
        """
        Анализ банкротного дела на наличие конфликтов
        
        Args:
            case_number: Номер дела (А40-12345/2024)
            manager_inn: ИНН арбитражного управляющего
            
        Returns:
            {
                "conflict_detected": bool,
                "conflict_score": int,  # [0-100]
                "trust_signal": str,
                "details": {...}
            }
        """
        
        if not self.parser_api:
            raise ValueError("Parser API client not initialized")
        
        # Запрос в КАД.АРБИТР
        try:
            cases = await self.parser_api.search_arbitr_cases(
                case_number=case_number
            )
        except Exception as e:
            logger.error(f"Failed to fetch arbitr cases: {e}")
            return {
                "conflict_detected": False,
                "conflict_score": 0,
                "trust_signal": "Данные недоступны",
                "details": {"error": str(e)}
            }
        
        # Анализ документов
        analysis = self._analyze_case_documents(cases)
        
        # Оценка конфликта
        conflict_score = self._calculate_conflict_score(analysis)
        
        # Интерпретация
        trust_signal = self._interpret_conflict(conflict_score, analysis)
        
        result = {
            "conflict_detected": conflict_score >= 30,
            "conflict_score": conflict_score,
            "trust_signal": trust_signal,
            "details": analysis
        }
        
        # Сохранить в БД для истории
        if manager_inn:
            await self._save_conflict_analysis(
                manager_inn=manager_inn,
                case_number=case_number,
                analysis=result
            )
        
        return result
    
    def _analyze_case_documents(self, cases: List[dict]) -> dict:
        """
        Анализ документов дела
        
        Считаем:
        - Жалобы должника
        - Жалобы кредиторов
        - Оспаривания сделок
        - Результаты рассмотрения
        
        Returns:
            Детальная статистика по делу
        """
        
        analysis = {
            "total_documents": len(cases),
            "debtor_complaints": 0,
            "creditor_complaints": 0,
            "transaction_disputes": 0,
            "removal_motions": 0,
            "complaints_granted": 0,
            "complaints_denied": 0,
            "case_types": []
        }
        
        for case in cases:
            case_type = case.get("type", "").lower()
            analysis["case_types"].append(case_type)
            
            # Жалобы должника
            if "жалоба" in case_type and "должник" in case.get("plaintiff", "").lower():
                analysis["debtor_complaints"] += 1
            
            # Жалобы кредиторов
            if "жалоба" in case_type and "кредитор" in case.get("plaintiff", "").lower():
                analysis["creditor_complaints"] += 1
            
            # Оспаривание сделок
            if "оспаривание" in case_type or "недействительн" in case_type:
                analysis["transaction_disputes"] += 1
            
            # Ходатайства об отстранении АУ
            if "отстранение" in case_type or "замена" in case_type:
                analysis["removal_motions"] += 1
            
            # Результаты
            result = case.get("result", "").lower()
            if "удовлетворен" in result:
                analysis["complaints_granted"] += 1
            elif "отказ" in result or "оставлен без удовлетворения" in result:
                analysis["complaints_denied"] += 1
        
        return analysis
    
    def _calculate_conflict_score(self, analysis: dict) -> int:
        """
        Расчёт уровня конфликта [0-100]
        
        Формула:
        + Жалобы должника * 15
        + Жалобы кредиторов * 10
        + Оспаривания сделок * 20
        + Ходатайства об отстранении * 25
        - (Отказанные жалобы * 5)  # Если жалобы отклоняют = АУ прав
        
        Returns:
            conflict_score [0-100]
        """
        
        score = 0
        
        # Положительные факторы (конфликт)
        score += analysis["debtor_complaints"] * 15
        score += analysis["creditor_complaints"] * 10
        score += analysis["transaction_disputes"] * 20
        score += analysis["removal_motions"] * 25
        
        # Отрицательные факторы (снижают конфликт)
        # Если жалобы отклонены = АУ действует законно
        score -= analysis["complaints_denied"] * 5
        
        return min(100, max(0, score))
    
    def _interpret_conflict(self, conflict_score: int, analysis: dict) -> str:
        """
        Интерпретация уровня конфликта
        
        Логика:
        - Высокий конфликт (60+) = АУ работает честно, должник сопротивляется
        - Средний конфликт (30-60) = Есть споры, но не критично
        - Низкий конфликт (<30) = Либо всё гладко, либо сговор
        """
        
        if conflict_score >= 60:
            return (
                "✅ ВЫСОКИЙ КОНФЛИКТ - Хороший знак! "
                "Управляющий активно продаёт имущество, должник сопротивляется. "
                "Это указывает на честную работу АУ."
            )
        elif conflict_score >= 30:
            return (
                "⚠️ УМЕРЕННЫЙ КОНФЛИКТ - Есть споры, но они в пределах нормы. "
                "Требуется детальный анализ."
            )
        else:
            # Низкий конфликт - неоднозначно
            if analysis["debtor_complaints"] == 0 and analysis["total_documents"] > 10:
                return (
                    "🚩 ПОДОЗРИТЕЛЬНО ТИХО - Должник не жалуется при большом "
                    "количестве действий АУ. Возможен сговор."
                )
            else:
                return (
                    "🤷 НИЗКАЯ АКТИВНОСТЬ - Мало данных для оценки конфликта. "
                    "Либо дело свежее, либо нет спорных моментов."
                )
    
    async def _save_conflict_analysis(
        self,
        manager_inn: str,
        case_number: str,
        analysis: dict
    ):
        """
        Сохранить результаты анализа в БД
        
        Создаёт запись в таблице manager_conflicts
        """
        
        await self.db.execute("""
            INSERT INTO manager_conflicts (
                manager_inn,
                case_number,
                conflict_score,
                trust_signal,
                details,
                analyzed_at
            ) VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (manager_inn, case_number) DO UPDATE SET
                conflict_score = EXCLUDED.conflict_score,
                trust_signal = EXCLUDED.trust_signal,
                details = EXCLUDED.details,
                analyzed_at = NOW()
        """,
            manager_inn,
            case_number,
            analysis["conflict_score"],
            analysis["trust_signal"],
            analysis["details"]
        )
    
    async def get_manager_conflict_history(
        self,
        manager_inn: str,
        limit: int = 10
    ) -> List[dict]:
        """
        История конфликтов управляющего
        
        Полезно для оценки паттерна поведения:
        - Всегда много конфликтов = системно честный
        - Всегда тихо = возможно, работает "по сговору"
        
        Args:
            manager_inn: ИНН управляющего
            limit: Максимум дел
            
        Returns:
            История анализов конфликтов
        """
        
        history = await self.db.fetch("""
            SELECT * FROM manager_conflicts
            WHERE manager_inn = $1
            ORDER BY analyzed_at DESC
            LIMIT $2
        """, manager_inn, limit)
        
        return [dict(h) for h in history]
    
    async def calculate_manager_trust_bonus(self, manager_inn: str) -> int:
        """
        Расчёт бонуса к trust_score на основе конфликтов
        
        Логика:
        - Если в 70%+ дел высокий конфликт = +15 к trust_score
        - Если в 70%+ дел низкий конфликт = -10 к trust_score
        
        Args:
            manager_inn: ИНН управляющего
            
        Returns:
            bonus [-10, +15]
        """
        
        history = await self.get_manager_conflict_history(manager_inn, limit=20)
        
        if not history:
            return 0
        
        high_conflict_count = sum(
            1 for h in history if h["conflict_score"] >= 60
        )
        low_conflict_count = sum(
            1 for h in history if h["conflict_score"] < 30
        )
        
        total = len(history)
        
        high_conflict_ratio = high_conflict_count / total
        low_conflict_ratio = low_conflict_count / total
        
        if high_conflict_ratio >= 0.7:
            return 15  # Бонус: Системно честный управляющий
        elif low_conflict_ratio >= 0.7:
            return -10  # Штраф: Подозрительно тихая работа
        else:
            return 0  # Нейтрально
    
    async def enrich_lot_with_conflict_data(self, lot_id: int) -> dict:
        """
        Обогатить лот данными о конфликте
        
        Args:
            lot_id: ID лота
            
        Returns:
            Лот + conflict_analysis
        """
        
        lot = await self.db.fetchrow("""
            SELECT 
                l.*,
                m.inn as manager_inn
            FROM lots l
            LEFT JOIN managers m ON l.manager_inn = m.inn
            WHERE l.id = $1
        """, lot_id)
        
        if not lot:
            raise ValueError(f"Лот {lot_id} не найден")
        
        lot_dict = dict(lot)
        
        # Анализ конфликта (если есть номер дела)
        if lot_dict.get("bankruptcy_case_number"):
            conflict_analysis = await self.analyze_bankruptcy_case(
                case_number=lot_dict["bankruptcy_case_number"],
                manager_inn=lot_dict.get("manager_inn")
            )
            lot_dict["conflict_analysis"] = conflict_analysis
        else:
            lot_dict["conflict_analysis"] = None
        
        return lot_dict
