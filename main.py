import os
import sqlite3
import threading
import uuid
import requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)

# ==================== الإعدادات والبيانات الأساسية ====================
BOT_TOKEN = "8322155608:AAFZhPOtImDmiNeFAg7KbrLO4BMr9qpjN4Q"
GEMINI_API_KEY = "AQ.Ab8RN6LocdZ7m93THCJUoa7492VWIbn1MoXCfdgrDMTj0t4ZMw"
USDT_WALLET_ADDRESS = "TE9je7QpBfLpG6pduWdyv7RqVz8vUZjWUX"

# ==================== سيرفر الويب وواجهة الـ API (B2B) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Agent-to-Agent SaaS Server is Running 24/7!"

# نقطة استقبال طلبات الوكلاء والبوتاً الأخرى برمجياً
@app.route('/api/v1/generate', methods=['POST'])
def api_generate():
    data = request.get_json() or {}
    api_key = data.get('api_key')
    prompt = data.get('prompt')

    if not api_key or not prompt:
        return jsonify({"status": "error", "message": "البيانات ناقصة (مطلوب api_key و prompt)"}), 400

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, credits FROM users WHERE api_key = ?", (api_key,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"status": "error", "message": "مفتاح API غير صالح"}), 401

    user_id, credits = user
    if credits <= 0:
        conn.close()
        return jsonify({"status": "error", "message": "الرصيد غير كافٍ لاستخدام الـ API"}), 402

    # توليد المحتوى من Gemini
    ai_response = generate_ai_response(prompt)

    # خصم نقطة وتسجيل الطلب
    cursor.execute("UPDATE users SET credits = credits - 1 WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO api_logs (user_id, prompt, status) VALUES (?, ?, ?)", (user_id, prompt, "SUCCESS"))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "result": ai_response,
        "remaining_credits": credits - 1
    }), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==================== قاعدة البيانات النظامية ====================
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 3,
            referred_by INTEGER,
            total_referrals INTEGER DEFAULT 0,
            api_key TEXT UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_tx (
            tx_hash TEXT PRIMARY KEY
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prompt TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id, referred_by=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT credits, total_referrals, api_key FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        new_api_key = f"key_{uuid.uuid4().hex[:16]}"
        cursor.execute("INSERT INTO users (user_id, credits, referred_by, api_key) VALUES (?, 3, ?, ?)", 
                       (user_id, referred_by, new_api_key))
        conn.commit()
        if referred_by:
            cursor.execute("UPDATE users SET credits = credits + 5, total_referrals = total_referrals + 1 WHERE user_id = ?", (referred_by,))
            conn.commit()
        row = (3, 0, new_api_key)
    elif not row[2]:
        new_api_key = f"key_{uuid.uuid4().hex[:16]}"
        cursor.execute("UPDATE users SET api_key = ? WHERE user_id = ?", (new_api_key, user_id))
        conn.commit()
        row = (row[0], row[1], new_api_key)

    conn.close()
    return {"credits": row[0], "referrals": row[1], "api_key": row[2]}

def update_credits(user_id, amount):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def is_tx_processed(tx_hash):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT tx_hash FROM processed_tx WHERE tx_hash = ?", (tx_hash,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def record_tx(tx_hash):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO processed_tx (tx_hash) VALUES (?)", (tx_hash,))
    conn.commit()
    conn.close()

# ==================== الفحص الشبكي USDT TRC20 ====================
def verify_usdt_trc20(tx_hash, wallet_address):
    if is_tx_processed(tx_hash):
        return False, "تم استخدام معرّف العملية (TxID) هذا من قبل."

    url = f"https://api.trongrid.io/v1/transactions/{tx_hash}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("ret") and data["ret"][0].get("contractRet") == "SUCCESS":
                contract = data["raw_data"]["contract"][0]
                if contract["type"] == "TriggerSmartContract":
                    record_tx(tx_hash)
                    return True, 100
    except Exception as e:
        print(f"TRON API Error: {e}")
    return False, "لم نتمكن من التأكد من التحويل أو العملية غير مكتملة بعد."

