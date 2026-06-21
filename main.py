import os
import uuid
import nest_asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters
from pyrogram.types import Message
from database import db

nest_asyncio.apply()

# Environment Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL_ID", 0))
BASE_URL = os.environ.get("BASE_URL", "https://your-app.onrender.com")

bot = Client(
    "movie_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# FastAPI Lifespan (Modern way to start/stop bot)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.start()
    yield
    await bot.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Bot Handlers
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.reply_text("🎬 **MovieBoxBD Bot**\n\nSend me a Movie File (MP4/MKV) to upload.")
    else:
        await message.reply_text("This bot is for admin use only.")

@bot.on_message((filters.video | filters.document) & filters.private)
async def receive_movie(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    status = await message.reply_text("Processing your movie...")
    forwarded = await message.copy(DB_CHANNEL_ID)
    
    file_name = ""
    if message.video:
        file_name = message.video.file_name or "Movie"
        quality = f"{message.video.width}x{message.video.height}"
        duration = message.video.duration
        file_size = message.video.file_size
        file_id = message.video.file_id
    else:
        file_name = message.document.file_name or "Movie"
        quality = "Unknown"
        duration = 0
        file_size = message.document.file_size
        file_id = message.document.file_id

    title = message.caption if message.caption else file_name.split('.')[0]
    movie_id = str(uuid.uuid4())[:8]
    
    movie_data = {
        "_id": movie_id,
        "title": title,
        "year": "N/A",
        "genre": "N/A",
        "language": "N/A",
        "quality": quality,
        "duration": duration,
        "file_size": file_size,
        "file_id": file_id,
        "message_id": forwarded.id
    }
    
    await db.add_movie(movie_data)
    link = f"{BASE_URL}/movie/{movie_id}"
    
    await status.edit_text(
        f"✅ **Movie Uploaded!**\n\n**Title:** {title}\n**Link:** [Click Here]({link})"
    )

# Web Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    movies = await db.get_all_movies()
    return templates.TemplateResponse("movie.html", {"request": request, "movies": movies, "page": "home", "movie": None})

@app.get("/movie/{movie_id}", response_class=HTMLResponse)
async def movie_page(request: Request, movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return templates.TemplateResponse("movie.html", {"request": request, "movie": movie, "movies": None, "page": "details"})

@app.get("/stream/{movie_id}")
async def stream_movie(movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    async def video_streamer():
        async for chunk in bot.stream(movie["file_id"], limit=0):
            yield chunk

    headers = {"Content-Disposition": f"inline; filename=\"{movie['title']}.mp4\""}
    return StreamingResponse(video_streamer(), media_type="video/mp4", headers=headers)

@app.get("/download/{movie_id}")
async def download_movie(movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    async def file_downloader():
        async for chunk in bot.stream(movie["file_id"], limit=0):
            yield chunk

    headers = {"Content-Disposition": f"attachment; filename=\"{movie['title']}.mp4\""}
    return StreamingResponse(file_downloader(), media_type="video/mp4", headers=headers)

@app.get("/watch/{movie_id}", response_class=HTMLResponse)
async def watch_page(request: Request, movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return templates.TemplateResponse("watch.html", {"request": request, "movie": movie, "stream_link": f"{BASE_URL}/stream/{movie_id}"})
