from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler, PicklePersistence
)

BOT_TOKEN = '7686011297:AAFJsW-woZr5qkrfGeZjcRIeuMdxYoMs4tg'
ADMIN_GROUP_ID = -1002504552520  # O'zingizning guruh ID'ingizni yozing

ASK_PHONE, ASK_CONTRACT, ASK_PAYMENT, CHOOSE_CONTRACT = range(4)

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    if 'phone' not in user_data:
        kb = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
        await update.message.reply_text("Ro'yhatdan o'tish uchun telefon raqamingizni yuboring:",
                                        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return ASK_PHONE
    else:
        return await show_main_menu(update, context)

# Telefon raqamni olish
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact:
        context.user_data['phone'] = contact.phone_number
        await update.message.reply_text("Shartnoma raqamingizni kiriting:")
        return ASK_CONTRACT
    else:
        await update.message.reply_text("Iltimos, telefon raqamni yuboring.")
        return ASK_PHONE

# Shartnoma raqamini olish
async def get_contract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contract = update.message.text.strip()
    contracts = context.user_data.get('contracts', [])
    if contract not in contracts:
        contracts.append(contract)
        context.user_data['contracts'] = contracts
    context.user_data['current_contract'] = contract
    await update.message.reply_text("Iltimos, shu shartnoma uchun to'lov chek rasmini yuboring:")
    return ASK_PAYMENT

# Rasm qabul qilish va guruhga yuborish
async def get_payment_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contract = context.user_data['current_contract']
    phone = context.user_data['phone']
    user = update.message.from_user

    caption = f"📄 Yangi to'lov\n👤 Foydalanuvchi: @{user.username or user.full_name}\n📞 Tel: {phone}\n📑 Shartnoma: {contract}"

    photo = update.message.photo[-1] if update.message.photo else None
    if photo:
        await context.bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=photo.file_id, caption=caption)
        await update.message.reply_text("To'lov cheki yuborildi! Rahmat.")
    else:
        await update.message.reply_text("Iltimos, rasm yuboring.")
        return ASK_PAYMENT

    return await show_main_menu(update, context)

# Asosiy menyu
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[KeyboardButton("➕ Yangi to'lov")], [KeyboardButton("📄 Mening shartnomalarim")]]
    await update.message.reply_text("Quyidagi tugmalardan birini tanlang:",
                                    reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return CHOOSE_CONTRACT

# To'lov tugmasi bosilganda
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ Yangi to'lov":
        await update.message.reply_text("Shartnoma raqamingizni kiriting:")
        return ASK_CONTRACT
    elif text == "📄 Mening shartnomalarim":
        contracts = context.user_data.get('contracts', [])
        if not contracts:
            await update.message.reply_text("Sizda hali shartnomalar mavjud emas.")
            return await show_main_menu(update, context)
        buttons = [[InlineKeyboardButton(contract, callback_data=contract)] for contract in contracts]
        buttons.append([InlineKeyboardButton("➕ Yangi shartnoma", callback_data="new_contract")])
        await update.message.reply_text("Quyidagi shartnomalardan birini tanlang:",
                                        reply_markup=InlineKeyboardMarkup(buttons))
        return CHOOSE_CONTRACT
    else:
        return await show_main_menu(update, context)

# Shartnoma tanlash
async def contract_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "new_contract":
        await query.message.reply_text("Yangi shartnoma raqamingizni kiriting:")
        return ASK_CONTRACT
    else:
        context.user_data['current_contract'] = query.data
        await query.message.reply_text("Shu shartnoma uchun to'lov chek rasmini yuboring:")
        return ASK_PAYMENT

# Botni ishga tushirish
if __name__ == '__main__':
    persistence = PicklePersistence(filepath="user_data.pkl")
    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PHONE: [MessageHandler(filters.CONTACT, get_phone)],
            ASK_CONTRACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contract)],
            ASK_PAYMENT: [MessageHandler(filters.PHOTO, get_payment_image)],
            CHOOSE_CONTRACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
                CallbackQueryHandler(contract_choice)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        name="main_conversation",
        persistent=True
    )

    app.add_handler(conv_handler)
    app.run_polling()
