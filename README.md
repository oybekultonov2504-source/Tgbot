# Tgbot — YouTube Downloader Bot

Telegram bot for downloading videos you are authorized to download.

## MVP
- Accept a YouTube URL
- Read video metadata
- Offer MP3 / 360p / 720p / best available
- Download with yt-dlp
- Merge/transcode with FFmpeg when needed
- Send the result to Telegram
- Delete temporary files

## Local setup

1. Install Python 3.11+ and FFmpeg.
2. Create a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env`.
5. Put your BotFather token in `.env`. Never commit the real token.
6. Run `python bot.py`.

The laptop must remain online while the bot is running.
