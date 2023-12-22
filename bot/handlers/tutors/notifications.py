from sqlalchemy.ext.asyncio import AsyncSession

from __main__ import bot
from db.queries import get_course_by_id, get_single_publication, get_students
from handlers.common.keyboards import main


async def publication_added(session: AsyncSession, data):
    """
    Notifies students about the addition of a new publication to a course.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course ID.
    """
    course = await get_course_by_id(session, data['course_id'])
    students = await get_students(session, data['course_id'])

    for student in students:
        await bot.send_message(chat_id=student.user_id, text=f'New publication in course "{course.name}"',
                               reply_markup=main)


async def student_kicked(session, data):
    """
    Notifies a student about being kicked from a course.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course ID and student ID.
    """
    course = await get_course_by_id(session, data['course_id'])
    await bot.send_message(chat_id=data['student_id'], text=f'You have been kicked from "{course.name}"',
                           reply_markup=main)


async def course_renamed(session, data, old_name):
    """
    Notifies students about a course being renamed.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course ID and new course name.
        old_name (str): The old name of the course.
    """
    students = await get_students(session, data['course_id'])

    for student in students:
        await bot.send_message(chat_id=student.user_id,
                               text=f'Course "{old_name}" name has been changed to "{data["name"]}"',
                               reply_markup=main)


async def course_deleted(data):
    """
    Notifies students about a course being deleted.

    Args:
        data (tuple): A tuple containing the course name and a list of student IDs.
    """
    course_name, students = data

    for student in students:
        await bot.send_message(chat_id=student,
                               text=f'Course "{course_name}" has been deleted',
                               reply_markup=main)


async def publication_deleted(session, data):
    """
    Notifies students about a publication being deleted from a course.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course ID.
    """
    course = await get_course_by_id(session, data['course_id'])

    students = await get_students(session, data['course_id'])

    for student in students:
        await bot.send_message(chat_id=student.user_id,
                               text=f'Publication in "{course.name}" has been deleted',
                               reply_markup=main)


async def publication_edited(session, data):
    """
    Notifies students about a publication being edited in a course.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the course ID and publication ID.
    """
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
    """
    Notifies a student about their submission being graded.

    Args:
        session (AsyncSession): The asynchronous database session.
        data (dict): Additional data, including the publication ID, student ID, and maximum grade.
        grade (int): The grade assigned to the submission.
    """
    publication = await get_single_publication(session, data['publication_id'])
    await bot.send_message(chat_id=data['student_id'],
                           text=f'Your submission for "{publication.title}" was graded for {grade}/{data["max_grade"]}',
                           reply_markup=main)
