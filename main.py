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

# ==================== الإعدادات المتغيرات ====================
BOT_TOKEN = "8322155608:AAGFScp10iuk726FmDsFykxmIq631b9mXB4"
GEMINI_API_KEY = "AQ.Ab8RN6LoodZ7m93THCJUoa7492VWIbn1MoXCfdgzDNTj0t4ZMm"
USDT_TRC20_WALLET = "TE9je7QpBfLpG6pduWdyv7RqVz8vUZjWUX"
# تحويل آمن لـ ADMIN_ID لمنع أي توقف للمشروع
try:
    ADMIN_ID = int(os.environ.get(523589053))
except ValueError:
    ADMIN_ID = 0

logging.basicConfig(level=logging.INFO)

# ==================== سيرفر WEB للتشغيل 24/7 على Render ====================
app = Flask(__name__)

@app.route("/")
def home():
    return "🚀 Autonomous Super Agent is Online 24/7!"

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

# ==================== كتالوج المنتجات الجاهزة والذكاء الاصطناعي ====================
PRODUCTS = {
    "prod_ads": {
        "title": "⚡ حزمة كتابة الإعلانات المحترفة (Ad & Content AI)",
        "desc": "صياغة إعلانات فيروسية، وصف منتجات مخصص لزيادة مبيعات المتاجر، وهاشتاجات مستهدفة.",
        "credits": 15,
        "stars": 15,
        "usdt": 2.0
    },
    "prod_ecom": {
        "title": "🛍️ حقيبة تحسين المتاجر وAmazon SEO",
        "desc": "تحليل الكلمات المفتاحية، صياغة قوائم المنتجات، وكتابة عناوين متوافقة مع محركات البحث.",
        "credits": 25,
        "stars": 25,
        "usdt": 3.0
    },
    "prod_agri": {
        "title": "🌱 دليل واستشارات الري الذكي والتسويق الزراعي",
        "desc": "خطط تسويق المعدات الزراعية، أنظمة الري بالرش والمؤقتات الرقمية، واستهداف الأسواق الخليجية.",
        "credits": 40,
        "stars": 40,
        "usdt": 5.0
    }
}

def generate_ai_response(prompt):
    if not GEMINI_API_KEY:
        return "خطأ: لم يتم ضبط مفتاح GEMINI_API_KEY."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    system_instruction = (
        "أنت الوكيل الذكي الخارق لتسويق المنتجات وتوليد النصوص الإعلانية. "
        "قدم استجابات تسويقية واحترافية عالية الجودة باللغة العربية، موجهة لزيادة المبيعات والتحويل."
    )
    payload = {"contents": [{"parts": [{"text": f"{system_instruction}\n\nطلب العميل: {prompt}"}]}]}
    try:
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        return f"عذراً، حدث خطأ أثناء الاتصال بالذكاء الاصطناعي (كود: {res.status_code})."
    except Exception as e:
        return "حدث خطأ في الاتصال بالسيرفر، يرجى المحاولة لاحقاً."

# ==================== الأتمتة المالية (USDT TRC20 Auto-Checker) ====================
async def auto_check_usdt_trc20(context: ContextTypes.DEFAULT_TYPE):
    """فحص تحويلات USDT TRC20 آلياً عبر شبكة TronGrid بمرور الوقت"""
    if not USDT_TRC20_WALLET or USDT_TRC20_WALLET.startswith("ضع_"):
        return

    # استعلام عن تحويلات عقد USDT على TRC20
    url = f"https://api.trongrid.io/v1/accounts/{USDT_TRC20_WALLET}/transactions/trc20?contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t&limit=15"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return
        data = res.json().get("data", [])
        
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()

        for tx in data:
            tx_hash = tx.get("transaction_id")
            to_addr = tx.get("to")
            value_raw = float(tx.get("value", 0)) / 1e6  # USDT يحتوي على 6 خانات عشرية

            # التحقق مما إذا كان التحويل للمحفظة ولم يتم معالجته
            if to_addr == USDT_TRC20_WALLET and tx_hash:
                cursor.execute("SELECT tx_hash FROM processed_txs WHERE tx_hash = ?", (tx_hash,))
                if not cursor.fetchone():
                    # مطابقة القيمة مع الباقات (مثال: 2.0 USDT أو 3.0 USDT أو 5.0 USDT)
                    added_credits = 0
                    if value_raw >= 4.9:
                        added_credits = 40
                    elif value_raw >= 2.9:
                        added_credits = 25
                    elif value_raw >= 1.9:
                        added_credits = 15

                    if added_credits > 0:
                        cursor.execute("INSERT INTO processed_txs VALUES (?)", (tx_hash,))
                        conn.commit()
                        
                        # إشعار الآدمن وتأكيد المعاملة
                        if ADMIN_ID != 0:
                            await context.bot.send_message(
                                chat_id=ADMIN_ID,
                                text=f"💰 **تم استلام دفع USDT TRC20 جديد!**\nالمبلغ: {value_raw} USDT\nالعملية: `{tx_hash}`",
                                parse_mode="Markdown"
                            )
        conn.close()
    except Exception as e:
        logging.error(f"TRC20 Checker Error: {e}")

