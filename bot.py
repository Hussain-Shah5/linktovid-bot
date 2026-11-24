"""
LinkToVid Bot v2 - TikTok / Instagram / Facebook / YouTube
Video Downloader Bot (without watermark where possible)
+ LONG VIDEO support

Banaya gaya: Syed ke liye
Naam: LinkToVid Bot
Kaam: Link bhejo -> Video download karke bhej dega
Long video bhi download hogi - parts mein bhej dega

Setup:
1. .env file mein BOT_TOKEN aur ADMIN_ID dalo
   (dekho .env.example)
2. pip install -r requirements.txt
3. ffmpeg install karo (long video ke liye zaroori hai)
   Windows: https://ffmpeg.org/download.html
   Linux: sudo apt install ffmpeg
   Mac: brew install ffmpeg
4. python bot.py

Access Control (aapki marzi):
- Default: Sirf ADMIN + allowed users
- /allow <user_id> - kisi ko allow karo
- /remove <user_id> - kisi ko hatao
- /users - allowed users ki list
- /public - sab ke liye khol do (public mode ON)
- /private - wapas sirf allowed users (public mode OFF)

Long Video:
- Telegram Bot ki limit 50 MB hai, is liye lambi video ko
  bot khud parts mein tod kar bhej dega.
  Example: 150 MB video -> Part 1, Part 2, Part 3, Part 4
- /mode split - Parts mein bhejo (default, quality same rehti hai)
- /mode compress - Chhoti quality mein compress karke ek file mein bhejo
"""

import os
import re
import json
import math
import logging
import asyncio
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# httpx NO_PROXY mein IPv6 brackets [::1] se crash hota hai, is liye saaf karo
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)

BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_FILE = BASE_DIR / "allowed_users.json"
SETTINGS_FILE = BASE_DIR / "settings.json"

# Telegram Bot API limit - 50 MB
MAX_SIZE_MB = 49
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
# Split karte waqt har part is se chhota rakho
PART_SIZE_BYTES = 45 * 1024 * 1024

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("LinkToVid")

# ---------- Storage helpers ----------

def load_allowed():
    if not ALLOWED_FILE.exists():
        return []
    try:
        return json.loads(ALLOWED_FILE.read_text())
    except Exception:
        return []

def save_allowed(users):
    ALLOWED_FILE.write_text(json.dumps(users, indent=2))

def load_settings():
    if not SETTINGS_FILE.exists():
        return {"public": False, "mode": "split"}
    try:
        data = json.loads(SETTINGS_FILE.read_text())
        if "mode" not in data:
            data["mode"] = "split"
        if "public" not in data:
            data["public"] = False
        return data
    except Exception:
        return {"public": False, "mode": "split"}

def save_settings(data):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))

