import re
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Any, Optional

@dataclass
class YaraRule:
    name: str
    meta: Dict[str, str]
    strings: Dict[str, str]
    condition: Callable[[str, Dict[str, bool]], bool]
    score: int = 0
    _compiled_patterns: Dict[str, re.Pattern] = field(init=False, default_factory=dict)

    def __post_init__(self):
        for key, pattern in self.strings.items():
            try:
                self._compiled_patterns[key] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                print(f"Error compiling regex {pattern}: {e}")

class SemanticFilter:
    def __init__(self):
        self.rules = self._load_rules()
        self.target_classifier_codes = {'0108001', '0402006', '0101014', '0101016', '0103'}

    def _load_rules(self) -> List[YaraRule]:
        return [
            YaraRule(
                name="LAND_MKD",
                meta={"description": "🏢 Участок под МКД", "severity": "HIGH"},
                score=100,
                strings={
                    "$mkd": r"многоквартирн\w+|мкд|высотная застройка|среднеэтажная|жилая застройка",
                    "$grad_plan": r"гпзу|градостроительный план",
                    "$permit": r"разрешение на строительство|рнс",
                    "$zone": r"\bж-[2-8]\b",
                    "$lease": r"право аренды|ппа|переуступка"
                },
                condition=lambda text, matches: (
                    (matches["$mkd"] or matches["$zone"]) and 
                    not (re.search(r"(?i)снт|днп|садоводство|огородничество|дачн\w+", text)) and
                    not (re.search(r"(?i)сельскохозяйств\w+|с/х|пашня", text)) and 
                    not (re.search(r"(?i)ижс|индивидуальн\w+ жилы\w+|лпх", text))
                )
            ),
            YaraRule(
                name="UNFINISHED_RESIDENTIAL",
                meta={"description": "🏗 Недострой (ЖК)", "severity": "CRITICAL"},
                score=90,
                strings={
                    "$unfinished": r"незавершенн\w+ строительств\w+|онс",
                    "$res_complex": r"жилой комплекс|жк\s+[\"«]",
                    "$shareholders": r"дольщик|дду|фонд защиты прав"
                },
                condition=lambda text, matches: (
                    matches["$unfinished"] and 
                    (matches["$res_complex"] or matches["$shareholders"])
                )
            ),
            YaraRule(
                name="COMMERCIAL_LAND",
                meta={"description": "🏪 Земля под ТЦ/Коммерцию", "severity": "MEDIUM"},
                score=50,
                strings={
                    "$commercial": r"торговый центр|магазин|деловое управление|общественное питание|гостиница",
                    "$zone_com": r"\bо-[1-5]\b|\bц-[1-5]\b"
                },
                condition=lambda text, matches: (
                    matches["$commercial"] or matches["$zone_com"]
                )
            )
        ]

    def analyze(self, lot) -> dict:
        report = {
            "is_interesting": False,
            "total_score": 0,
            "matched_rules": [],
            "tags": []
        }
        description = getattr(lot, 'description', '') or ''
        if not description:
            return report

        classifier_code = getattr(lot, 'classifier_code', None)
        if classifier_code and classifier_code not in self.target_classifier_codes:
             return report

        for rule in self.rules:
            matches = {}
            for key, pattern in rule._compiled_patterns.items():
                matches[key] = bool(pattern.search(description))
            
            if rule.condition(description, matches):
                report["matched_rules"].append(rule.name)
                report["total_score"] += rule.score
                report["tags"].append(rule.meta["description"])

        if report["total_score"] > 0:
            report["is_interesting"] = True
        
        return report