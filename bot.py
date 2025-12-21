import logging
import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== ТОКЕН ==========
# ⚠️ ВСТАВЬТЕ СЮДА НОВЫЙ ТОКЕН ОТ @BotFather ⚠️
TOKEN = "8434110078:AAEeXoKBAmmiWucygF8xiDUNMzbmEbI9vZE"

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
user_sprints = {}
active_sprints = {}

# ========== КОМАНДЫ МЕНЮ ==========
COMMANDS = [
    BotCommand("start", "Главное меню"),
    BotCommand("sprint", "Начать 5-минутный спринт"),
    BotCommand("stats", "Показать статистику"),
    BotCommand("library", "Библиотека микро-стартов"),
    BotCommand("help", "Помощь по использованию бота"),
    BotCommand("cancel", "Отменить текущий спринт"),
]

# ========== КЛАВИАТУРА ==========
main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("🚀 SPRINT"), KeyboardButton("📊 Статистика")],
    [KeyboardButton("📋 Библиотека стартов"), KeyboardButton("❓ Помощь")]
], resize_keyboard=True)

# ========== БИБЛИОТЕКА СТАРТОВ ==========
MICRO_STARTS = [
    "📝 Написать 3 предложения по задаче",
    "🗂️ Разобрать 5 файлов/бумаг на столе",
    "📞 Сделать один важный звонок",
    "📑 Создать структуру документа",
    "📧 Ответить на 2 письма",
    "🧹 Убрать рабочее место (5 минут)",
    "📚 Прочитать 5 страниц",
    "✏️ Составить список на день"
]

# ========== ФУНКЦИИ ТАЙМЕРОВ ==========
async def send_sprint_completion(context):
    job = context.job
    user_id = job.data['user_id']
    chat_id = job.data['chat_id']
    task = job.data['task']
    
    if user_id in active_sprints:
        del active_sprints[user_id]
    
    if user_id not in user_sprints:
        user_sprints[user_id] = {'current_task': '', 'sprint_count': 0, 'last_sprint': None}
    
    user_sprints[user_id]['sprint_count'] += 1
    user_sprints[user_id]['last_sprint'] = datetime.now()
    
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("✅ Да, стало проще"), KeyboardButton("🤔 Нет, пока сложно")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🚀 Новый спринт")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎉 **Спринт завершен!**\n\n"
                 f"📌 Задача: {task}\n\n"
                 "🔄 **Рефлексия:**\n\n"
                 "1. Что удалось сделать за 5 минут?\n"
                 "(Напиши ответ)\n\n"
                 "2. Стало ли проще продолжить?",
            reply_markup=keyboard
        )
        
        # Напоминание через 5 минут
        if context.application and context.application.job_queue:
            context.application.job_queue.run_once(
                send_success_reminder,
                300,
                data={'user_id': user_id, 'chat_id': chat_id, 'task': task},
                name=f"reminder_{user_id}"
            )
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")

async def send_success_reminder(context):
    job = context.job
    user_id = job.data['user_id']
    chat_id = job.data['chat_id']
    task = job.data['task']
    
    sprint_count = user_sprints.get(user_id, {}).get('sprint_count', 0)
    
    reminder_text = f"""
⏰ **Напоминание о твоих успехах!**

Ты завершил спринт по задаче:
📌 **{task}**

📊 Всего спринтов: **{sprint_count}**

Напиши /sprint для нового старта! 🚀
"""
    
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=reminder_text
        )
    except Exception as e:
        logger.error(f"Ошибка напоминания: {e}")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

🎯 Я — бот «5-минутный Стартер»!

🚀 **Как работает:**
1. Нажми 🚀 SPRINT
2. Выбери задачу
3. Работай 5 минут
4. Отмечай успехи

💡 Всего 5 минут могут запустить продуктивность!

Используй кнопки ниже ⬇️
"""
    
    await update.message.reply_text(welcome_text, reply_markup=main_keyboard)

async def sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in active_sprints:
        await update.message.reply_text("⏳ У тебя уже есть активный спринт!")
        return
    
    keyboard = [[KeyboardButton(start)] for start in MICRO_STARTS[:4]]
    keyboard.append([KeyboardButton("✏️ Ввести свою задачу")])
    keyboard.append([KeyboardButton("⬅️ Назад")])
    
    start_keyboard = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🎯 **Выбери задачу:**\n\n"
        "Или введи свою задачу\n"
        "Например: 'написать отчет'",
        reply_markup=start_keyboard
    )

async def cancel_sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in active_sprints:
        await update.message.reply_text("Нет активного спринта.")
        return
    
    task = active_sprints[user_id]['task']
    del active_sprints[user_id]
    
    await update.message.reply_text(f"❌ Спринт '{task}' отменен.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_sprints:
        user_sprints[user_id] = {'sprint_count': 0, 'last_sprint': None}
    
    stats_data = user_sprints[user_id]
    sprint_count = stats_data['sprint_count']
    
    if sprint_count == 0:
        message = "📊 Ты ещё не делал(а) спринтов.\nПопробуй прямо сейчас — 🚀 SPRINT!"
    else:
        message = f"📊 **Твоя статистика:**\n\n• Всего спринтов: {sprint_count}\n\n"
        if sprint_count == 1:
            message += "🎯 Отличное начало!"
        elif sprint_count < 5:
            message += "🔥 Продолжай в том же духе!"
        else:
            message += "🏆 Ты мастер стартов!"
    
    await update.message.reply_text(message, reply_markup=main_keyboard)

async def library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    starts_text = "📋 **Библиотека стартов:**\n\n"
    for i, start in enumerate(MICRO_STARTS, 1):
        starts_text += f"{i}. {start}\n"
    
    starts_text += "\nНажми 🚀 SPRINT для начала!"
    await update.message.reply_text(starts_text, reply_markup=main_keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
❓ **Помощь:**

**Команды:**
/start - Главное меню
/sprint - Начать спринт
/stats - Статистика
/library - Библиотека
/cancel - Отменить спринт
/help - Справка

**Как работает:**
1. 🚀 SPRINT
2. Выбираешь задачу
3. Работаешь 5 минут
4. Отмечаешь успехи

💡 5 минут — это только начало!
"""
    
    await update.message.reply_text(help_text, reply_markup=main_keyboard)

