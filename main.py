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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8322155608:AAGet4B90AjDjntI5E-sz9f4od3ud_x2Vdo")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LJZH5uY_-3KWMlyis3gXUyruGbSv0e866peA30LjeYWg")
USDT_WALLET_ADDRESS = os.environ.get("USDT_WALLET_ADDRESS", "TE9je7QpBfLpG6pduWdyv7RqVz8vUZjWUX")
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY", "bd404b0a-d24b-403c-9921-e1309111f04a")

# ==================== سيرفر ويب لـ UptimeRobot و OpenAPI ====================
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
            "description": "API for automated AI marketing content generation and B2B agent integration."
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
    system_instruction = (
        "You are an elite AI Chief Marketing Officer (CMO) and Copywriting Master fluent in Arabic and English.\n"
        "Your mission is to deliver high-converting, viral, and ultra-persuasive marketing content."
    )
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
    return "عذراً، حدث خطأ أثناء إعداد المحتوى التسويقي."

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
        f"🚀 **مرحباً بك في الوكيل التسويقي الذكي الشامل!**\n"
        f"🚀 **Welcome to the Ultimate AI Marketing Agent!**\n\n"
        f"🎁 **رصيدك الحالي / Your Credits:** {user_data['credits']} محاولات مجانية.\n\n"
        f"💡 **ماذا يمكنني أن أفعل لك؟ / Capabilities:**\n"
        f"• 🎯 صياغة إعلانات ممولة احترافية (FB / IG / TikTok).\n"
        f"• 🎥 كتابة سيناريو فيديو قصير (Reels / TikTok).\n"
        f"• 📦 وصف منتجات يزيد المبيعات.\n"
        f"• 📅 خطط محتوى واستراتيجيات نمو.\n"
        f"• 🖼️ **تحليل صور المنتجات آلياً** (أرسل صورة المنتج مباشرة!).\n"
        f"• 🤝 **عرض شراكة B2B** (عبر أمر `/pitch <وصف الخدمة>`).\n\n"
        f"🔗 **رابط الإحالة (احصل على 5 نقاط لكل صديق):**\n`{referral_link}`"
    )

    keyboard = [
        [InlineKeyboardButton("🎯 إعلان ممول | Paid Ad", callback_data="tmpl_ad"), InlineKeyboardButton("🎥 سيناريو فيديو | Video Script", callback_data="tmpl_script")],
        [InlineKeyboardButton("📦 وصف منتج | Product Description", callback_data="tmpl_product"), InlineKeyboardButton("📅 خطة محتوى | Content Strategy", callback_data="tmpl_strategy")],
        [InlineKeyboardButton("💳 شراء رصيد | Buy Credits", callback_data="buy_credits"), InlineKeyboardButton("📊 رصيدي | My Account", callback_data="check_status")]
    ]
    await safe_reply(update.message, welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def pitch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_description = " ".join(context.args)
    if not service_description:
        await update.message.reply_text("⚠️ أرسل وصف الخدمة بجانب الأمر.\nمثال: `/pitch توليد محتوى تسويقي تلقائي`")
        return
    prompt = f"قم بصياغة رسالة تسويقية احترافية B2B لعرض التكامل التقني للخدمة التالية: {service_description}"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, timeout=25)
        if res.status_code == 200:
            ai_text = res.json()['candidates'][0]['content']['parts'][0]['text']
            await update.message.reply_text(f"🤖 **مقترح الشراكة B2B:**\n\n{ai_text}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ حدث خطأ أثناء الاتصال بمحرك الذكاء الاصطناعي.")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if user_data['credits'] <= 0:
        await safe_reply(update.message, "⚠️ نفد رصيدك الحالي! يرجى الشراء أو دعوة الأصدقاء.")
        return
    status_msg = await update.message.reply_text("🧠 جاري التفكير وصياغة المحتوى بأعلى معايير التسويق... ⏳")
    ai_result = generate_ai_response(update.message.text)
    update_credits(user_id, -1)
    await safe_edit(status_msg, f"{ai_result}\n\n---\n✅ **تم خصم نقطة.** الرصيد المتبقي: {user_data['credits'] - 1}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if user_data['credits'] <= 0:
        await update.message.reply_text("⚠️ نفد رصيدك! قم بالشراء أو دعوة الأصدقاء لاستخدام خدمة تحليل الصور.")
        return
    status_msg = await update.message.reply_text("🖼️ جاري فحص صورة المنتج وتحليل أبعادها التسويقية... ⏳")
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    caption_text = update.message.caption or "قم بتحليل هذا المنتج وصياغة إعلان تسويقي ممتاز له."
    ai_result = generate_ai_response(caption_text, image_bytes=image_bytes)
    update_credits(user_id, -1)
    await safe_edit(status_msg, f"{ai_result}\n\n---\n✅ **تم تحليل الصورة وخصم نقطة.** الرصيد المتبقي: {user_data['credits'] - 1}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy_credits":
        pay_text = "💳 **اختر طريقة الدفع المناسبة لشحن رصيدك:**\n\n🌟 نجوم تلغرام\n💎 USDT (TRC20)"
        keyboard = [
            [InlineKeyboardButton("⭐ شراء بـ 250 نجمة (100 محاولة)", callback_data="buy_stars")],
            [InlineKeyboardButton("💎 شراء عبر USDT", callback_data="buy_usdt")]
        ]
        await safe_reply(query.message, pay_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "buy_stars":
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="100 محاولة استخدام",
            description="شحن رصيد الوكيل التسويقي الذكي بـ 100 محاولة.",
            payload="credits_pack_100",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("100 محاولة", 250)]
        )

    elif query.data == "buy_usdt":
        pay_text = f"💳 **عنوان محفظة USDT (TRC20):**\n`{USDT_WALLET_ADDRESS}`\n\n⚠️ بعد التحويل أرسل رقم المعاملة (TXID)."
        await safe_reply(query.message, pay_text)

    elif query.data == "check_status":
        user_data = get_user(query.from_user.id)
        await safe_reply(query.message, f"📊 **حالة الحساب:**\n\n• الرصيد المتبقي: {user_data['credits']} محاولات.\n• الإحالات: {user_data['referrals']} أصدقاء.")

    elif query.data.startswith("tmpl_"):
        prompts = {
            "tmpl_ad": "اكتب إعلان ممول جذاب جداً على منصة فيسبوك/انستغرام لمنتج [اكتب اسم منتجك وسعره هنا].",
            "tmpl_script": "اكتب سيناريو فيديو قصير (Reels/TikTok) مدته 30 ثانية لمنتج [اكتب اسم المنتج].",
            "tmpl_product": "اكتب وصف منتج احترافي ومحفز للشراء لمتجر إلكتروني لمنتج [اكتب اسم المنتج].",
            "tmpl_strategy": "ضع خطة محتوى أسبوعية (7 أيام) لمنصة انستغرام وتيك توك لمتجر متخصص في [اكتب مجال متجرك]."
        }
        chosen_prompt = prompts.get(query.data, "")
        await safe_reply(query.message, f"💡 **تفضل بنسخ هذا القالب وتعديل ما بين القوسين ثم إرساله لي:**\n\n`{chosen_prompt}`")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "credits_pack_100":
        await query.answer(ok=False, error_message="حدث خطأ في عملية الشراء.")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_credits(user_id, 100)
    await safe_reply(update.message, "🎉 **تمت عملية الشراء بنجاح!** تمت إضافة 100 نقطة إلى حسابك.")

def main():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("pitch", pitch_command))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 الوكيل التسويقي المتكامل وسيرفر الويب يعملان بنجاح تام...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
