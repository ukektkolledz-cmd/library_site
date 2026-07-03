import pandas as pd
import sqlite3

# --- НАСТРОЙКИ (измените здесь свои пути и имена) ---
excel_file_path = 'C:\\libraryy\\libra\\Список студентов на 2025-2026 год.xlsx'   # Путь к Excel-файлу
db_file_path = 'C:\\libraryy\\libra\\db.sqlite3'   # Путь к файлу SQLite
table_name = 'students'                 # Имя таблицы для импорта
# ----------------------------------------------------

# 1. Загружаем данные из Excel в DataFrame
try:
    df = pd.read_excel(excel_file_path, engine='openpyxl')
    print("Данные из Excel успешно загружены.")
except FileNotFoundError:
    print(f"Ошибка: Файл Excel не найден по пути {excel_file_path}")
    exit()

# 2. (Опционально) Приводим названия столбцов к формату SQLite
#    Заменяем пробелы на подчеркивания, приводим к нижнему регистру
df.columns = [c.lower().replace(' ', '_') for c in df.columns]
print("Названия столбцов нормализованы.")

# 3. Подключаемся к базе данных SQLite
conn = sqlite3.connect(db_file_path)
print(f"Подключение к БД {db_file_path} установлено.")

# 4. Импортируем DataFrame в таблицу SQLite
#    if_exists='replace' - заменит таблицу, если она существует
#    if_exists='append'  - добавит строки к существующей таблице
df.to_sql(table_name, conn, if_exists='replace', index=False)
print(f"Данные успешно импортированы в таблицу '{table_name}'.")

# 5. Закрываем соединение с БД
conn.close()
print("Работа завершена.")