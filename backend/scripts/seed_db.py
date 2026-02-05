import asyncio
from src.core.database import AsyncSessionLocal
# from src.core.models import User, Source # Import models as needed

async def seed():
    async with AsyncSessionLocal() as session:
        print("Seeding database...")
        # Add seeding logic here
        pass

if __name__ == "__main__":
    asyncio.run(seed())
