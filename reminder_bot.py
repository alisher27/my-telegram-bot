import logging
import pickle
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
import asyncio

# ⚙️ TOKEN VA ADMIN GROUP
BOT_TOKEN = "7155901441:AAH6bUxW0Vg5Pf65ov9V4YQtNXIi0_4T60g"
ADMIN_GROUP_ID = -1002546680679

# 🔧 Logging
logging.basicConfig(level=logging.INFO)

# 🧠 FSM holatlar
class Form(StatesGroup):
    waiting_for_phone = State()
    waiting_for_contract = State()
    waiting_for_payment = State()
    choosing_contract = State()

USER_DATA_FILE = "user_data.pkl"

def save_user_data(user_id, data):
    try:
        with open(USER_DATA_FILE, "rb") as file:
            users_data = pickle.load(file)
    except FileNotFoundError:
        users_data = {}
    users_data[user_id] = data
    with open(USER_DATA_FILE, "wb") as file:
        pickle.dump(users_data, file)

def get_user_data(user_id):
    try:
        with open(USER_DATA_FILE, "rb") as file:
            users_data = pickle.load(file)
        return users_data.get(user_id)
    except FileNotFoundError:
        return None

def phone_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
    ], resize_keyboard=True)

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Yangi to'lov")],
        [KeyboardButton(text="📄 Mening shartnomalarim")]
    ], resize_keyboard=True)

def contract_buttons(contracts):
    kb = InlineKeyboardBuilder()
    for contract in contracts:
        kb.button(text=contract, callback_data=contract)
    kb.button(text="➕ Yangi shartnoma", callback_data="new_contract")
    kb.adjust(1)
    return kb.as_markup()

async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    if user_data is None or 'phone' not in user_data:
        await message.answer("Ro'yhatdan o'tish uchun telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
        await state.set_state(Form.waiting_for_phone)
    else:
        await message.answer("Quyidagi tugmalardan birini tanlang:", reply_markup=main_menu())
        await state.set_state(Form.choosing_contract)

async def phone_received(message: types.Message, state: FSMContext):
    contact = message.contact
    if contact:
        user_id = message.from_user.id
        user_data = {'phone': contact.phone_number, 'contracts': []}
        save_user_data(user_id, user_data)
        await message.answer("Shartnoma raqamingizni kiriting:")
        await state.set_state(Form.waiting_for_contract)
    else:
        await message.answer("Iltimos, telefon raqamni yuboring.")

async def contract_received(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    contract = message.text.strip()
    user_data = get_user_data(user_id)
    if user_data:
        contracts = user_data.get('contracts', [])
        if contract not in contracts:
            contracts.append(contract)
        user_data['current_contract'] = contract
        user_data['contracts'] = contracts
        save_user_data(user_id, user_data)
        await message.answer("Iltimos, shu shartnoma uchun to'lov chek rasmini yuboring:")
        await state.set_state(Form.waiting_for_payment)

async def payment_received(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    if user_data:
        contract = user_data.get('current_contract')
        phone = user_data.get('phone')
        user = message.from_user
        caption = (
            f"📄 Yangi to'lov\n"
            f"👤 Foydalanuvchi: @{user.username or user.full_name}\n"
            f"📞 Tel: {phone}\n"
            f"📑 Shartnoma: {contract}"
        )
        photo = message.photo[-1] if message.photo else None
        if photo:
            await message.bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=photo.file_id, caption=caption)
            await message.answer("To'lov cheki yuborildi! Rahmat.", reply_markup=main_menu())
            await state.set_state(Form.choosing_contract)
        else:
            await message.answer("Iltimos, rasm yuboring.")

async def handle_main_menu(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    if user_data:
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

async def contract_chosen(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    if user_data:
        if callback.data == "new_contract":
            await callback.message.answer("Yangi shartnoma raqamingizni kiriting:")
            await state.set_state(Form.waiting_for_contract)
        else:
            user_data['current_contract'] = callback.data
            save_user_data(user_id, user_data)
            await callback.message.answer("Shu shartnoma uchun to'lov chek rasmini yuboring:")
            await state.set_state(Form.waiting_for_payment)
    await callback.answer()

# 🔁 Polling + webhookni tozalash
async def main():
    try:
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher(storage=MemoryStorage())

        # Webhookni o'chirib tashlash (shart!)
        await bot.delete_webhook(drop_pending_updates=True)

        dp.message.register(cmd_start, CommandStart())
        dp.message.register(phone_received, F.contact, Form.waiting_for_phone)
        dp.message.register(contract_received, F.text, Form.waiting_for_contract)
        dp.message.register(payment_received, F.photo, Form.waiting_for_payment)
        dp.message.register(handle_main_menu, F.text, Form.choosing_contract)
        dp.callback_query.register(contract_chosen, Form.choosing_contract)

        logging.info("🤖 Bot ishga tushdi (polling)...")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Botda xatolik yuz berdi: {e}")
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    asyncio.run(main())
