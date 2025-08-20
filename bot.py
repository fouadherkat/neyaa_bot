import os
import asyncio
import requests
import feedparser
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ==== التوكنات من Environment Variables ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
EASYVIDPLAY_TOKEN = os.getenv("EASYVIDPLAY_TOKEN")

EASYVIDPLAY_API = "https://easyvidplay.com/api/video"
RSS_URL = "https://nyaa.si/?page=rss&c=1_2&f=0"

# ==== تخزين الحلقات المرسلة ====
sent_items = set()
chat_id_global = None
scheduler = BackgroundScheduler()

# ==== رفع للسيرفر ====
def upload_to_server(magnet_link: str):
    headers = {"Authorization": f"Bearer {EASYVIDPLAY_TOKEN}"}
    data = {"url": magnet_link}
    try:
        r = requests.post(EASYVIDPLAY_API, headers=headers, json=data, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            return {"error": r.text}
    except Exception as e:
        return {"error": str(e)}

# ==== فحص RSS ====
async def check_rss(app: ApplicationBuilder):
    global sent_items, chat_id_global
    if not chat_id_global:
        return

    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries[:5]:  # آخر 5 حلقات
        if entry.link not in sent_items:
            sent_items.add(entry.link)

            # البحث عن Magnet
            magnet = None
            if hasattr(entry, "links"):
                for l in entry.links:
                    if "magnet:?" in l.href:
                        magnet = l.href
                        break

            # حجم الحلقة (إن وجد)
            size = getattr(entry, "nyaa_size", None)
            if not size:
                # محاولة استخراج الحجم من الوصف
                if hasattr(entry, "description"):
                    import re
                    match = re.search(r'Size:\s*([^\n<]+)', entry.description)
                    if match:
                        size = match.group(1)

            # الترجمة العربية
            arabic_sub = "نعم" if "[Arabic]" in entry.title or "[Ar]" in entry.title else "لا"

            # إعداد الأزرار
            buttons = []
            if magnet:
                buttons.append([
                    InlineKeyboardButton("📥 رفع على EasyVidPlay", callback_data=f"upload|{magnet}"),
                    InlineKeyboardButton("🔗 نسخ رابط Magnet", callback_data=f"copy|{magnet}")
                ])
            buttons.append([InlineKeyboardButton("🌐 صفحة الحلقة على Nyaa", url=entry.link)])
            keyboard = InlineKeyboardMarkup(buttons)

            # نص الرسالة
            text = f"🎬 *{entry.title}*\n"
            if size:
                text += f"💾 الحجم: {size}\n"
            text += f"🈶 ترجمة عربية: {arabic_sub}\n"
            text += f"🔗 [رابط Nyaa]({entry.link})"

            await app.bot.send_message(
                chat_id=chat_id_global,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

# ==== عند الضغط على زر ====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("upload|"):
        magnet = data.split("|", 1)[1]
        result = upload_to_server(magnet)
        if "error" in result:
            await query.edit_message_text(f"❌ فشل الرفع: {result['error']}")
        else:
            stream_url = result.get("url") or str(result)
            await query.edit_message_text(f"✅ تم الرفع بنجاح!\n{stream_url}")

    elif data.startswith("copy|"):
        magnet = data.split("|", 1)[1]
        await query.edit_message_text(f"🔗 رابط Magnet:\n`{magnet}`", parse_mode="Markdown")

# ==== /start ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id_global
    chat_id_global = update.effective_chat.id
    await update.message.reply_text("🚀 بدأ البوت بمراقبة Nyaa كل دقيقة...")

    # تشغيل الجدولة
    if not scheduler.running:
        scheduler.start()
        scheduler.add_job(lambda: asyncio.run(check_rss(context.application)), "interval", minutes=1)

# ==== main ====
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()