# ==================== محرك الذكاء الاصطناعي ====================
def generate_ai_response(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    system_instruction = "أنت مساعد تسويقي محترف وخبير إعلانات. اكتب نصوصاً إعلانية ووصف منتجات جذاباً باللغة العربية."
    
    payload = {
        "contents": [{"parts": [{"text": f"{system_instruction}\n\nطلب العميل: {prompt}"}]}]
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Gemini API Error: {e}")
    return "عذراً، حدث خطأ أثناء إعداد النص."

# ==================== معالجة أزرار وأوامر البوت ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referred_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
    
    user_data = get_user(user_id, referred_by)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    welcome_text = (
        f"🤖 **مرحباً بك في الوكيل الذكي لكتابة المحتوى والإعلانات!**\n\n"
        f"🎁 **رصيدك الحالي:** {user_data['credits']} محاولات مجانية.\n\n"
        f"💡 **الخدمات:** صياغة إعلانات احترافية، كتابة وصف منتجات، وخطط تسويقية.\n\n"
        f"🔗 **رابط الإحالة الخاص بك (للحصول على 5 نقاط مجاناً):**\n`{referral_link}`"
    )

    keyboard = [
        [InlineKeyboardButton("⭐ شراء رصيد (Stars)", callback_data="buy_stars")],
        [InlineKeyboardButton("💳 شراء رصيد (USDT TRC20)", callback_data="buy_usdt")],
        [InlineKeyboardButton("🔑 مفتاح الـ API للربط البرمجي", callback_data="get_api_key")],
        [InlineKeyboardButton("📊 حسابي والإحالات", callback_data="check_status")]
    ]
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    )

    keyboard = [
        [InlineKeyboardButton("⭐ شراء رصيد (Stars)", callback_data="buy_stars")],
        [InlineKeyboardButton("💳 شراء رصيد (USDT TRC20)", callback_data="buy_usdt")],
        [InlineKeyboardButton("🔑 مفتاح الـ API للربط البرمجي", callback_data="get_api_key")],
        [InlineKeyboardButton("📊 حسابي والإحالات", callback_data="check_status")]
    ]
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()
    
    if context.user_data.get("awaiting_txid"):
        context.user_data["awaiting_txid"] = False
        success, result = verify_usdt_trc20(user_text, USDT_WALLET_ADDRESS)
        if success:
            update_credits(user_id, result)
            await update.message.reply_text(f"✅ **تم التأكد من الدفع!** تم إضافة {result} محاولة لـ حسابك.")
        else:
            await update.message.reply_text(f"❌ **فشل التحقق:** {result}")
        return

    user_data = get_user(user_id)
    if user_data['credits'] <= 0:
        no_credits_text = "⚠️ **نفد رصيدك!** يمكنك الشراء بـ ⭐ النجوم أو 💳 USDT لاستمرار الاستخدام."
        keyboard = [
            [InlineKeyboardButton("⭐ شراء بالنجوم", callback_data="buy_stars")],
            [InlineKeyboardButton("💳 شراء بـ USDT", callback_data="buy_usdt")]
        ]
        await update.message.reply_text(no_credits_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    status_msg = await update.message.reply_text("⏳ جاري توليد المحتوى...")
    ai_result = generate_ai_response(user_text)
    
    update_credits(user_id, -1)
    await status_msg.edit_text(f"{ai_result}\n\n---\n✅ **تم خصم نقطة.** الرصيد المتبقي: {user_data['credits'] - 1}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy_stars":
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="باقة 50 محاولة",
            description="شحن آلي للرصيد عبر نجوم تلغرام",
            payload="stars_package_50",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("50 محاولة", 100)]
        )

    elif query.data == "buy_usdt":
        pay_text = (
            "💳 **شراء رصيد عبر USDT (TRC20):**\n\n"
            "• **100 محاولة** = 10 USDT\n\n"
            f"📌 **عنوان المحفظة:**\n`{USDT_WALLET_ADDRESS}`"
        )
        keyboard = [[InlineKeyboardButton("🔍 إدخال الـ TxID للتحقق", callback_data="enter_txid")]]
        await query.message.reply_text(pay_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "enter_txid":
        context.user_data["awaiting_txid"] = True
        await query.message.reply_text("أرسل الآن معرّف العملية (TxID):")

    elif query.data == "get_api_key":
        user_id = query.from_user.id
        user_data = get_user(user_id)
        api_text = (
            "🔑 **مفتاح الربط البرمجي الخاص بك (API Key):**\n\n"
            f"`{user_data['api_key']}`\n\n"
            "🌐 **عنوان الاستدعاء (Endpoint):**\n"
            "`https://<رابط_سيرفرك>/api/v1/generate`\n\n"
            "يمكن للوكلاء والأنظمة الأخرى استخدام هذا المفتاح لاستهلاك رصيدك برمجياً بآمان."
        )
        await query.message.reply_text(api_text, parse_mode="Markdown")

    elif query.data == "check_status":
        user_id = query.from_user.id
        user_data = get_user(user_id)
        status_text = f"📊 **حسابك:**\n• الرصيد: {user_data['credits']} محاولات\n• الإحالات: {user_data['referrals']} أصدقاء"
        await query.message.reply_text(status_text, parse_mode="Markdown")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_credits(user_id, 50)
    await update.message.reply_text("🎉 **تم الدفع بنجاح!** تم إضافة 50 محاولة لحسابك.")

# ==================== تشغيل النظام ====================
def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 المنصة تعمل بنجاح واستعداد تام للربط البرمجي البيني (Agent-to-Agent)...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
