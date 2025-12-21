import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ТОКЕН БОТА
TOKEN = "8434110078:AAEeXoKBAmmiWucygF8x1DUNMzbmEbI9vZE"

# Хранение данных
user_data = {}

# Клавиатура
main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("🚀 НАЧАТЬ СПРИНТ"), KeyboardButton("📊 СТАТИСТИКА")],
    [KeyboardButton("❓ ПОМОЩЬ")]
], resize_keyboard=True)

# Функции бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для борьбы с прокрастинацией.\n"
        "Нажми 🚀 НАЧАТЬ СПРИНТ для 5-минутной работы!",
        reply_markup=main_keyboard
    )

async def sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Инициализируем пользователя
    if user_id not in user_data:
        user_data[user_id] = {'sprints': 0, 'active': False}
    
    if user_data[user_id]['active']:
        await update.message.reply_text("⏳ У тебя уже идет спринт!", reply_markup=main_keyboard)
        return
    
    user_data[user_id]['active'] = True
    
    await update.message.reply_text(
        "🚀 **Старт 5-минутного спринта!**\n\n"
        "Работай 5 минут без отвлечений!\n"
        "Я напомню, когда время выйдет. 💪",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Таймер на 5 минут
    await asyncio.sleep(300)
    
    user_data[user_id]['sprints'] += 1
    user_data[user_id]['active'] = False
    
    await update.message.reply_text(
        f"🎉 **Спринт завершен!**\n\n"
        f"Ты сделал(а) {user_data[user_id]['sprints']} спринтов!\n\n"
        "Что удалось сделать за 5 минут?",
        reply_markup=main_keyboard
    )
    
    # Напоминание через 5 минут
    await asyncio.sleep(300)
    await update.message.reply_text(
        "⏰ Напоминание: 10 минут назад ты завершил спринт!\n"
        "Хочешь сделать еще один? 🚀",
        reply_markup=main_keyboard
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_data or user_data[user_id]['sprints'] == 0:
        await update.message.reply_text("📊 Ты еще не делал(а) спринтов.", reply_markup=main_keyboard)
    else:
        sprints = user_data[user_id]['sprints']
        await update.message.reply_text(
            f"📊 **Твоя статистика:**\n\n"
            f"• Всего спринтов: {sprints}\n"
            f"• Активный спринт: {'да' if user_data[user_id]['active'] else 'нет'}\n\n"
            f"🎯 Продолжай в том же духе!",
            reply_markup=main_keyboard
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ **Помощь:**\n\n"
        "🚀 НАЧАТЬ СПРИНТ - 5 минут работы\n"
        "📊 СТАТИСТИКА - посмотреть прогресс\n\n"
        "Как работает:\n"
        "1. Нажми 🚀 НАЧАТЬ СПРИНТ\n"
        "2. Работай 5 минут\n"
        "3. Получи напоминание через 5 минут\n"
        "4. Повторяй!",
        reply_markup=main_keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🚀 НАЧАТЬ СПРИНТ":
        await sprint(update, context)
    elif text == "📊 СТАТИСТИКА":
        await stats(update, context)
    elif text == "❓ ПОМОЩЬ":
        await help_command(update, context)
    else:
        await update.message.reply_text(
            "Используй кнопки меню ⬇️",
            reply_markup=main_keyboard
        )

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sprint", sprint))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("=" * 50)
    print("🚀 Бот запущен!")
    print("=" * 50)
    
    application.run_polling()

if __name__ == '__main__':
    main()
