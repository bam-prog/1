# stylist_bot.py
from flask import Flask, request, jsonify
from flask_cors import CORS  # Защита от CORS-ошибок
from colorthief import ColorThief
from io import BytesIO
import requests
import logging
import colorsys
import os
from PIL import Image

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Разрешить запросы с любых источников (безопасно для webhook)


def rgb_to_hsv(r: int, g: int, b: int) -> tuple:
    """Преобразует RGB в HSV ( Hue, Saturation, Value )"""
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)


def is_warm_color(h: float, s: float, v: float) -> bool:
    """Определяет, является ли цвет тёплым (красный/оранжевый/жёлтый)"""
    if s < 0.15:  # Почти нейтральный — не определяем
        return False
    return (h < 0.12) or (h > 0.92)  # Угол в круге: ~0–45° и 330–360°


def get_color_advice(dom_color: tuple) -> str:
    """Генерирует дружелюбную рекомендацию по цвету"""
    r, g, b = dom_color
    h, s, v = rgb_to_hsv(r, g, b)

    if s < 0.15:
        return (
            "Ты в нейтральных тонах — отлично! 😌\n"
            "Попробуй добавить яркий акцент: сумку, обувь или шарф."
        )
    if is_warm_color(h, s, v):
        return (
            "Твой образ в тёплых тонах 🌞\n"
            "Попробуй сочетать с бежевым, терракотой, оливковым или глубоким бордовым."
        )
    else:
        return (
            "Холодные оттенки — идеально! ❄️\n"
            "Отлично смотрятся с белым, серым, лавандовым или тёмно-синим."
        )


def is_valid_image(content: bytes) -> bool:
    """Проверяет, действительно ли контент — изображение"""
    try:
        img = Image.open(BytesIO(content))
        img.verify()  # Проверяет целостность
        return True
    except Exception:
        return False


@app.route('/analyze', methods=['POST'])
def analyze_outfit():
    try:
        data = request.get_json()

        if not data or 'image_url' not in data:
            return jsonify({"error": "❌ Требуется поле 'image_url'"}), 400

        image_url = data['image_url'].strip()
        if not image_url.startswith(('http://', 'https://')):
            return jsonify({"error": "❌ Некорректная ссылка на изображение"}), 400

        # Загружаем изображение с таймаутом
        logger.info(f"Запрос фото: {image_url}")
        resp = requests.get(image_url, timeout=10)
        resp.raise_for_status()

        if not resp.headers.get('content-type', '').startswith('image'):
            return jsonify({"error": "❌ По ссылке не изображение"}), 400

        image_content = resp.content
        if not is_valid_image(image_content):
            return jsonify({"error": "❌ Файл повреждён или не является изображением"}), 400

        # Анализ цвета
        image_stream = BytesIO(image_content)
        color_thief = ColorThief(image_stream)
        dominant_color = color_thief.get_color(quality=1)  # (R, G, B)

        advice = get_color_advice(dominant_color)
        hex_color = "#{:02x}{:02x}{:02x}".format(*dominant_color)

        return jsonify({
            "success": True,
            "dominant_color": dominant_color,
            "color_hex": hex_color,
            "recommendation": advice
        })

    except requests.exceptions.Timeout:
        logger.error("Таймаут при загрузке изображения")
        return jsonify({"error": "⏰ Не удалось загрузить фото — слишком долго"}), 408

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса: {e}")
        return jsonify({"error": "URLException: Не удалось открыть ссылку"}), 400

    except Exception as e:
        logger.exception("Неизвестная ошибка")
        return jsonify({"error": "🤖 Что-то пошло не так. Попробуй другое фото!"}), 500


# Только для локального запуска
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
