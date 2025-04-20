import os
import json
import asyncio
import random
import re
from rewrite_tools import rewrite_ai_response
import requests
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)

# ✅ دکمه‌ی برگشت به منوی انتخاب حالت
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🔙 بازگشت به منوی انتخاب حالت", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# 📦 بارگیری متغیرهای .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
USER_MODE_FILE = "user_modes.json"

# 🔧 تنظیم Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("deepseek/deepseek-chat-v3-0324:free")

# 🧠 پیکربندی تولید محتوا
generation_config = genai.GenerationConfig(
    temperature=0.5,
    top_p=0.95,
    top_k=40,
    max_output_tokens=2048,
)

# 🧾 مدیریت حالت کاربر
def load_user_mode(user_id):
    try:
        with open(USER_MODE_FILE, "r") as f:
            data = json.load(f)
            return data.get(str(user_id), "gemini")
    except:
        return "gemini"

def save_user_mode(user_id, mode):
    try:
        if os.path.exists(USER_MODE_FILE):
            with open(USER_MODE_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}
        data[str(user_id)] = mode
        with open(USER_MODE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ خطا در ذخیره حالت کاربر: {e}")

# 📡 تماس با OpenRouter
def ask_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = """
    وظیفه‌ی تو پاسخ دادن به سوالات کاربر به شکل مستقیم، سریع و دقیق است.
    هیچ مقدمه، توضیح اضافی، یا جمع‌بندی ننویس.
    فقط اصل جواب را بده. از زیاده‌گویی و توضیح واضحات خودداری کن.
    """

    data = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        res.raise_for_status()
        res_json = res.json()
        if isinstance(res_json, dict) and "choices" in res_json and len(res_json["choices"]) > 0:
            message = res_json["choices"][0].get("message", {})
            return message.get("content", "❌ پاسخ معتبری دریافت نشد.")
        else:
            return f"❌ پاسخ نامعتبر از OpenRouter:\n{res_json}"
    except requests.exceptions.RequestException as e:
        return f"❌ خطا در ارتباط با OpenRouter: {e}"

# 📡 بررسی و بازنویسی با OpenRouter
def check_and_rewrite_openrouter(text, user_input):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    check_prompt = f"""
     کاربر: «{user_input}»
    متن تولیدشده: «{text}»

    بررسی کن که آیا این متن به اندازه کافی محاوره‌ای، صمیمی و مثل گفت‌وگوی روزمره هست یا نه.
    اگر متن خیلی رسمی، خشک یا غیرمحاوره‌ایه، بازنویسیش کن تا:
    - مثل یه چت دوستانه و طبیعی باشه.
    - از عبارات محاوره‌ای، ساده و روزمره استفاده کن (مثل چیزی که تو مکالمه با رفیق می‌گی).
    - از کلمات سنگین یا ادبی پرهیز کن.
    اگر متن به اندازه کافی محاوره‌ای و خوبه، همون رو برگردون.
    فقط متن نهایی (بازنویسی‌شده یا اصلی) رو بنویس.
    """

    data = {
        "model": "google/gemini-2.0-flash-thinking-exp-1219:free",
        "messages": [
            {"role": "user", "content": check_prompt}
        ]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        res.raise_for_status()
        res_json = res.json()
        if isinstance(res_json, dict) and "choices" in res_json and len(res_json["choices"]) > 0:
            return res_json["choices"][0]["message"]["content"].strip()
        return text
    except requests.exceptions.RequestException as e:
        print(f"❌ خطا در بررسی و بازنویسی OpenRouter: {e}")
        return text

# 📡 تماس با DeepSeek
def ask_deepseek(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    raw_prompt = f"""
    کاربر: {prompt}

    لطفاً سریع و دقیق به این سوال پاسخ بده.
    از اضافه‌گویی و مقدمه‌چینی پرهیز کن. اصل مطلب رو بگو.
    """
    data1 = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [{"role": "user", "content": raw_prompt}]
    }

    try:
        res1 = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data1)
        res1.raise_for_status()
        res_json1 = res1.json()
        if "choices" not in res_json1 or not res_json1["choices"]:
            return "❌ خطا در دریافت پاسخ مرحله اول از DeepSeek."
        raw_response = res_json1["choices"][0]["message"]["content"].strip()

        friendly_prompt = f"""
        این پاسخ رو به زبونی خودمونی، صمیمی و انسانی بازنویسی کن. نه خیلی رسمی باشه، نه پیچیده.
        پاسخ اصلی:
        «{raw_response}»

        حالا جواب خودمونی رو بنویس:
        """
        data2 = {
            "model": "deepseek/deepseek-chat-v3-0324:free",
            "messages": [{"role": "user", "content": friendly_prompt}]
        }

        res2 = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data2)
        res2.raise_for_status()
        res_json2 = res2.json()
        if "choices" not in res_json2 or not res_json2["choices"]:
            return raw_response

        friendly_response = res_json2["choices"][0]["message"]["content"].strip()
        return friendly_response

    except requests.exceptions.RequestException as e:
        return f"❌ خطا در ارتباط با DeepSeek: {e}"

