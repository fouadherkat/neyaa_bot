import os
import asyncio
import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN")
RSS_URL = "https://nyaa.si/?page=rss&c=1_2&f=0"

sent_items = set()
chat_id_global = None
scheduler = AsyncIOScheduler()

async def check_rss(app):
    global sent_items, chat_id_global
    if not chat_id_global:
        return

    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        if entry.id not in sent_items:
            sent_items.add(entry.id)
            text = f"🎬 *{entry.title}*\n🔗 [صفحة الحلقة على Nyaa]({entry.link})"
            await app.bot.send_message(chat_id=chat_id_global, text=text, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id_global
    chat_id_global = update.effective_chat.id
    await update.message.reply_text("🚀 بدأ البوت بمراقبة Nyaa كل دقيقة...")

    # تشغيل الجدولة فقط مرة واحدة
    if not scheduler.running:
        scheduler.add_job(lambda: asyncio.ensure_future(check_rss(context.application)), "interval", minutes=1)
        scheduler.start()

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
