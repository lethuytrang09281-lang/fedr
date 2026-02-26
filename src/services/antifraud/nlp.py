# Файл: /home/quser/SOFT/FEDR/fedr/src/services/antifraud/nlp.py

"""
NLP Red Flag Detector - паттерны мошенничества в текстах
"""

from typing import List
import re


class NLPRedFlagDetector:
    """Детектор подозрительных паттернов в описании лотов"""
    
    def __init__(self):
        self.red_flags = [
            (r"срочно", "Срочная продажа (манипуляция вниманием)"),
            (r"уникальн\w+ предложение", "Завышенные обещания"),
            (r"гарантия выигрыша", "Признак сговора"),
            (r"прямая связь с АУ", "Коррупционный маркер"),
            (r"без осмотра", "Скрытие дефектов"),
            (r"звонить только в рабочее время", "Ограничение доступа к информации"),
            (r"[A-ZА-Я\s]{10,}", "Использование капслока (агрессивный маркетинг)"),
        ]
        
    async def detect_red_flags(self, description: str) -> List[str]:
        """
        Ищет подозрительные паттерны в тексте
        
        Args:
            description: Текст описания лота
            
        Returns:
            Список найденных флагов
        """
        if not description:
            return []
            
        found_flags = []
        for pattern, reason in self.red_flags:
            if re.search(pattern, description, re.IGNORECASE):
                found_flags.append(reason)
                
        return found_flags
