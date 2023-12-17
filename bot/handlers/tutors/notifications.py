from sqlalchemy.ext.asyncio import AsyncSession

from __main__ import bot
from db.queries import get_course_by_id, get_single_publication, get_students
from handlers.common.keyboards import main


async def publication_added(session: AsyncSession, data):
    course = await get_course_by_id(session, data['course_id'])
    students = await get_students(session, data['course_id'])

    for student in students:
        await bot.send_message(chat_id=student.user_id, text=f'New publication in course "{course.name}"', reply_markup=main)


async def student_kicked(session, data):
    course = await get_course_by_id(session, data['course_id'])
    await bot.send_message(chat_id=data['student_id'], text=f'You have been kicked from "{course.name}"',
                           reply_markup=main)


async def course_renamed(session, data, old_name):
    students = await get_students(session, data['course_id'])

    for student in students:
        await bot.send_message(chat_id=student.user_id,
                               text=f'Course "{old_name}" name have been changed to "{data["name"]}"',
                               reply_markup=main)


async def course_deleted(data):
    course_name, students = data

    for student in students:
        await bot.send_message(chat_id=student,
                               text=f'Course "{course_name}" has been deleted',
                               reply_markup=main)


async def publication_deleted(session, data):
    course = await get_course_by_id(session, data['course_id'])

    students = await get_students(session, data['course_id'])

    for student in students:
        await bot.send_message(chat_id=student.user_id,
                               text=f'Course "{course.name}" has been deleted',
                               reply_markup=main)


async def publication_edited(session, data):
    course = await get_course_by_id(session, data['course_id'])
    if not data['title']:
        publication = await get_single_publication(session, data['publication_id'])
        publication_title = publication.title
    else:
        publication_title = data['title']
    students = await get_students(session, data['course_id'])

    for student in students:
        await bot.send_message(chat_id=student.user_id,
                               text=f'Publication "{publication_title}" in "{course.name}" has been edited',
                               reply_markup=main)


async def submission_graded(session, data, grade):
    publication = await get_single_publication(session, data['publication_id'])
    await bot.send_message(chat_id=data['student_id'],
                           text=f'Your submission for "{publication.title}" was graded for {grade}/{data["max_grade"]}',
                           reply_markup=main)
