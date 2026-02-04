class AnomalyDetector:
    @staticmethod
    def check(text: str) -> dict:
        flags = []
        if "лично в руки" in text.lower(): flags.append("RESTRICTIVE")
        return {"is_suspicious": len(flags) > 0, "flags": flags}