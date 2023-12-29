import json
from datetime import datetime
from json import JSONDecodeError

from sqlalchemy import select, Sequence, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.__main__ import redis_cache as redis
from bot.db import Courses, CoursesStudents, Media, Publications, Users, Submissions


async def db_object_serializer(obj):
    """Serializes SQLAlchemy objects into JSON format"""
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
    """Deserializes JSON objects into SQLAlchemy objects"""
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
    """Changes the role of a user with the given student_id to a teacher."""
    stmt = update(Users).where(Users.user_id == student_id).values(is_teacher=True)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'user:{student_id}')


async def change_role_to_student(session: AsyncSession, teacher_id):
    """Changes the role of a user with the given teacher_id to a student."""
    stmt = update(Users).where(Users.user_id == teacher_id).values(is_teacher=False)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'user:{teacher_id}')


async def get_publications(session: AsyncSession, course_id: int, limit: int = None):
    """Retrieves publications for a given course from the database or cache."""
    cached_publications = await redis.get(f'publications_course:{course_id}')
    if limit:
        if cached_publications:
            json_publications = await db_object_deserializer(cached_publications)
            if type(json_publications) == list:
                posts = [Publications(**publication) for publication in json_publications[:limit]]
            else:
                posts = [Publications(**json_publications)]
        else:
            stmt = select(Publications).where(Publications.course_id == course_id).order_by(
                Publications.add_date.desc())
            res = await session.execute(stmt)
            posts = res.scalars().all()
            serialized_posts = await db_object_serializer(posts)
            await redis.set(f'publications_course:{course_id}', serialized_posts)
            await redis.expire(f'publications_course:{course_id}', 604800)
            posts = posts[:limit]
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
            serialized_posts = await db_object_serializer(posts)
            await redis.set(f'publications_course:{course_id}', serialized_posts)
            await redis.expire(f'publications_course:{course_id}', 604800)

    return posts


async def get_students(session: AsyncSession, course_id: int, limit: int = None):
    """Retrieves students for a given course from the database or cache."""
    cached_students = await redis.get(f'students_course:{course_id}')
    if limit:
        if cached_students:
            json_students = await db_object_deserializer(cached_students)
            if type(json_students) == list:
                students = [Users(**student) for student in json_students[:limit]]
            else:
                students = [Users(**json_students)]
        else:
            stmt = select(Users).join(CoursesStudents).where(CoursesStudents.course_id == course_id)
            result = await session.execute(stmt)
            students = result.scalars().all()
            serialized_students = await db_object_serializer(students)
            await redis.set(f'students_course:{course_id}', serialized_students)
            await redis.expire(f'students_course:{course_id}', 604800)
            students = students[:limit]
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
            serialized_students = await db_object_serializer(students)
            await redis.set(f'students_course:{course_id}', serialized_students)
            await redis.expire(f'students_course:{course_id}', 604800)

    return students


async def get_single_publication(session: AsyncSession, publication_id):
    """Retrieves a single publication by its ID from the database or cache."""
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
        await redis.expire(f'publication:{publication.id}', 604800)
    return publication


async def create_user(session, callback, is_teacher):
    """Retrieves a single publication by its ID from the database or cache."""
    await session.merge(
        Users(user_id=callback.from_user.id, username=callback.from_user.username,
              first_name=callback.from_user.first_name, second_name=callback.from_user.last_name,
              is_teacher=is_teacher))


async def delete_coursesstudents(session: AsyncSession, course_id):
    stmt = select(CoursesStudents.student_id).where(Courses.id == course_id)
    res = await session.execute(stmt)
    students = res.scalars().all()

    stmt = delete(CoursesStudents).where(CoursesStudents.course_id == course_id)
    await session.execute(stmt)

    await redis.delete(f'students_course:{course_id}')
    for student in students:
        await redis.delete(f'courses_student:{student}')
    return students


async def delete_submissions(session: AsyncSession, course_id: int = None, publication_id: int = None):
    if publication_id:
        stmt = delete(Media).where(
            Media.submission.in_(select(Submissions.id).where(Submissions.publication == publication_id)))
        await session.execute(stmt)
        stmt = delete(Submissions).where(Submissions.publication == publication_id)
        await session.execute(stmt)
    else:
        stmt = delete(Media).where(
            Media.submission.in_(select(Submissions.id).where(
                Submissions.publication.in_(select(Publications.id).where(Publications.course_id == course_id)))))
        await session.execute(stmt)

        stmt = delete(Submissions).where(
            Submissions.publication.in_(select(Publications.id).where(Publications.course_id == course_id)))
        await session.execute(stmt)


