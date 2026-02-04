import re
from dataclasses import dataclass

@dataclass
class Rule:
    name: str
    pattern: re.Pattern
    score: int

class SemanticFilter:
    def __init__(self):
        self.rules = [
            Rule("LAND_MKD", re.compile(r"многоквартирн\w+|мкд|высотная", re.I), 100),
            Rule("COMMERCIAL", re.compile(r"торговый центр|магазин", re.I), 50),
            Rule("BAD", re.compile(r"снт|огородничество", re.I), -100)
        ]

    def analyze(self, text: str) -> dict:
        score = 0
        tags = []
        for rule in self.rules:
            if rule.pattern.search(text):
                score += rule.score
                if rule.score > 0: tags.append(rule.name)
        return {"score": score, "tags": tags, "is_interesting": score > 0}