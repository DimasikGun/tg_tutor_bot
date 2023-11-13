from sqlalchemy import select, Sequence, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses, CoursesStudents, Media, Publications, Users, Submissions


async def get_publications(session: AsyncSession, course_id: int) -> Sequence:
    stmt = select(Publications).where(Publications.course_id == course_id).order_by(
        Publications.add_date.desc())
    res = await session.execute(stmt)
    posts = res.scalars().all()
    return posts


async def create_user(session, callback, is_teacher):
    await session.merge(
        Users(user_id=callback.from_user.id, username=callback.from_user.username,
              first_name=callback.from_user.first_name, second_name=callback.from_user.last_name,
              is_teacher=is_teacher))


async def get_students(session: AsyncSession, course_id: int) -> Sequence:
    stmt = select(Users).join(CoursesStudents).where(Courses.id == course_id)
    result = await session.execute(stmt)
    students = result.scalars().all()
    return students


async def get_code(session: AsyncSession, course_id: int) -> str:
    stmt = select(Courses).where(Courses.id == course_id)
    result = await session.execute(stmt)
    course = result.scalar()
    return f'{course.key}{course.id}'


async def delete_course(session: AsyncSession, course_id: int) -> tuple:
    stmt = select(CoursesStudents.student_id).where(Courses.id == course_id)
    res = await session.execute(stmt)
    students = res.scalars().all()

    stmt = delete(CoursesStudents).where(CoursesStudents.course_id == course_id)
    await session.execute(stmt)

    stmt = delete(Media).where(
        Media.submission.in_(select(Submissions.id).where(
            Submissions.publication.in_(select(Publications.id).where(Publications.course_id == course_id)))))
    await session.execute(stmt)

    stmt = delete(Submissions).where(
        Submissions.publication.in_(select(Publications.id).where(Publications.course_id == course_id)))
    await session.execute(stmt)
    stmt = delete(Media).where(
        Media.publication.in_(select(Publications.id).where(Publications.course_id == course_id)))
    await session.execute(stmt)
    stmt = delete(Publications).where(Publications.course_id == course_id)
    await session.execute(stmt)

    stmt = select(Courses.name).where(Courses.id == course_id)
    res = await session.execute(stmt)
    course_name = res.scalar()

    stmt = delete(Courses).where(Courses.id == course_id)
    await session.execute(stmt)
    await session.commit()
    return course_name, students


async def delete_publication_query(session: AsyncSession, publication_id: int) -> None:
    stmt = delete(Media).where(Media.publication == publication_id)
    await session.execute(stmt)
    stmt = delete(Media).where(
        Media.submission.in_(select(Submissions.id).where(Submissions.publication == publication_id)))
    await session.execute(stmt)
    stmt = delete(Submissions).where(Submissions.publication == publication_id)
    await session.execute(stmt)
    stmt = delete(Publications).where(Publications.id == publication_id)
    await session.execute(stmt)
    await session.commit()


async def get_submissions(session: AsyncSession, publication_id: int) -> Sequence:
    stmt = select(Submissions).where(Submissions.publication == publication_id).limit(5)
    result = await session.execute(stmt)
    submissions = result.scalars().all()
    return submissions


async def delete_student_from_course(session, student, course):
    stmt = delete(Media).where(
        Media.submission.in_(select(Submissions.id).where(
            Submissions.publication.in_(select(Publications.id).where(Publications.course_id == course)))))
    await session.execute(stmt)

    stmt = delete(Submissions).where(
        Submissions.publication.in_(select(Publications.id).where(Publications.course_id == course)))
    await session.execute(stmt)

    stmt = delete(CoursesStudents).where(
        CoursesStudents.course_id == course and CoursesStudents.user_id == student)
    await session.execute(stmt)
    await session.commit()
