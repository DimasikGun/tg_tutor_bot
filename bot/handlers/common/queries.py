from sqlalchemy import select

from db import Courses, CoursesStudents


async def get_students(session, course_id):
    stmt = select(Courses).join(CoursesStudents).where(Courses.id == course_id)
    result = await session.execute(stmt)
    students = result.scalars().all()
    return students


async def get_code(session, course_id):
    stmt = select(Courses).where(Courses.id == course_id)
    result = await session.execute(stmt)
    course = result.scalar()
    return f'{course.key}{course.id}'
