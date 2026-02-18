#!/usr/bin/env python3
"""
Загрузка cadastral данных из Arrow в PostgreSQL
"""
import pyarrow as pa
import pyarrow.ipc as ipc
import psycopg2
import os

# Читаем Arrow файл
print("📖 Читаю Arrow файл...")
with ipc.open_file('/app/data/cadastral/data-00000-of-00001.arrow') as reader:
    table = reader.read_all()

print(f"✅ Прочитано {len(table):,} записей")
print(f"📋 Колонок: {len(table.schema)}")

# Показываем схему
print("\n🔍 Схема данных:")
for field in table.schema:
    print(f"  {field.name}: {field.type}")

# Конвертируем в pandas
df = table.to_pandas()

print(f"\n📊 Первые 2 записи:")
print(df.head(2))

print(f"\n💾 Создаю таблицу cadastral_index...")

# Подключение к БД
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'db'),
    port=os.getenv('DB_PORT', '5432'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', 'quser'),
    database=os.getenv('DB_NAME', 'fedresurs_db')
)
cur = conn.cursor()

# Создаем таблицу (упрощенная схема)
cur.execute("""
    CREATE TABLE IF NOT EXISTS cadastral_index (
        id SERIAL PRIMARY KEY,
        cadastral_number VARCHAR(50) UNIQUE,
        address TEXT,
        area DECIMAL(15, 2),
        cadastral_value DECIMAL(20, 2),
        purpose VARCHAR(200),
        rights TEXT,
        latitude DECIMAL(10, 7),
        longitude DECIMAL(10, 7),
        data_source VARCHAR(50) DEFAULT 'huggingface',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

print("✅ Таблица создана")

print(f"\n📥 Загружаю {len(df)} записей в БД (это может занять время)...")

# Загружаем данные batch-ами
batch_size = 1000
inserted = 0

for i in range(0, len(df), batch_size):
    batch = df.iloc[i:i+batch_size]

    for _, row in batch.iterrows():
        try:
            # Извлекаем нужные поля (адаптируем к реальной схеме)
            cadastral_number = row.get('cadastral_number') or row.get('cn') or row.get('id')
            address = row.get('address') or row.get('addr') or ''
            area = row.get('area') or row.get('square') or 0
            cadastral_value = row.get('cadastral_cost') or row.get('value') or 0
            purpose = row.get('utilization') or row.get('purpose') or ''

            cur.execute("""
                INSERT INTO cadastral_index
                (cadastral_number, address, area, cadastral_value, purpose)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (cadastral_number) DO NOTHING
            """, (cadastral_number, address, area, cadastral_value, purpose))

            inserted += 1
        except Exception as e:
            print(f"⚠️ Ошибка в записи {i}: {e}")
            continue

    conn.commit()
    if (i // batch_size) % 10 == 0:
        print(f"  ... {inserted:,} записей загружено")

print(f"\n✅ Загрузка завершена: {inserted:,} записей")

# Проверка
cur.execute("SELECT COUNT(*) FROM cadastral_index")
count = cur.fetchone()[0]
print(f"📊 Записей в БД: {count:,}")

cur.close()
conn.close()
