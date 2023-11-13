from sqlalchemy import select

from __main__ import bot
from db import Courses, Publications, Users
from handlers.common.keyboards import main
from handlers.common.services import bot_session_closer, student_name_builder


@bot_session_closer
async def joined_course(name, teacher):
    await bot.send_message(chat_id=teacher, text=f'New student just joined your "{name}" course',
                           reply_markup=main)


@bot_session_closer
async def left_course(session, data, student):
    stmt = select(Users).where(Users.user_id == student)
    result = await session.execute(stmt)
    user = result.scalar()
    student_name = await student_name_builder(user)

    stmt = select(Courses.name, Courses.teacher).where(Courses.id == data['course_id'])
    result = await session.execute(stmt)
    course = result.fetchone()

    await bot.send_message(chat_id=course.teacher,
                           text=f'{student_name} just left your "{course.name}" course',
                           reply_markup=main)


@bot_session_closer
async def added_submission(session, data):
    stmt = select(Courses.name, Courses.teacher).where(Courses.id == data['course_id'])
    result = await session.execute(stmt)
    course = result.fetchone()

    stmt = select(Publications.title).where(Publications.id == data['publication_id'])
    result = await session.execute(stmt)
    publication_name = result.scalar()

    await bot.send_message(chat_id=course.teacher,
                           text=f'Student just added a new submission to "{publication_name}" in your "{course.name}" course',
                           reply_markup=main)


@bot_session_closer
async def deleted_submission(session, data):
    stmt = select(Courses.name, Courses.teacher).where(Courses.id == data['course_id'])
    result = await session.execute(stmt)
    course = result.fetchone()

    stmt = select(Publications.title).where(Publications.id == data['publication_id'])
    result = await session.execute(stmt)
    publication_name = result.scalar()

    await bot.send_message(chat_id=course.teacher,
                           text=f'Student just deleted his submission of "{publication_name}" in your "{course.name}" course',
                           reply_markup=main)
