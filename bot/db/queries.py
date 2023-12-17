import json
from datetime import datetime
from json import JSONDecodeError

from sqlalchemy import select, Sequence, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from __main__ import redis_cache as redis
from db import Courses, CoursesStudents, Media, Publications, Users, Submissions


async def db_object_serializer(obj):
    if type(obj) == list:
        serialized_data = []
        for item in obj:
            serialized_single_data = {}
            for key, value in item.__dict__.items():
                if key not in ['metadata', 'registry', '_sa_instance_state']:
                    if isinstance(value, datetime):
                        serialized_single_data[key] = value.isoformat()
                    else:
                        serialized_single_data[key] = value
            serialized_data.append(serialized_single_data)

        serialized_data_json = json.dumps(serialized_data)

    else:
        serialized_single_data = {}
        for key, value in obj.__dict__.items():
            if key not in ['metadata', 'registry', '_sa_instance_state']:
                if isinstance(value, datetime):
                    serialized_single_data[key] = value.isoformat()
                else:
                    serialized_single_data[key] = value
        serialized_data_json = json.dumps(serialized_single_data)

    return serialized_data_json


async def db_object_deserializer(json_obj):
    deserialized_data = json.loads(json_obj)

    date_attributes = ["reg_date", "upd_date", "add_date", "finish_date"]

    if type(deserialized_data) == list:
        for item in deserialized_data:
            for attr in item:
                if attr in deserialized_data and deserialized_data[attr] is not None:
                    deserialized_data[attr] = datetime.fromisoformat(deserialized_data[attr])

    else:
        for attr in date_attributes:
            if attr in deserialized_data and deserialized_data[attr] is not None:
                deserialized_data[attr] = datetime.fromisoformat(deserialized_data[attr])

    return deserialized_data


async def change_role_to_teacher(session: AsyncSession, student_id):
    stmt = update(Users).where(Users.user_id == student_id).values(is_teacher=True)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'user:{student_id}')


async def change_role_to_student(session: AsyncSession, teacher_id):
    stmt = update(Users).where(Users.user_id == teacher_id).values(is_teacher=False)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'user:{teacher_id}')


async def get_publications(session: AsyncSession, course_id: int, limit: int = None):
    cached_publications = await redis.get(f'publications_course:{course_id}')
    if limit:
        if cached_publications:
            json_publications = await db_object_deserializer(cached_publications)
            if type(json_publications) == list:
                posts = [Publications(**publication) for publication in json_publications[:5]]
            else:
                posts = [Publications(**json_publications)]
        else:
            stmt = select(Publications).where(Publications.course_id == course_id).order_by(
                Publications.add_date.desc()).limit(limit)
            res = await session.execute(stmt)
            posts = res.scalars().all()
    else:
        if cached_publications:
            json_publications = await db_object_deserializer(cached_publications)
            if type(json_publications) == list:
                posts = [Publications(**publication) for publication in json_publications]
            else:
                posts = [Publications(**json_publications)]
        else:
            stmt = select(Publications).where(Publications.course_id == course_id).order_by(
                Publications.add_date.desc())
            res = await session.execute(stmt)
            posts = res.scalars().all()
            serialized_user = await db_object_serializer(posts)
            await redis.set(f'publications_course:{course_id}', serialized_user)

    return posts


async def get_students(session: AsyncSession, course_id: int, limit: int = None):
    cached_students = await redis.get(f'students_course:{course_id}')
    if limit:
        if cached_students:
            json_students = await db_object_deserializer(cached_students)
            if type(json_students) == list:
                students = [Users(**student) for student in json_students[:5]]
            else:
                students = [Users(**json_students)]
        else:
            stmt = select(Users).join(CoursesStudents).where(CoursesStudents.course_id == course_id).limit(limit)
            result = await session.execute(stmt)
            students = result.scalars().all()
    else:
        if cached_students:
            json_students = await db_object_deserializer(cached_students)
            if type(json_students) == list:
                students = [Users(**student) for student in json_students]
            else:
                students = [Users(**json_students)]
        else:
            stmt = select(Users).join(CoursesStudents).where(CoursesStudents.course_id == course_id)
            result = await session.execute(stmt)
            students = result.scalars().all()
            serialized_user = await db_object_serializer(students)
            await redis.set(f'students_course:{course_id}', serialized_user)

    return students


async def get_single_publication(session: AsyncSession, publication_id):
    cached_publication = await redis.get(f'publication:{publication_id}')
    if cached_publication:
        json_publication = await db_object_deserializer(cached_publication)
        publication = Publications(**json_publication)
    else:
        stmt = select(Publications).where(Publications.id == publication_id)
        result = await session.execute(stmt)
        publication = result.scalar()
        serialized_publication = await db_object_serializer(publication)
        await redis.set(f'publication:{publication.id}', serialized_publication)
    return publication


