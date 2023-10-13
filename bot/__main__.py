import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from handlers.tutors.handlers import router as teacher_router
from handlers.common.handlers import router
from handlers.students.handlers import router as student_router
from middlewares.db import DbSessionMiddleware


async def main():
    load_dotenv()
    engine = create_async_engine(url=os.getenv('DB-URL'), echo=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    bot = Bot(token=os.getenv('TOKEN'))
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware(session_pool=sessionmaker))
    dp.include_routers(teacher_router, student_router, router,)
    await dp.start_polling(bot)


# TODO: remove  URL from alembic.ini
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('end of work')
