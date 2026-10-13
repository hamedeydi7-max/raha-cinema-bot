import os
import logging
import httpx

from telegram import (
Update,
InlineKeyboardButton,
InlineKeyboardMarkup,
)
from telegram.ext import (
Application,
CommandHandler,
MessageHandler,
CallbackQueryHandler,
ContextTypes,
filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TMDB_TOKEN = os.getenv("TMDB_TOKEN", "")

TMDB_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

logging.basicConfig(
format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(name)

def main_menu():
keyboard = [
[
InlineKeyboardButton("🎬 فیلم‌های محبوب", callback_data="popular_movie"),
InlineKeyboardButton("📺 سریال‌های محبوب", callback_data="popular_tv"),
],
[
InlineKeyboardButton("🔥 فیلم‌های جدید", callback_data="trending_movie"),
InlineKeyboardButton("⭐ سریال‌های جدید", callback_data="trending_tv"),
],
[
InlineKeyboardButton("🔎 جست‌وجوی فیلم و سریال", callback_data="search"),
InlineKeyboardButton("ℹ️ راهنما", callback_data="help"),
],
]
return InlineKeyboardMarkup(keyboard)

async def tmdb_request(endpoint, params=None):
if not TMDB_TOKEN:
raise RuntimeError("TMDB_TOKEN is not configured.")

headers = {
    "Authorization": f"Bearer {TMDB_TOKEN}",
    "accept": "application/json",
}

async with httpx.AsyncClient(timeout=20) as client:
    response = await client.get(
        f"{TMDB_BASE}/{endpoint.lstrip('/')}",
        headers=headers,
        params=params or {},
    )
    response.raise_for_status()
    return response.json()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
context.user_data["awaiting_search"] = False

text = (
    "🎬 به RAHA CINEMA خوش اومدی!\n\n"
    "اینجا می‌تونی اطلاعات فیلم‌ها و سریال‌ها رو پیدا کنی.\n"
    "از منوی زیر انتخاب کن یا اسم فیلم یا سریال رو بفرست.\n\n"
    "اطلاعات و تصاویر با استفاده از TMDB ارائه می‌شن."
)

await update.effective_message.reply_text(
    text,
    reply_markup=main_menu(),
)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.effective_message.reply_text(
"راهنمای RAHA CINEMA 🎬\n\n"
"• اسم فیلم یا سریال رو ارسال کن تا جست‌وجو کنم.\n"
"• از منو برای فیلم‌ها و سریال‌های محبوب استفاده کن.\n"
"• برای شروع دوباره /start رو بزن.\n\n"
"این ربات اطلاعات و پوسترها رو از TMDB دریافت می‌کنه.\n"
"پخش فیلم فقط در صورت داشتن مجوز مناسب امکان‌پذیره."
)

async def send_movie_list(message, category, media_type="movie"):
try:
if category == "popular":
endpoint = f"{media_type}/popular"
else:
endpoint = f"trending/{media_type}/week"

    data = await tmdb_request(endpoint, {"language": "en-US", "page": 1})
    results = data.get("results", [])[:8]

    if not results:
        await message.reply_text("فعلاً نتیجه‌ای پیدا نشد.")
        return

    for item in results:
        title = item.get("title") or item.get("name") or "Untitled"
        overview = item.get("overview") or "No description available."
        rating = item.get("vote_average", 0)
        date = item.get("release_date") or item.get("first_air_date") or "Unknown"
        poster = item.get("poster_path")

        caption = (
            f"🎬 {title}\n"
            f"📅 {date}\n"
            f"⭐ امتیاز TMDB: {rating}/10\n\n"
            f"{overview[:700]}\n\n"
            "Source: TMDB"
        )

        if poster:
            await message.reply_photo(
                photo=f"{IMAGE_BASE}{poster}",
                caption=caption[:1020],
            )
        else:
            await message.reply_text(caption[:4000])

except Exception:
    logger.exception("Failed to fetch list")
    await message.reply_text(
        "ارتباط با سرویس اطلاعات فیلم برقرار نشد. کمی بعد دوباره تلاش کن."
    )

async def search_media(message, query):
try:
data = await tmdb_request(
"search/multi",
{
"query": query,
"language": "en-US",
"include_adult": "false",
"page": 1,
},
)

    results = [
        item for item in data.get("results", [])
        if item.get("media_type") in ("movie", "tv", "person")
    ][:8]

    if not results:
        await message.reply_text(
            "چیزی پیدا نکردم. اسم رو به انگلیسی امتحان کن."
        )
        return

    for item in results:
        media_type = item.get("media_type")
        title = (
            item.get("title")
            or item.get("name")
            or "Untitled"
        )
        date = (
            item.get("release_date")
            or item.get("first_air_date")
            or ""
        )
        rating = item.get("vote_average", 0)
        overview = item.get("overview") or "No description available."
        poster = item.get("poster_path")

        if media_type == "person":
            text = f"👤 {title}\nSource: TMDB"
            profile = item.get("profile_path")
            if profile:
                await message.reply_photo(
                    photo=f"{IMAGE_BASE}{profile}",
                    caption=text,
                )
            else:
                await message.reply_text(text)
            continue

        label = "🎬 فیلم" if media_type == "movie" else "📺 سریال"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔍 جزئیات بیشتر",
                    callback_data=f"details:{media_type}:{item['id']}",
                )
            ]
        ])

        caption = (
            f"{label}: {title}\n"
            f"📅 تاریخ: {date or 'نامشخص'}\n"
            f"⭐ امتیاز: {rating}/10\n\n"
            f"{overview[:650]}\n\n"
            "Source: TMDB"
        )

        if poster:
            await message.reply_photo(
                photo=f"{IMAGE_BASE}{poster}",
                caption=caption[:1020],
                reply_markup=keyboard,
            )
        else:
            await message.reply_text(
                caption[:4000],
                reply_markup=keyboard,
            )

