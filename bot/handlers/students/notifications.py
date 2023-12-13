from __main__ import bot
from db.queries import get_user, get_course_by_id, get_single_publication
from handlers.common.keyboards import main
from handlers.common.services import student_name_builder


async def joined_course(name, teacher):
    await bot.send_message(chat_id=teacher, text=f'New student just joined your "{name}" course',
                           reply_markup=main)


async def left_course(session, data, student):
    user = await get_user(session, student)
    student_name = await student_name_builder(user)

    course = await get_course_by_id(session, data['course_id'])
    await bot.send_message(chat_id=course.teacher,
                           text=f'{student_name} just left your "{course.name}" course',
                           reply_markup=main)


async def added_submission(session, data):
    course = await get_course_by_id(session, data['course_id'])
    publication = await get_single_publication(session, data['publication_id'])
    await bot.send_message(chat_id=course.teacher,
                           text=f'Student just added a new submission to "{publication.title}" in your "{course.name}" course',
                           reply_markup=main)


async def deleted_submission(session, data):
    course = await get_course_by_id(session, data['course_id'])
    publication = await get_single_publication(session, data['publication_id'])

    await bot.send_message(chat_id=course.teacher,
                           text=f'Student just deleted his submission of "{publication.title}" in your "{course.name}" course',
                           reply_markup=main)
