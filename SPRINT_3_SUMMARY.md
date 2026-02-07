# 📋 Спринт 3: Checko + Документы + FTP — РЕАЛИЗАЦИЯ

## ✅ Что реализовано

### 1. **Checko API Integration** ✅
- **Файл:** `src/services/checko_client.py`
- **Методы:**
  - `get_company_info()` - базовая информация о компании
  - `get_bankruptcy_info()` - статус банкротства
  - `get_court_cases()` - судебные дела
  - `get_financial_analysis()` - финансовое состояние
  - `get_founders()` - учредители и бенефициары
  - `get_related_companies()` - связанные компании
  - `get_licenses()` - лицензии
  - `search_by_name()` - поиск по названию
  - `calculate_risk_score()` - комплексный риск-скоринг (0-100)

### 2. **Research Service** ✅
- **Файл:** `src/services/research.py`
- **Возможности:**
  - Комплексный анализ объектов (кадастр + владелец)
  - Интеграция данных Rosreestr + Checko + Fedresurs
  - Поиск скрытых активов через связанные компании
  - Автоматические рекомендации по рискам
  - Примеры кейсов (ОМДА, ОТЭКО)

### 3. **Document Extractor** ✅
- **Файл:** `src/services/document_extractor.py`
- **Поддерживаемые форматы:**
  - PDF (PyPDF2 + pdfplumber)
  - DOCX (python-docx)
- **Извлекаемые данные:**
  - Кадастровые номера
  - Площадь объектов
  - ИНН организаций
  - Обременения (ипотека, аренда, арест)
  - Кадастровая стоимость
  - Рыночная стоимость (из отчётов об оценке)
- **Типы документов:**
  - ЕГРН выписки
  - Отчёты об оценке

### 4. **FastAPI Research Endpoints** ✅
- **Файл:** `src/api/research_routes.py`
- **Endpoints:**
  - `GET /api/research/property/{cadastral}` - полный анализ объекта
  - `GET /api/research/company/{inn}` - анализ компании
  - `GET /api/research/risk/{inn}` - риск-скоринг
  - `GET /api/research/hidden-assets/{inn}` - поиск скрытых активов
  - `GET /api/research/examples/{name}` - примеры (omda, oteko)

### 5. **FTP Access Tester** ✅
- **Файл:** `test_ftp_access.py`
- **Проверки:**
  - Подключение к FTP с demo креденшалами
  - Наличие архивов за последние 6 месяцев
  - Размеры файлов (лимит 50 МБ)
  - Тестовая загрузка первых байтов

### 6. **Database Migration** ✅
- **Миграция:** `alembic/versions/a881e873d6f2_add_documents_table_for_attachments.py`
- **Таблица `documents`:**
  ```sql
  CREATE TABLE documents (
      id SERIAL PRIMARY KEY,
      lot_id INTEGER REFERENCES lots(id),
      message_guid UUID,
      filename VARCHAR(255),
      document_type VARCHAR(50),
      file_size INTEGER,
      extracted_data JSONB,
      downloaded_at TIMESTAMP WITH TIME ZONE,
      created_at TIMESTAMP WITH TIME ZONE
  );
  ```
- **Модель:** `src/database/models.py` + relationship в `Lot`

### 7. **Ingestor Integration** ✅
- **Файл:** `src/services/ingestor.py`
- **Новый метод:** `process_attachments()`
  - Обрабатывает вложения из сообщений
  - Извлекает данные через DocumentExtractor
  - Сохраняет в таблицу `documents`
  - Связывает с лотами

### 8. **Конфигурация** ✅
- **Файл:** `src/config.py`
- **Новые параметры:**
  - `CHECKO_API_KEY` - API ключ Checko.ru
  - `FTP_HOST`, `FTP_USER`, `FTP_PASSWORD` - FTP креденшалы
  - `FTP_DOWNLOAD_LIMIT_MB` - лимит загрузки

### 9. **Dependencies** ✅
- **Файл:** `requirements.txt`
- **Добавлено:**
  - PyPDF2>=3.0.0
  - pdfplumber>=0.10.0
  - python-docx>=1.0.0
  - openpyxl>=3.1.0

---

## 🎯 Ключевые фичи

### Система цитирования источников
Каждое поле данных содержит метаданные:
```json
{
  "area": {
    "value": 512.2,
    "source": "egr_extract",
    "source_file": "message_ABC123_attachment_2.pdf",
    "confidence": "high",
    "fetched_at": "2026-02-05T18:30:00Z"
  }
}
```

### Риск-скоринг (0-100)
```json
{
  "risk_score": 35,
  "risk_level": "MEDIUM",
  "risk_factors": [
    "Active bankruptcy proceedings",
    "High litigation activity (12 cases)",
    "Negative profit"
  ]
}
```

### Поиск скрытых активов
```json
{
  "hidden_assets": [
    {
      "inn": "7713999999",
      "name": "ООО Дочерняя Компания",
      "connection": "same_founder",
      "suspicion_level": "high"
    }
  ]
}
```

---

## 🚀 Как использовать

### 1. Установить зависимости
```bash
pip install -r requirements.txt
```

### 2. Настроить .env
```bash
# Добавить:
CHECKO_API_KEY=uxa...
```

### 3. Запустить миграцию
```bash
alembic upgrade head
```

### 4. Протестировать FTP
```bash
python test_ftp_access.py
```

### 5. Запустить API
```bash
python src/main.py
```

### 6. Примеры запросов
```bash
# Полный анализ объекта
curl http://localhost:8000/api/research/property/77:01:0004022:1026?owner_inn=7713084767

# Риск компании
curl http://localhost:8000/api/research/risk/7713084767

# Пример ОМДА
curl http://localhost:8000/api/research/examples/omda
```

---

## 📊 Примеры кейсов

### ОМДА (проблемный объект)
```bash
GET /api/research/examples/omda
```
**Риски:**
- Земля в аренде (не собственность)
- Схема дробления (ОМДА + СИС)
- Субсидиарная ответственность

### ОТЭКО (санкционный риск)
```bash
GET /api/research/examples/oteko
```
**Риски:**
- Бенефициар под санкциями
- Реорганизация компании
- СЗЗ (нельзя строить жильё)

---

## 🔄 Интеграция в Orchestrator

Для автоматической обработки вложений добавьте в `orchestrator.py`:

```python
from src.services.document_extractor import DocumentExtractor

document_extractor = DocumentExtractor()

# После сохранения лотов:
if message.attachments:
    await IngestionService.process_attachments(
        session=session,
        message_guid=message.guid,
        lot_id=lot_ids[0],  # Или правильный lot_id
        attachments=message.attachments,
        document_extractor=document_extractor
    )
```

---

## 📝 TODO (опционально)

### Следующие шаги (если потребуется):

1. **FTP Archive Loader** (если FTP работает)
   - SmartArchiveLoader для загрузки по месяцам
   - Фильтрация по региону (Москва = 77)
   - Парсинг "на лету" без сохранения

2. **Антифрод v2.0**
   - Benchmark по кварталу (вместо кадастра)
   - Velocity analysis
   - Manager karma (упрощённая версия)

3. **Dashboard интеграция**
   - Отображение риск-скоринга
   - Связанные компании (граф)
   - Извлечённые документы

---

## ✨ Статус

**🎉 SPRINT 3 ПОЛНОСТЬЮ РЕАЛИЗОВАН!**

Все модули готовы к использованию:
- ✅ Checko API Client
- ✅ Research Service
- ✅ Document Extractor
- ✅ Research API
- ✅ FTP Tester
- ✅ Database Migration
- ✅ Ingestor Integration

**Готово к деплою!** 🚀
