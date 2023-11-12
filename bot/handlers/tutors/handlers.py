from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery, \
    InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db import Courses, Publications, Media, Users, CoursesStudents, Submissions
from handlers.common.keyboards import choose
from handlers.common.queries import get_students, get_code, delete_course, get_publications, delete_publication_query, \
    get_submissions
from handlers.common.services import CourseInteract, publications, create_inline_courses, course_info, \
    single_publication, Pagination, pagination_handler, paginator, student_name_builder, add_media, \
    submission_name_builder, single_submission
from handlers.tutors import keyboards as kb
from handlers.tutors.filters import Teacher
from handlers.tutors.services import publication_date, publication_time

router = Router()


@router.message(Teacher(), F.text == 'My courses')
async def tutor_courses(message: Message, session: AsyncSession):
    stmt = select(Courses).where(Courses.teacher == message.from_user.id)
    res = await session.execute(stmt)
    courses = res.scalars().all()
    if courses:
        await create_inline_courses(courses, message, kb)
    else:
        await message.answer('You don`t have any courses for now', reply_markup=kb.courses)


@router.callback_query(Teacher(), F.data.startswith('course_'))
async def teacher_course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    course_id = int(callback.data[7:])
    await course_info(callback, session, state, kb, course_id)
    code = await get_code(session, course_id)
    students = await get_students(session, course_id)
    await callback.message.answer(f'Now there are <b>{len(students) if students else "no"}</b> students\nInvite code:',
                                  parse_mode='HTML')
    await callback.message.answer(f'<b>{code}</b>',
                                  parse_mode='HTML')


