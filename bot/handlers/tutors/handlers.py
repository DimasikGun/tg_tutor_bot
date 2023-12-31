from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery, \
    InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.queries import get_students, delete_course, get_publications, delete_publication_query, \
    get_submissions, delete_student_from_course, change_role_to_student, get_courses_teacher, \
    create_publication, add_max_grade, \
    get_single_submission_teacher, set_submission_grade, edit_publication_title, \
    edit_publication_text, edit_publication_media, create_course, edit_course_name, get_course_by_id, create_media, \
    get_user, get_single_publication
from bot.handlers.common.keyboards import choose, choose_ultimate
from bot.handlers.common.services import CourseInteract, publications, create_inline_courses, course_info, \
    single_publication, Pagination, pagination_handler, paginator, student_name_builder, add_media, \
    submission_name_builder, single_submission
from bot.handlers.tutors import keyboards as kb
from bot.handlers.tutors.filters import Teacher
from bot.handlers.tutors.notifications import publication_edited, submission_graded, student_kicked, publication_deleted, \
    course_deleted, course_renamed
from bot.handlers.tutors.services import publication_date, publication_time

router = Router()


@router.message(Teacher(), F.text == 'Change role')
async def tutor_change_role(message: Message, session: AsyncSession):
    """Change the role of the user to a student and notify them about the change."""
    await change_role_to_student(session, message.from_user.id)
    await message.answer('Now you are a student')


@router.callback_query(Teacher(), Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'courses'))
async def pagination_handler_courses(query: CallbackQuery, callback_data: Pagination, session: AsyncSession):
    """Handle pagination for courses when navigating through them."""
    courses = await get_courses_teacher(session, query.from_user.id)
    await pagination_handler(query, callback_data, courses)


@router.message(Teacher(), F.text == 'My courses')
async def tutor_courses(message: Message, session: AsyncSession):
    """Retrieve and display the tutor's courses with inline keyboards for navigation."""
    courses = await get_courses_teacher(session, message.from_user.id, 5)
    await create_inline_courses(courses, message, kb)


