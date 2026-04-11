import os
import requests
import json
from dotenv import load_dotenv

# 1. Загрузка настроек из .env.local
# Ищем файл в той же папке, где лежит скрипт
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env.local')
load_dotenv(env_path)

# Читаем переменные
RETAILCRM_URL = os.getenv("RETAILCRM_URL")
RETAILCRM_KEY = os.getenv("RETAILCRM_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_custom_field_value(custom_fields, code):
    """Извлекает значение кастомного поля (работает со списками и словарями)."""
    if not custom_fields:
        return None
    if isinstance(custom_fields, list):
        for field in custom_fields:
            if isinstance(field, dict) and field.get("code") == code:
                return field.get("value")
    elif isinstance(custom_fields, dict):
        return custom_fields.get(code)
    return None

def sync_all_data():
    # Проверка наличия ключей перед запуском
    if not all([RETAILCRM_URL, RETAILCRM_KEY, SUPABASE_URL, SUPABASE_KEY]):
        print("❌ Ошибка: Не все ключи найдены в .env.local")
        print(f"Путь к файлу: {env_path}")
        return

    print("🚀 Начинаю глубокую синхронизацию...")
    
    # 1. Запрос к RetailCRM
    try:
        rcrm_res = requests.get(
            f"{RETAILCRM_URL}/orders", 
            params={"apiKey": RETAILCRM_KEY, "limit": 50},
            timeout=15
        )
        rcrm_res.raise_for_status()
        orders = rcrm_res.json().get("orders", [])
    except Exception as e:
        print(f"❌ Ошибка RetailCRM: {e}")
        return

    if not orders:
        print("📭 Заказов не найдено.")
        return

    prepared_for_supabase = []

    for o in orders:
        # --- Сбор названий товаров и расчет суммы ---
        items = o.get("items", [])
        item_names = []
        calculated_total = 0
        
        for i in items:
            name = (i.get("productName") or 
                    i.get("name") or 
                    i.get("offer", {}).get("itemName") or 
                    i.get("offer", {}).get("name") or 
                    "Без названия")
            
            qty = i.get("quantity", 1)
            price = float(i.get("initialPrice") or 0)
            
            item_names.append(f"{name} (x{qty})")
            calculated_total += price * qty
        
        items_summary = ", ".join(item_names)

        # --- Формируем строку для Supabase ---
        row = {
            "id": o.get("id"),
            "external_id": str(o.get("externalId") or ""),
            "status": o.get("status"),
            "order_type": o.get("orderType"),
            "order_method": o.get("orderMethod"),
            "customer_name": f"{o.get('firstName', '')} {o.get('lastName', '')}".strip(),
            "customer_phone": o.get("phone"),
            "customer_email": o.get("email"),
            "delivery_city": o.get("delivery", {}).get("address", {}).get("city"),
            "delivery_address": o.get("delivery", {}).get("address", {}).get("text"),
            "total_sum": calculated_total,
            "utm_source": get_custom_field_value(o.get("customFields"), "utm_source"),
            "items_summary": items_summary[:1000], 
            "created_at": o.get("createdAt")
        }
        prepared_for_supabase.append(row)

    # 2. Отправка в Supabase
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-encoding"
    }

    try:
        sb_res = requests.post(
            f"{SUPABASE_URL}/rest/v1/orders",
            headers=headers,
            json=prepared_for_supabase,
            timeout=15
        )
        
        if sb_res.status_code in [200, 201, 204]:
            print(f"✅ Успешно синхронизировано {len(prepared_for_supabase)} заказов!")
        else:
            print(f"❌ Ошибка базы данных ({sb_res.status_code}): {sb_res.text}")
            
    except Exception as e:
        print(f"❌ Ошибка сети при отправке в Supabase: {e}")

if __name__ == "__main__":
    sync_all_data()