async def create_user(session, callback, is_teacher):
    await session.merge(
        Users(user_id=callback.from_user.id, username=callback.from_user.username,
              first_name=callback.from_user.first_name, second_name=callback.from_user.last_name,
              is_teacher=is_teacher))


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

    stmt = select(Courses).where(Courses.id == course_id)
    res = await session.execute(stmt)
    course = res.scalar()

    stmt = select(Publications.id).where(Publications.course_id == course_id)
    res = await session.execute(stmt)
    publications = res.scalars().all()

    stmt = delete(Courses).where(Courses.id == course_id)
    await session.execute(stmt)
    await session.commit()

    await redis.delete(f'publications_course:{course_id}')
    await redis.delete(f'students_course:{course_id}')
    await redis.delet(f'courses_teacher:{course.teacher_id}')
    await redis.delet(f'course:{course_id}')
    for student in students:
        await redis.delete(f'courses_student:{student}')
    for publication in publications:
        await redis.delete(f'submissions_publication:{publication.id}')
        await redis.delete(f'medias_publication:{publication.id}')

    return course.name, students


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

    stmt = select(Publications.course_id).where(Publications.id == publication_id)
    result = await session.execute(stmt)
    course_id = result.scalar()
    await redis.delete(f'publication:{publication_id}')
    await redis.delete(f'publications_course:{course_id}')
    await redis.delete(f'submissions_publication:{publication_id}')
    await redis.delete(f'medias_publication:{publication_id}')


async def get_submissions(session: AsyncSession, publication_id: int, limit: int = None) -> Sequence:
    cached_submissions = await redis.get(f'submissions_publication:{publication_id}')
    if limit:
        if cached_submissions:
            json_submissions = await db_object_deserializer(cached_submissions)
            if type(json_submissions) == list:
                submissions = [Submissions(**submission) for submission in json_submissions[:5]]
            else:
                submissions = [Submissions(**json_submissions)]
        else:
            stmt = select(Submissions).where(Submissions.publication == publication_id).limit(limit)
            result = await session.execute(stmt)
            submissions = result.scalars().all()
    else:
        if cached_submissions:
            json_submissions = await db_object_deserializer(cached_submissions)
            if type(json_submissions) == list:
                submissions = [Submissions(**submission) for submission in json_submissions]
            else:
                submissions = [Submissions(**json_submissions)]
        else:
            stmt = select(Submissions).where(Submissions.publication == publication_id)
            result = await session.execute(stmt)
            submissions = result.scalars().all()
            serialized_submissions = await db_object_serializer(submissions)
            await redis.set(f'submissions_publication:{publication_id}', serialized_submissions)

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
    await redis.delete(f'students_course:{course}')


async def get_course_by_id(session: AsyncSession, course_id):
    cached_course = await redis.get(f'course:{course_id}')
    if cached_course:
        json_course = await db_object_deserializer(cached_course)
        course = Courses(**json_course)
    else:
        stmt = select(Courses).where(Courses.id == course_id)
        result = await session.execute(stmt)
        course = result.scalar()
        serialized_course = await db_object_serializer(course)
        await redis.set(f'course{course_id}', serialized_course)
    return course


async def get_courses_teacher(session: AsyncSession, teacher_id, limit: int = None):
    cached_courses = await redis.get(f'courses_teacher:{teacher_id}')
    if limit:
        if cached_courses:
            json_courses = await db_object_deserializer(cached_courses)
            if type(json_courses) == list:
                courses = [Courses(**course) for course in json_courses[:5]]
            else:
                courses = [Courses(**json_courses)]
        else:
            stmt = select(Courses).where(Courses.teacher == teacher_id).limit(limit)
            res = await session.execute(stmt)
            courses = res.scalars().all()
    else:
        if cached_courses:
            json_courses = await db_object_deserializer(cached_courses)
            if type(json_courses) == list:
                courses = [Courses(**course) for course in json_courses]
            else:
                courses = [Courses(**json_courses)]
        else:
            stmt = select(Courses).where(Courses.teacher == teacher_id)
            res = await session.execute(stmt)
            courses = res.scalars().all()
            serialized_courses = db_object_serializer(courses)
            redis.set(f'courses_teacher:{teacher_id}', serialized_courses)

    return courses


async def get_courses_student(session: AsyncSession, student_id, limit: int = None):
    cached_courses = await redis.get(f'courses_student:{student_id}')
    if limit:
        if cached_courses:
            json_courses = await db_object_deserializer(cached_courses)
            if type(json_courses) == list:
                courses = [Courses(**course) for course in json_courses[:5]]
            else:
                courses = [Courses(**json_courses)]
        else:
            stmt = select(Courses).join(CoursesStudents).where(CoursesStudents.student_id == student_id).limit(limit)
            res = await session.execute(stmt)
            courses = res.scalars().all()
    else:
        if cached_courses:
            json_courses = await db_object_deserializer(cached_courses)
            if type(json_courses) == list:
                courses = [Courses(**course) for course in json_courses]
            else:
                courses = [Courses(**json_courses)]
        else:
            stmt = select(Courses).join(CoursesStudents).where(CoursesStudents.student_id == student_id)
            res = await session.execute(stmt)
            courses = res.scalars().all()
            serialized_courses = db_object_serializer(courses)
            redis.set(f'courses_student:{student_id}', serialized_courses)

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
    await redis.delete(f'submissions_publication:{data["publication_id"]}')
    return submission


