from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from handlers.students import keyboards as kb
from db import CoursesStudents

router = Router()


@router.message(F.text == 'My courses')
async def student_courses(message: Message, session: AsyncSession):
    stmt = select(CoursesStudents).where(CoursesStudents.student_id == message.from_user.id)
    res = await session.execute(stmt)
    if res.all():
        await message.answer('Here are your courses:', reply_markup=kb.courses)
    else:
        await message.answer('You haven`t joined any courses yet', reply_markup=kb.courses)
