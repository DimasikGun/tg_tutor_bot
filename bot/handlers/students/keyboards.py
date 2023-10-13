from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Join course'),
     KeyboardButton(text='Profile')],
    [KeyboardButton(text='Home page')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')
