import os
import tempfile
import logging
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

CHANNEL = "@erred33"
CHANNEL_LINK = "https://t.me/erred33"

MAX_SIZE = 49 * 1024 * 1024

WELCOME = """
🎬 أهلاً بك في بوت حمّلها HD

أرسل رابط الفيديو وسأحاول تحميله بأفضل جودة متاحة.

⚠️ استخدم البوت للمحتوى الذي تملكه أو لديك إذن بتنزيله.
"""


def valid_url(url):
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )
    except Exception:
        return False


def subscription_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 اشترك في القناة",
                url=CHANNEL_LINK
            )
        ],
        [
            InlineKeyboardButton(
                "✅ تحقق من الاشتراك",
                callback_data="check_subscription"
            )
        ]
    ])


async def is_subscribed(user_id, context):
    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL,
            user_id=user_id
        )

        return (
            member.status in ("creator", "administrator", "member")
            or (
                member.status == "restricted"
                and member.is_member
            )
        )

    except Exception:
        logging.exception("Subscription check failed")
        return False


async def require_subscription(update, context):
    user_id = update.effective_user.id

    if await is_subscribed(user_id, context):
        return True

    message = (
        "🔒 عذراً! لا يمكنك استخدام بوت حمّلها HD قبل الاشتراك.\n\n"
        "📢 اشترك في قناتنا أولاً، ثم اضغط تحقق من الاشتراك."
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(
            message,
            reply_markup=subscription_keyboard()
        )
    else:
        await update.effective_message.reply_text(
            message,
            reply_markup=subscription_keyboard()
        )

    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_subscription(update, context):
        return

    await update.message.reply_text(WELCOME)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_subscription(update, context):
        return

    await update.message.reply_text(
        "📥 طريقة الاستخدام:\n\n"
        "1- انسخ رابط الفيديو.\n"
        "2- أرسله هنا.\n"
        "3- انتظر تجهيز الملف.\n\n"
        "يمكنك إرسال رابط واحد في كل مرة."
    )


async def check_subscription(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    if await is_subscribed(query.from_user.id, context):
        await query.edit_message_text(
            "✅ تم التحقق من اشتراكك بنجاح!\n\n"
            "🎬 يمكنك الآن استخدام بوت حمّلها HD.\n"
            "أرسل رابط الفيديو للبدء."
        )
    else:
        await query.answer(
            "❌ لم يتم العثور على اشتراكك بعد.",
            show_alert=True
        )


async def download_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await require_subscription(update, context):
        return

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
                "socket_timeout": 60,
                "retries": 5,
                "fragment_retries": 5,
                "max_filesize": MAX_SIZE,
                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.0.0 Safari/537.36"
                    )
                },
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
                    "⚠️ حجم الفيديو أكبر من الحد المسموح به."
                )
                return

            await status.edit_text(
                "📤 تم التحميل، جارٍ إرسال الفيديو..."
            )

            with open(video_path, "rb") as video:
                await update.message.reply_document(
                    document=video,
                    filename="HamlhaHD.mp4",
                    caption=f"✅ {title}\n\nتم التحميل بواسطة حمّلها HD"
                )

            await status.delete()

    except yt_dlp.utils.DownloadError:
        logging.exception("yt-dlp download error")
        await status.edit_text(
            "❌ تعذر تحميل الفيديو من المصدر.\n"
            "قد تكون المنصة غيّرت طريقة الوصول أو أن الرابط غير متاح."
        )

    except Exception:
        logging.exception("Download error")
        await status.edit_text(
            "❌ تعذر تحميل الفيديو.\n"
            "قد يكون حجم الفيديو كبيراً أو أن الرابط غير مدعوم."
        )


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        CallbackQueryHandler(
            check_subscription,
            pattern="^check_subscription$"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            download_video
        )
    )

    print("Hamlha HD Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
