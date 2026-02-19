"""
DealScorer — скоринг лотов банкротных торгов.

deal_score = investment_score - (fraud_score * 0.6)

>= 80 → 🔥 HOT DEAL
>= 60 → ✅ GOOD DEAL
>= 40 → ⚠️ REVIEW
<  40 → ❌ SKIP
"""

from typing import Optional


class DealScorer:

    # Веса антифрод-флагов
    FRAUD_WEIGHTS = {
        "МассРуковод": 15,
        "МассУчред": 15,
        "ДисквЛицо": 25,
        "ДисквЛица": 25,
        "Санкции": 30,
        "СанкцУчр": 30,
        "НелегалФин": 20,
        "ЕФРСБ": 25,
        "НедобПост": 15,
    }

    def calculate(self, lot: dict, antifraud_flags: Optional[list] = None) -> dict:
        """
        Считает deal_score для лота.

        lot dict ожидаемые ключи:
            location_zone    — 'GARDEN_RING', 'TTK', или None
            start_price      — стартовая цена торгов (float)
            rosreestr_value  — кадастровая стоимость (float | None)
            description      — описание лота (str)

        antifraud_flags — список флагов из checko_client.get_antifraud_flags()

        Возвращает dict:
            deal_score, investment_score, fraud_score, breakdown
        """
        investment_score = self._investment_score(lot)
        fraud_score = self._fraud_score(antifraud_flags or [])
        deal_score = max(0.0, investment_score - fraud_score * 0.6)

        label = self._label(deal_score)

        return {
            "deal_score": round(deal_score, 1),
            "investment_score": investment_score,
            "fraud_score": fraud_score,
            "label": label,
            "breakdown": {
                "geography": self._geo_score(lot.get("location_zone")),
                "discount": self._discount_score(lot.get("start_price"), lot.get("rosreestr_value")),
                "liquidity": self._liquidity_score(lot.get("description", "")),
                "timing": 5,
                "fraud_flags": antifraud_flags or [],
            },
        }

    # ------------------------------------------------------------------
    # investment_score
    # ------------------------------------------------------------------

    def _investment_score(self, lot: dict) -> float:
        geo = self._geo_score(lot.get("location_zone"))
        discount = self._discount_score(lot.get("start_price"), lot.get("rosreestr_value"))
        liquidity = self._liquidity_score(lot.get("description", ""))
        timing = 5
        return min(100.0, geo + discount + liquidity + timing)

    def _geo_score(self, zone: Optional[str]) -> float:
        return {"GARDEN_RING": 40.0, "TTK": 25.0}.get(zone or "", 10.0)

    def _discount_score(self, start_price: Optional[float], rosreestr_value: Optional[float]) -> float:
        if not rosreestr_value or not start_price:
            return 0.0
        if rosreestr_value <= 0 or start_price >= rosreestr_value:
            return 0.0
        discount_pct = (rosreestr_value - start_price) / rosreestr_value * 100
        return min(40.0, discount_pct * 0.8)

    def _liquidity_score(self, description: str) -> float:
        desc = description.lower()
        if "мкд" in desc or "многоквартирн" in desc:
            return 18.0
        if "здание" in desc:
            return 20.0
        return 5.0

    # ------------------------------------------------------------------
    # fraud_score
    # ------------------------------------------------------------------

    def _fraud_score(self, flags: list) -> float:
        score = sum(self.FRAUD_WEIGHTS.get(f, 0) for f in flags)
        return min(100.0, float(score))

    # ------------------------------------------------------------------
    # label
    # ------------------------------------------------------------------

    def _label(self, score: float) -> str:
        if score >= 80:
            return "HOT"
        if score >= 60:
            return "GOOD"
        if score >= 40:
            return "REVIEW"
        return "SKIP"
