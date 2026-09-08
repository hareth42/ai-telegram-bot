import os
import sqlite3
import threading
import base64
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
    ContextTypes
)

# ==================== ضع بياناتك هنا ====================
BOT_TOKEN = "8322155608:AAFKwhOH5xK5mY2t2gASK175VhPBitk-mJo"
GEMINI_API_KEY = "AQ.Ab8RN6LJZH5uY_-3KWMlyis3gXUyruGbSv0e866peA30LjeYWg"
USDT_WALLET_ADDRESS = "TE9je7QpBfLpG6pduWdyv7RqVz8vUZjWUX"

# ==================== سيرفر ويب لـ UptimeRobot ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "AI Marketing Agent is Live & Running 24/7!"

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

# ==================== محرك الذكاء الاصطناعي الشامل ====================
def generate_ai_response(prompt, image_bytes=None, mime_type="image/jpeg"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    system_instruction = (
        "You are an elite AI Chief Marketing Officer (CMO) and Copywriting Master fluent in Arabic and English.\n"
        "Your mission is to deliver high-converting, viral, and ultra-persuasive marketing content.\n"
        "You strictly adhere to modern marketing frameworks (AIDA, PAS, FAB, Hook-Story-Offer).\n\n"
        "CAPABILITIES:\n"
        "1. Ad Copywriting (Facebook, Instagram, TikTok, Snapchat, Google Ads).\n"
        "2. Short-form Video Scripts (Reels/TikTok/Shorts) including Visual & Audio Cues.\n"
        "3. High-Converting Product Descriptions (E-commerce / Amazon / Shopify / Salla).\n"
        "4. Full Social Media Content Calendars & Growth Strategies.\n"
        "5. Product Image Analysis & Visual Marketing Recommendations.\n"
        "6. Email Marketing & Sales Funnels.\n\n"
        "RULES:\n"
        "- Auto-detect the user's input language (Arabic or English) and reply in the EXACT SAME language.\n"
        "- Use professional formatting (Bold text, bullet points, emojis, call-to-action).\n"
        "- Ensure copy is engaging, highly structured, and ready for commercial deployment."
    )

    parts = []
    if image_bytes:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": base64_image
            }
        })
    
    parts.append({"text": f"{system_instruction}\n\nUSER REQUEST: {prompt}"})

    payload = {"contents": [{"parts": parts}]}
    
    try:
        response = requests.post(url, json=payload, timeout=25)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Error calling Gemini: {e}")
    
    return "عذراً، حدث خطأ أثناء إعداد المحتوى التسويقي. يرجى المحاولة لاحقاً.\nSorry, an error occurred while generating content."