async def delete_publication_query(session: AsyncSession, publication_id: int = None, course_id: int = None):
    """Deletes a publication and related data from the database."""
    if publication_id:
        stmt = select(Publications.course_id).where(Publications.id == publication_id)
        result = await session.execute(stmt)
        course_id = result.scalar()
        stmt = select(Submissions.id).where(Submissions.publication == publication_id)
        result = await session.execute(stmt)
        submissions = result.scalars().all()

        await delete_submissions(session, publication_id=publication_id)

        stmt = delete(Media).where(Media.publication == publication_id)
        await session.execute(stmt)

        stmt = delete(Publications).where(Publications.id == publication_id)
        await session.execute(stmt)

        await session.commit()

        await redis.delete(f'publication:{publication_id}')
        await redis.delete(f'submissions_publication:{publication_id}')
        await redis.delete(f'medias_publication:{publication_id}')

        for submission in submissions:
            await redis.delete(f'submission:{submission}')
    else:
        stmt = select(Publications.id).where(Publications.course_id == course_id)
        res = await session.execute(stmt)
        publications = res.scalars().all()
        stmt = delete(Media).where(
            Media.publication.in_(select(Publications.id).where(Publications.course_id == course_id)))
        await session.execute(stmt)

        stmt = delete(Publications).where(Publications.course_id == course_id)
        await session.execute(stmt)

        for publication in publications:
            await redis.delete(f'publication:{publication}')
            await redis.delete(f'submissions_publication:{publication}')
            await redis.delete(f'medias_publication:{publication}')
            stmt = select(Submissions.id).where(Submissions.publication == publication)
            result = await session.execute(stmt)
            submissions = result.scalars().all()
            for submission in submissions:
                await redis.delete(f'submission:{submission}')

    await redis.delete(f'publications_course:{course_id}')


async def delete_course(session: AsyncSession, course_id: int) -> tuple:
    """Deletes a course and related data from the database."""
    stmt = select(Courses).where(Courses.id == course_id)
    res = await session.execute(stmt)
    course = res.scalar()

    students = await delete_coursesstudents(session, course_id)

    await delete_submissions(session, course_id=course_id)

    await delete_publication_query(session, course_id=course_id)

    stmt = delete(Courses).where(Courses.id == course_id)
    await session.execute(stmt)

    await session.commit()

    await redis.delete(f'courses_teacher:{course.teacher_id}')
    await redis.delete(f'course:{course_id}')

    return course.name, students


async def get_submissions(session: AsyncSession, publication_id: int, limit: int = None) -> Sequence:
    """Retrieves submissions for a given publication from the database or cache."""
    cached_submissions = await redis.get(f'submissions_publication:{publication_id}')
    if limit:
        if cached_submissions:
            json_submissions = await db_object_deserializer(cached_submissions)
            if type(json_submissions) == list:
                submissions = [Submissions(**submission) for submission in json_submissions[:limit]]
            else:
                submissions = [Submissions(**json_submissions)]
        else:
            stmt = select(Submissions).where(Submissions.publication == publication_id)
            result = await session.execute(stmt)
            submissions = result.scalars().all()
            serialized_submissions = await db_object_serializer(submissions)
            await redis.set(f'submissions_publication:{publication_id}', serialized_submissions)
            await redis.expire(f'submissions_publication:{publication_id}', 604800)
            submissions = submissions[:limit]
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
            await redis.expire(f'submissions_publication:{publication_id}', 604800)

    return submissions


async def delete_student_from_course(session: AsyncSession, student, course):
    """Removes a student from a course in the database."""
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
    await redis.delete(f'courses_student:{student}')


async def get_course_by_id(session: AsyncSession, course_id):
    """Retrieves a course by its ID from the database or cache."""
    cached_course = await redis.get(f'course:{course_id}')
    if cached_course:
        json_course = await db_object_deserializer(cached_course)
        course = Courses(**json_course)
    else:
        stmt = select(Courses).where(Courses.id == course_id)
        result = await session.execute(stmt)
        course = result.scalar()
        serialized_course = await db_object_serializer(course)
        await redis.set(f'course:{course_id}', serialized_course)
        await redis.expire(f'course:{course_id}', 604800)
    return course


