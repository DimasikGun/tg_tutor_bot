from aiogram.filters import Filter
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Users


class Teacher(Filter):

    async def __call__(self, message: Message, session: AsyncSession) -> bool:
        stmt = select(Users).where(Users.user_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar()
        try:
            return user.is_teacher
        except AttributeError:
            return False
