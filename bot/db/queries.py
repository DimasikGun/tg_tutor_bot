from sqlalchemy import select, Sequence, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses, CoursesStudents, Media, Publications, Users, Submissions


async def change_role_to_teacher(session: AsyncSession, student_id):
    stmt = update(Users).where(Users.user_id == student_id).values(is_teacher=True)
    await session.execute(stmt)
    await session.commit()


async def change_role_to_student(session: AsyncSession, teacher_id):
    stmt = update(Users).where(Users.user_id == teacher_id).values(is_teacher=False)
    await session.execute(stmt)
    await session.commit()


async def get_publications(session: AsyncSession, course_id: int, limit: int = None):
    if limit:
        stmt = select(Publications).where(Publications.course_id == course_id).order_by(
            Publications.add_date.desc()).limit(limit)
    else:
        stmt = select(Publications).where(Publications.course_id == course_id).order_by(
            Publications.add_date.desc())
    res = await session.execute(stmt)
    posts = res.scalars().all()
    return posts


async def get_single_publication(session: AsyncSession, publication_id):
    stmt = select(Publications).where(Publications.id == publication_id)
    result = await session.execute(stmt)
    publication = result.scalar()
    return publication


async def create_user(session, callback, is_teacher):
    await session.merge(
        Users(user_id=callback.from_user.id, username=callback.from_user.username,
              first_name=callback.from_user.first_name, second_name=callback.from_user.last_name,
              is_teacher=is_teacher))


async def get_students(session: AsyncSession, course_id: int, limit: int = None) -> Sequence:
    if limit:
        stmt = select(Users).join(CoursesStudents).where(CoursesStudents.course_id == course_id).limit(limit)
    else:
        stmt = select(Users).join(CoursesStudents).where(CoursesStudents.course_id == course_id)
    result = await session.execute(stmt)
    students = result.scalars().all()
    return students


async def get_single_student(session: AsyncSession, student_id):
    stmt = select(Users).where(Users.user_id == student_id)
    result = await session.execute(stmt)
    student = result.scalar()
    return student


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


async def get_submissions(session: AsyncSession, publication_id: int, limit: int = None) -> Sequence:
    if limit:
        stmt = select(Submissions).where(Submissions.publication == publication_id).limit(limit)
    else:
        stmt = select(Submissions).where(Submissions.publication == publication_id)
    result = await session.execute(stmt)
    submissions = result.scalars().all()
    return submissions


async def delete_student_from_course(session: AsyncSession, student, course):
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


async def get_course_by_id(session: AsyncSession, course_id):
    stmt = select(Courses).where(Courses.id == course_id)
    result = await session.execute(stmt)
    course = result.scalar()
    return course


async def get_courses_teacher(session: AsyncSession, teacher_id, limit: int = None):
    if limit:
        stmt = select(Courses).where(Courses.teacher == teacher_id).limit(limit)
    else:
        stmt = select(Courses).where(Courses.teacher == teacher_id)
    res = await session.execute(stmt)
    courses = res.scalars().all()
    return courses


async def get_courses_student(session: AsyncSession, student_id, limit: int = None):
    if limit:
        stmt = select(Courses).join(CoursesStudents).where(CoursesStudents.student_id == student_id).limit(limit)
    else:
        stmt = select(Courses).join(CoursesStudents).where(CoursesStudents.student_id == student_id)
    res = await session.execute(stmt)
    courses = res.scalars().all()
    return courses


async def get_course_by_key(session: AsyncSession, course_id, key):
    stmt = select(Courses).where(Courses.id == course_id and Courses.key == key)
    res = await session.execute(stmt)
    course = res.scalar()
    return course


async def create_submission(session: AsyncSession, data, student_id):
    submission = await session.merge(
        Submissions(text=data['text'], publication=data['publication_id'], student=student_id))
    await session.commit()
    return submission


async def create_publication(session: AsyncSession, data):
    publication = await session.merge(Publications(title=data['title'], course_id=data['course_id'], text=data['text']))
    await session.commit()
    return publication