# 📡 بررسی و بازنویسی با DeepSeek
def check_and_rewrite_deepseek(text, user_input):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    check_prompt = f"""
     کاربر: «{user_input}»
    متن تولیدشده: «{text}»

    بررسی کن که آیا این متن به اندازه کافی محاوره‌ای، صمیمی و مثل گفت‌وگوی روزمره هست یا نه.
    اگر متن خیلی رسمی، خشک یا غیرمحاوره‌ایه، بازنویسیش کن تا:
    - مثل یه چت دوستانه و طبیعی باشه.
    - از عبارات محاوره‌ای، ساده و روزمره استفاده کن (مثل چیزی که تو مکالمه با رفیق می‌گی).
    - از کلمات سنگین یا ادبی پرهیز کن.
    اگر متن به اندازه کافی محاوره‌ای و خوبه، همون رو برگردون.
    فقط متن نهایی (بازنویسی‌شده یا اصلی) رو بنویس.
    """

    data = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {"role": "user", "content": check_prompt}
        ]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        res.raise_for_status()
        res_json = res.json()
        if isinstance(res_json, dict) and "choices" in res_json and len(res_json["choices"]) > 0:
            return res_json["choices"][0]["message"]["content"].strip()
        return text
    except requests.exceptions.RequestException as e:
        print(f"❌ خطا در بررسی و بازنویسی DeepSeek: {e}")
        return text

