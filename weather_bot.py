import os
import sys
import time
import requests
import schedule
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
 
load_dotenv()
 
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
# u can use another ai_agent, i use groq, because it's free
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL")
WEATHER_API = os.getenv("WEATHER_API")
 
LAT = "your lat"
LON = "your lon"
CITY_QUERY = f"{LAT},{LON}"
 
TIMEZONE = ZoneInfo("your timezone")
 
 
# ---------------------------------------------------------------------------
# weather
# ---------------------------------------------------------------------------
 
def get_weather_data(days=2):
    """take forecast from weatherapi.com. days=2 — today and next day"""
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": WEATHER_API,
        "q": CITY_QUERY,
        "days": days,
        "lang": "ru",
        "aqi": "no",
        "alerts": "no",
    }
 
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка получения погоды: {e}")
        return None
 
 
def format_weather_summary(weather_json, day_index=0):
    if not weather_json:
        return None
 
    forecast_days = weather_json["forecast"]["forecastday"]
    if day_index >= len(forecast_days):
        print(f"❌ Нет данных прогноза для дня с индексом {day_index}")
        return None
 
    forecast_day = forecast_days[day_index]
    day = forecast_day.get("day", {})
    astro = forecast_day.get("astro", {})
    date_str = forecast_day.get("date", "")

    hours = forecast_day.get("hour", [])
    key_hours = [6, 9, 12, 15, 18, 21]
    hourly_lines = []
    for h in hours:
        hour_num = int(h["time"].split(" ")[1].split(":")[0])
        if hour_num in key_hours:
            hourly_lines.append(
                f"- {hour_num:02d}:00 — {h['temp_c']}°C, "
                f"{h['condition']['text']}, ветер {h['wind_kph']} км/ч, "
                f"осадки {h.get('chance_of_rain', 0)}% дождь / "
                f"{h.get('chance_of_snow', 0)}% снег"
            )
 
    current_block = ""
    if day_index == 0:
        current = weather_json.get("current", {})
        current_block = f"""current weather today:
- Temperature: {current.get('temp_c')}°C, feels like {current.get('feelslike_c')}°C
- State: {current.get('condition', {}).get('text')}
- Wind: {current.get('wind_kph')} км/ч, порывы до {current.get('gust_kph')} км/ч
- Humidity: {current.get('humidity')}%
- Pressure: {current.get('pressure_mb')} мбар
- UV-index: {current.get('uv')}
 
"""
 
    summary = f"""Date: {date_str}
 #
{current_block}Forecast {'today' if day_index == 0 else 'tomorrow'}:
- Мин/Макс температура: {day.get('mintemp_c')}°C / {day.get('maxtemp_c')}°C
- Вероятность дождя: {day.get('daily_chance_of_rain', 0)}%
- Вероятность снега: {day.get('daily_chance_of_snow', 0)}%
- Общее описание: {day.get('condition', {}).get('text')}
 
Почасовой прогноз (ключевые часы):
{chr(10).join(hourly_lines)}
 
Восход: {astro.get('sunrise')}, Закат: {astro.get('sunset')}
"""
    return summary
 
 
# ---------------------------------------------------------------------------
# Groq AI
# ---------------------------------------------------------------------------
 
