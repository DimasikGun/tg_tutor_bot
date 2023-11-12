from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Add course'),
     KeyboardButton(text='Profile')],
    [KeyboardButton(text='Home page')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')

single_course = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Publications'),
     KeyboardButton(text='Edit course')],
    [KeyboardButton(text='Add publication'),
     KeyboardButton(text='Students')],
    [KeyboardButton(text='Home page')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')

edit_course = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Change name'),
     KeyboardButton(text='Students')],
    [KeyboardButton(text='Delete course'),
     KeyboardButton(text='Home page')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')

ready = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Ready')]
],
    resize_keyboard=True,
    input_field_placeholder='Press a button when you are ready'
)

publication_interact = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text='Edit'),
                KeyboardButton(text='Delete'),
                KeyboardButton(text='Submissions'),
            ],
            [KeyboardButton(text='Go back')]
        ], resize_keyboard=True)

submission_graded = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Change grade')],
            [KeyboardButton(text='Go back')]
        ], resize_keyboard=True)

submission_not_graded = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Grade')],
            [KeyboardButton(text='Go back')]
        ], resize_keyboard=True)