except Exception:
    logger.exception("Search failed")
    await message.reply_text(
        "جست‌وجو ناموفق بود. لطفاً دوباره امتحان کن."
    )

async def show_details(query, media_type, item_id):
try:
item = await tmdb_request(
f"{media_type}/{item_id}",
{"language": "en-US"},
)

    title = item.get("title") or item.get("name") or "Untitled"
    overview = item.get("overview") or "No description available."
    date = item.get("release_date") or item.get("first_air_date") or "Unknown"
    rating = item.get("vote_average", 0)
    genres = ", ".join(
        genre.get("name", "")
        for genre in item.get("genres", [])
    ) or "Unknown"

    credits = await tmdb_request(
        f"{media_type}/{item_id}/credits"
    )
    cast = ", ".join(
        person.get("name", "")
        for person in credits.get("cast", [])[:5]
    ) or "Unknown"

    videos = await tmdb_request(
        f"{media_type}/{item_id}/videos",
        {"language": "en-US"},
    )

    trailer = next(
        (
            video for video in videos.get("results", [])
            if video.get("site") == "YouTube"
            and video.get("type") == "Trailer"
            and video.get("key")
        ),
        None,
    )

    text = (
        f"🎬 {title}\n"
        f"📅 تاریخ: {date}\n"
        f"⭐ امتیاز: {rating}/10\n"
        f"🎭 ژانر: {genres}\n"
        f"👥 بازیگران: {cast}\n\n"
        f"📖 داستان:\n{overview[:1800]}\n\n"
        "اطلاعات: TMDB"
    )

    keyboard = None
    if trailer:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "▶️ تماشای تریلر در YouTube",
                    url=f"https://www.youtube.com/watch?v={trailer['key']}",
                )
            ]
        ])

    poster = item.get("poster_path")
    if poster:
        await query.message.reply_photo(
            photo=f"{IMAGE_BASE}{poster}",
            caption=text[:1020],
            reply_markup=keyboard,
        )
        if len(text) > 1020:
            await query.message.reply_text(text[1020:4000])
    else:
        await query.message.reply_text(
            text[:4000],
            reply_markup=keyboard,
        )

except Exception:
    logger.exception("Details failed")
    await query.message.reply_text(
        "دریافت جزئیات ناموفق بود. کمی بعد دوباره تلاش کن."
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()

action = query.data

if action == "popular_movie":
    await query.message.reply_text("🎬 فیلم‌های محبوب:")
    await send_movie_list(query.message, "popular", "movie")

elif action == "popular_tv":
    await query.message.reply_text("📺 سریال‌های محبوب:")
    await send_movie_list(query.message, "popular", "tv")

elif action == "trending_movie":
    await query.message.reply_text("🔥 فیلم‌های پرطرفدار این هفته:")
    await send_movie_list(query.message, "trending", "movie")

elif action == "trending_tv":
    await query.message.reply_text("⭐ سریال‌های پرطرفدار این هفته:")
    await send_movie_list(query.message, "trending", "tv")

elif action == "search":
    context.user_data["awaiting_search"] = True
    await query.message.reply_text(
        "🔎 اسم فیلم یا سریال رو بفرست؛ بهتره انگلیسی باشه."
    )

elif action == "help":
    await query.message.reply_text(
        "اسم فیلم یا سریال رو بفرست تا جست‌وجو کنم.\n"
        "برای منوی اصلی /start رو بزن."
    )

elif action.startswith("details:"):
    _, media_type, item_id = action.split(":")
    await show_details(query, media_type, int(item_id))

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
message = update.effective_message
query = (message.text or "").strip()

if not query:
    return

context.user_data["awaiting_search"] = False
await search_media(message, query)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
logger.error("Unhandled bot error", exc_info=context.error)

def main():
if not BOT_TOKEN:
raise RuntimeError("BOT_TOKEN environment variable is missing.")

if not TMDB_TOKEN:
    raise RuntimeError("TMDB_TOKEN environment variable is missing.")

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
app.add_error_handler(error_handler)

logger.info("RAHA CINEMA is starting...")
app.run_polling()

if name == "main":
main()