def get_groq_response(user_message, system_prompt=None):
    """Получить ответ от Groq API"""
    if system_prompt is None:
        system_prompt = "Ты полезный ассистент-метеоролог. Отвечай на русском языке."
 
    try:
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
 
        payload = {
            'model': 'openai/gpt-oss-120b',
            'messages': [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            'temperature': 0.7,
            'max_tokens': 2000
        }
 
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
 
        if response.status_code == 200:
            result = response.json()
            ai_message = result['choices'][0]['message']['content']
            return ai_message
        else:
            print(f"❌ Ошибка Groq API: {response.status_code}")
            print(f"Ответ: {response.text}")
            return f"Извините, произошла ошибка при обращении к Groq (код: {response.status_code})"
 
    except requests.exceptions.Timeout:
        return "Извините, запрос к Groq занял слишком много времени. Попробуйте позже."
    except Exception as e:
        print(f"❌ Ошибка Groq: {e}")
        return f"Извините, произошла ошибка: {str(e)}"
 
 
# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
 
def send_message_to_telegram(text):
    """Отправляет сообщение в Telegram канал"""
    url = f"https://api.telegram.org/bot{API_TOKEN}/sendMessage"
 
    data = {
        'chat_id': CHANNEL_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
 
    try:
        response = requests.post(url, json=data, timeout=30)
        if response.status_code == 200:
            print(f"✅ Отправлено в Telegram")
            return True
        else:
            print(f"❌ Ошибка Telegram: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")
        return False
 
 
# ---------------------------------------------------------------------------
# General logic of weather forecast
# ---------------------------------------------------------------------------

# u can change this text
WEATHER_SYSTEM_PROMPT = (
    "Ты — профессиональный метеоролог, который ведёт телеграм-канал о погоде. "
    "На основе предоставленных данных напиши живой, подробный и понятный прогноз погоды "
    "на русском языке. Используй эмодзи для наглядности (☀️🌧️❄️🌡️💨 и т.д.), "
    "структурируй текст по времени суток (утро/день/вечер), дай рекомендации "
    "по одежде и активностям. Пиши тепло и по-человечески, без сухого перечисления цифр. "
    "Формат — обычный текст с HTML-тегами <b> для акцентов (Telegram HTML parse_mode), "
    "без markdown-звёздочек."
)
 
 
def send_weather_forecast(time_of_day="день", day_index=0):
    """Получить погоду, сгенерировать описание через Groq и отправить в Telegram.
 
    day_index: 0 — прогноз на сегодня, 1 — прогноз на завтра
    """
    target_label = "сегодня" if day_index == 0 else "завтра"
    print(f"\n🌤 Формирование прогноза погоды ({time_of_day}, на {target_label})...")
 
    weather_json = get_weather_data(days=max(2, day_index + 1))
    if not weather_json:
        print("❌ Не удалось получить данные о погоде, отправка отменена")
        return
 
    weather_summary = format_weather_summary(weather_json, day_index=day_index)
    if not weather_summary:
        print("❌ Не удалось сформировать сводку погоды")
        return
 
    prompt = (
        f"Сейчас {time_of_day}. Вот данные о погоде на {target_label}:\n\n{weather_summary}\n\n"
        f"Напиши на их основе подробный прогноз погоды на {target_label} для подписчиков "
        f"телеграм-канала."
    )
 
    ai_forecast = get_groq_response(prompt, system_prompt=WEATHER_SYSTEM_PROMPT)
 
    print(f"\nGenerated forecast:\n{ai_forecast}\n")
 
    send_message_to_telegram(ai_forecast)
 
 
def morning_forecast():
    """Morning shedule (10:00) — forecast today"""
    send_weather_forecast(time_of_day="утро", day_index=0)
 
 
def evening_forecast():
    """Evening shedule (20:00) — forecast tomorrow"""
    send_weather_forecast(time_of_day="вечер", day_index=1)
 
 
# ---------------------------------------------------------------------------
# sheduler
# ---------------------------------------------------------------------------
 
def run_scheduler():
    print("=" * 60)
    print("Weather → Groq → Telegram scheduler")
    print("=" * 60)
    print(f"Time zone: {TIMEZONE}")
    print("Mailing planed to 10:00 and 20:00")
    print("Press Ctrl+C for stopped")
    print("-" * 60)
 
    schedule.every().day.at("10:00").do(morning_forecast)
    schedule.every().day.at("20:00").do(evening_forecast)
 
    while True:
        schedule.run_pending()
        now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
        print(f"\r⏳ Waiting... current time: {now}", end="", flush=True)
        time.sleep(30)
 
 
# ---------------------------------------------------------------------------
# interactive mode
# ---------------------------------------------------------------------------
 
def run_interactive():
    print("=" * 60)
    print("Groq → Telegram Channel Sender (interactive mode)")
    print("=" * 60)
 
    try:
        r = requests.get(f"https://api.telegram.org/bot{API_TOKEN}/getMe", timeout=10)
        if r.status_code == 200:
            bot = r.json()['result']
            print(f"Telegram бот: @{bot['username']}")
            print(f"Канал ID: {CHANNEL_ID}")
        else:
            print("Ошибка подключения к Telegram")
            return
    except Exception as e:
        print(f"Нет подключения к Telegram: {e}")
        return
 
    print("\nКоманды:")
    print("/exit или /quit - выход")
    print("/weather - сгенерировать и отправить прогноз погоды прямо сейчас")
    print("/telegram <текст> - отправить текст напрямую в Telegram (без Groq)")
    print("-" * 60 + "\n")
 
    while True:
        try:
            user_input = input("Вы: ")
 
            if user_input.lower() in ['/exit', '/quit', '/q']:
                print("До свидания!")
                break
            elif user_input.lower() == '/weather':
                send_weather_forecast(time_of_day="сейчас")
                continue
            elif user_input.lower().startswith('/telegram'):
                direct_text = user_input.replace('/telegram', '', 1).strip()
                if not direct_text:
                    print("Введите текст после команды /telegram")
                    continue
                send_message_to_telegram(direct_text)
                continue
            elif not user_input.strip():
                continue
 
            groq_response = get_groq_response(user_input)
            print(f"\nGroq: {groq_response}\n")
            send_message_to_telegram(groq_response)
 
        except KeyboardInterrupt:
            print("\nbot stopped")
            break
        except Exception as e:
            print(f"error: {e}")
 
 
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        run_interactive()
    elif len(sys.argv) > 1 and sys.argv[1] == "test-weather":
        send_weather_forecast(time_of_day="тест")
    else:
        run_scheduler()
 
 
if __name__ == '__main__':
    main()
 