async def get_courses_teacher(session: AsyncSession, teacher_id, limit: int = None):
    """Retrieves courses for a given teacher from the database or cache."""
    cached_courses = await redis.get(f'courses_teacher:{teacher_id}')
    if limit:
        if cached_courses:
            json_courses = await db_object_deserializer(cached_courses)
            if type(json_courses) == list:
                courses = [Courses(**course) for course in json_courses[:limit]]
            else:
                courses = [Courses(**json_courses)]
        else:
            stmt = select(Courses).where(Courses.teacher == teacher_id)
            res = await session.execute(stmt)
            courses = res.scalars().all()
            serialized_courses = await db_object_serializer(courses)
            await redis.set(f'courses_teacher:{teacher_id}', serialized_courses)
            await redis.expire(f'courses_teacher:{teacher_id}', 604800)
            courses = courses[:limit]
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
            serialized_courses = await db_object_serializer(courses)
            await redis.set(f'courses_teacher:{teacher_id}', serialized_courses)
            await redis.expire(f'courses_teacher:{teacher_id}', 604800)

    return courses


async def get_courses_student(session: AsyncSession, student_id, limit: int = None):
    """Retrieves courses for a given student from the database or cache."""
    cached_courses = await redis.get(f'courses_student:{student_id}')
    if limit:
        if cached_courses:
            json_courses = await db_object_deserializer(cached_courses)
            if type(json_courses) == list:
                courses = [Courses(**course) for course in json_courses[:limit]]
            else:
                courses = [Courses(**json_courses)]
        else:
            stmt = select(Courses).join(CoursesStudents).where(CoursesStudents.student_id == student_id)
            res = await session.execute(stmt)
            courses = res.scalars().all()
            serialized_courses = await db_object_serializer(courses)
            await redis.set(f'courses_student:{student_id}', serialized_courses)
            await redis.expire(f'courses_student:{student_id}', 604800)
            courses = courses[:limit]
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
            serialized_courses = await db_object_serializer(courses)
            await redis.set(f'courses_student:{student_id}', serialized_courses)
            await redis.expire(f'courses_student:{student_id}', 604800)

    return courses


async def get_course_by_key(session: AsyncSession, course_id, key):
    """Retrieves a course by its ID and key from the database."""
    stmt = select(Courses).where(Courses.id == course_id and Courses.key == key)
    res = await session.execute(stmt)
    course = res.scalar()
    return course


async def create_submission(session: AsyncSession, data, student_id):
    """Creates a new submission in the database."""
    submission = await session.merge(
        Submissions(text=data['text'], publication=data['publication_id'], student=student_id))
    await session.commit()
    await redis.delete(f'submissions_publication:{data["publication_id"]}')
    return submission


async def create_publication(session: AsyncSession, data):
    """Creates a new publication in the database."""
    publication = await session.merge(Publications(title=data['title'], course_id=data['course_id'], text=data['text']))
    await session.commit()
    await redis.delete(f'publications_course:{data["course_id"]}')
    return publication


async def create_media(session: AsyncSession, media, submission=None, publication=None):
    """Creates new media entries in the database."""
    await session.merge(
        Media(media_type=media[0], file_id=media[1], submission=submission.id if submission else None,
              publication=publication.id if publication else None))
    await session.commit()


async def delete_submission_query(session: AsyncSession, data, student_id):
    """Deletes a submission and related data from the database."""
    submission_id_query = select(Submissions.id).where(
        Submissions.publication == data['publication_id'] and Submissions.student == student_id)
    submission_id = await session.execute(submission_id_query)
    submission_id = submission_id.scalar()
    stmt = delete(Media).where(
        Media.submission.in_(select(Submissions.id).where(
            Submissions.publication == data['publication_id'] and Submissions.student == student_id)))
    await session.execute(stmt)
    stmt = delete(Submissions).where(
        Submissions.publication == data['publication_id'] and Submissions.student == student_id)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'submissions_publication:{data["publication_id"]}')
    await redis.delete(f'medias_submission:{submission_id}')
    await redis.delete(f'submission:{submission_id}')


async def get_single_coursestudent(session: AsyncSession, course_id, student_id):
    """Retrieves a single course student entry from the database."""
    stmt = select(CoursesStudents).where(
        CoursesStudents.course_id == course_id,
        CoursesStudents.student_id == student_id
    )
    res = await session.execute(stmt)
    coursestudent = res.scalar()
    return coursestudent


