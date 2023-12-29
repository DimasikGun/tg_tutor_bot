from aiogram.filters import Filter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.queries import get_user


class Teacher(Filter):

    async def __call__(self, message: Message, session: AsyncSession) -> bool:
        user = await get_user(session, message.from_user.id)
        try:
            return user.is_teacher
        except AttributeError:
            return False