# 🧠 پردازش پیام متنی
async def process_message(user_input, mode="gemini"):
    try:
        print(f"🛠️ شروع با: {mode}")

        if mode == "gemini":
            prompt = f"""
             کاربر:
            «{user_input}»

            لطفاً به صورت واضح، دقیق، و قابل فهم برای انسان به این سوال پاسخ بده.
            از لحن صمیمی استفاده کن و پاسخ کاربردی بده.
            """
            print("📝 پیام ساخته شد\n", prompt)

            try:
                response_raw = model.generate_content(prompt, generation_config=generation_config)
                print("✅ خروجی خام Gemini:", response_raw)
                response = response_raw.text.strip() if response_raw and response_raw.text else ""
                print("📤 پاسخ اولیه Gemini:", response)
            except Exception as e:
                print("❌ خطا در فراخوانی Gemini:", e)
                return "❌ خطا در دریافت پاسخ از Gemini."

            if not response:
                return "❌ Gemini پاسخی تولید نکرد."

            try:
                humanized_response = rewrite_ai_response(response)
                print("🌀 خروجی بازنویسی‌شده اولیه:", humanized_response)
            except Exception as e:
                print("❌ خطا در بازنویسی اولیه:", e)
                return "❌ مشکلی در بازنویسی پاسخ پیش آمد."

            # بررسی و بازنویسی با Gemini
            check_prompt = f"""
             کاربر: «{user_input}»
            متن تولیدشده: «{humanized_response}»

            بررسی کن که آیا این متن به اندازه کافی محاوره‌ای، صمیمی و مثل گفت‌وگوی روزمره هست یا نه.
            اگر متن خیلی رسمی، خشک یا غیرمحاوره‌ایه، بازنویسیش کن تا:
            - مثل یه چت دوستانه و طبیعی باشه.
            - از عبارات محاوره‌ای، ساده و روزمره استفاده کن (مثل چیزی که تو مکالمه با رفیق می‌گی).
            - از کلمات سنگین یا ادبی پرهیز کن.
            اگر متن به اندازه کافی محاوره‌ای و خوبه، همون رو برگردون.
            فقط متن نهایی (بازنویسی‌شده یا اصلی) رو بنویس.
            """
            try:
                conversational_response = model.generate_content(check_prompt, generation_config=generation_config).text.strip()
                print("📝 متن محاوره‌ای Gemini:", conversational_response)
            except Exception as e:
                print("❌ خطا در بررسی و بازنویسی Gemini:", e)
                conversational_response = humanized_response

            # انسانی‌سازی نهایی
            try:
                final_response = rewrite_ai_response(conversational_response)
                print("🌀 خروجی بازنویسی‌شده نهایی:", final_response)
            except Exception as e:
                print("❌ خطا در بازنویسی نهایی:", e)
                final_response = conversational_response

            return final_response

        elif mode == "openrouter":
            response = await asyncio.to_thread(ask_openrouter, user_input)
            if "❌" in response or not response.strip():
                return response

            humanized_response = rewrite_ai_response(response)
            print("🌀 خروجی بازنویسی‌شده اولیه OpenRouter:", humanized_response)

            conversational_response = await asyncio.to_thread(check_and_rewrite_openrouter, humanized_response, user_input)
            print("📝 متن محاوره‌ای OpenRouter:", conversational_response)

            final_response = rewrite_ai_response(conversational_response)
            print("🌀 خروجی بازنویسی‌شده نهایی OpenRouter:", final_response)
            return final_response

        elif mode == "deepseek":
            response = await asyncio.to_thread(ask_deepseek, user_input)
            if "❌" in response or not response.strip():
                return response

            humanized_response = rewrite_ai_response(response)
            print("🌀 خروجی بازنویسی‌شده اولیه DeepSeek:", humanized_response)

            conversational_response = await asyncio.to_thread(check_and_rewrite_deepseek, humanized_response, user_input)
            print("📝 متن محاوره‌ای DeepSeek:", conversational_response)

            final_response = rewrite_ai_response(conversational_response)
            print("🌀 خروجی بازنویسی‌شده نهایی DeepSeek:", final_response)
            return final_response

        elif mode == "refined":
            openrouter_resp = await asyncio.to_thread(ask_openrouter, user_input)
            deepseek_resp = await asyncio.to_thread(ask_deepseek, user_input)

            print(f"📨 پاسخ OpenRouter: {openrouter_resp}")
            print(f"📨 پاسخ DeepSeek: {deepseek_resp}")

            if not openrouter_resp or "❌" in openrouter_resp:
                openrouter_resp = ""
            if not deepseek_resp or "❌" in deepseek_resp:
                deepseek_resp = ""

            if not openrouter_resp and not deepseek_resp:
                return "❌ هیچ پاسخی از مدل‌ها دریافت نشد. لطفاً بعداً دوباره امتحان کن."

            responses_combined = ""
            if openrouter_resp:
                responses_combined += f"🧠 پاسخ OpenRouter:\n{openrouter_resp}\n\n"
            if deepseek_resp:
                responses_combined += f"🤖 پاسخ DeepSeek:\n{deepseek_resp}"

            merge_prompt = f"""
             کاربر:
            {user_input}

            {responses_combined}

            🔍 لطفاً با بررسی پاسخ‌های بالا، یک جواب نهایی تولید کن که:
            - دقیق، ساده و کاربردی باشه ✅
            - لحن صمیمی، انسانی و قابل درک داشته باشه 🤝
            - اضافه‌گویی نداشته باشه ❌
            - در صورت نیاز از ایموجی استفاده کن 🎯

            فقط نتیجه نهایی رو بگو، نه مراحل پردازش رو.
            """

            try:
                reply = model.generate_content(merge_prompt, generation_config=generation_config).text.strip()
                if not reply:
                    return "❌ پاسخ نهایی تولید نشد."

                humanized_response = rewrite_ai_response(reply)
                print("🌀 خروجی بازنویسی‌شده اولیه Refined:", humanized_response)

                check_prompt = f"""
                 کاربر: «{user_input}»
                متن تولیدشده: «{humanized_response}»

                بررسی کن که آیا این متن به اندازه کافی محاوره‌ای، صمیمی و مثل گفت‌وگوی روزمره هست یا نه.
                اگر متن خیلی رسمی، خشک یا غیرمحاوره‌ایه، بازنویسیش کن تا:
                - مثل یه چت دوستانه و طبیعی باشه.
                - از عبارات محاوره‌ای، ساده و روزمره استفاده کن (مثل چیزی که تو مکالمه با رفیق می‌گی).
                - از کلمات سنگین یا ادبی پرهیز کن.
                اگر متن به اندازه کافی محاوره‌ای و خوبه، همون رو برگردون.
                فقط متن نهایی (بازنویسی‌شده یا اصلی) رو بنویس.
                """
                conversational_response = model.generate_content(check_prompt, generation_config=generation_config).text.strip()
                print("📝 متن محاوره‌ای Refined:", conversational_response)

                final_response = rewrite_ai_response(conversational_response)
                print("🌀 خروجی بازنویسی‌شده نهایی Refined:", final_response)
                return final_response
            except Exception as e:
                print("❌ خطا از Gemini:", e)
                return "❌ مشکلی در تولید پاسخ نهایی پیش آمد."

    except Exception as e:
        print("❌ خطا در process_message:", e)
        return f"خطا: {str(e)}"