def is_allowed(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    if load_settings().get("public", False):
        return True
    return user_id in load_allowed()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

# ---------- URL detection ----------

URL_RE = re.compile(r"https?://[^\s]+")

SUPPORTED = [
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "fb.watch",
    "fb.com",
    "youtube.com",
    "youtu.be",
]

def extract_url(text: str):
    if not text:
        return None
    m = URL_RE.search(text)
    return m.group(0) if m else None

def is_supported(url: str) -> bool:
    url_low = url.lower()
    return any(s in url_low for s in SUPPORTED)

def platform_name(url: str) -> str:
    u = url.lower()
    if "tiktok" in u:
        return "TikTok"
    if "instagram" in u:
        return "Instagram"
    if "facebook" in u or "fb.watch" in u or "fb.com" in u:
        return "Facebook"
    if "youtube" in u or "youtu.be" in u:
        return "YouTube"
    return "Video"

# ---------- Long video helpers (ffmpeg) ----------

def get_duration(filepath: Path) -> float:
    """Video ki length seconds mein nikalo (ffprobe se)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"ffprobe error: {e}")
        return 0

def compress_video(input_path: Path) -> Path | None:
    """Video ko 480p mein compress karo taake size kam ho jaye."""
    output_path = DOWNLOADS_DIR / f"{input_path.stem}-compressed.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", "scale=-2:480",
            "-c:v", "libx264", "-crf", "28", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "96k",
            str(output_path)
        ], capture_output=True, timeout=600, check=True)
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
    except Exception as e:
        logger.error(f"Compress error: {e}")
    return None

def split_video(input_path: Path) -> list[Path]:
    """
    Lambi video ko 45 MB wale parts mein todo.
    -c copy use hota hai, is liye quality same rehti hai aur jaldi hota hai.
    """
    duration = get_duration(input_path)
    size = input_path.stat().st_size

    if duration <= 0:
        # Duration na mile to size se andaza lagao, 60 sec ke parts
        parts_count = math.ceil(size / PART_SIZE_BYTES)
        # Duration nahi pata, is liye compress try karo, split nahi
        return []

    parts_count = math.ceil(size / PART_SIZE_BYTES)
    part_duration = duration / parts_count

    parts = []
    for i in range(parts_count):
        start = i * part_duration
        part_path = DOWNLOADS_DIR / f"{input_path.stem}-part{i+1}.mp4"
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(start), "-t", str(part_duration),
                "-i", str(input_path),
                "-c", "copy",
                str(part_path)
            ], capture_output=True, timeout=300, check=True)
            if part_path.exists() and part_path.stat().st_size > 0:
                parts.append(part_path)
        except Exception as e:
            logger.error(f"Split part {i+1} error: {e}")

    return parts

def cleanup_files(paths):
    for p in paths:
        try:
            Path(p).unlink()
        except Exception:
            pass

# ---------- Commands ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text(
            "Sorry, is bot ko use karne ki permission nahi hai.\n"
            "Admin se contact karo."
        )
        return

    mode = load_settings().get("mode", "split")
    await update.message.reply_text(
        "👋 Assalam-o-Alaikum! Main hoon *LinkToVid Bot*.\n\n"
        "Bas mujhe kisi bhi video ka link bhejo:\n"
        "• TikTok\n"
        "• Instagram Reels\n"
        "• Facebook Video\n"
        "• YouTube / YouTube Shorts\n\n"
        "Main wo video download karke yahin bhej dunga.\n"
        "TikTok wali video without watermark aayegi.\n\n"
        "📹 *Long video bhi chalegi!*\n"
        "Lambi video 50 MB se bari ho to main usay parts mein\n"
        "tod kar bhej dunga - Part 1, Part 2, Part 3...\n"
        f"Abhi mode: {mode}\n\n"
        "Commands:\n"
        "/help - Madad\n"
        "/stats - Apna status\n"
        "/mode split - Long video parts mein bhejo\n"
        "/mode compress - Long video compress karke bhejo\n\n"
        "Admin ke liye:\n"
        "/allow, /remove, /users, /public, /private",
        parse_mode="Markdown",
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Kaise use karein:\n\n"
        "1. TikTok / Instagram / Facebook / YouTube se video ka link copy karo\n"
        "2. Yahan paste karke bhej do\n"
        "3. Thodi der wait karo, video mil jayegi\n\n"
        "Long Video:\n"
        "• Lambi video bhi download hogi\n"
        "• Default: Parts mein aayegi (quality same)\n"
        "• /mode compress likho to ek file mein aayegi, quality thodi kam hogi\n"
        "• /mode split likho to wapas parts wala mode ho jayega\n\n"
        "Note:\n"
        "• Private account ki video download nahi hogi\n"
        "• Bahut lambi video (1 ghanta+) mein time zyada lag sakta hai\n"
        "• Sirf apne use ke liye download karo"
    )

async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Ye command sirf Admin use kar sakta hai.")
        return
    if not context.args or context.args[0].lower() not in ("split", "compress"):
        await update.message.reply_text(
            "Use: /mode split  ya  /mode compress\n\n"
            "split - Long video parts mein bhejo (quality same)\n"
            "compress - Long video compress karke ek file mein bhejo (quality kam)"
        )
        return
    mode = context.args[0].lower()
    s = load_settings()
    s["mode"] = mode
    save_settings(s)
    await update.message.reply_text(f"✅ Long video mode: {mode}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = load_settings()
    mode_text = "Public (sab use kar sakte hain)" if settings.get("public") else "Private (sirf allowed users)"
    await update.message.reply_text(
        f"📊 Status\n\n"
        f"Your ID: `{user.id}`\n"
        f"Admin: {'Yes' if is_admin(user.id) else 'No'}\n"
        f"Bot Mode: {mode_text}\n"
        f"Long Video Mode: {settings.get('mode', 'split')}\n"
        f"Allowed Users: {len(load_allowed())}",
        parse_mode="Markdown",
    )

async def allow_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Ye command sirf Admin use kar sakta hai.")
        return
    if not context.args:
        await update.message.reply_text("Use: /allow <user_id>\nExample: /allow 123456789")
        return
    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID number hona chahiye.")
        return
    users = load_allowed()
    if new_id not in users:
        users.append(new_id)
        save_allowed(users)
    await update.message.reply_text(f"✅ User {new_id} ko allow kar diya.")

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Ye command sirf Admin use kar sakta hai.")
        return
    if not context.args:
        await update.message.reply_text("Use: /remove <user_id>")
        return
    try:
        rem_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID number hona chahiye.")
        return
    users = load_allowed()
    if rem_id in users:
        users.remove(rem_id)
        save_allowed(users)
    await update.message.reply_text(f"❌ User {rem_id} ko hata diya.")

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Ye command sirf Admin use kar sakta hai.")
        return
    users = load_allowed()
    if not users:
        await update.message.reply_text("Abhi koi allowed user nahi hai (Admin ke ilawa).")
        return
    text = "Allowed Users:\n" + "\n".join(f"• {u}" for u in users)
    await update.message.reply_text(text)

async def public_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Ye command sirf Admin use kar sakta hai.")
        return
    s = load_settings()
    s["public"] = True
    save_settings(s)
    await update.message.reply_text("🌍 Public mode ON - Ab koi bhi is bot ko use kar sakta hai.")

async def private_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("Ye command sirf Admin use kar sakta hai.")
        return
    s = load_settings()
    s["public"] = False
    save_settings(s)
    await update.message.reply_text("🔒 Private mode ON - Ab sirf allowed users use kar sakte hain.")

# ---------- Download ----------

def download_video(url: str):
    """yt-dlp se video download karo. File ka path return karo."""
    import yt_dlp

    # Purani files saaf karo taake jagah na bhare
    for f in DOWNLOADS_DIR.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass

    # Long video ke liye 720p tak limit rakho taake size control mein rahe
    # max_filesize hata diya hai - ab lambi video bhi download hogi
    ydl_opts = {
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
        "outtmpl": str(DOWNLOADS_DIR / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not Path(filename).exists():
            stem = Path(filename).stem
            for f in DOWNLOADS_DIR.glob(f"{stem}.*"):
                filename = str(f)
                break
        return filename, info.get("title", "Video")

async def send_video_file(update, path: Path, caption: str):
    with open(path, "rb") as video_file:
        await update.message.reply_video(
            video=video_file,
            caption=caption[:900],
            supports_streaming=True,
        )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""

    if not is_allowed(user.id):
        await update.message.reply_text(
            "Sorry, is bot ko use karne ki permission nahi hai."
        )
        return

    url = extract_url(text)
    if not url:
        await update.message.reply_text(
            "Mujhe video ka link bhejo.\nExample: TikTok / Instagram / Facebook / YouTube ka link"
        )
        return

    if not is_supported(url):
        await update.message.reply_text(
            "Ye link support nahi hai.\nSirf TikTok, Instagram, Facebook aur YouTube support karta hoon."
        )
        return

    plat = platform_name(url)
    status = await update.message.reply_text(f"⏳ {plat} video download ho rahi hai, wait karo...")

    try:
        loop = asyncio.get_running_loop()
        filepath, title = await loop.run_in_executor(None, download_video, url)

        path = Path(filepath)
        if not path.exists():
            await status.edit_text("❌ Video download nahi ho saki. Link check karke dobara bhejo.")
            return

        size = path.stat().st_size
        size_mb = size // (1024 * 1024)
        mode = load_settings().get("mode", "split")

        # Chhoti video - seedha bhej do
        if size <= MAX_SIZE_BYTES:
            await status.edit_text("📤 Video bhej raha hoon...")
            caption = f"🎬 {title}\n📥 LinkToVid Bot se download hui"
            await send_video_file(update, path, caption)
            await status.delete()
            cleanup_files([path])
            return

        # LONG VIDEO - 50 MB se bari hai
        await status.edit_text(
            f"📹 Long video hai ({size_mb} MB), is liye parts mein bhej raha hoon...\n"
            f"Mode: {mode}\nThoda wait karo."
        )

        if not ffmpeg_available():
            await status.edit_text(
                f"❌ Video {size_mb} MB ki hai, Telegram 50 MB se bari file ek saath nahi bhej sakta.\n"
                "Aur is server/computer par ffmpeg install nahi hai, is liye parts bhi nahi bana sakta.\n"
                "ffmpeg install karo, phir dobara try karo. Dekho README mein ffmpeg wala hissa."
            )
            cleanup_files([path])
            return

        # Mode: compress - pehle compress karke dekho, agar fit ho jaye to ek file mein bhej do
        if mode == "compress":
            await status.edit_text(f"📹 Long video hai ({size_mb} MB), compress kar raha hoon...")
            compressed = await loop.run_in_executor(None, compress_video, path)
            if compressed and compressed.stat().st_size <= MAX_SIZE_BYTES:
                caption = f"🎬 {title} (compressed)\n📥 LinkToVid Bot se download hui"
                await send_video_file(update, compressed, caption)
                await status.delete()
                cleanup_files([path, compressed])
                return
            # Compress se bhi fit na hui to split karo
            if compressed:
                # Compressed wali ko split karo, original hata do
                cleanup_files([path])
                path = compressed
                size = path.stat().st_size
                size_mb = size // (1024 * 1024)
                await status.edit_text(f"Compress ke baad bhi {size_mb} MB hai, parts mein bhej raha hoon...")
            # else neeche split continue karega original se

        # Mode: split (default) - parts mein todo
        parts = await loop.run_in_executor(None, split_video, path)
        if not parts:
            await status.edit_text(
                "❌ Long video ko parts mein nahi tod saka.\n"
                "Dusri video try karo ya /mode compress try karo."
            )
            cleanup_files([path])
            return

        await status.edit_text(f"📤 {len(parts)} parts bhej raha hoon...")
        for i, part in enumerate(parts, start=1):
            caption = f"🎬 {title}\nPart {i}/{len(parts)}\n📥 LinkToVid Bot"
            await send_video_file(update, part, caption)

        await status.delete()
        cleanup_files([path] + parts)

    except Exception as e:
        logger.error(f"Download error for {url}: {e}")
        try:
            await status.edit_text(
                "❌ Video download nahi ho saki.\n"
                "Ho sakta hai video private ho, delete ho gayi ho, ya link galat ho.\n"
                "Dusra link try karo."
            )
        except Exception:
            await update.message.reply_text("❌ Video download nahi ho saki, dobara try karo.")

# ---------- Main ----------

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN nahi mila. .env file banao, dekho .env.example")
        return
    if ADMIN_ID == 0:
        print("WARNING: ADMIN_ID nahi dala. .env mein apni Telegram ID dalo.")
        print("Apni ID janne ke liye @userinfobot ko /start bhejo.")
    if not ffmpeg_available():
        print("WARNING: ffmpeg nahi mila. Long video (50 MB+) parts mein nahi bhej payega.")
        print("ffmpeg install karo: Windows - ffmpeg.org, Linux - sudo apt install ffmpeg, Mac - brew install ffmpeg")

    if not ALLOWED_FILE.exists():
        save_allowed([])
    if not SETTINGS_FILE.exists():
        save_settings({"public": False, "mode": "split"})

    # Slow network / proxy ke liye lamba timeout, warna get_me timeout ho jata hai
    from telegram.request import HTTPXRequest
    from telegram.error import RetryAfter, TimedOut
    import time

    print("LinkToVid Bot v2 (long video support) chal raha hai... Ctrl+C se band karo.")

    # Telegram kabhi kabhi flood control (429) deta hai, to wait karke dobara try karo
    # Bar bar getMe karne se limit badhti hai, is liye ek hi process wait karke retry karega
    while True:
        try:
            request = HTTPXRequest(
                connect_timeout=60.0,
                read_timeout=60.0,
                write_timeout=60.0,
                pool_timeout=60.0,
            )
            app = Application.builder().token(BOT_TOKEN).request(request).build()

            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("help", help_cmd))
            app.add_handler(CommandHandler("mode", mode_cmd))
            app.add_handler(CommandHandler("stats", stats))
            app.add_handler(CommandHandler("allow", allow_cmd))
            app.add_handler(CommandHandler("remove", remove_cmd))
            app.add_handler(CommandHandler("users", users_cmd))
            app.add_handler(CommandHandler("public", public_cmd))
            app.add_handler(CommandHandler("private", private_cmd))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

            app.run_polling()
            break
        except RetryAfter as e:
            wait = int(getattr(e, "retry_after", 32)) + 10
            print(f"Telegram flood control, {wait} sec wait karna hoga. Process band ho raha hai, wrapper dobara chalaye ga.")
            # Event loop band ho jata hai, is liye isi process mein dobara run_polling nahi ho sakta
            # Bahar wala run.sh wait karke dobara chalaye ga
            return
        except TimedOut:
            print("Telegram timeout, process band ho raha hai, wrapper dobara chalaye ga.")
            return

if __name__ == "__main__":
    main()
