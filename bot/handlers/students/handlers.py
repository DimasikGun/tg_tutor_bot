from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.queries import get_publications, delete_student_from_course, change_role_to_teacher, get_courses_student, \
    create_submission, get_single_submission_student, get_course_by_key, \
    get_single_coursestudent, join_course_student, create_media
from handlers.common.keyboards import choose_ultimate
from handlers.common.services import CourseInteract, publications, create_inline_courses, single_publication, \
    Pagination, pagination_handler, add_media, single_submission
from handlers.students import keyboards as kb
from handlers.students.notifications import joined_course, added_submission, deleted_submission, left_course

router = Router()


@router.message(F.text == 'Change role')
async def change_role_student(message: Message, session: AsyncSession):
    await change_role_to_teacher(session, message.from_user.id)
    await message.answer('Now you are a teacher')


@router.callback_query(Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'courses'))
async def pagination_handler_student(query: CallbackQuery, callback_data: Pagination, session: AsyncSession):
    courses = await get_courses_student(session, query.message.from_user.id)
    await pagination_handler(query, callback_data, courses)


@router.message(F.text == 'My courses')
async def student_courses(message: Message, session: AsyncSession):
    courses = await get_courses_student(session, message.from_user.id, 5)
    await create_inline_courses(courses, message, kb)


@router.callback_query(CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'publications'))
async def pagination_handler_student(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                     state: FSMContext):
    data = await state.get_data()
    course_id = data['course_id']
    posts = await get_publications(session, course_id)
    await pagination_handler(query, callback_data, posts)


@router.message(F.text == 'Publications', CourseInteract.single_course)
async def publications_student(message: Message, session: AsyncSession, state: FSMContext):
    await publications(message, session, state, kb)


class LeaveCourse(StatesGroup):
    leave_course_confim = State()


@router.message(F.text == 'Leave course', CourseInteract.single_course)
async def leave_course(message: Message, state: FSMContext):
    await state.set_state(LeaveCourse.leave_course_confim)
    await message.answer('Are you sure you want to leave this course?', reply_markup=choose_ultimate)


@router.message(LeaveCourse.leave_course_confim)
async def leave_course(message: Message, session: AsyncSession, state: FSMContext):
    if message.text == 'Yes':
        data = await state.get_data()
        await delete_student_from_course(session, message.from_user.id, data['course_id'])
        await left_course(session, data, message.from_user.id)
        await state.set_state(CourseInteract.single_course)
        await message.answer('You left the course', reply_markup=kb.single_course)

    if message.text == 'No':
        await state.set_state(CourseInteract.single_course)
        await message.answer('You still in the course', reply_markup=kb.single_course)
    else:
        await state.set_state(LeaveCourse.leave_course_confim)
        await message.answer('Choose "Yes" or "No"')


class AddSubmission(StatesGroup):
    single_publication = State()
    delete = State()
    text = State()
    media = State()


@router.callback_query(F.data.startswith('publication_'))
async def student_single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.update_data(publication_id=int(callback.data[12:]))
    await single_publication(callback, session, state, kb, 'student')
    await state.set_state(AddSubmission.single_publication)


@router.message(AddSubmission.single_publication, F.text == 'Add submission')
async def add_submission(message: Message, state: FSMContext):
    await message.answer('Enter a text of your submission or press "Ready" button to leave it blank',
                         reply_markup=kb.ready)
    await state.update_data(text=None, media=[])
    await state.set_state(AddSubmission.text)


@router.message(AddSubmission.text)
async def submission_add_text(message: Message, state: FSMContext):
    if message.text == 'Ready':
        await message.answer('Now send media or press "Ready" button')
        await state.set_state(AddSubmission.media)
    elif len(message.text) >= 4096:
        await state.set_state(AddSubmission.text)
        await message.answer('Text is too long, try shorter')
    else:
        await message.answer('Text added, now send media or press "Ready" button')
        await state.update_data(text=message.text)
        await state.set_state(AddSubmission.media)


@router.message(F.text == 'Ready', AddSubmission.media)
async def add_publication_ready(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()

    submission = await create_submission(session, data, message.from_user.id)

    for media in data['media']:
        await create_media(session, media, submission=submission)

    await message.answer('Submission has been added', reply_markup=kb.single_course)
    await added_submission(session, data)
    await state.set_state(CourseInteract.single_course)
    await publications(message, session, state, kb)


@router.message(AddSubmission.media)
async def submission_add_media(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(AddSubmission.media)
    data = await state.get_data()
    if len(data['media']) >= 20:
        await add_publication_ready(message, session, state)
    else:
        await add_media(message, session, state, data)


@router.message(AddSubmission.single_publication, F.text == 'Go back')
async def publication_go_back(message: Message, session: AsyncSession, state: FSMContext):
    await message.answer('No further actions with publication', reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await publications(message, session, state, kb)


@router.message(AddSubmission.single_publication, F.text == 'Delete submission')
async def delete_submission(message: Message, state: FSMContext):
    await message.answer('Are you sure you want to delete your submission?', reply_markup=choose_ultimate)
    await state.set_state(AddSubmission.delete)


@router.message(AddSubmission.delete, F.text.casefold() == 'yes')
async def delete_submission_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    await delete_submission(session, data, message.from_user.id)
    await message.reply(
        f'Your submission has been deleted',
        reply_markup=kb.single_course)
    await deleted_submission(session, data)
    await state.set_state(CourseInteract.single_course)
    await publications(message, session, state, kb)


@router.message(AddSubmission.delete, F.text.casefold() == 'no')
async def delete_submission_declined(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(CourseInteract.single_course)
    await publications(message, session, state, kb)
    await message.answer('Or choose an option below:', reply_markup=kb.single_course)


@router.message(AddSubmission.delete)
async def delete_submission_other(message: Message, session: AsyncSession, state: FSMContext):
    await state.set_state(AddSubmission.delete)
    await publications(message, session, state, kb)
    await message.answer('Choose "Yes" or "No"', reply_markup=kb.single_course)


@router.message(AddSubmission.single_publication, F.text == 'Watch submission')
async def watch_submission(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    submission, max_grade = get_single_submission_student(session, data, message.from_user.id)
    await single_submission(message, session, submission, kb, max_grade, 'student')
    await state.set_state(AddSubmission.single_publication)


class JoinCourse(StatesGroup):
    join = State()


@router.message(F.text == 'Join course')
async def add_course_start(message: Message, state: FSMContext):
    await state.set_state(JoinCourse.join)
    await message.answer('Enter a code of course', reply_markup=ReplyKeyboardRemove())


@router.message(JoinCourse.join)
async def join_course(message: Message, state: FSMContext, session: AsyncSession):
    code = message.text
    try:
        course_id = int(code[6:])
        key = str(code[:6])
    except ValueError:
        await state.clear()
        await message.answer('Wrong code', reply_markup=kb.courses)
        return

    course = await get_course_by_key(session, course_id, key)

    try:
        name = course.name
        teacher = course.teacher

        coursestudent = await get_single_coursestudent(session, course_id, message.from_user.id)

        if coursestudent:
            await message.answer(f'You`ve already joined "{name}" course', reply_markup=kb.courses)
        elif teacher == message.from_user.id:
            await message.answer(f'You can`t join your own course', reply_markup=kb.courses)
        else:
            await state.clear()
            await join_course_student(session, course_id, message.from_user.id)
            await message.answer(f'You`ve just joined a "{name}" course', reply_markup=kb.courses)
            await joined_course(name, teacher)
            await student_courses(message, session)

    except AttributeError:
        await message.answer('There is no course with such code', reply_markup=kb.courses)
