import json
import logging
import os
import sys
from typing import Any, Dict, List
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
# Добавленный импорт
from dotenv import load_dotenv 

# --- Загрузка настроек ---
# Ищем файл .env.local в текущей папке
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env.local')
load_dotenv(env_path)

# Ключи теперь подтянутся из .env.local
RETAILCRM_URL = os.getenv("RETAILCRM_URL", "https://dorexclub.retailcrm.ru/api/v5")
RETAILCRM_KEY = os.getenv("RETAILCRM_KEY")
RETAILCRM_SITE = os.getenv("RETAILCRM_SITE", "dorex-club") 
ORDERS_FILE = os.getenv("ORDERS_FILE", "mock_orders.json")

MAX_WORKERS = int(os.getenv("MAX_WORKERS", 5))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crm_import.log", encoding="utf-8")
    ],
)
logger = logging.getLogger(__name__)

def check_order_exists(external_id: str) -> bool:
    """Проверка дубликата по externalId"""
    if not external_id: return False
    url = f"{RETAILCRM_URL}/orders"
    params = {"apiKey": RETAILCRM_KEY, "filter[externalIds][]": [external_id]}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        return data.get("success") and data.get("orders")
    except Exception:
        return False

def transform_order(order: Dict[str, Any]) -> Dict[str, Any]:
    """Приведение данных к формату RetailCRM v5 (Тип заказа: main)"""
    return {
        "externalId": str(order.get("externalId", "")),
        "orderType": "main",
        "orderMethod": order.get("orderMethod", "shopping-cart"),
        "status": order.get("status", "new"),
        "firstName": order.get("firstName"),
        "lastName": order.get("lastName"),
        "email": order.get("email"),
        "phone": str(order.get("phone", "")),
        "items": order.get("items", []),
        "delivery": order.get("delivery", {})
    }

def send_order(order: Dict[str, Any]) -> bool:
    ext_id = order.get("externalId")
    if not ext_id:
        logger.error("❌ Пропуск: у заказа нет externalId")
        return False

    if check_order_exists(ext_id):
        logger.info("⏭️ %s уже есть в системе", ext_id)
        return True

    url = f"{RETAILCRM_URL}/orders/create"
    params = {"apiKey": RETAILCRM_KEY, "site": RETAILCRM_SITE}
    
    payload = {"order": json.dumps(transform_order(order), ensure_ascii=False)}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, params=params, data=payload, headers=headers, timeout=15)
            result = response.json()

            if result.get("success"):
                logger.info("✅ %s успешно создан", ext_id)
                return True
            
            if response.status_code == 400:
                errors = result.get("errors", result)
                logger.error("❌ Ошибка валидации %s: %s", ext_id, errors)
                return False 

            logger.warning("⚠️ Попытка %s (%s): %s", attempt, ext_id, result)
        except Exception as e:
            logger.warning("⚠️ Ошибка сети на попытке %s: %s", attempt, e)
        
        time.sleep(1)

    logger.error("❌ Не удалось отправить %s после %s попыток", ext_id, MAX_RETRIES)
    return False

def load_orders(filename: str) -> List[Dict[str, Any]]:
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("orders", [])

def main():
    if not RETAILCRM_KEY:
        logger.error("❌ RETAILCRM_KEY не найден в .env.local!")
        return

    if not os.path.exists(ORDERS_FILE):
        logger.error("Файл %s не найден!", ORDERS_FILE)
        return

    try:
        orders = load_orders(ORDERS_FILE)
        logger.info("🚀 Начинаем импорт %s заказов", len(orders))
    except Exception as e:
        logger.error("Критическая ошибка загрузки JSON: %s", e)
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(send_order, o) for o in orders]
        results = [f.result() for f in as_completed(futures)]

    logger.info("🎯 Итог: %s успешно, %s провалено", sum(results), len(results) - sum(results))

if __name__ == "__main__":
    main()