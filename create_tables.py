import asyncio
from db import engine, Base, AsyncSession
# import models so SQLAlchemy metadata includes them
import models_db  # noqa: F401
from sqlalchemy import insert
from models_db import Category  # assuming your model is called Category


CATEGORY_NAMES = [
    'Трубогиб',
    'Опрессовочный насос',
    'Тиски',
    'Труборез',
    'Лебедка',
    'Пресс гидравлический',
    'Головки резьбонарезные трубные',
    'Маслостанции',
    'Гидроцилиндры',
    'Съемники подшипников гидравлические',
    'Домкраты',
    'Шинообрабатывающие станки',
    'Шиногибы',
    'Шинодыры',
    'Шинорезы',
    'Уголкорезы гидравлические',
    'Разгонщик фланцев',
    'Арматурогибы',
    'Тросорезы',
    'Опрессовщики',
    'Станок'
]


async def create_all():
    async with engine.begin() as conn:
        # create tables
        await conn.run_sync(Base.metadata.create_all)

    # insert categories
    async with AsyncSession(engine) as session:
        async with session.begin():
            stmt = insert(Category).values([{"name": name} for name in CATEGORY_NAMES])
            await session.execute(stmt)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_all())
