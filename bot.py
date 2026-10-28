import os
import re
import html
import logging
from io import BytesIO
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

app = Flask(__name__)
telegram_app = Application.builder().token(TOKEN).build()

def extract_links(raw_html: str):
    soup = BeautifulSoup(raw_html, "html.parser")
    videos, pdfs = [], []
    seen_video, seen_pdf = set(), set()

    # Links in anchors
    for a in soup.find_all("a", href=True):
        url = html.unescape(a["href"].strip())
        if not url.startswith(("https://", "http://")):
            continue
        title = a.get_text(" ", strip=True) or url
        low_url, low_title = url.lower(), title.lower()

        is_pdf = ".pdf" in low_url or any(x in low_title for x in ("pdf", "notes", "slides"))
        is_video = (
            bool(re.search(r"\.(mp4|m3u8|webm)(?:$|[?#])", low_url))
            or any(x in low_title for x in ("video", "lecture", "watch", "play"))
            or any(x in low_url for x in ("youtube.com", "youtu.be", "vimeo.com"))
        )

        if is_pdf and url not in seen_pdf:
            pdfs.append((title, url))
            seen_pdf.add(url)
        elif is_video and url not in seen_video:
            videos.append((title, url))
            seen_video.add(url)

    # Explicit PDF/video URLs sometimes appear as plain text in the page.
    for raw_url in re.findall(r'https?://[^\s"\'<>]+', raw_html):
        url = html.unescape(raw_url).rstrip("),;]")
        low_url = url.lower()
        if ".pdf" in low_url and url not in seen_pdf:
            pdfs.append((url.rsplit("/", 1)[-1], url))
            seen_pdf.add(url)
        elif re.search(r"\.(mp4|m3u8|webm)(?:$|[?#])", low_url) and url not in seen_video:
            videos.append((url.rsplit("/", 1)[-1], url))
            seen_video.add(url)

    return videos, pdfs

async def send_pdf(context: ContextTypes.DEFAULT_TYPE, chat_id: int, title: str, url: str):
    response = requests.get(
        url,
        timeout=75,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    data = response.content
    content_type = response.headers.get("Content-Type", "").lower()
    if not data.startswith(b"%PDF") and "pdf" not in content_type:
        raise ValueError("URL se PDF file nahi mili; link login-protected ho sakta hai.")

    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._") or "document"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    file_obj = BytesIO(data)
    file_obj.name = filename
    await context.bot.send_document(
        chat_id=chat_id,
        document=file_obj,
        filename=filename,
        caption=title[:900],
    )

async def handle_html(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    document = message.document
    if not document or not (document.file_name or "").lower().endswith((".html", ".htm")):
        await message.reply_text("HTML file (.html/.htm) bhejo. Main video links aur PDF extract karunga.")
        return

    status = await message.reply_text("HTML receive hua. Links extract kar raha hoon…")
    try:
        tg_file = await context.bot.get_file(document.file_id)
        downloaded = await tg_file.download_as_bytearray()
        raw_html = bytes(downloaded).decode("utf-8", errors="replace")
        videos, pdfs = extract_links(raw_html)

        if not videos and not pdfs:
            await status.edit_text("Is HTML mein recognized video/PDF links nahi mile.")
            return

        await status.edit_text(f"Mil gaya: {len(videos)} video link(s), {len(pdfs)} PDF(s). Sending shuru…")

        for idx, (title, url) in enumerate(videos, 1):
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"▶️ {title}\n{url}",
                    disable_web_page_preview=True,
                )
            except Exception as exc:
                logger.exception("Could not send video URL")
                await context.bot.send_message(chat_id=user.id, text=f"Video link send nahi hua: {title}\n{exc}")

        for idx, (title, url) in enumerate(pdfs, 1):
            try:
                await send_pdf(context, user.id, title, url)
            except Exception as exc:
                logger.exception("Could not upload PDF")
                await context.bot.send_message(chat_id=user.id, text=f"PDF upload fail: {title}\n{exc}")

        await context.bot.send_message(
            chat_id=user.id,
            text=f"Done! {len(videos)} video link(s) aur {len(pdfs)} PDF link(s) process kiye.",
        )
    except Exception as exc:
        logger.exception("HTML processing failed")
        await status.edit_text(f"HTML process nahi ho paya: {exc}")

telegram_app.add_handler(MessageHandler(filters.Document.ALL, handle_html))

@app.get("/")
def health():
    return "Telegram HTML bot is running.", 200

@app.post("/telegram-webhook")
def webhook():
    if WEBHOOK_SECRET:
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if supplied != WEBHOOK_SECRET:
            return jsonify({"ok": False, "error": "unauthorized"}), 403

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    # Run update handler in the current async app loop.
    import asyncio
    asyncio.run(telegram_app.process_update(update))
    return jsonify({"ok": True})

if __name__ == "__main__":
    import asyncio

    async def initialize():
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/telegram-webhook",
            secret_token=WEBHOOK_SECRET or None,
            allowed_updates=["message"],
        )

    asyncio.run(initialize())
    app.run(host="0.0.0.0", port=PORT)
