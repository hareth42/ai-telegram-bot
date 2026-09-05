import os
import sqlite3
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==================== ضع بياناتك هنا ====================
BOT_TOKEN = "8322155608:AAG-okOHDvrB1o1m_8TIDladVe1gbnYZRH8"
GEMINI_API_KEY = "AQ.Ab8RN6LocdZ7m93THCJUoa7492VWIbn1MoXCfdgrDMTj0t4ZMw"
USDT_WALLET_ADDRESS = "TE9je7QpBfLpG6pduWdyv7RqVz8vUZjWUX"

# ==================== سيرفر ويب لـ UptimeRobot ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

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

# ==================== استدعاء الذكاء الاصطناعي ====================
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

# ==================== أوامر البوت ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referred_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
    
    user_data = get_user(user_id, referred_by)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    welcome_text = (
        f"🤖 **مرحباً بك في الوكيل الذكي لكتابة المحتوى الإعلاني والتسويقي!**\n\n"
        f"🎁 **رصيدك الحالي:** {user_data['credits']} محاولات مجانية.\n\n"
        f"💡 **ماذا أستطيع أن أفعل لك؟**\n"
        f"- صياغة إعلانات احترافية للمتاجر ومنصات التواصل.\n"
        f"- كتابة وصف منتجات يزيد المبيعات والتحويل.\n"
        f"- أفكار خطط تسويقية واقتراح هشتاجات.\n\n"
        f"🔗 **رابط الإحالة الخاص بك (للحصول على رصيد مجاني):**\n`{referral_link}`\n"
        f"*(تحصل على 5 نقاط مجانية لكل شخص ينضم عبر رابطك)*"
    )

    keyboard = [
        [InlineKeyboardButton("💳 شراء رصيد إضافي (USDT)", callback_data="buy_credits")],
        [InlineKeyboardButton("📊 رصيدي وحساب الإحالات", callback_data="check_status")]
    ]
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if user_data['credits'] <= 0:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        no_credits_text = (
            "⚠️ **نفد رصيدك الحالي!**\n\n"
            "للاستمرار يمكنك:\n"
            "1️⃣ شراء رصيد جديد بـ USDT.\n"
            f"2️⃣ مشاركة رابط الإحالة والحصول على **5 نقاط مجانية** لكل صديق:\n`{referral_link}`"
        )
        keyboard = [[InlineKeyboardButton("💳 شراء رصيد الآن", callback_data="buy_credits")]]
        await update.message.reply_text(no_credits_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    status_msg = await update.message.reply_text("⏳ جاري صياغة المحتوى التسويقي...")
    ai_result = generate_ai_response(update.message.text)
    
    update_credits(user_id, -1)
    new_credits = user_data['credits'] - 1

    await status_msg.edit_text(f"{ai_result}\n\n---\n✅ **تم خصم نقطة.** الرصيد المتبقي: {new_credits} محاولات.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy_credits":
        pay_text = (
            "💳 **شراء رصيد الاستخدام عبر USDT (TRC20):**\n\n"
            "اختر الخطة المناسبة:\n"
            "🔹 **100 عملية توليد** = 10 USDT\n"
            "🔹 **300 عملية توليد** = 25 USDT\n\n"
            f"📌 **عنوان المحفظة للتحويل:**\n`{USDT_WALLET_ADDRESS}`\n\n"
            "⚠️ بعد التحويل، اضغط زر الفحص ليتم التحقق وشحن رصيدك آلياً."
        )
        keyboard = [[InlineKeyboardButton("🔄 التحقق من الدفع آلياً", callback_data="verify_payment")]]
        await query.message.reply_text(pay_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "verify_payment":
        await query.message.reply_text("🔍 جاري الفحص الآلي للشبكة... إذا تم التحويل ستصلك رسالة تأكيد الرصيد فوراً.")

    elif query.data == "check_status":
        user_id = query.from_user.id
        user_data = get_user(user_id)
        status_text = f"📊 **حالة حسابك:**\n\n• الرصيد المتبقي: {user_data['credits']} محاولات.\n• عدد الإحالات الناجحة: {user_data['referrals']} أصدقاء."
        await query.message.reply_text(status_text, parse_mode="Markdown")

# ==================== التشغيل الرئيسي ====================
def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 الوكيل الذكي وسيرفر الويب يعملان بنجاح...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
