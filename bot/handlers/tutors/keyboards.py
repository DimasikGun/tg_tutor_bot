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
     KeyboardButton(text='Course info')],
    [KeyboardButton(text='Add publication'),
     KeyboardButton(text='Home page')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')

# publications = ReplyKeyboardMarkup(keyboard=[
#     [KeyboardButton(text='Add publication'),
#      KeyboardButton(text='Profile')],
#     [KeyboardButton(text='Home page')]
# ],
#     resize_keyboard=True,
#     input_field_placeholder='Choose option below')

ready = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Ready')]
],
    resize_keyboard=True,
    input_field_placeholder='Press a button when you are ready')
