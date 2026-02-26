---
# FEDRESURS PRO — КОНТЕКСТ ДЛЯ АГЕНТА

## Проект
Система раннего обнаружения коммерческой недвижимости в банкротных процедурах Москвы.
Мониторинг ЕФРСБ на стадиях инвентаризации/оценки (за 1-2 года до торгов).
Цель: здания внутри Садового кольца, 1М-300М руб, максимальный дисконт.

## Инфраструктура
VPS: root@157.22.231.149  /root/fedr/
Docker: fedr-app-1 (FastAPI :8000), fedr-db-1 (PostgreSQL fedresurs_db)
GitHub: https://github.com/lethuytrang09281-lang/fedr (master)

## Структура
/root/fedr/src/main.py              — FastAPI точка входа
/root/fedr/src/orchestrator.py      — главный цикл 6ч
/root/fedr/src/database/models.py   — все модели SQLAlchemy (единственный источник)
/root/fedr/src/database/base.py     — engine, get_db_session
/root/fedr/src/services/            — fedresurs_search, enricher, checko, rosreestr, hunter/
/root/fedr/src/logic/scorer.py      — DealScorer
/root/fedr/src/bot/notifier.py      — Telegram
/root/fedr/Claude.md                — состояние проекта (читать первым)
/root/fedr/TASKS.md                 — бэклог задач (читать вторым)

## Текущие задачи
Читай /root/fedr/TASKS.md — там актуальная очередь.
Текущий приоритет: BUG-002..007 (починить перед новой разработкой)

## Правила
- Читай Claude.md и TASKS.md перед началом
- Один файл = одна задача, не трогай остальное
- Не переписывай работающий код
- После выполнения: git add -A && git commit -m "fix: TASK-XXX описание" && git push origin master
- Обнови статус задачи в TASKS.md → 🟢 готова

## Проверочные команды
docker logs -f fedr-app-1
docker exec fedr-app-1 python -c "from src.orchestrator import Orchestrator; print('OK')"
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "SELECT COUNT(*) FROM lots;"
curl -s "https://parser-api.com/stat/?key=ede50185e3ccc8589a5c6c6efebc14cc"
---