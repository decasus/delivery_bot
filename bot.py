import os
from datetime import datetime
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Настройка SQLAlchemy ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан в переменных окружения")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модель для хранения настроек
class Setting(Base):
    __tablename__ = 'setting'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)

# Создаем таблицу, если её ещё нет
Base.metadata.create_all(bind=engine)

def get_delivery_status() -> str:
    session = SessionLocal()
    try:
        setting = session.query(Setting).filter_by(key="DELIVERY_STATUS").first()
        if setting:
            return setting.value
        else:
            setting = Setting(key="DELIVERY_STATUS", value="ACTIVE")
            session.add(setting)
            session.commit()
            return setting.value
    finally:
        session.close()

def set_delivery_status(new_status: str) -> None:
    session = SessionLocal()
    try:
        setting = session.query(Setting).filter_by(key="DELIVERY_STATUS").first()
        if setting:
            setting.value = new_status
        else:
            setting = Setting(key="DELIVERY_STATUS", value=new_status)
            session.add(setting)
        session.commit()
    finally:
        session.close()

# --- Ограничение доступа для определённых chat_id ---
ALLOWED_CHAT_IDS = {42542920, 316653210}

def restricted(func):
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        chat_id = None
        if update.effective_chat:
            chat_id = update.effective_chat.id
        elif update.callback_query and update.callback_query.message:
            chat_id = update.callback_query.message.chat.id
        if chat_id not in ALLOWED_CHAT_IDS:
            # Можно отправить уведомление о недостатке прав
            if update.effective_message:
                update.effective_message.reply_text("Доступ запрещён.")
            return
        return func(update, context, *args, **kwargs)
    return wrapper

# --- Telegram Bot Handlers ---

@restricted
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Привет! Отправьте сообщение 'Доставка', чтобы управлять статусом доставки, или /status для просмотра текущего состояния."
    )

@restricted
def handle_delivery(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton("Включить", callback_data="enable_delivery"),
            InlineKeyboardButton("Отключить", callback_data="disable_delivery")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

@restricted
def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if query.data == "enable_delivery":
        set_delivery_status("ACTIVE")
        query.edit_message_text(text="Доставка включена")
    elif query.data == "disable_delivery":
        set_delivery_status("DISABLED")
        query.edit_message_text(text="Доставка отключена")

@restricted
def status_command(update: Update, context: CallbackContext) -> None:
    current_status = get_delivery_status()
    status_text = "Включена" if current_status == "ACTIVE" else "Отключена"
    update.message.reply_text(f"Текущий статус доставки: {status_text}")

def main():
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения")
    
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.regex("^(Доставка)$"), handle_delivery))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(CommandHandler("status", status_command))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
