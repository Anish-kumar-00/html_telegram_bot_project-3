# Personal HTML → Telegram Bot (Webhook)

Send an `.html` or `.htm` document to your Telegram bot in a private chat. It extracts lesson/video URLs and PDF links, sends video URLs as messages, and downloads/uploads accessible PDFs back to your private chat.

## Files
- `bot.py` — webhook service
- `requirements.txt` — Python dependencies
- `render.yaml` — optional Render web-service blueprint (not needed for Streamlit)
- `README.md` — setup notes

## Honest hosting note
Streamlit Community Cloud is designed for Streamlit apps, not a persistent Telegram webhook server. A webhook needs a public HTTPS route that accepts Telegram POST updates. If you specifically want Streamlit hosting, this can be adapted into a Streamlit app with a webhook listener, but the Streamlit app may sleep/restart and webhook reliability is not guaranteed. For a continuously available bot, use a persistent web service.

## Environment variables
- `TELEGRAM_BOT_TOKEN`: BotFather token
- `WEBHOOK_URL`: public HTTPS base URL of the running service
- `WEBHOOK_SECRET`: optional webhook secret token
- `PORT`: hosting-provided port, usually set by platform

## Notes
- Video files are not downloaded; only their URLs are sent.
- PDFs must be publicly reachable without a login. Link-only HTMLs that hide content behind authentication can fail.
- Use only content you own or are allowed to redistribute.
- Keep the bot token private. Never commit it to GitHub.
