from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Join course'),
     KeyboardButton(text='Profile')],
    [KeyboardButton(text='Home page')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')

single_course = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Publications'),
     KeyboardButton(text='Leave course')],
    [KeyboardButton(text='Home page')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')

publication_interact_submitted = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Delete submission'),
             KeyboardButton(text='Watch submission')],
            [KeyboardButton(text='Go back')]
        ], resize_keyboard=True)

publication_interact_not_submitted = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Add submission')],
            [KeyboardButton(text='Go back')]
        ], resize_keyboard=True)

ready = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Ready')]
],
    resize_keyboard=True,
    input_field_placeholder='Press a button when you are ready'
)