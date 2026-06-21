import os
import uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters
from pyrogram.types import Message
from database import db

# Environment Variables
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 123456789))
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL_ID", -1001234567890))
BASE_URL = os.environ.get("BASE_URL", "https://your-app-name.onrender.com")

# Pyrogram Client
bot = Client(
    "movie_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Bot Command: /start
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.reply_text(
            "🎬 **MovieBoxBD Bot**\n\n"
            "Send me a Movie File (MP4/MKV) and I will upload it to the database and generate a public link.\n\n"
            "Use `/movies` to see all uploaded movies."
        )
    else:
        await message.reply_text("This bot is for admin use only.")

# Bot Command: /movies
@bot.on_message(filters.command("movies") & filters.private)
async def list_movies(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    movies = await db.get_all_movies()
    if not movies:
        await message.reply_text("No movies found.")
        return
    
    text = "🎬 **Uploaded Movies:**\n\n"
    for movie in movies:
        text += f"**{movie['title']}**\nLink: {BASE_URL}/movie/{movie['_id']}\n\n"
    await message.reply_text(text)

# Bot: Receive Video/Document
@bot.on_message((filters.video | filters.document) & filters.private)
async def receive_movie(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    status = await message.reply_text("Processing your movie...")
    
    # Forward to DB Channel
    forwarded = await message.copy(DB_CHANNEL_ID)
    
    # Extract Details
    title = message.caption or (message.video.file_name if message.video else message.document.file_name).split('.')[0]
    year = "N/A" # Admin can type in caption or update later
    genre = "N/A"
    language = "N/A"
    
    if message.video:
        quality = message.video.width, message.video.height
        quality = f"{quality[0]}x{quality[1]}"
        duration = message.video.duration
        file_size = message.video.file_size
        file_id = message.video.file_id
    else:
        quality = "Unknown"
        duration = 0
        file_size = message.document.file_size
        file_id = message.document.file_id

    # Generate Unique ID
    movie_id = str(uuid.uuid4())[:8]
    
    movie_data = {
        "_id": movie_id,
        "title": title,
        "year": year,
        "genre": genre,
        "language": language,
        "quality": quality,
        "duration": duration,
        "file_size": file_size,
        "file_id": file_id,
        "message_id": forwarded.id
    }
    
    await db.add_movie(movie_data)
    link = f"{BASE_URL}/movie/{movie_id}"
    
    await status.edit_text(
        f"✅ **Movie Uploaded Successfully!**\n\n"
        f"**Title:** {title}\n"
        f"**Public Link:** [Click Here]({link})"
    )

# Web Route: Home
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    movies = await db.get_all_movies()
    return templates.TemplateResponse("movie.html", {"request": request, "movies": movies, "page": "home", "movie": None})

# Web Route: Movie Details Page
@app.get("/movie/{movie_id}", response_class=HTMLResponse)
async def movie_page(request: Request, movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return templates.TemplateResponse("movie.html", {"request": request, "movie": movie, "movies": None, "page": "details"})

# Web Route: Watch Online (Streaming)
@app.get("/watch/{movie_id}", response_class=HTMLResponse)
async def watch_page(request: Request, movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Get Telegram Direct Download/Stream Link
    # Note: This link expires in 1 hour, but it's perfect for streaming without Render load
    stream_link = await bot.get_download_url(movie["file_id"])
    
    return templates.TemplateResponse("watch.html", {"request": request, "movie": movie, "stream_link": stream_link})

# Web Route: Direct Download
@app.get("/download/{movie_id}")
async def download_movie(movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    stream_link = await bot.get_download_url(movie["file_id"])
    # Redirect to Telegram's direct link to trigger browser download manager
    return RedirectResponse(url=stream_link)

# FastAPI Startup & Shutdown
@app.on_event("startup")
async def startup_event():
    await bot.start()

@app.on_event("shutdown")
async def shutdown_event():
    await bot.stop()
