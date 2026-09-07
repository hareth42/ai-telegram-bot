import os
import sqlite3
import threading
import requests
import logging
from flask import Flask
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

# ==================== الإعدادات والأسرار ====================
BOT_TOKEN = os.environ.get(8322155608:AAGFScpl0iuk726FmDsFykxmIq63lb9mXB4)
GEMINI_API_KEY = os.environ.get(AQ.Ab8RN6LocdZ7m93THCJUoa7492VWIbn1MoXCfdgrDMTj0t4ZMw)
TON_WALLET_ADDRESS = os.environ.get(UQBQWnjoB021NjvkMF61DuDfcY7-rvAonOep9X45694G7L6l)
ADMIN_ID = int(os.environ.get(523589053))  # معرفك في تلغرام لصلاحيات الإدارة

logging.basicConfig(level=logging.INFO)

# ==================== سيرفر ويب للتشغيل المستمر (24/7) ====================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Status: 100% Autonomous & Operational!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==================== قاعدة البيانات (SQLite) ====================
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 3,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_txs (
            tx_hash TEXT PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, credits, referrals, referred_by FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, credits, referrals, referred_by) VALUES (?, 3, 0, 0)", (user_id,))
        conn.commit()
        user_data = {"user_id": user_id, "credits": 3, "referrals": 0, "referred_by": 0, "is_new": True}
    else:
        user_data = {"user_id": row[0], "credits": row[1], "referrals": row[2], "referred_by": row[3], "is_new": False}
    conn.close()
    return user_data

