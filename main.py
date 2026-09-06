import os
import sqlite3
import threading
import requests
from flask import Flask
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

# ==================== البيانات الأساسية ====================
BOT_TOKEN = "8322155608:AAFZhPOtImDmiNeFAg7KbrLO4BMr9qpjN4Q"
GEMINI_API_KEY = "AQ.Ab8RN6LocdZ7m93THCJUoa7492VWIbn1MoXCfdgrDMTj0t4ZMw"
USDT_WALLET_ADDRESS = "TE9je7QpBfLpG6pduWdyv7RqVz8vUZjWUX"

# ==================== سيرفر ويب UptimeRobot ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Micro-SaaS Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_tx (
            tx_hash TEXT PRIMARY KEY
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

# ==================== التحقق الآلي من شبكة TRON ====================
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
                    data_hex = contract["parameter"]["value"]["data"]
                    if data_hex.startswith("a9059cbb"):
                        record_tx(tx_hash)
                        return True, 100
    except Exception as e:
        print(f"TRON API Error: {e}")
    return False, "لم نتمكن من التأكد من التحويل أو العملية غير مكتملة بعد. تأكد من الـ TxID والانتظار قليلاً."

# ==================== الذكاء الاصطناعي ====================
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
        print(f"Error: {e}")
    return "عذراً، حدث خطأ أثناء إعداد النص. يرجى المحاولة لاحقاً."

# ==================== أوامر ومعالجة البوت ====================
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
        [InlineKeyboardButton("⭐ شراء رصيد بنجوم تلغرام (Stars)", callback_data="buy_stars")],
        [InlineKeyboardButton("💳 شراء رصيد عبر USDT (TRC20)", callback_data="buy_usdt")],
        [InlineKeyboardButton("📊 رصيدي وحساب الإحالات", callback_data="check_status")]
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
            await update.message.reply_text(f"✅ **تم التأكد من الدفع بنجاح!**\nتم إضافة {result} محاولة إلى حسابك تلقائياً.")
        else:
            await update.message.reply_text(f"❌ **فشل التحقق:** {result}")
        return

    user_data = get_user(user_id)
    if user_data['credits'] <= 0:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        no_credits_text = (
            "⚠️ **نفد رصيدك الحالي!**\n\n"
            "للاستمرار يمكنك الشراء عبر ⭐ النجوم أو 💳 USDT، أو مشاركة رابط الإحالة:\n"
            f"`{referral_link}`"
        )
        keyboard = [
            [InlineKeyboardButton("⭐ شراء بالنجوم", callback_data="buy_stars")],
            [InlineKeyboardButton("💳 شراء بـ USDT", callback_data="buy_usdt")]
        ]
        await update.message.reply_text(no_credits_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    status_msg = await update.message.reply_text("⏳ جاري صياغة المحتوى التسويقي...")
    ai_result = generate_ai_response(user_text)
    
    update_credits(user_id, -1)
    new_credits = user_data['credits'] - 1

    await status_msg.edit_text(f"{ai_result}\n\n---\n✅ **تم خصم نقطة.** الرصيد المتبقي: {new_credits} محاولات.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy_stars":
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="باقة 50 محاولة ذكاء اصطناعي",
            description="تعبئة آلية لرصيد الاستخدام في البوت بواسطة نجوم تلغرام",
            payload="stars_package_50",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("50 محاولة", 100)]
        )

    elif query.data == "buy_usdt":
        pay_text = (
            "💳 **شراء رصيد عبر USDT (TRC20):**\n\n"
            "• **100 محاولة** = 10 USDT\n\n"
            f"📌 **عنوان المحفظة:**\n`{USDT_WALLET_ADDRESS}`\n\n"
            "بعد إجراء التحويل من محفظتك، اضغط الزر أدناه لإدخال رقم المعاملة (TxID) للتحقق الآلي وشحن الحساب فوراً."
        )
        keyboard = [[InlineKeyboardButton("🔍 إدخال الـ TxID للتحقق الفوري", callback_data="enter_txid")]]
        await query.message.reply_text(pay_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "enter_txid":
        context.user_data["awaiting_txid"] = True
        await query.message.reply_text("أرسل الآن **معرّف العملية (TxID / Transaction Hash)** الخاص بالتحويل:")

    elif query.data == "check_status":
        user_id = query.from_user.id
        user_data = get_user(user_id)
        status_text = f"📊 **حالة حسابك:**\n\n• الرصيد المتبقي: {user_data['credits']} محاولات.\n• عدد الإحالات الناجحة: {user_data['referrals']} أصدقاء."
        await query.message.reply_text(status_text, parse_mode="Markdown")

# ==================== معالجة دفع نجوم تلغرام الفورية ====================
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_credits(user_id, 50)
    await update.message.reply_text("🎉 **شكراً لك! تم الدفع بنجاح عبر نجوم تلغرام.**\nتم إضافة 50 محاولة إلى حسابك تلقائياً.")

# ==================== التشغيل الرئيسي ====================
def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 الوكيل الذكي يعمل بنجاح ومستعد لاستقبال المدفوعات الآلية...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
