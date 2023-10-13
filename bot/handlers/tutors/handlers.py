from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses
from handlers.tutors import keyboards as kb
from handlers.tutors.filters import Teacher

router = Router()


@router.message(Teacher(), F.text == 'My courses')
async def tutor_courses(message: Message, session: AsyncSession):
    stmt = select(Courses).where(Courses.teacher == message.from_user.id)
    res = await session.execute(stmt)
    if res.all():
        await message.answer('Here are your courses:', reply_markup=kb.courses)
    else:
        await message.answer('You don`t have any courses for now', reply_markup=kb.courses)


# @router.message()
# async def echo(message: Message):
#     message_type = message.content_type
#     # photo = message.photo[-1].file_id
#
#     if message_type in (
#             ContentType.VIDEO, ContentType.ANIMATION, ContentType.AUDIO, ContentType.DOCUMENT,
#             ContentType.VOICE,
#             ContentType.VIDEO_NOTE, ContentType.STICKER):
#         file_id = eval(f"message.{message_type}.file_id")
#
#         # file_id = getattr(message, message_type + "_file_id", None)
#     elif message_type == ContentType.PHOTO:
#         file_id = message.photo[-1].file_id
#     else:
#         file_id = None
#     # Отправляем ответ
#     await message.answer(f"I don't get it(, type: {message_type} with id: {file_id}")
#     await message.answer_video(file_id)