async def create_media(session: AsyncSession, media, submission=None, publication=None):
    await session.merge(
        Media(media_type=media[0], file_id=media[1], submission=submission.id, publication=publication.id))
    await session.commit()


async def delete_submission(session: AsyncSession, data, student_id):
    stmt = delete(Media).where(
        Media.submission.in_(select(Submissions.id).where(
            Submissions.publication == data['publication_id'] and Submissions.student == student_id)))
    await session.execute(stmt)
    stmt = delete(Submissions).where(
        Submissions.publication == data['publication_id'] and Submissions.student == student_id)
    await session.execute(stmt)
    await session.commit()


async def get_single_submission_student(session: AsyncSession, data, student_id):
    stmt = select(Submissions).where(
        Submissions.publication == data['publication_id'] and Submissions.student == student_id)
    result = await session.execute(stmt)
    submission = result.scalar()
    stmt = select(Publications.max_grade).where(Publications.id == submission.publication)
    result = await session.execute(stmt)
    max_grade = result.scalar()
    return submission, max_grade


async def get_single_coursestudent(session: AsyncSession, course_id, student_id):
    stmt = select(CoursesStudents).where(
        CoursesStudents.course_id == course_id,
        CoursesStudents.student_id == student_id
    )
    res = await session.execute(stmt)
    coursestudent = res.scalar()
    return coursestudent


async def get_coursestudents(session: AsyncSession, data):
    stmt = select(CoursesStudents).where(CoursesStudents.course_id == data['course_id'])
    result = await session.execute(stmt)
    students = result.scalars().all()
    return students


async def join_course_student(session: AsyncSession, course_id, student_id):
    await session.merge(CoursesStudents(course_id=course_id, student_id=student_id))
    await session.commit()


async def add_max_grade(session: AsyncSession, data, max_grade):
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(max_grade=max_grade)
    await session.execute(stmt)
    await session.commit()


async def get_single_submission_teacher(session: AsyncSession, submission_id):
    stmt = select(Submissions).where(Submissions.id == submission_id)
    result = await session.execute(stmt)
    submission = result.scalar()
    stmt = select(Publications.max_grade).where(Publications.id == submission.publication)
    result = await session.execute(stmt)
    max_grade = result.scalar()
    return submission, max_grade


async def get_single_submission_by_student_and_publication(session: AsyncSession, publication_id, student_id):
    stmt = select(Submissions).where(
        Submissions.publication == publication_id and Submissions.student == student_id)
    result = await session.execute(stmt)
    submission = result.scalar()
    return submission


async def set_submission_grade(session: AsyncSession, data, grade):
    stmt = update(Submissions).where(Submissions.id == data['submission_id']).values(grade=grade)
    await session.execute(stmt)
    await session.commit()


async def edit_publication_title(session: AsyncSession, data, title):
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(title=title)
    await session.execute(stmt)
    await session.commit()


async def edit_publication_text(session: AsyncSession, data, text):
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(text=text)
    await session.execute(stmt)
    await session.commit()


async def edit_publication_media(session: AsyncSession, data):
    stmt = delete(Media).where(Media.publication == data['publication_id'])
    await session.execute(stmt)
    await session.commit()
    for media in data['media']:
        await session.merge(Media(media_type=media[0], file_id=media[1], publication=data['publication_id']))
    await session.commit()


async def edit_publication_datetime(session: AsyncSession, data, datetime):
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(finish_date=datetime)
    await session.execute(stmt)
    await session.commit()


async def create_course(session: AsyncSession, data, teacher):
    await session.merge(Courses(name=data['name'], teacher=teacher))
    await session.commit()


async def get_user(session: AsyncSession, user_id):
    stmt = select(Users).where(Users.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar()
    return user


async def get_media(session: AsyncSession, publication_id=None, submission_id=None):
    if publication_id:
        query = select(Media).where(Media.publication == publication_id)
    else:
        query = select(Media).where(Media.submission == submission_id)
    result = await session.execute(query)
    media_files = result.scalars().all()
    return media_files


async def edit_course_name(session: AsyncSession, data):
    stmt = update(Courses).where(Courses.id == data['course_id']).values(name=data['name'])
    await session.execute(stmt)
    await session.commit()