# 🧠 پردازش تصویر
async def process_image(image_path, caption, mode="gemini"):
    try:
        if mode == "gemini":
            # بارگذاری تصویر
            with open(image_path, "rb") as img_file:
                image_data = genai.upload_file(img_file.name)
            
            # تنظیم پرامپت
            prompt = f"""
            تصویر زیر را بررسی کن و بر اساس درخواست کاربر پاسخ بده:
            درخواست: «{caption}»
            پاسخ را به صورت صمیمی، محاوره‌ای و قابل فهم بنویس.
            """
            
            # ارسال به Gemini
            response = model.generate_content(
                [image_data, prompt],
                generation_config=generation_config
            )
            response_text = response.text.strip() if response and response.text else "❌ پاسخی دریافت نشد."
            
            # بازنویسی پاسخ برای محاوره‌ای شدن
            humanized_response = rewrite_ai_response(response_text)
            
            # بررسی و بازنویسی نهایی
            check_prompt = f"""
             کاربر: «{caption}»
            متن تولیدشده: «{humanized_response}»
            بررسی کن که آیا این متن به اندازه کافی محاوره‌ای، صمیمی و مثل گفت‌وگوی روزمره هست یا نه.
            اگر متن خیلی رسمی، خشک یا غیرمحاوره‌ایه، بازنویسیش کن تا:
            - مثل یه چت دوستانه و طبیعی باشه.
            - از عبارات محاوره‌ای، ساده و روزمره استفاده کن.
            - از کلمات سنگین یا ادبی پرهیز کن.
            اگر متن به اندازه کافی محاوره‌ای و خوبه، همون رو برگردون.
            فقط متن نهایی رو بنویس.
            """
            conversational_response = model.generate_content(check_prompt, generation_config=generation_config).text.strip()
            final_response = rewrite_ai_response(conversational_response)
            return final_response
        
        else:
            return "❌ پردازش تصویر فقط با مدل Gemini امکان‌پذیر است. لطفاً مدل Gemini را انتخاب کنید."
            
    except Exception as e:
        return f"❌ خطا در پردازش تصویر: {str(e)}"

