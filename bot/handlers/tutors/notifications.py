from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from __main__ import bot
from db import Courses, CoursesStudents, Publications
from handlers.common.keyboards import main
from handlers.common.services import bot_session_closer


@bot_session_closer
async def publication_added(session: AsyncSession, data):
    stmt = select(Courses.name).where(Courses.id == data['course_id'])
    result = await session.execute(stmt)
    course_name = result.scalar()
    stmt = select(CoursesStudents.student_id).where(CoursesStudents.course_id == data['course_id'])
    result = await session.execute(stmt)
    students = result.scalars().all()

    for student in students:
        await bot.send_message(chat_id=student, text=f'New publication in course "{course_name}"', reply_markup=main)


@bot_session_closer
async def student_kicked(session, data):
    stmt = select(Courses.name).where(Courses.id == data['course_id'])
    result = await session.execute(stmt)
    course_name = result.scalar()
    await bot.send_message(chat_id=data['student_id'], text=f'You have been kicked from "{course_name}"',
                           reply_markup=main)


@bot_session_closer
async def course_renamed(session, data, old_name):
    stmt = select(CoursesStudents.student_id).where(CoursesStudents.course_id == data['course_id'])
    result = await session.execute(stmt)
    students = result.scalars().all()

    for student in students:
        await bot.send_message(chat_id=student,
                               text=f'Course "{old_name}" name have been changed to "{data["name"]}"',
                               reply_markup=main)


@bot_session_closer
async def course_deleted(data):
    course_name, students = data

    for student in students:
        await bot.send_message(chat_id=student,
                               text=f'Course "{course_name}" has been deleted',
                               reply_markup=main)


@bot_session_closer
async def publication_deleted(session, data):
    stmt = select(Courses.name).where(Courses.id == data['course_id'])
    result = await session.execute(stmt)
    course_name = result.scalar()

    stmt = select(CoursesStudents.student_id).where(CoursesStudents.course_id == data['course_id'])
    result = await session.execute(stmt)
    students = result.scalars().all()

    for student in students:
        await bot.send_message(chat_id=student,
                               text=f'Course "{course_name}" has been deleted',
                               reply_markup=main)


@bot_session_closer
async def publication_edited(session, data):
    stmt = select(Courses.name).where(Courses.id == data['course_id'])
    result = await session.execute(stmt)
    course_name = result.scalar()
    if not data['title']:
        stmt = select(Publications.title).where(Publications.id == data['publication_id'])
        result = await session.execute(stmt)
        publication_title = result.scalar()
    else:
        publication_title = data['title']
    stmt = select(CoursesStudents.student_id).where(CoursesStudents.course_id == data['course_id'])
    result = await session.execute(stmt)
    students = result.scalars().all()

    for student in students:
        await bot.send_message(chat_id=student,
                               text=f'Publication "{publication_title}" in "{course_name}" has been edited',
                               reply_markup=main)


@bot_session_closer
async def submission_graded(session, data, grade):
    stmt = select(Publications.title).where(Publications.id == data['publication_id'])
    result = await session.execute(stmt)
    publication_title = result.scalar()
    await bot.send_message(chat_id=data['student_id'],
                           text=f'Your submission for "{publication_title}" was graded for {grade}/{data["max_grade"]}',
                           reply_markup=main)
