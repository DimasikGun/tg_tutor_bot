from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

start = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='I am a student', callback_data='student'),
     InlineKeyboardButton(text='I am a teacher', callback_data='teacher')]])


main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='My courses'),
     KeyboardButton(text='Profile')],
    [KeyboardButton(text='Support')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')
