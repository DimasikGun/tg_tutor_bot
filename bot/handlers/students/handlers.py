from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import CoursesStudents, Courses
from handlers.common.queries import get_publications
from handlers.common.services import CourseInteract, publications, create_inline_courses, course_info, \
    single_publication, Pagination, pagination_handler
from handlers.students import keyboards as kb

router = Router()


@router.message(F.text == 'My courses')
async def student_courses(message: Message, session: AsyncSession):
    stmt = select(Courses).join(CoursesStudents).filter(CoursesStudents.student_id == message.from_user.id)
    result = await session.execute(stmt)
    courses = result.scalars().all()

    if courses:
        await create_inline_courses(courses, message, kb)
    else:
        await message.answer('You haven`t joined any courses yet', reply_markup=kb.courses)


@router.callback_query(F.data.startswith('course_'))
async def student_course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    course_id = int(callback.data[7:])
    await course_info(callback, session, state, kb, course_id)


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


@router.callback_query(F.data.startswith('publication_'))
async def student_single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await single_publication(callback, session, state, kb)
    await state.set_state(CourseInteract.single_course)
    await publications_student(callback.message, session, state)


class JoinCourse(StatesGroup):
    join = State()


@router.message(F.text == 'Join course')
async def add_course_start(message: Message, state: FSMContext):
    await state.set_state(JoinCourse.join)
    await message.answer('Enter a code of course', reply_markup=ReplyKeyboardRemove())


@router.message(JoinCourse.join)
async def add_course(message: Message, state: FSMContext, session: AsyncSession):
    # Extract the code from the message text
    code = message.text
    try:
        # Parse the course_id and key from the code
        course_id = int(code[6:])
        key = str(code[:6])
    except ValueError:
        await state.clear()
        await message.answer('Wrong code', reply_markup=kb.courses)
        return

    # Check if the provided course_id and key match a course in the database
    stmt = select(Courses).where(Courses.id == course_id and Courses.key == key)
    res = await session.execute(stmt)
    res = res.scalar()

    try:
        # If the course exists, get its name
        name = res.name
        # Check if there is an existing record in CoursesStudents for this user and course
        stmt = select(CoursesStudents).where(
            CoursesStudents.course_id == course_id,
            CoursesStudents.student_id == message.from_user.id
        )
        res = await session.execute(stmt)
        existing_record = res.scalar()

        if existing_record:
            # If an existing record is found, inform the user
            await message.answer(f'You`ve already joined "{name}" course', reply_markup=kb.courses)
        else:
            # If no existing record is found, clear state, create a new CoursesStudents record, and commit the changes
            await state.clear()
            await session.merge(CoursesStudents(course_id=course_id, student_id=message.from_user.id))
            await session.commit()
            await message.answer(f'You`ve just joined a "{name}" course', reply_markup=kb.courses)
            await student_courses(message, session)

    except AttributeError:
        # If there is no matching course, inform the user
        await message.answer('There is no course with such code(', reply_markup=kb.courses)