async def join_course_student(session: AsyncSession, course_id, student_id):
    """Adds a student to a course in the database."""
    await session.merge(CoursesStudents(course_id=course_id, student_id=student_id))
    await session.commit()
    await redis.delete(f'students_course:{course_id}')
    await redis.delete(f'courses_student:{student_id}')


async def add_max_grade(session: AsyncSession, data, max_grade):
    """Updates the maximum grade for a publication in the database."""
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(max_grade=max_grade)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'publication:{data["publication_id"]}')



async def get_single_submission_teacher(session: AsyncSession, submission_id):
    """Retrieves a single submission by its ID from the database or cache."""
    cached_submission = await redis.get(f'submission:{submission_id}')
    if cached_submission:
        json_submission = await db_object_deserializer(cached_submission)
        submission = Submissions(**json_submission)
    else:
        stmt = select(Submissions).where(Submissions.id == submission_id)
        result = await session.execute(stmt)
        submission = result.scalar()
        serialized_submission = await db_object_serializer(submission)
        await redis.set(f'submission:{submission_id}', serialized_submission)
        await redis.expire(f'submission:{submission_id}', 604800)
    return submission


async def get_single_submission_by_student_and_publication(session: AsyncSession, publication_id, student_id):
    """Retrieves a single submission by student and publication ID from the database."""
    stmt = select(Submissions).where(
        Submissions.publication == publication_id and Submissions.student == student_id)
    result = await session.execute(stmt)
    submission = result.scalar()
    return submission


async def set_submission_grade(session: AsyncSession, data, grade):
    """Sets the grade for a submission in the database."""
    stmt = update(Submissions).where(Submissions.id == data['submission_id']).values(grade=grade)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'submission:{data["submission_id"]}')


async def edit_publication_title(session: AsyncSession, data, title):
    """Updates the title of a publication in the database."""
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(title=title)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'publication:{data["publication_id"]}')
    await redis.delete(f'publications_course:{data["course_id"]}')



async def edit_publication_text(session: AsyncSession, data, text):
    """Updates the text of a publication in the database."""
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(text=text)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'publication:{data["publication_id"]}')


async def edit_publication_media(session: AsyncSession, data):
    """Updates the media files associated with a publication in the database."""
    stmt = delete(Media).where(Media.publication == data['publication_id'])
    await redis.delete(f'medias_publication:{data["publication_id"]}')
    await session.execute(stmt)
    await session.commit()
    for media in data['media']:
        await session.merge(Media(media_type=media[0], file_id=media[1], publication=data['publication_id']))
    await session.commit()


async def edit_publication_datetime(session: AsyncSession, data, dt):
    """Updates the finish date of a publication in the database."""
    stmt = update(Publications).where(Publications.id == data['publication_id']).values(finish_date=dt)
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'publication:{data["publication_id"]}')


async def create_course(session: AsyncSession, data, teacher):
    """Creates a new course in the database"""
    await session.merge(Courses(name=data['name'], teacher=teacher))
    await session.commit()
    await redis.delete(f'courses_teacher:{teacher}')


async def get_user(session: AsyncSession, user_id):
    """Retrieves a user by ID from the database or cache."""
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
        await redis.expire(f'user:{user.user_id}', 604800)
    return user


async def get_media(session: AsyncSession, publication_id=None, submission_id=None):
    """Retrieves media files for a publication or submission from the database or cache."""
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
                await redis.expire(f'medias_publication:{publication_id}', 604800)
            else:
                await redis.set(f'medias_publication:{publication_id}', str(None))
                await redis.expire(f'medias_publication:{publication_id}', 604800)
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
                await redis.expire(f'medias_submission:{submission_id}', 604800)
            else:
                await redis.set(f'medias_submission:{submission_id}', str(None))
                await redis.expire(f'medias_submission:{submission_id}', 604800)
                media_files = None

    return media_files


async def edit_course_name(session: AsyncSession, data):
    """Updates the name of a course in the database."""
    stmt = select(CoursesStudents.student_id).where(Courses.id == data['course_id'])
    res = await session.execute(stmt)
    students = res.scalars().all()

    stmt = select(Courses.teacher).where(Courses.id == data['course_id'])
    res = await session.execute(stmt)
    teacher = res.scalars().all()

    stmt = update(Courses).where(Courses.id == data['course_id']).values(name=data['name'])
    await session.execute(stmt)
    await session.commit()
    await redis.delete(f'course:{data["course_id"]}')

    for student in students:
        await redis.delete(f'courses_student:{student}')

    await redis.delete(f'courses_teacher:{teacher}')