async def create_publication(session: AsyncSession, data):
    publication = await session.merge(Publications(title=data['title'], course_id=data['course_id'], text=data['text']))
    await session.commit()
    await redis.delete(f'publications_course:{data["course_id"]}')
    return publication


async def create_media(session: AsyncSession, media, submission=None, publication=None):
    await session.merge(
        Media(media_type=media[0], file_id=media[1], submission=submission.id if submission else None,
              publication=publication.id if publication else None))
    await session.commit()


async def delete_submission(session: AsyncSession, data, student_id):
    submission_id_query = select(Submissions.id).where(
        Submissions.publication == data['publication_id'] and Submissions.student == student_id)
    submission_id = await session.execute(submission_id_query)
    submission_id = submission_id.scalar()
    stmt = delete(Media).where(
        Media.submission.in_(select(Submissions.id).where(
            Submissions.publication == data['publication_id'] and Submissions.student == student_id)))
    await redis.delete(f'medias_submission:{submission_id}')
    await session.execute(stmt)
    stmt = delete(Submissions).where(
        Submissions.publication == data['publication_id'] and Submissions.student == student_id)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'submissions_publication:{data["publication_id"]}')
    await redis.delete(f'medias_submission:{submission_id}')


async def get_single_coursestudent(session: AsyncSession, course_id, student_id):
    stmt = select(CoursesStudents).where(
        CoursesStudents.course_id == course_id,
        CoursesStudents.student_id == student_id
    )
    res = await session.execute(stmt)
    coursestudent = res.scalar()
    return coursestudent


async def join_course_student(session: AsyncSession, course_id, student_id):
    await session.merge(CoursesStudents(course_id=course_id, student_id=student_id))
    await session.commit()
    await redis.delete(f'students_course:{course_id}')


async def add_max_grade(session: AsyncSession, data, max_grade):
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(max_grade=max_grade)
    await session.execute(stmt)
    await session.commit()


async def get_single_submission_teacher(session: AsyncSession, submission_id):
    stmt = select(Submissions).where(Submissions.id == submission_id)
    result = await session.execute(stmt)
    submission = result.scalar()
    return submission

#TODO: REWORK UPPER FUNC AND BELOW ONE(CACHING)


async def get_single_submission_by_student_and_publication(session: AsyncSession, publication_id, student_id):
    cached_submission = await redis.get(f'submission:{publication_id}:{student_id}')
    if cached_submission:
        json_submission = await db_object_deserializer(cached_submission)
        submission = Submissions(**json_submission)
    else:
        stmt = select(Submissions).where(
            Submissions.publication == publication_id and Submissions.student == student_id)
        result = await session.execute(stmt)
        submission = result.scalar()
        serialized_submission = db_object_serializer(submission)
        await redis.set(f'submission:{publication_id}:{student_id}', serialized_submission)
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
    await redis.delete(f'medias_publication:{data["publication_id"]}')
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
    cached_user = await redis.get(f'user:{user_id}')
    if cached_user:
        json_user = await db_object_deserializer(cached_user)
        user = Users(**json_user)
    else:
        stmt = select(Users).where(Users.user_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar()
        serialized_user = await db_object_serializer(user)
        await redis.set(f'user:{user.user_id}', serialized_user)
    return user


async def get_media(session: AsyncSession, publication_id=None, submission_id=None):
    if publication_id:
        cached_media = await redis.get(f'medias_publication:{publication_id}')
        if cached_media:
            try:
                json_media = json.loads(cached_media)
                if type(json_media) == list:
                    media_files = [Media(**media_data) for media_data in json_media]
                else:
                    media_files = [Media(**json_media)]
            except JSONDecodeError:
                media_files = None
        else:
            query = select(Media).where(Media.publication == publication_id)
            result = await session.execute(query)
            media_files = result.scalars().all()
            if len(media_files) != 0:
                serialized_media = await db_object_serializer(media_files)
                await redis.set(f'medias_publication:{publication_id}', serialized_media)
            else:
                await redis.set(f'medias_publication:{publication_id}', str(None))
                media_files = None
    else:
        cached_media = await redis.get(f'medias_submission:{submission_id}')
        if cached_media:
            try:
                json_media = json.loads(cached_media)
                if type(json_media) == list:
                    media_files = [Media(**media_data) for media_data in json_media]
                else:
                    media_files = [Media(**json_media)]
            except JSONDecodeError:
                media_files = None
        else:
            query = select(Media).where(Media.submission == submission_id)
            result = await session.execute(query)
            media_files = result.scalars().all()
            if len(media_files) != 0:
                serialized_media = await db_object_serializer(media_files)
                await redis.set(f'medias_submission:{submission_id}', serialized_media)
            else:
                await redis.set(f'medias_submission:{submission_id}', str(None))
                media_files = None

    return media_files


async def edit_course_name(session: AsyncSession, data):
    stmt = update(Courses).where(Courses.id == data['course_id']).values(name=data['name'])
    await session.execute(stmt)
    await session.commit()
