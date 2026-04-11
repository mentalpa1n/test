import asyncio
import httpx
import os
from dotenv import load_dotenv
from telegram import Bot

# Получаем путь к папке скрипта и загружаем .env.local
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env.local")
load_dotenv(env_path)

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RETAIL_KEY = os.getenv("RETAILCRM_KEY")
RETAIL_URL = os.getenv("RETAILCRM_URL")

CHECK_INTERVAL = 30
MIN_AMOUNT = 50000

# Переменная для отслеживания последнего обработанного заказа
last_processed_order_id = None

async def check_retail_orders(bot: Bot):
    global last_processed_order_id
    
    if not all([TELEGRAM_TOKEN, CHAT_ID, RETAIL_KEY, RETAIL_URL]):
        print("❌ Ошибка: Переменные из .env.local не загружены.")
        return

    # Формируем URL. Убираем лишние параметры сортировки, вызывающие 400 ошибку
    endpoint = f"{RETAIL_URL}/orders"
    params = {
        "apiKey": RETAIL_KEY,
        "limit": 50  # Берем последние 50 заказов
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(endpoint, params=params)
            
            # Если получили ошибку 400+, выводим тело ответа для диагностики
            if response.status_code != 200:
                print(f"⚠️ Ошибка API ({response.status_code}): {response.text}")
                return
                
            data = response.json()

        orders = data.get("orders", [])
        if not orders:
            return

        # Сортируем по ID (от старых к новым), чтобы правильно обновить last_processed_order_id
        orders.sort(key=lambda x: x['id'])

        for order in orders:
            order_id = order.get("id")
            total_sum = float(order.get("totalSumm", 0))
            order_number = order.get("number")

            # Пропускаем, если уже видели этот заказ
            if last_processed_order_id and order_id <= last_processed_order_id:
                continue

            # Если сумма больше порога — отправляем в TG
            if total_sum > MIN_AMOUNT:
                admin_base = RETAIL_URL.replace("/api/v5", "")
                message = (
                    f"🚀 **Крупный заказ!**\n\n"
                    f"Номер: `{order_number}`\n"
                    f"Сумма: **{total_sum} ₸**\n"
                    f"Клиент: {order.get('firstName', 'Не указано')}\n"
                    f"Ссылка: {admin_base}/orders/{order_id}/edit"
                )
                try:
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
                except Exception as tg_err:
                    print(f"❌ Ошибка отправки в Telegram: {tg_err}")

            # Обновляем метку последнего заказа
            if not last_processed_order_id or order_id > last_processed_order_id:
                last_processed_order_id = order_id

    except Exception as e:
        print(f"⚠️ Системная ошибка: {e}")

async def main():
    if not TELEGRAM_TOKEN:
        print(f"❌ Файл не найден или TELEGRAM_TOKEN пуст по пути: {env_path}")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    print(f"✅ Бот запущен. Проверка RetailCRM каждые {CHECK_INTERVAL} сек.")
    
    # При первом запуске запоминаем ID последнего существующего заказа,
    # чтобы не спамить старыми заказами из базы.
    print("Загрузка текущего состояния заказов...")
    await check_retail_orders(bot)
    print("Мониторинг активен.")

    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        await check_retail_orders(bot)

if __name__ == "__main__":
    asyncio.run(main())