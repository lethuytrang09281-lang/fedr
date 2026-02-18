#!/usr/bin/env python3
"""
Загрузка cadastral данных из HuggingFace Dataset в PostgreSQL
"""
from datasets import load_from_disk
import psycopg2
import os

print("📖 Загружаю dataset...")
ds = load_from_disk('/app/data/cadastral')

print(f"✅ Загружено {len(ds):,} кварталов")

# Подсчитываем общее количество записей
total_records = sum(item['total'] for item in ds)
print(f"📊 Всего кадастровых записей: {total_records:,}")

# Подключение к БД
print("\n🔌 Подключаюсь к БД...")
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'db'),
    port=os.getenv('DB_PORT', '5432'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', 'quser'),
    database=os.getenv('DB_NAME', 'fedresurs_db')
)
cur = conn.cursor()

# Создаем таблицу
print("🗄️ Создаю таблицу cadastral_index...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS cadastral_index (
        id SERIAL PRIMARY KEY,
        cadastral_number VARCHAR(50) UNIQUE,
        cadastral_quarter VARCHAR(50),
        address TEXT,
        layer_name VARCHAR(50),
        pkk_id VARCHAR(20),
        data_source VARCHAR(50) DEFAULT 'huggingface',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_cadastral_number ON cadastral_index(cadastral_number);
    CREATE INDEX IF NOT EXISTS idx_cadastral_quarter ON cadastral_index(cadastral_quarter);
""")
conn.commit()
print("✅ Таблица создана")

print(f"\n📥 Загружаю данные в БД...")
inserted = 0
skipped = 0
batch_size = 1000
values_batch = []

for quarter_idx, quarter_data in enumerate(ds):
    quarter = quarter_data['quarter']
    items = quarter_data['items']

    for item in items:
        cad_num = item.get('cad_num', '')
        address = item.get('address', '')
        layer_name = item.get('layer_name', '')
        pkk_id = item.get('id', '')

        if not cad_num:
            skipped += 1
            continue

        values_batch.append((cad_num, quarter, address, layer_name, pkk_id))

        # Batch insert
        if len(values_batch) >= batch_size:
            try:
                cur.executemany("""
                    INSERT INTO cadastral_index
                    (cadastral_number, cadastral_quarter, address, layer_name, pkk_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (cadastral_number) DO NOTHING
                """, values_batch)
                conn.commit()
                inserted += len(values_batch)
                values_batch = []

                if inserted % 10000 == 0:
                    print(f"  ... {inserted:,} записей загружено")
            except Exception as e:
                print(f"⚠️ Ошибка в batch: {e}")
                conn.rollback()
                values_batch = []

# Остаток
if values_batch:
    try:
        cur.executemany("""
            INSERT INTO cadastral_index
            (cadastral_number, cadastral_quarter, address, layer_name, pkk_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (cadastral_number) DO NOTHING
        """, values_batch)
        conn.commit()
        inserted += len(values_batch)
    except Exception as e:
        print(f"⚠️ Ошибка в последнем batch: {e}")
        conn.rollback()

print(f"\n✅ Загрузка завершена!")
print(f"   Вставлено: {inserted:,}")
print(f"   Пропущено: {skipped:,}")

# Проверка
cur.execute("SELECT COUNT(*) FROM cadastral_index")
count = cur.fetchone()[0]
print(f"\n📊 Всего записей в БД: {count:,}")

# Примеры
print(f"\n🔍 Примеры записей:")
cur.execute("SELECT cadastral_number, address FROM cadastral_index LIMIT 3")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1][:60]}...")

cur.close()
conn.close()
print("\n✅ Готово!")