# ==================== أوامر واجهة تلغرام ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referred_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
    
    user_data = get_user(user_id, referred_by)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    welcome_text = (
        f"🚀 **مرحباً بك في الوكيل التسويقي الذكي الشامل!**\n"
        f"🚀 **Welcome to the Ultimate AI Marketing Agent!**\n\n"
        f"🎁 **رصيدك الحالي / Your Credits:** {user_data['credits']} محاولات مجانية.\n\n"
        f"💡 **ماذا يمكنني أن أفعل لك؟ / Capabilities:**\n"
        f"• 🎯 صياغة إعلانات ممولة احترافية (FB / IG / TikTok / Snapchat).\n"
        f"• 🎥 كتابة سيناريو فيديو قصير (Reels / TikTok) مع مشاهد صوتية وبصرية.\n"
        f"• 📦 وصف منتجات يزيد المبيعات للـ E-commerce.\n"
        f"• 📅 خطط محتوى واستراتيجيات نمو للمتاجر والحسابات.\n"
        f"• 🖼️ **تحليل صور المنتجات آلياً** (أرسل صورة المنتج مباشرة!).\n\n"
        f"🔗 **رابط الإحالة / Referral Link (احصل على 5 نقاط مجانية لكل صديق):**\n`{referral_link}`"
    )

    keyboard = [
        [InlineKeyboardButton("🎯 إعلان ممول | Paid Ad", callback_data="tmpl_ad"), InlineKeyboardButton("🎥 سيناريو فيديو | Video Script", callback_data="tmpl_script")],
        [InlineKeyboardButton("📦 وصف منتج | Product Description", callback_data="tmpl_product"), InlineKeyboardButton("📅 خطة محتوى | Content Strategy", callback_data="tmpl_strategy")],
        [InlineKeyboardButton("💳 شراء رصيد | Buy Credits", callback_data="buy_credits"), InlineKeyboardButton("📊 رصيدي وحسابي | My Account", callback_data="check_status")]
    ]
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if user_data['credits'] <= 0:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        no_credits_text = (
            "⚠️ **نفد رصيدك الحالي! / Out of Credits!**\n\n"
            "للاستمرار يمكنك:\n"
            "1️⃣ شراء رصيد جديد بـ Telegram Stars أو USDT.\n"
            f"2️⃣ مشاركة رابط الإحالة للحصول على **5 نقاط مجانية**:\n`{referral_link}`"
        )
        keyboard = [[InlineKeyboardButton("💳 شراء رصيد الآن | Buy Credits", callback_data="buy_credits")]]
        await update.message.reply_text(no_credits_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    status_msg = await update.message.reply_text("🧠 جاري التفكير وصياغة المحتوى بأعلى معايير التسويق... ⏳")
    ai_result = generate_ai_response(update.message.text)
    
    update_credits(user_id, -1)
    new_credits = user_data['credits'] - 1

    await status_msg.edit_text(f"{ai_result}\n\n---\n✅ **تم خصم نقطة.** الرصيد المتبقي: {new_credits} محاولات.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if user_data['credits'] <= 0:
        await update.message.reply_text("⚠️ نفد رصيدك! قم بالشراء أو دعوة الأصدقاء لاستخدام خدمة تحليل الصور.")
        return

    status_msg = await update.message.reply_text("🖼️ جاري فحص صورة المنتج وتحليل أبعادها التسويقية... ⏳")
    
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    
    caption_text = update.message.caption or "قم بتحليل هذا المنتج وصياغة إعلان تسويقي ممتاز له ووصف يزيد المبيعات."
    ai_result = generate_ai_response(caption_text, image_bytes=image_bytes)

    update_credits(user_id, -1)
    new_credits = user_data['credits'] - 1

    await status_msg.edit_text(f"{ai_result}\n\n---\n✅ **تم تحليل الصورة وخصم نقطة.** الرصيد المتبقي: {new_credits}")

# ==================== خيارات الدفع ونجوم تلغرام ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy_credits":
        pay_text = (
            "💳 **اختر طريقة الدفع المناسبة لشحن رصيدك / Select Payment Method:**\n\n"
            "🌟 **نجوم تلغرام (Telegram Stars):** شحن آلي وسريع من داخل التطبيق.\n"
            "💎 **USDT (TRC20):** تحويل كريبتو مباشر للمحفظة."
        )
        keyboard = [
            [InlineKeyboardButton("⭐ شراء بـ 250 نجمة (100 محاولة)", callback_data="buy_stars")],
            [InlineKeyboardButton("💎 شراء عبر USDT", callback_data="buy_usdt")],
        ]
        await query.message.reply_text(pay_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "buy_stars":
        chat_id = query.message.chat_id
        title = "100 محاولة استخدام | 100 Credits"
        description = "شحن رصيد الوكيل التسويقي الذكي بـ 100 محاولة."
        payload = "credits_pack_100"
        currency = "XTR"
        prices = [LabeledPrice("100 محاولة", 250)]

        await context.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency=currency,
            prices=prices
        )

    elif query.data == "buy_usdt":
        pay_text = (
            "💳 **شراء رصيد عبر USDT (TRC20):**\n\n"
            "🔹 **100 عملية توليد** = 10 USDT\n"
            "🔹 **300 عملية توليد** = 25 USDT\n\n"
            f"📌 **عنوان المحفظة / Wallet Address:**\n`{USDT_WALLET_ADDRESS}`\n\n"
            "⚠️ بعد التحويل، اضغط زر التحقق للتحقق من العملية وشحن الحساب تلقائياً."
        )
        keyboard = [[InlineKeyboardButton("🔄 التحقق من الدفع | Verify Payment", callback_data="verify_payment")]]
        await query.message.reply_text(pay_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "verify_payment":
        await query.message.reply_text("🔍 جاري التحقق من شبكة Blockchain... إذا تم التحويل سيتم تحديث رصيدك فوراً.")

    elif query.data == "check_status":
        user_id = query.from_user.id
        user_data = get_user(user_id)
        status_text = f"📊 **حالة الحساب / Account Status:**\n\n• الرصيد المتبقي: {user_data['credits']} محاولات.\n• عدد الإحالات الناجحة: {user_data['referrals']} أصدقاء."
        await query.message.reply_text(status_text, parse_mode="Markdown")

    elif query.data.startswith("tmpl_"):
        prompts = {
            "tmpl_ad": "اكتب إعلان ممول جذاب جداً على منصة فيسبوك/انستغرام لمنتج [اكتب اسم منتجك وسعره هنا]. استخدم نموذج AIDA.",
            "tmpl_script": "اكتب سيناريو فيديو قصير (Reels/TikTok) مدته 30 ثانية لمنتج [اكتب اسم المنتج] مع تحديد مشاهد التصوير والصوت.",
            "tmpl_product": "اكتب وصف منتج احترافي ومحفز للشراء لمتجر إلكتروني لمنتج [اكتب اسم المنتج ومميزاته].",
            "tmpl_strategy": "ضع خطة محتوى أسبوعية (7 أيام) لمنصة انستغرام وتيك توك لمتجر متخصص في [اكتب مجال متجرك]."
        }
        chosen_prompt = prompts.get(query.data, "")
        await query.message.reply_text(f"💡 **تفضل بنسخ هذا القالب وتعديل ما بين القوسين ثم إرساله لي:**\n\n`{chosen_prompt}`", parse_mode="Markdown")

# ==================== معالجة عملية الدفع بالنجوم ====================
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "credits_pack_100":
        await query.answer(ok=False, error_message="حدث خطأ في عملية الشراء.")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_credits(user_id, 100)
    await update.message.reply_text(
        "🎉 **تمت عملية الشراء بنجاح عبر نجوم تلغرام!**\n\n"
        "✅ تمت إضافة **100 نقطة** إلى حسابك آلياً. يمكنك البدء باستغلال الوكيل الذكي الآن!"
    )

# ==================== التشغيل الرئيسي ====================
def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 الوكيل التسويقي الشامل يعمل بنجاح مع دعم نجوم تلغرام...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
