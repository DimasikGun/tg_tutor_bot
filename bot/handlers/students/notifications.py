from bot.__main__ import bot
from bot.db.queries import get_user, get_course_by_id, get_single_publication
from bot.handlers.common.keyboards import main
from bot.handlers.common.services import student_name_builder


async def joined_course(name, teacher):
    """
    Notifies the teacher about a new student joining a course.

    Args:
        name (str): The name of the course.
        teacher (int): The user ID of the teacher.
    """
    await bot.send_message(chat_id=teacher, text=f'New student just joined your "{name}" course',
                           reply_markup=main)


async def left_course(session, data, student):
    """
    Notifies the teacher about a student leaving a course.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course ID.
        student (int): The user ID of the student.
    """
    user = await get_user(session, student)
    student_name = await student_name_builder(user)

    course = await get_course_by_id(session, data['course_id'])
    await bot.send_message(chat_id=course.teacher,
                           text=f'{student_name} just left your "{course.name}" course',
                           reply_markup=main)


async def added_submission(session, data):
    """
    Notifies the teacher about a student adding a new submission.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course and publication IDs.
    """
    course = await get_course_by_id(session, data['course_id'])
    publication = await get_single_publication(session, data['publication_id'])
    await bot.send_message(chat_id=course.teacher,
                           text=f'Student just added a new submission to "{publication.title}" in your "{course.name}" course',
                           reply_markup=main)


async def deleted_submission(session, data):
    """
    Notifies the teacher about a student deleting a submission.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course and publication IDs.
    """
    course = await get_course_by_id(session, data['course_id'])
    publication = await get_single_publication(session, data['publication_id'])

    await bot.send_message(chat_id=course.teacher,
                           text=f'Student just deleted his submission of "{publication.title}" in your "{course.name}" course',
                           reply_markup=main)