@router.callback_query(Teacher(), F.data.startswith('course_'))
async def teacher_course_info(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Display detailed information about a specific course for a teacher."""
    course_id = int(callback.data[7:])
    await course_info(callback, session, state, kb, course_id)
    course = await get_course_by_id(session, course_id)
    code = f'{course.key}{course.id}'
    students = await get_students(session, course_id)
    await callback.message.answer(f'Now there are <b>{len(students) if students else "no"}</b> students\nInvite code:',
                                  parse_mode='HTML')
    await callback.message.answer(f'<b>{code}</b>',
                                  parse_mode='HTML')


@router.callback_query(Teacher(), CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'publications'))
async def pagination_handler_teacher(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                     state: FSMContext):
    """Handle pagination for publications and students within a specific course for a teacher."""
    data = await state.get_data()
    course_id = data['course_id']
    posts = await get_publications(session, course_id)
    await pagination_handler(query, callback_data, posts)


@router.message(Teacher(), F.text == 'Publications', CourseInteract.single_course)
async def publications_teacher(message: Message, session: AsyncSession, state: FSMContext):
    """Display publications within a specific course for a teacher."""
    await publications(message, session, state, kb)


@router.callback_query(Teacher(), CourseInteract.single_course, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'students'))
async def pagination_handler_students(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                      state: FSMContext):
    """Handle pagination of students within a specific course for a teacher."""
    data = await state.get_data()
    course_id = data['course_id']
    students = await get_students(session, course_id)
    await pagination_handler(query, callback_data, students)


@router.message(Teacher(), F.text == 'Students', CourseInteract.single_course)
async def students(message: Message, session: AsyncSession, state: FSMContext):
    """Display students within a specific course for a teacher."""
    data = await state.get_data()
    course_id = data['course_id']
    students = await get_students(session, course_id, 5)
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
    """Handle a callback for a single student in the teacher's course."""
    student_id = int(callback.data[8:])
    student = await get_user(session, student_id)
    if student.username:
        student_name = '@' + student.username
    elif student.first_name:
        student_name = student.first_name
    else:
        student_name = callback.data
    await callback.answer()
    await callback.message.answer(f'Do you want to delete {student_name} from your course?',
                                  reply_markup=choose_ultimate)
    await state.set_state(Students.delete_confirm)
    await state.update_data(student_id=student_id)


@router.message(Teacher(), Students.delete_confirm)
async def delete_student_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    """Handle teacher`s answer about kick of the student from the course."""
    if message.text == 'Yes':
        data = await state.get_data()
        course_id = data['course_id']
        student_id = data['student_id']
        await delete_student_from_course(session, student_id, course_id)
        await message.reply(
            f'User have been deleted from your course',
            reply_markup=kb.single_course)
        await student_kicked(session, data)
        await students(message, session, state)
        await state.set_state(CourseInteract.single_course)
    elif message.text == 'No':
        await students(message, session, state)
        await message.answer('Or choose an option below:', reply_markup=kb.single_course)
        await state.set_state(CourseInteract.single_course)
    elif message.text != 'No' or message.text != 'Yes':
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
    """Initiate the process of adding a publication for a teacher."""
    await state.set_state(AddPublication.title)
    await message.answer('How would you like to call your publication?', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddPublication.title)
async def add_publication_title(message: Message, state: FSMContext):
    """Handle the input of the title for a new publication."""
    if len(message.text) >= 35:
        await state.set_state(AddPublication.title)
        await message.answer('Name is too long, try shorter')
    else:
        await state.update_data(title=message.text, media=[])
        await state.set_state(AddPublication.text)
        await message.answer('Now enter a text of your publication:')


@router.message(Teacher(), AddPublication.text)
async def add_publication_text(message: Message, state: FSMContext):
    """Handle the input of the text for a new publication."""
    if len(message.text) >= 4096:
        await state.set_state(AddPublication.text)
        await message.answer('Text is too long, try shorter')
    else:
        await state.update_data(text=message.text)
        await state.set_state(AddPublication.media)
        await message.answer('Now send a media for your publication one by one or press "Ready" button',
                             reply_markup=kb.ready)


@router.message(Teacher(), F.text == 'Ready', AddPublication.media)
async def add_publication_ready(message: Message, session: AsyncSession, state: FSMContext):
    """Finalize the creation of a new publication with optional media for a teacher."""
    data = await state.get_data()

    publication = await create_publication(session, data)

    for media in data['media']:
        await create_media(session, media, publication=publication)

    await message.answer('Publication has been created')
    await state.set_state(AddPublication.grade)
    await state.update_data(publication_id=publication.id, max_grade=None)
    await message.answer(
        'Now enter a maximum grade for this task or press "Ready" to leave the publication without grading',
        reply_markup=kb.ready)


@router.message(Teacher(), AddPublication.grade)
async def add_publication_grade(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the input of the maximum grade for a new publication."""
    if message.text == 'Ready':
        await state.set_state(AddPublication.date)
        await state.update_data(date=None, time=None)
        await message.answer('Now enter finish date(dd.mm.yyyy) or press "Ready" button', reply_markup=kb.ready)
    elif message.text.isdigit() and 0 < int(message.text) <= 100:
        data = await state.get_data()
        await add_max_grade(session, data, int(message.text))
        await state.set_state(AddPublication.date)
        await state.update_data(date=None, time=None)
        await message.answer('Now enter finish date(dd.mm.yyyy) or press "Ready" button', reply_markup=kb.ready)
    else:
        await state.set_state(AddPublication.grade)
        await message.answer('Max grade must be greater then 0 and less or equals 100')


@router.message(Teacher(), AddPublication.media)
async def add_publication_media(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the input of media for a new publication."""
    await state.set_state(AddPublication.media)
    data = await state.get_data()
    if len(data['media']) >= 20:
        await add_publication_ready(message, session, state)
    else:
        await add_media(message, state, data)


@router.message(Teacher(), AddPublication.date)
async def add_publication_date(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the input of the finish date for a new publication."""
    await publication_date(message, session, state, AddPublication.date, AddPublication.time, 'created')


@router.message(Teacher(), AddPublication.time)
async def add_publication_time(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the input of the finish time for a new publication."""
    await publication_time(message, session, state, AddPublication.time, 'updated')


class PublicationInteract(StatesGroup):
    interact = State()
    title_confirm = State()
    max_grade_confirm = State()
    text_confirm = State()
    media_confirm = State()
    date_confirm = State()
    time_confirm = State()
    grade_submission = State()
    grade_confirm = State()


@router.callback_query(Teacher(), F.data.startswith('publication_'))
async def teacher_single_publication(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Display details of a specific publication for a teacher."""
    await single_publication(callback, session, kb)
    await state.set_state(PublicationInteract.interact)
    await state.update_data(publication_id=int(callback.data[12:]))


@router.callback_query(Teacher(), PublicationInteract.interact, Pagination.filter(F.action.in_(('prev', 'next'))),
                       Pagination.filter(F.entity_type == 'submissions'))
async def pagination_handler_submissions(query: CallbackQuery, callback_data: Pagination, session: AsyncSession,
                                         state: FSMContext):
    """Handle pagination for submissions within a publication for a teacher."""
    data = await state.get_data()
    submissions = await get_submissions(session, data['publication_id'])
    await pagination_handler(query, callback_data, submissions, session)


@router.message(Teacher(), F.text == 'Submissions', PublicationInteract.interact)
async def submissions(message: Message, session: AsyncSession, state: FSMContext):
    """Display submissions within a publication for a teacher."""
    data = await state.get_data()
    submissions = await get_submissions(session, data['publication_id'], 5)
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
        await message.answer('There is no any submissions yet')


@router.callback_query(Teacher(), F.data.startswith('submission_'))
async def teacher_single_submission(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Display details of a specific submission for a teacher."""
    submission = await get_single_submission_teacher(session, int(callback.data[11:]))
    publication = await get_single_publication(session, submission.publication)
    max_grade = publication.max_grade
    await state.update_data(submission_id=submission.id, max_grade=max_grade, student_id=submission.student)
    await single_submission(callback.message, session, submission, kb, max_grade)
    await callback.answer()
    await state.set_state(PublicationInteract.grade_submission)


@router.message(Teacher(), PublicationInteract.grade_submission, F.text.in_(('Change grade', 'Grade')))
async def grade_submission(message: Message, state: FSMContext):
    """Initiate the grading process for a submission."""
    await message.answer('Enter a grade for submission', reply_markup=kb.ready)
    await state.set_state(PublicationInteract.grade_confirm)
    if message.text == 'Change grade':
        await state.update_data(action='update')
    else:
        await state.update_data(action='grade')


@router.message(Teacher(), PublicationInteract.grade_confirm)
async def grade_submission_confirm(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the confirmation of a grade for a submission."""
    data = await state.get_data()
    if message.text == 'Ready':
        await state.set_state(PublicationInteract.interact)
        await message.answer('No further actions', reply_markup=kb.publication_interact)
        await submissions(message, session, state)

    elif message.text.isdigit() and 0 < int(message.text) <= data['max_grade']:
        await set_submission_grade(session, data, int(message.text))
        if data['action'] == 'update':
            await message.answer('Grade has been changed', reply_markup=kb.publication_interact)
        else:
            await message.answer('Submission has been graded', reply_markup=kb.publication_interact)

        await submission_graded(session, data, message.text)

        await state.set_state(PublicationInteract.interact)
        await submissions(message, session, state)
    else:
        await state.set_state(PublicationInteract.grade_confirm)
        await message.answer(f'Grade must be greater then 0 and less or equals to {data["max_grade"]}')


@router.message(Teacher(), PublicationInteract.grade_submission, F.text == 'Go back')
async def grade_go_back(message: Message, session: AsyncSession, state: FSMContext):
    """Go back to the interaction options after grading a submission."""
    await state.set_state(PublicationInteract.interact)
    await message.answer('No further actions with submissions', reply_markup=kb.publication_interact)
    await submissions(message, session, state)


@router.message(Teacher(), PublicationInteract.interact, F.text == 'Edit')
async def edit_publication(message: Message, state: FSMContext):
    """Initiate the process of editing a publication."""
    await message.answer('What would you like to edit?', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Title', callback_data='title'),
         InlineKeyboardButton(text='Text', callback_data='text')],
        [InlineKeyboardButton(text='Media', callback_data='media'),
         InlineKeyboardButton(text='Submit date', callback_data='submit_date')],
        [InlineKeyboardButton(text='Max grade', callback_data='max_grade')]]))


@router.callback_query(Teacher(), PublicationInteract.interact, F.data == 'title')
async def edit_title(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('Enter a title of your publication')
    await state.set_state(PublicationInteract.title_confirm)


@router.message(Teacher(), PublicationInteract.title_confirm)
async def edit_title_confirm(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the confirmation of editing the title of a publication."""
    if len(message.text) >= 35:
        await state.set_state(PublicationInteract.title_confirm)
        await message.answer('Title is too long, try shorter')
    else:
        data = await state.get_data()
        await edit_publication_title(session, data, message.text)
        await message.answer('Title has been changed')
        await publication_edited(session, data)
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)


@router.callback_query(Teacher(), PublicationInteract.interact, F.data == 'text')
async def edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('Enter a text of your publication')
    await state.set_state(PublicationInteract.text_confirm)


@router.message(Teacher(), PublicationInteract.text_confirm)
async def edit_text_confirm(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the confirmation of editing the title of a publication."""
    if len(message.text) >= 4096:
        await state.set_state(PublicationInteract.text_confirm)
        await message.answer('Text is too long, try shorter')
    else:
        data = await state.get_data()
        await edit_publication_text(session, data, message.text)
        await message.answer('Text has been changed')
        await publication_edited(session, data)
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)


@router.message(Teacher(), F.text == 'Ready', PublicationInteract.media_confirm)
async def edit_media_ready(message: Message, session: AsyncSession, state: FSMContext):
    """Finalize the process of editing media for a publication."""
    data = await state.get_data()

    if len(data['media']) == 0:
        await message.answer('Nothing to add, all media stayed the same', reply_markup=kb.single_course)
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)

    else:
        await edit_publication_media(session, data)
        await message.answer('All media have been added', reply_markup=kb.single_course)
        await state.set_state(CourseInteract.single_course)
        await publication_edited(session, data)
        await publications_teacher(message, session, state)


@router.callback_query(Teacher(), PublicationInteract.interact, F.data == 'media')
async def edit_media(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        'All media from this publication will be deleted, so you will add it from the very beginning\nNow send media or press "Ready button to leave the same',
        reply_markup=kb.ready)
    await state.update_data(media=[])
    await state.set_state(PublicationInteract.media_confirm)


@router.message(Teacher(), PublicationInteract.media_confirm)
async def edit_media_confirm(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the confirmation of editing media for a publication."""
    await state.set_state(PublicationInteract.media_confirm)
    data = await state.get_data()
    if len(data['media']) >= 20:
        await edit_media_ready(message, session, state)
    else:
        await add_media(message, state, data)


@router.callback_query(Teacher(), PublicationInteract.interact, F.data == 'max_grade')
async def edit_max_grade(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        'Now text a new max grade or press "Ready button to leave it blank',
        reply_markup=kb.ready)
    await state.set_state(PublicationInteract.max_grade_confirm)


@router.message(Teacher(), PublicationInteract.max_grade_confirm)
async def edit_max_grade_confirm(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the confirmation of editing max grade for a publication."""
    if message.text == 'Ready':
        data = await state.get_data()
        await message.answer('Now there is no max grade for this publication')
        await publication_edited(session, data)
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)
    elif message.text.isdigit() and 0 < int(message.text) <= 100:
        data = await state.get_data()
        await add_max_grade(session, data, int(message.text))
        await message.answer(f'Now max grade for this publication is {message.text}', reply_markup=kb.single_course)
        await publication_edited(session, data)
        await state.set_state(CourseInteract.single_course)
        await publications_teacher(message, session, state)
    else:
        await state.set_state(PublicationInteract.max_grade_confirm)
        await message.answer('Max grade must be greater then 0 and less or equals 100')


@router.callback_query(Teacher(), PublicationInteract.interact, F.data == 'submit_date')
async def edit_datetime(callback: CallbackQuery, state: FSMContext):
    """Initiate the process of editing the date and time of a publication."""
    await callback.answer()
    await callback.message.answer('Now enter submit date (dd:mm:yyyy) or press "Ready" button to clear it',
                                  reply_markup=kb.ready)
    await state.update_data(date=None, time=None)
    await state.set_state(PublicationInteract.date_confirm)


@router.message(Teacher(), PublicationInteract.date_confirm)
async def edit_date(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the input of the new date for a publication."""
    await publication_date(message, session, state, PublicationInteract.date_confirm, PublicationInteract.time_confirm,
                           'created')


@router.message(Teacher(), PublicationInteract.time_confirm)
async def edit_time(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the input of the new time for a publication."""
    await publication_time(message, session, state, PublicationInteract.time_confirm, 'updated')


@router.message(Teacher(), PublicationInteract.interact, F.text == 'Delete')
async def delete_publication(message: Message, session: AsyncSession, state: FSMContext):
    """Initiate the process of deleting a publication."""
    data = await state.get_data()
    await delete_publication_query(session, data['publication_id'])
    await message.answer('Publication has been deleted', reply_markup=kb.single_course)
    await publication_deleted(session, data)
    await state.set_state(CourseInteract.single_course)
    await publications_teacher(message, session, state)


@router.message(Teacher(), PublicationInteract.interact, F.text == 'Go back')
async def publication_go_back(message: Message, session: AsyncSession, state: FSMContext):
    """Go back to the interaction options after dealing with a publication."""
    await message.answer('No further actions with publication', reply_markup=kb.single_course)
    await state.set_state(CourseInteract.single_course)
    await publications_teacher(message, session, state)


class AddCourse(StatesGroup):
    name = State()
    confirm = State()


@router.message(Teacher(), F.text == 'Add course')
async def add_course_start(message: Message, state: FSMContext):
    """Initiate the process of adding a new course."""
    await state.set_state(AddCourse.name)
    await message.answer('How would you like to call your course?', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), AddCourse.name)
async def add_course(message: Message, state: FSMContext):
    """Handle the input of the name for a new course."""
    if len(message.text) >= 30:
        await state.set_state(AddCourse.name)
        await message.answer('Name is too long, try shorter')
    else:
        await state.update_data(name=message.text)
        await state.set_state(AddCourse.confirm)
        await message.answer(f'Are you sure with name: "{message.text}"?', reply_markup=choose)


@router.message(Teacher(), AddCourse.confirm)
async def add_course_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the teacher`s answer about adding a new course and prompt for a new name."""
    if message.text == 'Yes':
        data = await state.get_data()
        await state.clear()
        await create_course(session, data, message.from_user.id)
        await message.reply(
            f'Your course "{data["name"]}" have been created',
            reply_markup=kb.courses)
        await tutor_courses(message, session)
    elif message.text == 'No':
        await state.set_state(AddCourse.name)
        await message.answer("Then enter a new one", reply_markup=ReplyKeyboardRemove())
    elif message.text == 'Cancel':
        await state.clear()
        await message.answer(
            text="Action was cancelled",
            reply_markup=kb.courses)
    elif message.text != 'No' or message.text != 'Yes':
        await state.set_state(AddCourse.confirm)
        await message.reply('I don`t get it, choose "Yes", "No" or "Cancel"')


class EditCourse(StatesGroup):
    name = State()
    name_confirm = State()
    delete_confirm = State()


@router.message(Teacher(), F.text == 'Edit course', CourseInteract.single_course)
async def edit_course(message: Message, state: FSMContext):
    """Initiate the process of editing a course."""
    await message.answer('Edit your course', reply_markup=kb.edit_course)
    await state.set_state(CourseInteract.single_course)


@router.message(Teacher(), F.text == 'Change name', CourseInteract.single_course)
async def change_course_name_start(message: Message, state: FSMContext):
    """Initiate the process of changing the name of a course."""
    await state.set_state(EditCourse.name)
    await message.answer('Enter a new name for your course', reply_markup=ReplyKeyboardRemove())


@router.message(Teacher(), EditCourse.name)
async def change_course_name(message: Message, state: FSMContext):
    """Handle the input of the new name for a course."""
    await add_course(message, state)
    await state.set_state(EditCourse.name_confirm)


@router.message(Teacher(), EditCourse.name_confirm)
async def change_course_name_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the teacher`s answer about changing the name of a course."""
    if message.text == 'Yes':
        data = await state.get_data()

        course = await get_course_by_id(session, data['course_id'])

        old_name = course.name

        await edit_course_name(session, data)
        await message.reply(
            f'Course "{old_name}" name have been changed to "{data["name"]}"',
            reply_markup=kb.courses)
        await course_renamed(session, data, old_name)
        await tutor_courses(message, session)
        await state.set_state(CourseInteract.single_course)

    elif message.text == 'No':
        await message.answer("Then enter a new one", reply_markup=ReplyKeyboardRemove())
        await state.set_state(EditCourse.name)
    elif message.text == 'Cancel':
        await message.answer("Action was canceled", reply_markup=kb.single_course)
        await state.set_state(CourseInteract.single_course)
    else:
        await state.set_state(EditCourse.name_confirm)
        await message.reply('I don`t get it, choose "Yes", "No" or "Cancel"')


@router.message(Teacher(), F.text == 'Delete course', CourseInteract.single_course)
async def delete_course_start(message: Message, state: FSMContext):
    """Initiate the process of deleting a course."""
    await state.set_state(EditCourse.delete_confirm)
    await message.answer(f'Are you sure you want to delete your course?', reply_markup=choose_ultimate)


@router.message(Teacher(), EditCourse.delete_confirm)
async def delete_course_confirmed(message: Message, session: AsyncSession, state: FSMContext):
    """Handle the teacher`s answer about deleting a course."""
    if message.text == 'Yes':
        data = await state.get_data()
        course_id = data['course_id']
        data = await delete_course(session, course_id)
        await message.reply(
            f'Course have been deleted',
            reply_markup=kb.courses)
        await course_deleted(data)
        await state.clear()
        await tutor_courses(message, session)
    elif message.text == 'No':
        await tutor_courses(message, session)
    elif message.text != 'No' or message.text != 'Yes':
        await state.set_state(EditCourse.delete_confirm)
        await message.answer('Choose "Yes" or "No"')
