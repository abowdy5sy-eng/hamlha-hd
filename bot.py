import os
import re
import tempfile
import logging
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_SIZE = 49 * 1024 * 1024

WELCOME = """
🎬 أهلاً بك في بوت حمّلها HD

أرسل رابط الفيديو وسأحاول تحميله بأفضل جودة متاحة.

المنصات المدعومة تعتمد على المواقع التي يدعمها yt-dlp.

⚠️ استخدم البوت للمحتوى الذي تملكه أو لديك إذن بتنزيله.
"""

def valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📥 طريقة الاستخدام:\n"
        "1- انسخ رابط الفيديو.\n"
        "2- أرسله هنا.\n"
        "3- انتظر تجهيز الملف.\n\n"
        "يمكنك إرسال رابط واحد في كل مرة."
    )


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not valid_url(url):
        await update.message.reply_text("❌ الرابط غير صحيح.")
        return

    status = await update.message.reply_text(
        "⏳ جارٍ فحص الرابط وتجهيز الفيديو..."
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = str(Path(temp_dir) / "video.%(ext)s")

            options = {
                "format": (
                    "best[ext=mp4][filesize<49000000]/"
                    "best[filesize<49000000]/best[ext=mp4]/best"
                ),
                "outtmpl": output,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "retries": 2,
                "max_filesize": MAX_SIZE,
            }

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "video")
                ydl.download([url])

            files = list(Path(temp_dir).glob("video.*"))

            if not files:
                raise Exception("لم يتم العثور على ملف الفيديو.")

            video_path = files[0]

            if video_path.stat().st_size > MAX_SIZE:
                await status.edit_text(
                    "⚠️ حجم الفيديو أكبر من الحد المسموح به في البوت."
                )
                return

            await status.edit_text("📤 تم التحميل، جارٍ إرسال الفيديو...")

            with open(video_path, "rb") as video:
                await update.message.reply_document(
                    document=video,
                    filename="HamlhaHD.mp4",
                    caption=f"✅ {title}\n\nتم التحميل بواسطة حمّلها HD"
                )

            await status.delete()

    except Exception as error:
        logging.exception("Download error")
        await status.edit_text(
            "❌ تعذر تحميل الفيديو.\n"
            "قد يكون الرابط غير مدعوم أو يتطلب صلاحيات خاصة، "
            "أو أن حجم الفيديو كبير."
        )


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, download_video)
    )

    print("Hamlha HD Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
