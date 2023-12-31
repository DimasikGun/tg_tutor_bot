import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aioredis import Redis
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from bot.middlewares.db import DbSessionMiddleware

load_dotenv()
bot = Bot(token=os.getenv('TOKEN'))
redis_fsm = Redis(host='redis', port=6379)
redis_cache = Redis(host='redis', port=6379, db=1)


async def main():
    from bot.handlers.common.handlers import router
    from bot.handlers.students.handlers import router as student_router
    from bot.handlers.tutors.handlers import router as teacher_router
    engine = create_async_engine(url=os.getenv('DB-URL'), echo=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    dp = Dispatcher(storage=RedisStorage(redis=redis_fsm))
    dp.update.middleware(DbSessionMiddleware(session_pool=sessionmaker))
    dp.include_routers(teacher_router, student_router, router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('end of work')