async def handle_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    if user_input == "⬅️ Назад":
        await update.message.reply_text("Главное меню", reply_markup=main_keyboard)
        return
    
    if user_input == "✏️ Ввести свою задачу":
        await update.message.reply_text("✍️ Напиши свою задачу:", reply_markup=ReplyKeyboardRemove())
        context.user_data['awaiting_custom_task'] = True
        return
    
    if user_input in MICRO_STARTS:
        await start_sprint_timer(update, context, user_input)
    elif context.user_data.get('awaiting_custom_task'):
        context.user_data['awaiting_custom_task'] = False
        await start_sprint_timer(update, context, user_input)
    else:
        await update.message.reply_text("Выбери задачу из списка", reply_markup=main_keyboard)

async def start_sprint_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, task: str):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    active_sprints[user_id] = {'task': task}
    
    await update.message.reply_text(
        f"🚀 **Старт спринта!**\n\n"
        f"📌 Задача: {task}\n"
        f"⏱️ 5 минут\n\n"
        "Сосредоточься! 💪",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Таймер через JobQueue
    if context.application and context.application.job_queue:
        context.application.job_queue.run_once(
            send_sprint_completion,
            300,
            data={'user_id': user_id, 'chat_id': chat_id, 'task': task},
            name=f"sprint_{user_id}"
        )
    else:
        # Резервный таймер
        asyncio.create_task(simple_timer(user_id, chat_id, task, context.bot))

async def simple_timer(user_id: int, chat_id: int, task: str, bot):
    """Простой таймер если JobQueue недоступен"""
    await asyncio.sleep(300)
    
    if user_id in active_sprints:
        del active_sprints[user_id]
    
    if user_id not in user_sprints:
        user_sprints[user_id] = {'sprint_count': 0}
    
    user_sprints[user_id]['sprint_count'] += 1
    
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("✅ Да"), KeyboardButton("🤔 Нет")],
        [KeyboardButton("🚀 Новый спринт")]
    ], resize_keyboard=True)
    
    await bot.send_message(
        chat_id=chat_id,
        text=f"🎉 **Спринт завершен!**\n\n"
             f"📌 Задача: {task}\n\n"
             "Стало ли проще продолжить?",
        reply_markup=keyboard
    )

async def handle_reflection_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    if user_input == "✅ Да":
        response = "Отлично! Продолжай! 🎯"
    elif user_input == "🤔 Нет":
        response = "Главное — начало! 💪"
    elif user_input == "🚀 Новый спринт":
        await sprint(update, context)
        return
    else:
        await update.message.reply_text("Ответь Да или Нет")
        return
    
    await update.message.reply_text(response, reply_markup=main_keyboard)

async def set_bot_commands(application):
    await application.bot.set_my_commands(COMMANDS)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Используй кнопки или команды:\n"
        "/start - меню\n"
        "/sprint - начать",
        reply_markup=main_keyboard
    )

# ========== ЗАПУСК ==========
def main():
    print("=" * 50)
    print("🚀 Запуск бота...")
    print("=" * 50)
    
    if TOKEN == "8434110078:AAEeXoKBAmmiWucygF8xiDUNMzbmEbI9vZE":
        print("❌ ОШИБКА: Вставьте свой токен от @BotFather в строку 19!")
        print("1. Откройте Telegram")
        print("2. Найдите @BotFather")
        print("3. Создайте нового бота: /newbot")
        print("4. Скопируйте токен")
        print("5. Вставьте в код вместо 'ВАШ_НОВЫЙ_ТОКЕН_ЗДЕСЬ'")
        return
    
    try:
        application = Application.builder().token(TOKEN).build()
        application.post_init = set_bot_commands
        
        # Регистрация команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("sprint", sprint))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("library", library))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("cancel", cancel_sprint))
        
        # Регистрация кнопок
        application.add_handler(MessageHandler(filters.Text(["🚀 SPRINT"]), sprint))
        application.add_handler(MessageHandler(filters.Text(["📊 Статистика"]), stats))
        application.add_handler(MessageHandler(filters.Text(["📋 Библиотека стартов"]), library))
        application.add_handler(MessageHandler(filters.Text(["❓ Помощь"]), help_command))
        
        # Обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_selection))
        application.add_handler(MessageHandler(filters.Text(["✅ Да", "🤔 Нет", "🚀 Новый спринт"]), handle_reflection_response))
        application.add_handler(MessageHandler(filters.ALL, unknown))
        
        print("✅ Бот запущен!")
        print("✅ Откройте Telegram и найдите своего бота")
        print("=" * 50)
        
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("Проверьте токен!")

if __name__ == '__main__':
    main()