def add_credits(user_id, amount):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def set_referrer(user_id, referrer_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))
    cursor.execute("UPDATE users SET credits = credits + 5, referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
    conn.commit()
    conn.close()

def deduct_credit(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits - 1 WHERE user_id = ? AND credits > 0", (user_id,))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_all_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_zero_credit_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE credits = 0")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# ==================== الذكاء الاصطناعي (Gemini 2.0) ====================
def generate_ai_response(prompt):
    if not GEMINI_API_KEY:
        return "خطأ: لم يتم ضبط مفتاح GEMINI_API_KEY."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    system_instruction = "أنت مساعد تسويقي محترف وخبير إعلانات. اكتب نصوصاً إعلانية ووصف منتجات جذاباً باللغة العربية."
    payload = {"contents": [{"parts": [{"text": f"{system_instruction}\n\nطلب العميل: {prompt}"}]}]}
    try:
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        return f"عذراً، حدث خطأ أثناء إعداد النص (رمز الخطأ: {res.status_code})."
    except Exception as e:
        return "عذراً، حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."

# ==================== المهام التلقائية (TON Checker & Retargeting) ====================
async def auto_check_ton_payments(context: ContextTypes.DEFAULT_TYPE):
    """فحص تحويلات شبكة TON وتأكيدها آلياً بدون تدخل بشري"""
    if not TON_WALLET_ADDRESS or TON_WALLET_ADDRESS.startswith("ضع_"):
        return
    url = f"https://toncenter.com/api/v2/getTransactions?address={TON_WALLET_ADDRESS}&limit=10"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return
        txs = res.json().get("result", [])
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()

        for tx in txs:
            tx_hash = tx.get("transaction_id", {}).get("hash")
            in_msg = tx.get("in_msg", {})
            value = int(in_msg.get("value", 0)) / 1e9  # التحويل لـ TON
            comment = in_msg.get("message", "").strip()

            if tx_hash and comment.isdigit() and value >= 0.4:
                cursor.execute("SELECT tx_hash FROM processed_txs WHERE tx_hash = ?", (tx_hash,))
                if not cursor.fetchone():
                    user_id = int(comment)
                    cursor.execute("INSERT INTO processed_txs VALUES (?)", (tx_hash,))
                    conn.commit()
                    add_credits(user_id, 20)
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="🎉 **تم تأكيد دفع عملة TON بنجاح!**\nتم إضافة **20 محاولة جديدة** إلى حسابك تلقائياً.",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
        conn.close()
    except Exception as e:
        logging.error(f"TON Checker Error: {e}")

async def auto_retargeting_job(context: ContextTypes.DEFAULT_TYPE):
    """إرسال عروض تسويقية أوتوماتيكية للعملاء الذين انتهى رصيدهم"""
    zero_users = get_zero_credit_users()
    keyboard = [
        [InlineKeyboardButton("⭐ شحن الرصيد بالنجوم (خصم 50%)", callback_data="buy_stars")],
        [InlineKeyboardButton("🔗 الحصول على محاولات مجانية", callback_data="my_credits")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    promo_text = (
        "🔥 **عرض خاص ومؤقت!**\n\n"
        "لاحظنا أن رصيدك المجاني قد انتهى. اشحن حسابك الآن بنجوم تلغرام واحصل على ضعف المحاولات، "
        "أو شارك رابط الإحالة الخاص بك مع أصدقائك للحصول على 5 محاولات مجانية لكل شخص ينضم!"
    )
    for uid in zero_users:
        try:
            await context.bot.send_message(chat_id=uid, text=promo_text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            pass

# ==================== الأوامر والوظائف ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    # معالجة نظام الإحالة التلقائي
    if user['is_new'] and context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id != user_id:
            set_referrer(user_id, referrer_id)
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 **انضم صديق جديد عبر رابطك!**\nتم شحن **5 محاولات مجانية** في حسابك تلقائياً.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={user_id}"

    keyboard = [
        [InlineKeyboardButton("⭐ شراء رصيد (نجوم تلغرام)", callback_data="buy_stars")],
        [InlineKeyboardButton("💎 شراء رصيد (عملة TON)", callback_data="buy_ton")],
        [InlineKeyboardButton("📊 رصيدي ورابط الإحالة", callback_data="my_credits")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"مرحباً بك في الوكيل الذكي لكتابة المحتوى الإعلاني! 🤖\n\n"
        f"🎁 **رصيدك الحالي:** {user['credits']} محاولات.\n\n"
        f"🔗 **رابط الإحالة التلقائي الخاص بك:**\n`{referral_link}`\n"
        f"(احصل على 5 محاولات مجانية تلقائياً عن كل شخص ينضم عبر رابطك)"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "my_credits":
        user = get_user(user_id)
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        await query.message.reply_text(
            f"📊 **حالة حسابك:**\n\n• الرصيد المتبقي: **{user['credits']}** محاولات.\n"
            f"• عدد الإحالات: **{user['referrals']}** أصدقاء.\n\n"
            f"🔗 رابط الدعوة الخاص بك:\n`{ref_link}`",
            parse_mode="Markdown"
        )

    elif query.data == "buy_stars":
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="شراء 10 محاولات تسويقية",
            description="شحن فورى وذاتي لـ 10 محاولات ذكاء اصطناعي.",
            payload=f"stars_10_{user_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("10 محاولات", 10)]
        )

    elif query.data == "buy_ton":
        text = (
            f"💎 **الشراء التلقائي عبر عملة TON:**\n\n"
            f"أرسل **0.5 TON** إلى العنوان التالي:\n`{TON_WALLET_ADDRESS}`\n\n"
            f"⚠️ **مهم جداً:** ضع رقم حسابك هذا في خانة (Memo/Comment) ليصلك الشحن فوراً تلقائياً:\n`{user_id}`"
        )
        await query.message.reply_text(text, parse_mode="Markdown")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_credits(user_id, 10)
    await update.message.reply_text("🎉 **تم الشحن بنجاح عبر نجوم تلغرام!**\nتمت إضافة 10 محاولات إلى حسابك.", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if user['credits'] <= 0:
        keyboard = [
            [InlineKeyboardButton("⭐ شراء رصيد بالنجوم", callback_data="buy_stars")],
            [InlineKeyboardButton("💎 شراء رصيد بـ TON", callback_data="buy_ton")]
        ]
        await update.message.reply_text("❌ **نفد رصيدك!** اشحن حسابك الآن للاستمرار:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if deduct_credit(user_id):
        wait_msg = await update.message.reply_text("⏳ جاري صياغة المحتوى...")
        ai_response = generate_ai_response(update.message.text)
        rem = get_user(user_id)['credits']
        await wait_msg.edit_text(f"{ai_response}\n\n---\n🎯 *المتبقي في رصيدك: {rem} محاولات.*", parse_mode="Markdown")

# ==================== لوحة التحكم الخاصة بالآدمن ====================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("يرجى كتابة الرسالة بعد الأمر. مثال:\n`/broadcast عرض خاص اليوم!`", parse_mode="Markdown")
        return
    users = get_all_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
            count += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ تم إرسال الإعلان التلقائي إلى {count} مستخدم.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = get_all_users()
    zero_users = get_zero_credit_users()
    await update.message.reply_text(
        f"📊 **إحصائيات البوت الحالية:**\n\n"
        f"• إجمالي المشتركين: **{len(users)}**\n"
        f"• المستخدمين بدون رصيد: **{len(zero_users)}**\n"
        f"• المستخدمين النشطين: **{len(users) - len(zero_users)}**",
        parse_mode="Markdown"
    )

# ==================== التشغيل الرئيسي والجدولة ====================
def main():
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()

    if not BOT_TOKEN or not GEMINI_API_KEY:
        raise RuntimeError("يرجى التأكد من ضبط مفاتيح البيئة TELEGRAM_BOT_TOKEN و GEMINI_API_KEY.")

    app_bot = Application.builder().token(BOT_TOKEN).build()

    # إضافة المهام المجدولة للتسويق الآلي وفحص شبكة TON
    job_queue = app_bot.job_queue
    if job_queue:
        job_queue.run_repeating(auto_check_ton_payments, interval=60, first=10) # فحص TON كل دقيقة
        job_queue.run_repeating(auto_retargeting_job, interval=86400, first=3600) # التسويق الآلي كل 24 ساعة

    # المسجلات الأوامر
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("broadcast", broadcast))
    app_bot.add_handler(CommandHandler("stats", stats))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 الوكيل الذكي يعمل بكامل طاقته وأتمتته 100%...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
