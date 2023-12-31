from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

start = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='I am a student', callback_data='student'),
     InlineKeyboardButton(text='I am a teacher', callback_data='teacher')]])

main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='My courses'),
     KeyboardButton(text='Change role')]
],
    resize_keyboard=True,
    input_field_placeholder='Choose option below')

choose = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='Yes'),
            KeyboardButton(text='No'),
        ],
        [KeyboardButton(text='Cancel')]
    ], resize_keyboard=True)

choose_ultimate = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='Yes'),
            KeyboardButton(text='No'),
        ]
    ], resize_keyboard=True)