# 🎛️ کیبورد پایین چت
def get_persistent_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            ["🏠 منوی اصلی", "🧠 تغییر مدل"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# 🎛️ انتخاب مدل هوش مصنوعی
async def show_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🌟 Gemini", callback_data="set_gemini"),
            InlineKeyboardButton("🧠 OpenRouter", callback_data="set_openrouter")
        ],
        [
            InlineKeyboardButton("🤖 DeepSeek", callback_data="set_deepseek"),
            InlineKeyboardButton("🧪 ترکیبی", callback_data="set_refined")
        ],
        [
            InlineKeyboardButton("🏠 بازگشت به منو", callback_data="main_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("مدل مورد نظر رو انتخاب کن:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("مدل مورد نظر رو انتخاب کن:", reply_markup=reply_markup)

# 🏠 منوی اصلی
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧠 انتخاب مدل هوش مصنوعی", callback_data="change_model")],
        [InlineKeyboardButton("📝 پرسیدن سوال جدید", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("♻️ ریست", callback_data="reset_all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 خوش اومدی! چه کاری می‌خوای انجام بدی؟", reply_markup=reply_markup)

# ♻️ ریست
async def reset_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.clear()
    await update.message.reply_text("🔄 همه چیز ریست شد. از /start یا /menu دوباره شروع کن.", reply_markup=get_persistent_keyboard())

# ✅ استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = load_user_mode(user_id)
    context.chat_data["mode"] = mode
    await update.message.reply_text("سلام! من آماده‌ام 🧠", reply_markup=get_persistent_keyboard())
    await show_mode_selection(update, context)

# 🧠 انتخاب یا بازگشت به حالت هوش مصنوعی
async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "main_menu":
        await query.edit_message_text("لطفاً یک حالت هوش مصنوعی انتخاب کنید:")
        await show_mode_selection(update, context)
        return

    mode_map = {
        "set_gemini": "gemini",
        "set_openrouter": "openrouter",
        "set_deepseek": "deepseek",
        "set_refined": "refined"
    }
    selected_mode = mode_map.get(query.data, "gemini")
    context.chat_data["mode"] = selected_mode
    save_user_mode(user_id, selected_mode)
    await query.edit_message_text(f"✅ مدل انتخاب شد: {selected_mode.upper()}")

# 🛠️ تابع تقسیم متن برای تلگرام
def split_text_for_telegram(text, max_length=4000):
    parts = []
    current_part = ""
    
    sentences = re.split(r'(?<=[.!؟])\s+', text.strip()) if text else [""]
    
    for sentence in sentences:
        if len(current_part) + len(sentence) + 1 > max_length:
            if current_part:
                parts.append(current_part.strip())
                current_part = sentence
            else:
                while len(sentence) > max_length:
                    split_index = sentence.rfind(" ", 0, max_length - 1)
                    if split_index == -1:
                        split_index = max_length
                    parts.append(sentence[:split_index].strip())
                    sentence = sentence[split_index:].strip()
                current_part = sentence
        else:
            current_part += (" " + sentence if current_part else sentence)
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts if parts else [text]

# 💬 مدیریت پیام متنی کاربر
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    mode = context.chat_data.get("mode", "gemini")

    print(f"\n📥 پیام کاربر: {user_input}")
    print(f"🎛️ حالت انتخاب‌شده: {mode}")

    loading_texts = [
        "⏳ در حال پردازش.",
        "⏳ در حال پردازش..",
        "⏳ در حال پردازش...",
        "⏳ در حال پردازش.....",
        "⏳ در حال پردازش..",
        "⏳ در حال پردازش.......",
        "⏳ در حال پردازش. . ."
    ]
    loading_message = await update.message.reply_text(random.choice(loading_texts))

    async def animate_loading():
        while not context.chat_data.get("done_processing", False):
            await asyncio.sleep(0.8)
            try:
                await loading_message.edit_text(random.choice(loading_texts))
            except:
                pass

    context.chat_data["done_processing"] = False
    loading_task = asyncio.create_task(animate_loading())

    try:
        reply = await process_message(user_input, mode=mode)
        context.chat_data["done_processing"] = True
        await loading_task

        if reply and reply.strip():
            await loading_message.delete()
            message_parts = split_text_for_telegram(reply, max_length=4000)
            for i, part in enumerate(message_parts):
                reply_markup = get_main_menu() if i == len(message_parts) - 1 else None
                await update.message.reply_text(part, reply_markup=reply_markup)
        else:
            await loading_message.edit_text("❌ پاسخ خالی بود.", reply_markup=get_main_menu())

    except Exception as e:
        context.chat_data["done_processing"] = True
        await loading_task
        error_msg = f"❌ خطا هنگام ارسال پاسخ:\n{str(e)}"
        print(error_msg)
        try:
            await loading_message.edit_text(error_msg, reply_markup=get_main_menu())
        except:
            await update.message.reply_text(error_msg, reply_markup=get_main_menu())

# 📷 مدیریت پیام‌های حاوی عکس
async def handle_user_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = context.chat_data.get("mode", "gemini")
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    loading_texts = [
        "⏳ در حال پردازش تصویر...",
        "⏳ لطفاً صبر کنید...",
        "⏳ پردازش در جریان است..."
    ]
    loading_message = await update.message.reply_text(random.choice(loading_texts))

    photo_path = f"temp_{user_id}_{photo.file_id}.jpg"
    try:
        await file.download_to_drive(photo_path)
        
        response = await process_image(photo_path, update.message.caption or "تصویر را توصیف کن", mode)
        
        await loading_message.delete()
        
        message_parts = split_text_for_telegram(response, max_length=4000)
        for i, part in enumerate(message_parts):
            reply_markup = get_main_menu() if i == len(message_parts) - 1 else None
            await update.message.reply_text(part, reply_markup=reply_markup)
            
    except Exception as e:
        await loading_message.edit_text(f"❌ خطا در پردازش تصویر: {str(e)}", reply_markup=get_main_menu())
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

# 🚀 اجرای بات
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_main_menu))
    app.add_handler(CommandHandler("reset", reset_session))
    
    app.add_handler(CallbackQueryHandler(handle_mode))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_user_photo))
    
    print("🤖 ربات شروع شد")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())