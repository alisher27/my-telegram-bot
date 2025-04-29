import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.utils.token import TokenValidationError
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import asyncio

BOT_TOKEN = '7268279008:AAErO5BSSbqgIyJTjiTBNaRIS5SgHD8lPPw'
ADMIN_GROUP_ID = -1002314667838  # O'zingizning guruh ID'ingiz

logging.basicConfig(level=logging.INFO)

# FSM holatlar
class Form(StatesGroup):
    waiting_for_phone = State()
    waiting_for_contract = State()
    waiting_for_payment = State()
    choosing_contract = State()

# User ma’lumotlarini xotirada saqlash uchun
user_data_store = {}

# Telefon raqamni olish keyboard
def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True
    )

# Asosiy menyu
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Yangi to'lov")],
            [KeyboardButton(text="📄 Mening shartnomalarim")]
        ],
        resize_keyboard=True
    )

# Inline tugmalar: shartnomalar
def contract_buttons(contracts):
    kb = InlineKeyboardBuilder()
    for contract in contracts:
        kb.button(text=contract, callback_data=contract)
    kb.button(text="➕ Yangi shartnoma", callback_data="new_contract")
    kb.adjust(1)
    return kb.as_markup()


# Start komandasi
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_data_store or 'phone' not in user_data_store[user_id]:
        await message.answer("Ro'yhatdan o'tish uchun telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
        await state.set_state(Form.waiting_for_phone)
    else:
        await message.answer("Quyidagi tugmalardan birini tanlang:", reply_markup=main_menu())
        await state.set_state(Form.choosing_contract)


# Telefon raqamni olish
async def phone_received(message: types.Message, state: FSMContext):
    contact = message.contact
    if contact:
        user_id = message.from_user.id
        user_data_store[user_id] = {
            'phone': contact.phone_number,
            'contracts': []
        }
        await message.answer("Shartnoma raqamingizni kiriting:")
        await state.set_state(Form.waiting_for_contract)
    else:
        await message.answer("Iltimos, telefon raqamni yuboring.")


# Shartnoma raqamini olish
async def contract_received(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    contract = message.text.strip()
    user_data = user_data_store.get(user_id, {})
    contracts = user_data.get('contracts', [])
    if contract not in contracts:
        contracts.append(contract)
    user_data['current_contract'] = contract
    user_data['contracts'] = contracts
    user_data_store[user_id] = user_data

    await message.answer("Iltimos, shu shartnoma uchun to'lov chek rasmini yuboring:")
    await state.set_state(Form.waiting_for_payment)


# To‘lov rasmini olish
async def payment_received(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = user_data_store.get(user_id, {})
    contract = user_data.get('current_contract')
    phone = user_data.get('phone')
    user = message.from_user

    caption = f"📄 Yangi to'lov\n👤 Foydalanuvchi: @{user.username or user.full_name}\n📞 Tel: {phone}\n📑 Shartnoma: {contract}"
    photo = message.photo[-1] if message.photo else None

    if photo:
        await message.bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=photo.file_id, caption=caption)
        await message.answer("To'lov cheki yuborildi! Rahmat.", reply_markup=main_menu())
        await state.set_state(Form.choosing_contract)
    else:
        await message.answer("Iltimos, rasm yuboring.")


# Asosiy menyu tugmalari
async def handle_main_menu(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = user_data_store.get(user_id, {})
    text = message.text

    if text == "➕ Yangi to'lov":
        await message.answer("Shartnoma raqamingizni kiriting:")
        await state.set_state(Form.waiting_for_contract)
    elif text == "📄 Mening shartnomalarim":
        contracts = user_data.get('contracts', [])
        if not contracts:
            await message.answer("Sizda hali shartnomalar mavjud emas.", reply_markup=main_menu())
        else:
            await message.answer("Quyidagi shartnomalardan birini tanlang:", reply_markup=contract_buttons(contracts))


# Inline tugma: shartnoma tanlash
async def contract_chosen(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_data = user_data_store.get(user_id, {})

    if callback.data == "new_contract":
        await callback.message.answer("Yangi shartnoma raqamingizni kiriting:")
        await state.set_state(Form.waiting_for_contract)
    else:
        user_data['current_contract'] = callback.data
        user_data_store[user_id] = user_data
        await callback.message.answer("Shu shartnoma uchun to'lov chek rasmini yuboring:")
        await state.set_state(Form.waiting_for_payment)
    await callback.answer()


# Botni ishga tushirish
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(phone_received, F.contact, Form.waiting_for_phone)
    dp.message.register(contract_received, F.text, Form.waiting_for_contract)
    dp.message.register(payment_received, F.photo, Form.waiting_for_payment)
    dp.message.register(handle_main_menu, F.text, Form.choosing_contract)
    dp.callback_query.register(contract_chosen, Form.choosing_contract)

    await bot.delete_webhook(drop_pending_updates=True)  # polling uchun

    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
