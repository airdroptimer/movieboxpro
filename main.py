import os
import uuid
import asyncio
import nest_asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters
from pyrogram.types import Message
from database import db

# Fix asyncio conflict between FastAPI and Pyrogram
nest_asyncio.apply()

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
    bot_token=BOT_TOKEN,
    in_memory=True
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---------------- Bot Handlers ----------------

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

@bot.on_message((filters.video | filters.document) & filters.private)
async def receive_movie(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    status = await message.reply_text("Processing your movie...")
    
    # Forward to DB Channel
    forwarded = await message.copy(DB_CHANNEL_ID)
    
    # Extract Details
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
    
    # Generate Unique ID
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
        f"✅ **Movie Uploaded Successfully!**\n\n"
        f"**Title:** {title}\n"
        f"**Public Link:** [Click Here]({link})"
    )

# ---------------- Web Routes ----------------

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

# Streaming Route: Telegram server streams directly to user's browser
@app.get("/stream/{movie_id}")
async def stream_movie(movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    file_id = movie["file_id"]
    
    async def video_streamer():
        # This streams directly from Telegram's servers to the client
        async for chunk in bot.stream(file_id, limit=0):
            yield chunk

    headers = {
        "Content-Disposition": f"inline; filename=\"{movie['title']}.mp4\"", # inline = stream
        "Accept-Ranges": "bytes"
    }
    
    return StreamingResponse(video_streamer(), media_type="video/mp4", headers=headers)

# Direct Download Route
@app.get("/download/{movie_id}")
async def download_movie(movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    file_id = movie["file_id"]
    
    async def file_downloader():
        async for chunk in bot.stream(file_id, limit=0):
            yield chunk

    # attachment = forces browser to download the file instead of playing it
    headers = {
        "Content-Disposition": f"attachment; filename=\"{movie['title']}.mp4\"",
        "Accept-Ranges": "bytes"
    }
    
    return StreamingResponse(file_downloader(), media_type="video/mp4", headers=headers)

# Watch Page Route
@app.get("/watch/{movie_id}", response_class=HTMLResponse)
async def watch_page(request: Request, movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # We use our own /stream route in the video player
    stream_link = f"{BASE_URL}/stream/{movie_id}"
    
    return templates.TemplateResponse("watch.html", {"request": request, "movie": movie, "stream_link": stream_link})

# ---------------- FastAPI Startup & Shutdown ----------------

@app.on_event("startup")
async def startup_event():
    await bot.start()

@app.on_event("shutdown")
async def shutdown_event():
    await bot.stop()

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
