import os
import asyncio
import requests
import feedparser
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
scheduler = AsyncIOScheduler()

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

# ==== تحليل صفحة الحلقة للحصول على الحجم والفئة والترجمة ====
def parse_episode_page(link):
    try:
        r = requests.get(link, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")

        # الحجم
        size_elem = soup.find("td", string="Size:")
        size = size_elem.find_next_sibling("td").text if size_elem else "غير معروف"

        # الفئة
        cat_elem = soup.find("td", string="Category:")
        category = cat_elem.find_next_sibling("td").text if cat_elem else "غير معروف"

        # الترجمة العربية
        arabic = "نعم" if "Arabic" in soup.get_text() else "لا"

        return size, category, arabic
    except:
        return "غير معروف", "غير معروف", "لا"

# ==== فحص RSS ====
async def check_rss(app: ApplicationBuilder):
    global sent_items, chat_id_global
    if not chat_id_global:
        return

    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        if entry.id not in sent_items:
            sent_items.add(entry.id)

            # رابط صفحة الحلقة
            episode_link = f"https://nyaa.si/view/{entry.id.split('/')[-1]}"

            # البحث عن magnet
            magnet = None
            for l in entry.links:
                if l.type == "application/x-bittorrent" or "magnet:?" in l.href:
                    magnet = l.href

            # استخراج معلومات إضافية من صفحة الحلقة
            size, category, arabic = parse_episode_page(episode_link)

            # إنشاء الأزرار
            buttons = []
            if magnet:
                buttons.append(InlineKeyboardButton("📥 رفع على EasyVidPlay", callback_data=f"upload|{magnet}"))
                buttons.append(InlineKeyboardButton("🧲 نسخ رابط Magnet", url=magnet))
            keyboard = InlineKeyboardMarkup([buttons]) if buttons else None

            # نص الرسالة
            text = (
                f"🎬 *{entry.title}*\n"
                f"📄 [صفحة الحلقة على Nyaa]({episode_link})\n"
                f"💾 الحجم: {size}\n"
                f"📂 الفئة: {category}\n"
                f"🇸🇦 ترجمة عربية: {arabic}"
            )

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

# ==== /start ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id_global
    chat_id_global = update.effective_chat.id
    await update.message.reply_text("🚀 بدأ البوت بمراقبة Nyaa كل دقيقة...")

    # تشغيل الجدولة
    if not scheduler.running:
        scheduler.add_job(lambda: asyncio.create_task(check_rss(context.application)), "interval", minutes=1)
        scheduler.start()

# ==== main ====
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()