@router.callback_query(Teacher(), CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'publications'))
async def pagination_handler_teacher(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                     state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    posts = await get_publications(session, course_id)
    await pagination_handler(query, callback_data, posts)


@router.message(Teacher(), F.text == 'Publications', CourseInteract.single_course)
async def publications_teacher(message: Message, session: AsyncSession, state: FSMContext):
    await publications(message, session, state, kb)


@router.callback_query(Teacher(), CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'students'))
async def pagination_handler_students(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                      state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    students = await get_students(session, course_id)
    await pagination_handler(query, callback_data, students)


@router.message(Teacher(), F.text == 'Students', CourseInteract.single_course)
async def students(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    stmt = select(Users).join(CoursesStudents).where(Courses.id == course_id).limit(5)
    res = await session.execute(stmt)
    students = res.scalars().all()
    if students:
        pag = paginator(entity_type='students')
        builder = InlineKeyboardBuilder()
        for student in students:
            student_name = await student_name_builder(student)
            builder.row(InlineKeyboardButton(text=student_name, callback_data=f'student_{student.user_id}'))

        builder.row(*pag.buttons, width=2)
        await state.set_state(CourseInteract.single_course)
        await message.answer('Here is students:', reply_markup=builder.as_markup())
    else:
        await state.set_state(CourseInteract.single_course)
        await message.answer('There is no any students yet', reply_markup=kb.single_course)


class Students(StatesGroup):
    delete_confirm = State()


@router.callback_query(Teacher(), F.data.startswith('student_'), CourseInteract.single_course)
async def single_student(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    student_id = int(callback.data[8:])
    stmt = select(Users).where(Users.user_id == student_id)
    result = await session.execute(stmt)
    student = result.scalar()
    if student.username:
        student_name = '@' + student.username
    elif student.first_name:
        student_name = student.first_name
    else:
        student_name = callback.data
    await callback.answer()
    keyboard = choose
    keyboard.keyboard.pop()
    await callback.message.answer(f'Do you want to delete {student_name} from your course?',
                                  reply_markup=keyboard)
    await state.set_state(Students.delete_confirm)
    await state.update_data(student_id=student_id)


@router.message(Teacher(), Students.delete_confirm, F.text.casefold() == 'yes')
async def delete_student_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    student_id = data['student_id']
    stmt = delete(CoursesStudents).where(
        CoursesStudents.course_id == course_id and CoursesStudents.user_id == student_id)
    await session.execute(stmt)
    await session.commit()
    await message.reply(
        f'User have been deleted from your course',
        reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await students(message, session, state)


@router.message(Teacher(), Students.delete_confirm, F.text.casefold() == 'no')
async def delete_student_declined(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(CourseInteract.single_course)
    await students(message, session, state)
    await message.answer('Or choose an option below:', reply_markup=kb.single_course)


@router.message(Teacher(), Students.delete_confirm)
async def delete_student_other(message: Message, state: FSMContext):
    await state.set_state(Students.delete_confirm)
    await message.answer('Сhoose "Yes" or "No"')


class AddPublication(StatesGroup):
    title = State()
    text = State()
    media = State()
    grade = State()
    date = State()
    time = State()


@router.message(Teacher(), F.text == 'Add publication', CourseInteract.single_course)
async def add_publication_start(message: Message, state: FSMContext):
    await state.set_state(AddPublication.title)
    await message.answer('How would you like to call your publication?', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddPublication.title)
async def add_publication_title(message: Message, state: FSMContext):
    if len(message.text) >= 35:
        # If the name is too long, stay in the AddCourse.name state and inform the user
        await state.set_state(AddPublication.title)
        await message.answer('Name is too long, try shorter')
    else:
        # If the name is acceptable, move to the AddCourse.confirm state
        await state.update_data(title=message.text, media=[])
        await state.set_state(AddPublication.text)
        await message.answer('Now enter a text of your publication:')


@router.message(Teacher(), AddPublication.text)
async def add_publication_text(message: Message, state: FSMContext):
    if len(message.text) >= 4096:
        # If the name is too long, stay in the AddCourse.name state and inform the user
        await state.set_state(AddPublication.text)
        await message.answer('Text is too long, try shorter')
    else:
        # If the name is acceptable, move to the AddCourse.confirm state
        await state.update_data(text=message.text)
        await state.set_state(AddPublication.media)
        await message.answer('Now send a media for your publication or press "Ready" button', reply_markup=kb.ready)


@router.message(Teacher(), F.text == 'Ready', AddPublication.media)
async def add_publication_ready(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()

    publication = await session.merge(Publications(title=data['title'], course_id=data['course_id'], text=data['text']))
    await session.commit()

    for media in data['media']:
        await session.merge(Media(media_type=media[0], file_id=media[1], publication=publication.id))

    await session.commit()
    await message.answer('Publication has been created')
    await state.set_state(AddPublication.grade)
    await state.update_data(publication_id=publication.id, max_grade=None)
    await message.answer(
        'Now enter a maximum grade for this task or press "Ready" to leave the publication without grading',
        reply_markup=kb.ready)


@router.message(Teacher(), AddPublication.grade)
async def add_publication_grade(message: Message, session: AsyncSession, state: FSMContext):
    if message.text == 'Ready':
        await state.set_state(AddPublication.date)
        await state.update_data(date=None, time=None)
        await message.answer('Now enter finish date(dd.mm.yyyy) or press "Ready" button', reply_markup=kb.ready)
    elif message.text.isdigit() and 0 < int(message.text) <= 100:
        data = await state.get_data()
        stmt = update(Publications).where(Publications.id == data['publication_id']).values(max_grade=int(message.text))
        await session.execute(stmt)
        await session.commit()
        await state.set_state(AddPublication.date)
        await state.update_data(date=None, time=None)
        await message.answer('Now enter finish date(dd.mm.yyyy) or press "Ready" button', reply_markup=kb.ready)
    else:
        await state.set_state(AddPublication.grade)
        await message.answer('Max grade must be greater then 0 and less or equals 100')


@router.message(Teacher(), AddPublication.media)
async def add_publication_media(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(AddPublication.media)
    data = await state.get_data()
    if len(data['media']) >= 20:
        await add_publication_ready(message, session, state)
    else:
        await add_media(message, session, state, data)


@router.message(Teacher(), AddPublication.date)
async def add_publication_date(message: Message, session: AsyncSession, state: FSMContext):
    await publication_date(message, session, state, AddPublication.date, AddPublication.time)


@router.message(Teacher(), AddPublication.time)
async def add_publication_time(message: Message, session: AsyncSession, state: FSMContext):
    await publication_time(message, session, state, AddPublication.time)


class PublicationInteract(StatesGroup):
    interact = State()
    edit = State()
    title_confirm = State()
    text_confirm = State()
    media_confirm = State()
    date_confirm = State()
    time_confirm = State()
    grade_submission = State()
    grade_confirm = State()


@router.callback_query(Teacher(), F.data.startswith('publication_'))
async def teacher_single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await single_publication(callback, session, state, kb)
    await state.set_state(PublicationInteract.interact)
    await state.update_data(publication_id=int(callback.data[12:]))


@router.callback_query(Teacher(), PublicationInteract.interact, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'submissions'))
async def pagination_handler_submissions(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                         state: FSMContext):
    data = await state.get_data()
    submissions = await get_submissions(session, data['publication_id'])
    await pagination_handler(query, callback_data, submissions, session)


@router.message(Teacher(), F.text == 'Submissions', PublicationInteract.interact)
async def submissions(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    publication_id = data['publication_id']
    stmt = select(Submissions).where(Submissions.publication == publication_id).limit(5)
    res = await session.execute(stmt)
    submissions = res.scalars().all()
    if submissions:
        pag = paginator(entity_type='submissions')
        builder = InlineKeyboardBuilder()
        for submission in submissions:
            student_name = await submission_name_builder(session, submission.student)
            builder.row(InlineKeyboardButton(text=student_name, callback_data=f'submission_{submission.id}'))

        builder.row(*pag.buttons, width=2)
        await state.set_state(PublicationInteract.interact)
        await message.answer('Here is submissions:', reply_markup=builder.as_markup())
    else:
        await message.answer('There is no any submissions yet', reply_markup=kb.single_course)


@router.callback_query(Teacher(), F.data.startswith('submission_'))
async def teacher_single_submission(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    stmt = select(Submissions).where(Submissions.id == int(callback.data[11:]))
    result = await session.execute(stmt)
    submission = result.scalar()
    stmt = select(Publications.max_grade).where(Publications.id == submission.publication)
    result = await session.execute(stmt)
    max_grade = result.scalar()
    await state.update_data(submission_id=submission.id, max_grade=max_grade)
    await single_submission(callback.message, session, submission, kb, max_grade)
    await callback.answer()
    await state.set_state(PublicationInteract.grade_submission)


@router.message(Teacher(), PublicationInteract.grade_submission, F.text.in_(('Change grade', 'Grade')))
async def grade_submission(message: Message, state: FSMContext):
    await message.answer('Enter a grade for submission', reply_markup=kb.ready)
    await state.set_state(PublicationInteract.grade_confirm)
    if message.text == 'Change grade':
        await state.update_data(action='update')
    else:
        await state.update_data(action='grade')


@router.message(Teacher(), PublicationInteract.grade_confirm)
async def grade_submission_confirm(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    if message.text == 'Ready':
        await state.set_state(PublicationInteract.interact)
        await message.answer('No further actions', reply_markup=kb.publication_interact)
        await submissions(message, session, state)

    elif message.text.isdigit() and 0 < int(message.text) <= data['max_grade']:
        stmt = update(Submissions).where(Submissions.id == data['submission_id']).values(grade=int(message.text))
        await session.execute(stmt)
        await session.commit()
        if data['action'] == 'update':
            await message.answer('Grade hs been changed', reply_markup=kb.publication_interact)
        else:
            await message.answer('Submission has been graded', reply_markup=kb.publication_interact)

        await state.set_state(PublicationInteract.interact)
        await submissions(message, session, state)
    else:
        await state.set_state(PublicationInteract.grade_confirm)
        await message.answer(f'Grade must be greater then 0 and less or equals to {data["max_grade"]}')


@router.message(Teacher(), PublicationInteract.grade_submission, F.text == 'Go back')
async def grade_go_back(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(PublicationInteract.interact)
    await message.answer('No further actions with submissions', reply_markup=kb.publication_interact)
    await submissions(message, session, state)


@router.message(Teacher(), PublicationInteract.interact, F.text == 'Edit')
async def edit_publication(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(PublicationInteract.edit)
    await message.answer('What would you like to edit?', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Title', callback_data='title'),
         InlineKeyboardButton(text='Text', callback_data='text')],
        [InlineKeyboardButton(text='Media', callback_data='media'),
         InlineKeyboardButton(text='Submit date', callback_data='submit_date')]]))


@router.callback_query(Teacher(), PublicationInteract.edit, F.data == 'title')
async def edit_title(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    await callback.message.answer('Enter a title of your publication')
    await state.set_state(PublicationInteract.title_confirm)


@router.message(Teacher(), PublicationInteract.title_confirm)
async def edit_title_confirm(message: Message, session: AsyncSession, state: FSMContext):
    if len(message.text) >= 35:
        await state.set_state(PublicationInteract.title_confirm)
        await message.answer('Title is too long, try shorter')
    else:
        data = await state.get_data()
        stmt = update(Publications).where(Publications.id == data['publication_id']).values(title=message.text)
        await session.execute(stmt)
        await session.commit()
        await message.answer('Title has been changed')
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)


@router.callback_query(Teacher(), PublicationInteract.edit, F.data == 'text')
async def edit_title(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    await callback.message.answer('Enter a text of your publication')
    await state.set_state(PublicationInteract.text_confirm)


@router.message(Teacher(), PublicationInteract.text_confirm)
async def edit_title_confirm(message: Message, session: AsyncSession, state: FSMContext):
    if len(message.text) >= 4096:
        await state.set_state(PublicationInteract.text_confirm)
        await message.answer('Text is too long, try shorter')
    else:
        data = await state.get_data()
        stmt = update(Publications).where(Publications.id == data['publication_id']).values(text=message.text)
        await session.execute(stmt)
        await session.commit()
        await message.answer('Text has been changed')
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)


@router.message(Teacher(), F.text == 'Ready', PublicationInteract.media_confirm)
async def edit_media_ready(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()

    if len(data['media']) == 0:
        await message.answer('Nothing to add, all media stayed the same', reply_markup=kb.single_course)
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)

    else:
        stmt = delete(Media).where(Media.publication == data['publication_id'])
        await session.execute(stmt)
        await session.commit()
        for media in data['media']:
            await session.merge(Media(media_type=media[0], file_id=media[1], publication=data['publication_id']))
        await session.commit()
        await message.answer('All media have been added', reply_markup=kb.single_course)
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)


@router.callback_query(Teacher(), PublicationInteract.edit, F.data == 'media')
async def edit_media(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        'All media from this publication will be deleted, so you will add it from the very beginning\nNow send media or press "Ready button to leave the same',
        reply_markup=kb.ready)
    await state.update_data(media=[])
    await state.set_state(PublicationInteract.media_confirm)


@router.message(Teacher(), PublicationInteract.media_confirm)
async def edit_media_confirm(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(PublicationInteract.media_confirm)
    data = await state.get_data()
    if len(data['media']) >= 20:
        await edit_media_ready(message, session, state)
    else:
        await add_media(message, session, state, data)


@router.callback_query(Teacher(), PublicationInteract.edit, F.data == 'submit_date')
async def edit_datetime(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    await callback.message.answer('Now enter submit date (dd:mm:yyyy) or press "Ready" button to clear it',
                                  reply_markup=kb.ready)
    await state.update_data(date=None, time=None)
    await state.set_state(PublicationInteract.date_confirm)


@router.message(Teacher(), PublicationInteract.date_confirm)
async def edit_date(message: Message, session: AsyncSession, state: FSMContext):
    await publication_date(message, session, state, PublicationInteract.date_confirm, PublicationInteract.time_confirm)


@router.message(Teacher(), PublicationInteract.time_confirm)
async def add_publication_time(message: Message, session: AsyncSession, state: FSMContext):
    await publication_time(message, session, state, PublicationInteract.time_confirm)


@router.message(Teacher(), PublicationInteract.interact, F.text == 'Delete')
async def delete_publication(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    await delete_publication_query(session, data['publication_id'])
    await message.answer('Publication has been deleted', reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await publications_teacher(message, session, state)


@router.message(Teacher(), PublicationInteract.interact, F.text == 'Go back')
async def publication_go_back(message: Message, session: AsyncSession, state: FSMContext):
    await message.answer('No further actions with publication', reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await publications_teacher(message, session, state)


class AddCourse(StatesGroup):
    name = State()
    confirm = State()


@router.message(Teacher(), F.text == 'Add course')
async def add_course_start(message: Message, state: FSMContext):
    # Set the state to AddCourse.name to collect the course name
    await state.set_state(AddCourse.name)
    await message.answer('How would you like to call your course?', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddCourse.name)
async def add_course(message: Message, state: FSMContext):
    # Update the state posts with the course name
    if len(message.text) >= 30:
        # If the name is too long, stay in the AddCourse.name state and inform the user
        await state.set_state(AddCourse.name)
        await message.answer('Name is too long, try shorter')
    else:
        # If the name is acceptable, move to the AddCourse.confirm state
        await state.update_data(name=message.text)
        await state.set_state(AddCourse.confirm)
        await message.answer(f'Are you sure with name: "{message.text}"?', reply_markup=choose)


@router.message(F.text.casefold() == "cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text="Action was cancelled",
        reply_markup=kb.courses)


@router.message(Teacher(), AddCourse.confirm, F.text.casefold() == 'yes')
async def add_course_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    # Retrieve the course name from the state posts, create a new course, and commit it
    data = await state.get_data()
    await state.clear()
    await session.merge(Courses(name=data['name'], teacher=message.from_user.id))
    await session.commit()
    await message.reply(
        f'Your course "{data["name"]}" have been created',
        reply_markup=kb.courses)
    await tutor_courses(message, session)


@router.message(Teacher(), AddCourse.confirm, F.text.casefold() == 'no')
async def add_course_declined(message: Message, state: FSMContext):
    # If the user declines, return to the AddCourse.name state
    await state.set_state(AddCourse.name)
    await message.answer("Then enter a new one", reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddCourse.confirm)
async def add_course_unknown(message: Message):
    # Handle an unknown response in the AddCourse.confirm state
    await message.reply('I don`t get it, choose "yes", "no" or "cancel"')


class EditCourse(StatesGroup):
    name = State()
    name_confirm = State()
    delete_confirm = State()


@router.message(Teacher(), F.text == 'Edit course', CourseInteract.single_course)
async def edit_course(message: Message, state: FSMContext):
    await message.answer('Edit your course', reply_markup=kb.edit_course)
    await state.set_state(CourseInteract.single_course)


@router.message(Teacher(), F.text == 'Change name', CourseInteract.single_course)
async def change_course_name_start(message: Message, state: FSMContext):
    await state.set_state(EditCourse.name)
    await message.answer('Enter a new name for your course', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), EditCourse.name)
async def change_course_name(message: Message, state: FSMContext):
    await add_course(message, state)
    await state.set_state(EditCourse.name_confirm)


@router.message(Teacher(), EditCourse.name_confirm, F.text.casefold() == 'yes')
async def change_course_name_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    stmt = update(Courses).where(Courses.id == data['course_id']).values(name=data['name'])
    await session.execute(stmt)
    await session.commit()
    await message.reply(
        f'Course name have been changed to "{data["name"]}"',
        reply_markup=kb.courses)
    await tutor_courses(message, session)
    await state.set_state(CourseInteract.single_course)


@router.message(Teacher(), EditCourse.name_confirm, F.text.casefold() == 'no')
async def change_course_name_declined(message: Message, state: FSMContext):
    await message.answer("Then enter a new one", reply_markup=ReplyKeyboardRemove())
    await state.set_state(EditCourse.name)


@router.message(Teacher(), EditCourse.name_confirm)
async def add_course_unknown(message: Message):
    await message.reply('I don`t get it, choose "yes", "no" or "cancel"')


@router.message(Teacher(), F.text == 'Delete course', CourseInteract.single_course)
async def change_course_name_start(message: Message, state: FSMContext):
    keyboard = choose
    keyboard.keyboard.pop()
    await state.set_state(EditCourse.delete_confirm)
    await message.answer(f'Are you sure you want to delete your course?', reply_markup=keyboard)


@router.message(Teacher(), EditCourse.delete_confirm, F.text.casefold() == 'yes')
async def change_course_name_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    await delete_course(session, course_id)
    await message.reply(
        f'Course have been deleted',
        reply_markup=kb.courses)
    await state.clear()
    await tutor_courses(message, session)


@router.message(Teacher(), EditCourse.delete_confirm, F.text.casefold() == 'no')
async def change_course_name_declined(message: Message, session: AsyncSession):
    await tutor_courses(message, session)


@router.message(Teacher(), EditCourse.delete_confirm)
async def change_course_name_other(message: Message, state: FSMContext):
    await state.set_state(EditCourse.delete_confirm)
    await message.answer('Choose "yes" or "no"')
