import asyncio
from db import engine, Base
# import models so SQLAlchemy metadata includes them
import models_db  # noqa: F401


async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_all())