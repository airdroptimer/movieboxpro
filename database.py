import motor.motor_asyncio
import os

MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_atlas_uri_here")

class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        self.db = self.client.movieboxbd
        self.movies = self.db.movies

    async def add_movie(self, movie_data):
        await self.movies.insert_one(movie_data)
        return movie_data

    async def get_movie(self, movie_id):
        return await self.movies.find_one({"_id": movie_id})

    async def get_all_movies(self):
        cursor = self.movies.find({})
        return await cursor.to_list(length=None)

db = Database()
