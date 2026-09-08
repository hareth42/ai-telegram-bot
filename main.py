import os
import sqlite3
import threading
import base64
import requests
from flask import Flask, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes
)

# ==================== استقبال البيانات من متغيرات البيئة أو القيم المباشرة ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8322155608:AAFKwhOH5xK5mY2t2gASK175VhPBitk-mJo")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LJZH5uY_-3KWMlyis3gXUyruGbSv0e866peA30LjeYWg")
USDT_WALLET_ADDRESS = os.environ.get("USDT_WALLET_ADDRESS", "TE9je7QpBfLpG6pduWdyv7RqVz8vUZjWUX")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY", "bd404b0a-d24b-403c-9921-e1309111f04a")

# ==================== سيرفر ويب لـ UptimeRobot و OpenAPI (Flask) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "AI Marketing Agent & B2B Micro-SaaS is Live & Running 24/7! 🚀"

@app.route('/openapi.json')
def openapi_spec():
    return jsonify({
        "openapi": "3.1.0",
        "info": {
            "title": "AI Marketing Agent Micro-SaaS API",
            "version": "1.0.0",
            "description": "API for automated AI marketing content generation."
        },
        "servers": [{"url": request.host_url.rstrip("/")}],
        "paths": {
            "/api/v1/generate": {
                "post": {
                    "summary": "Generate AI Marketing Content",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"prompt": {"type": "string"}},
                                    "required": ["prompt"]
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Successful Generation"}}
                }
            }
        }
    })

@app.route("/api/v1/generate", methods=["POST"])
def api_generate():
    data = request.json
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' in request body"}), 400
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        system_instruction = "You are an elite AI Chief Marketing Officer (CMO)."
        payload = {"contents": [{"parts": [{"text": f"{system_instruction}\n\nUSER REQUEST: {data['prompt']}"}]}]}
        response = requests.post(url, json=payload, timeout=25)
        if response.status_code == 200:
            res_text = response.json()['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"status": "success", "result": res_text}), 200
        return jsonify({"error": "Failed to generate from AI engine"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json
    tx_id = data.get("tx_id")
    if not tx_id or not TRONGRID_API_KEY:
        return jsonify({"error": "Missing transaction ID or TronGrid API key"}), 400
    url = f"https://api.trongrid.io/v1/transactions/{tx_id}/events"
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            events = res.json().get("data", [])
            if events:
                return jsonify({"status": "verified", "message": "Payment confirmed successfully."}), 200
        return jsonify({"status": "pending", "message": "Transaction not found or invalid."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 3,
            referred_by INTEGER,
            total_referrals INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id, referred_by=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT credits, total_referrals FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, credits, referred_by) VALUES (?, 3, ?)", (user_id, referred_by))
        conn.commit()
        if referred_by:
            cursor.execute("UPDATE users SET credits = credits + 5, total_referrals = total_referrals + 1 WHERE user_id = ?", (referred_by,))
            conn.commit()
        row = (3, 0)
    conn.close()
    return {"credits": row[0], "referrals": row[1]}

def update_credits(user_id, amount):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# ==================== محرك الذكاء الاصطناعي ====================
def generate_ai_response(prompt, image_bytes=None, mime_type="image/jpeg"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    system_instruction = "You are an elite AI Chief Marketing Officer (CMO) and Copywriting Master fluent in Arabic and English."
    parts = []
    if image_bytes:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        parts.append({"inline_data": {"mime_type": mime_type, "data": base64_image}})
    parts.append({"text": f"{system_instruction}\n\nUSER REQUEST: {prompt}"})
    payload = {"contents": [{"parts": parts}]}
    try:
        response = requests.post(url, json=payload, timeout=25)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Error calling Gemini: {e}")
    return "عذراً، حدث خطأ أثناء إعداد المحتوى."

async def safe_reply(message, text, reply_markup=None):
    try:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        await message.reply_text(text, reply_markup=reply_markup)

async def safe_edit(message, text):
    try:
        await message.edit_text(text, parse_mode="Markdown")
    except Exception:
        await message.edit_text(text)

# ==================== أوامر تلغرام ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referred_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
    user_data = get_user(user_id, referred_by)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    welcome_text = (
        f"🚀 **مرحباً بك في الوكيل التسويقي الذكي الشامل!**\n\n"
        f"🎁 **رصيدك الحالي:** {user_data['credits']} محاولات مجانية.\n\n"
        f"🔗 **رابط الإحالة (احصل على 5 نقاط لكل صديق):**\n`{referral_link}`"
    )
    keyboard = [
        [InlineKeyboardButton("🎯 إعلان ممول", callback_data="tmpl_ad"), InlineKeyboardButton("🎥 سيناريو فيديو", callback_data="tmpl_script")],
        [InlineKeyboardButton("💳 شراء رصيد", callback_data="buy_credits"), InlineKeyboardButton("📊 رصيدي", callback_data="check_status")]
    ]
    await safe_reply(update.message, welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if user_data['credits'] <= 0:
        await safe_reply(update.message, "⚠️ نفد رصيدك الحالي! يرجى الشراء أو دعوة الأصدقاء.")
        return
    status_msg = await update.message.reply_text("🧠 جاري التفكير وصياغة المحتوى... ⏳")
    ai_result = generate_ai_response(update.message.text)
    update_credits(user_id, -1)
    await safe_edit(status_msg, f"{ai_result}\n\n---\n✅ تم خصم نقطة. الرصيد المتبقي: {user_data['credits'] - 1}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "buy_credits":
        pay_text = "💳 اختر طريقة الشحن:\n\n🌟 نجوم تلغرام\n💎 USDT"
        keyboard = [[InlineKeyboardButton("⭐ شراء بـ 250 نجمة", callback_data="buy_stars")]]
        await safe_reply(query.message, pay_text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == "buy_stars":
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="100 محاولة",
            description="شحن رصيد الوكيل التسويقي",
            payload="credits_pack_100",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("100 محاولة", 250)]
        )
    elif query.data == "check_status":
        user_data = get_user(query.from_user.id)
        await safe_reply(query.message, f"📊 رصيدك الحالي: {user_data['credits']} محاولات.")

def main():
    # تشغيل سيرفر الويب في خلفية منفصلة لفتح المنفذ المطلوب في Render
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    # تشغيل بوت تيليجرام
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 الوكيل التسويقي وسيرفر الويب يعملان بنجاح معاً...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