async def auto_retargeting_job(context: ContextTypes.DEFAULT_TYPE):
    """إرسال عروض تسويقية أوتوماتيكية للمستخدمين الذين استهلكوا رصيدهم"""
    zero_users = get_zero_credit_users()
    keyboard = [
        [InlineKeyboardButton("🛒 استعراض الكتالوج والمنتجات", callback_data="view_catalog")],
        [InlineKeyboardButton("⭐ شحن مباشر بالنجوم", callback_data="buy_stars_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    promo_text = (
        "🔥 **عرض خاص أوتوماتيكي!**\n\n"
        "أنفقت محاولاتك المجانية؟ اشحن حسابك الآن بـ **Telegram Stars** أو **USDT TRC20** "
        "واحصل على رصيد إضافي مضاعف لتوليد الحملات التسويقية والسكريبتات الإعلانية فوراً!"
    )
    for uid in zero_users:
        try:
            await context.bot.send_message(chat_id=uid, text=promo_text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            pass

# ==================== معالجات الأوامر والتفاعل ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    # معالجة نظام الإحالات التلقائي
    if user['is_new'] and context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id != user_id:
            set_referrer(user_id, referrer_id)
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text="🎉 **انضم مستخدم جديد عبر رابطك!**\nتم إضافة 5 محاولات مجانية لحسابك أوتوماتيكياً.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={user_id}"

    keyboard = [
        [InlineKeyboardButton("🛍️ المنتجات والباقات المتاحة", callback_data="view_catalog")],
        [InlineKeyboardButton("⭐ الشحن عبر نجوم تلغرام", callback_data="buy_stars_menu")],
        [InlineKeyboardButton("💎 الشحن بـ USDT TRC20", callback_data="buy_usdt_menu")],
        [InlineKeyboardButton("📊 حسابي ورابط الإحالة", callback_data="my_account")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"مرحباً بك في **الوكيل الذكي الخارق للتسويق والبيع الأوتوماتيكي** 🚀\n\n"
        f"🎁 **رصيدك الحالي:** {user['credits']} محاولات مجانية.\n\n"
        f"🔗 **رابط التسويق بالإحالة الخاص بك:**\n`{referral_link}`\n"
        f"(تحصل على 5 محاولات مجانية فوراً لكل شخص يسجل من خلالك)"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "view_catalog":
        text = "🛍️ **كتالوج المنتجات والخدمات المطلوبة في السوق:**\n\n"
        keyboard = []
        for p_id, p_info in PRODUCTS.items():
            text += f"▪️ **{p_info['title']}**\n{p_info['desc']}\nالسعر: {p_info['stars']} نجمة أو {p_info['usdt']} USDT\n\n"
            keyboard.append([InlineKeyboardButton(f"شراء: {p_info['title']}", callback_data=f"buy_prod_{p_id}")])
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data.startswith("buy_prod_"):
        p_id = query.data.replace("buy_prod_", "")
        p_info = PRODUCTS.get(p_id)
        if p_info:
            keyboard = [
                [InlineKeyboardButton(f"⭐ دفع {p_info['stars']} نجمة", callback_data=f"pay_stars_{p_id}")],
                [InlineKeyboardButton(f"💎 دفع {p_info['usdt']} USDT (TRC20)", callback_data=f"pay_usdt_{p_id}")],
                [InlineKeyboardButton("🔙 الكتالوج", callback_data="view_catalog")]
            ]
            await query.message.reply_text(
                f"اختر طريقة الدفع المناسبة لشراء:\n**{p_info['title']}**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    elif query.data.startswith("pay_stars_") or query.data == "buy_stars_menu":
        amount = 15
        payload = f"stars_purchase_{user_id}"
        if query.data.startswith("pay_stars_"):
            p_id = query.data.replace("pay_stars_", "")
            amount = PRODUCTS[p_id]["stars"]
            payload = f"stars_prod_{p_id}_{user_id}"

        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="شراء رصيد عبر نجوم تلغرام",
            description="شحن أوتوماتيكي ومباشر للرصيد والمحاولات.",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("شراء محاولات", amount)]
        )

    elif query.data.startswith("pay_usdt_") or query.data == "buy_usdt_menu":
        text = (
            f"💎 **الدفع التلقائي عبر عملة USDT (شبكة TRC20):**\n\n"
            f"يرجى تحويل المبلغ المطلوب إلى عنوان المحفظة التالي:\n\n"
            f"`{USDT_TRC20_WALLET}`\n\n"
            f"⚡ **ملاحظة:** يتم فحص الشبكة وتأكيد الشحن أوتوماتيكياً عبر الخادم فور وصول التحويل."
        )
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "my_account":
        user = get_user(user_id)
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        await query.message.reply_text(
            f"📊 **تفاصيل حسابك:**\n\n"
            f"• الرصيد المتبقي: **{user['credits']}** محاولات.\n"
            f"• الإحالات الناجحة: **{user['referrals']}** أصدقاء.\n\n"
            f"🔗 رابط الدعوة للتسويق الفيروسي:\n`{ref_link}`",
            parse_mode="Markdown"
        )

    elif query.data == "main_menu":
        await start(update, context)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload
    
    credits_to_add = 15
    if "prod_ecom" in payload:
        credits_to_add = 25
    elif "prod_agri" in payload:
        credits_to_add = 40

    add_credits(user_id, credits_to_add)
    await update.message.reply_text(
        f"🎉 **تم الدفع بنجاح عبر نجوم تلغرام!**\nتم إضافة **{credits_to_add} محاولة** إلى حسابك تلقائياً.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if user['credits'] <= 0:
        keyboard = [
            [InlineKeyboardButton("🛍️ شراء منتج / باقة جديدة", callback_data="view_catalog")],
            [InlineKeyboardButton("⭐ شحن بنجوم تلغرام", callback_data="buy_stars_menu")]
        ]
        await update.message.reply_text(
            "❌ **نفد رصيد المحاولات الخاص بك!**\nاشحن حسابك للوصول للخدمات والذكاء الاصطناعي:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if deduct_credit(user_id):
        wait_msg = await update.message.reply_text("⏳ جاري توليد المحتوى والتنفيذ بالذكاء الاصطناعي...")
        ai_res = generate_ai_response(update.message.text)
        rem = get_user(user_id)['credits']
        await wait_msg.edit_text(f"{ai_res}\n\n---\n🎯 *المتبقي في رصيدك: {rem} محاولات.*", parse_mode="Markdown")

# ==================== لوحة الآدمن للتسويق المباشر ====================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or ADMIN_ID == 0:
        return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("اكتب الرسالة بعد الأمر: `/broadcast رسالتك التسويقية`", parse_mode="Markdown")
        return
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ تم البث بنجاح إلى {sent} مستخدم.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or ADMIN_ID == 0:
        return
    users = get_all_users()
    zero_users = get_zero_credit_users()
    await update.message.reply_text(
        f"📊 **إحصائيات الوكيل الخارق:**\n\n"
        f"• المستخدمين الكليين: **{len(users)}**\n"
        f"• المستهلكين كامل رصيدهم: **{len(zero_users)}**\n"
        f"• المستخدمين النشطين: **{len(users) - len(zero_users)}**",
        parse_mode="Markdown"
    )

# ==================== التشغيل والجدولة ====================
def main():
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()

    if not BOT_TOKEN or not GEMINI_API_KEY:
        raise RuntimeError("مفاتيح TELEGRAM_BOT_TOKEN و GEMINI_API_KEY مطلوبة للتشغيل.")

    app_bot = Application.builder().token(BOT_TOKEN).build()

    # المهام الأوتوماتيكية المجدولة
    job_queue = app_bot.job_queue
    if job_queue:
        job_queue.run_repeating(auto_check_usdt_trc20, interval=60, first=10)   # فحص USDT TRC20 كل 60 ثانية
        job_queue.run_repeating(auto_retargeting_job, interval=86400, first=3600) # التسويق والتذكير التلقائي كل 24 ساعة

    # التسجيل
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("broadcast", broadcast))
    app_bot.add_handler(CommandHandler("stats", stats))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 الوكيل الخارق جاهز ويعمل باستقلالية كاملة 100%...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
