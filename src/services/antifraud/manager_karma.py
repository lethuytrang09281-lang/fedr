# Файл: /home/quser/SOFT/FEDR/fedr/src/services/antifraud/manager_karma.py

"""
Manager Karma Service - оценка надёжности арбитражных управляющих
"""

from typing import Optional, List
import asyncpg
from .models import ManagerProfile, ManagerKarmaResult, RiskLevel
import re


class ManagerKarmaService:
    """Сервис оценки кармы управляющих"""
    
    def __init__(
        self, 
        db_pool: asyncpg.Pool,
        parser_api_key: Optional[str] = None,
        checko_api_key: Optional[str] = None
    ):
        self.db = db_pool
        self.parser_api_key = parser_api_key
        self.checko_api_key = checko_api_key
    
    async def get_manager(self, inn: str) -> Optional[ManagerProfile]:
        """Получить профиль управляющего по ИНН"""
        result = await self.db.fetchrow("""
            SELECT * FROM managers WHERE inn = $1
        """, inn)
        
        if result:
            return ManagerProfile(**dict(result))
        return None
    
    async def create_or_update_manager(
        self,
        name: str,
        inn: str,
        email: Optional[str] = None
    ) -> ManagerProfile:
        """Создать или обновить профиль управляющего"""
        
        # Проверить email
        email_is_disposable = self._is_disposable_email(email) if email else False
        
        # Upsert
        result = await self.db.fetchrow("""
            INSERT INTO managers (name, inn, email, email_is_disposable)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (inn) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                email_is_disposable = EXCLUDED.email_is_disposable,
                updated_at = NOW()
            RETURNING *
        """, name, inn, email, email_is_disposable)
        
        return ManagerProfile(**dict(result))
    
    async def calculate_karma(self, inn: str) -> ManagerKarmaResult:
        """
        Рассчитать карму управляющего
        
        Returns:
            ManagerKarmaResult с trust_score и факторами
        """
        manager = await self.get_manager(inn)
        
        if not manager:
            # Управляющий неизвестен
            return ManagerKarmaResult(
                manager_inn=inn,
                manager_name="Unknown",
                trust_score=50,
                risk_level=RiskLevel.UNKNOWN,
                risk_score=0,
                factors=["Управляющий не найден в базе"],
                success_rate=0.0,
                years_of_experience=0,
                arbitr_cases_count=0,
                has_red_flags=False
            )
        
        # Расчёт кармы
        base_score = 50
        bonuses = []
        penalties = []
        
        # --- БОНУСЫ ---
        
        # Опыт
        if manager.years_of_experience >= 10:
            base_score += 20
            bonuses.append(f"+20: опыт {manager.years_of_experience} лет")
        elif manager.years_of_experience >= 5:
            base_score += 15
            bonuses.append(f"+15: опыт {manager.years_of_experience} лет")
        elif manager.years_of_experience >= 3:
            base_score += 10
            bonuses.append(f"+10: опыт {manager.years_of_experience} лет")
        elif manager.years_of_experience >= 1:
            base_score += 5
            bonuses.append(f"+5: опыт {manager.years_of_experience} лет")
        
        # Success rate
        success_rate = manager.success_rate
        if success_rate >= 90:
            base_score += 20
            bonuses.append(f"+20: success rate {success_rate:.1f}%")
        elif success_rate >= 80:
            base_score += 15
            bonuses.append(f"+15: success rate {success_rate:.1f}%")
        elif success_rate >= 70:
            base_score += 10
            bonuses.append(f"+10: success rate {success_rate:.1f}%")
        
        # Количество торгов
        if manager.total_auctions >= 100:
            base_score += 5
            bonuses.append(f"+5: {manager.total_auctions} торгов")
        elif manager.total_auctions >= 50:
            base_score += 3
            bonuses.append(f"+3: {manager.total_auctions} торгов")
        
        # --- ШТРАФЫ ---
        
        has_red_flags = False
        
        # Судимость
        if manager.has_criminal_record:
            base_score -= 30
            penalties.append("-30: судимость")
            has_red_flags = True
        
        # Проигранные дела
        if manager.arbitr_lost_cases > 5:
            base_score -= 25
            penalties.append(f"-25: {manager.arbitr_lost_cases} проигранных дел")
            has_red_flags = True
        
        # Одноразовая почта
        if manager.email_is_disposable:
            base_score -= 15
            penalties.append("-15: одноразовая почта")
            has_red_flags = True
        
        # Много дел в арбитраже
        if manager.arbitr_cases_count > 10:
            base_score -= 10
            penalties.append(f"-10: {manager.arbitr_cases_count} дел в арбитраже")
        
        # Низкий success rate
        if success_rate < 50 and manager.total_auctions > 5:
            base_score -= 10
            penalties.append(f"-10: низкий success rate ({success_rate:.1f}%)")
        
        # Нет опыта
        if manager.years_of_experience < 1:
            base_score -= 5
            penalties.append("-5: менее года опыта")
        
        # Ограничить диапазон [0, 100]
        trust_score = max(0, min(100, base_score))
        
        # Определить risk_level (инверсия trust_score)
        if trust_score >= 80:
            risk_level = RiskLevel.LOW
            risk_score = 0
        elif trust_score >= 60:
            risk_level = RiskLevel.MEDIUM
            risk_score = 10
        elif trust_score >= 40:
            risk_level = RiskLevel.HIGH
            risk_score = 25
        else:
            risk_level = RiskLevel.CRITICAL
            risk_score = 40
        
        # Собрать факторы
        factors = bonuses + penalties
        
        return ManagerKarmaResult(
            manager_inn=inn,
            manager_name=manager.name,
            trust_score=trust_score,
            risk_level=risk_level,
            risk_score=risk_score,
            factors=factors,
            success_rate=success_rate,
            years_of_experience=manager.years_of_experience,
            arbitr_cases_count=manager.arbitr_cases_count,
            has_red_flags=has_red_flags
        )
    
    async def enrich_from_parser_api(self, inn: str) -> bool:
        """
        Обогатить данные управляющего из parser-api.com (КАД.АРБИТР)
        
        Returns:
            True если данные обновлены
        """
        if not self.parser_api_key:
            return False
        
        # TODO: Реализовать запрос к parser-api arbitr_api
        return True
    
    async def enrich_from_checko(self, inn: str) -> bool:
        """
        Обогатить данные из Checko API
        
        Returns:
            True если данные обновлены
        """
        if not self.checko_api_key:
            return False
        
        # TODO: Реализовать запрос к Checko API
        return True
    
    @staticmethod
    def _is_disposable_email(email: str) -> bool:
        """Проверка на одноразовую почту"""
        disposable_domains = [
            "tempmail.com", "10minutemail.com", "guerrillamail.com",
            "mailinator.com", "yopmail.com", "throwaway.email",
            "temp-mail.org", "fakeinbox.com"
        ]
        
        if not email or "@" not in email:
            return False
        
        domain = email.split("@")[1].lower()
        return domain in disposable_domains
