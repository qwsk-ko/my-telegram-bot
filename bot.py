import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, JobQueue
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные для хранения состояния
user_sprints = {}  # {user_id: {'current_task': str, 'sprint_count': int, 'last_sprint': datetime, 'active_jobs': list}}
active_sprints = {}  # {user_id: {'chat_id': int, 'task': str, 'start_time': datetime}}

# Команды для меню
COMMANDS = [
    BotCommand("start", "Главное меню"),
    BotCommand("sprint", "Начать 5-минутный спринт"),
    BotCommand("stats", "Показать статистику"),
    BotCommand("library", "Библиотека микро-стартов"),
    BotCommand("help", "Помощь по использованию бота"),
    BotCommand("cancel", "Отменить текущий спринт"),
]

# Клавиатура для главного меню
main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("🚀 SPRINT"), KeyboardButton("📊 Статистика")],
    [KeyboardButton("📋 Библиотека стартов"), KeyboardButton("❓ Помощь")]
], resize_keyboard=True)

# Библиотека микро-стартов
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

# ========== ФУНКЦИИ ДЛЯ ТАЙМЕРОВ ==========

async def send_sprint_completion(context):
    """Отправляет сообщение о завершении спринта"""
    job = context.job
    user_id = job.data['user_id']
    chat_id = job.data['chat_id']
    task = job.data['task']
    
    # Удаляем из активных спринтов
    if user_id in active_sprints:
        del active_sprints[user_id]
    
    # Обновляем статистику
    if user_id not in user_sprints:
        user_sprints[user_id] = {'current_task': '', 'sprint_count': 0, 'last_sprint': None, 'active_jobs': []}
    
    user_sprints[user_id]['sprint_count'] += 1
    user_sprints[user_id]['last_sprint'] = datetime.now()
    
    # Вопросы для рефлексии
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("✅ Да, стало проще"), KeyboardButton("🤔 Нет, пока сложно")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🚀 Новый спринт")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎉 **Отлично! Спринт завершен!**\n\n"
                 f"Ты только что посвятил 5 минут задаче:\n"
                 f"📌 **{task}**\n\n"
                 "🔄 **Время для рефлексии:**\n\n"
                 "1. Что удалось сделать за эти 5 минут?\n"
                 "(Напиши ответ в чат)\n\n"
                 "2. Стало ли сейчас проще продолжить?",
            reply_markup=keyboard
        )
        logger.info(f"Sprint completion sent to user {user_id}")
        
        # Запланировать напоминание через 5 минут
        reminder_job = context.job_queue.run_once(
            send_success_reminder,
            300,  # 5 минут
            data={'user_id': user_id, 'chat_id': chat_id, 'task': task},
            name=f"reminder_{user_id}_{datetime.now().timestamp()}"
        )
        
        # Сохраняем ID работы для возможной отмены
        user_sprints[user_id]['active_jobs'].append(reminder_job.name)
        
    except Exception as e:
        logger.error(f"Failed to send sprint completion to user {user_id}: {e}")

async def send_success_reminder(context):
    """Отправляет напоминание об успехах через 5 минут"""
    job = context.job
    user_id = job.data['user_id']
    chat_id = job.data['chat_id']
    task = job.data['task']
    
    # Получаем статистику пользователя
    sprint_count = user_sprints.get(user_id, {}).get('sprint_count', 0)
    
    reminder_text = f"""
    ⏰ **Напоминание о твоих успехах!**
    
    Всего 10 минут назад ты завершил спринт по задаче:
    📌 **{task}**
    
    📊 За всё время ты уже сделал(а) **{sprint_count}** спринтов!
    
    💡 Помни: даже маленькие шаги ведут к большим результатам.
    
    Хочешь сделать ещё один 5-минутный рывок?
    
    Напиши /sprint для нового старта! 🚀
    """
    
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=reminder_text
        )
        logger.info(f"Success reminder sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send reminder to user {user_id}: {e}")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Инициализация пользователя
    if user_id not in user_sprints:
        user_sprints[user_id] = {'current_task': '', 'sprint_count': 0, 'last_sprint': None, 'active_jobs': []}
    
    welcome_text = f"""
    👋 Привет, {user.first_name}!

    🎯 Я — твой «5-минутный Стартер» — бот для борьбы с прокрастинацией!

    🚀 **Как это работает:**
    1. Нажимаешь «🚀 SPRINT» или пишешь /sprint
    2. Выбираешь задачу (или пишешь свою)
    3. Работаешь 5 минут без отвлечений
    4. Отмечаешь успехи и получаешь награду!

    💡 Всего 5 минут могут запустить продуктивный поток!

    Используй кнопки ниже или команды через / ⬇️
    """
    
    await update.message.reply_text(welcome_text, reply_markup=main_keyboard)

async def sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, нет ли уже активного спринта
    if user_id in active_sprints:
        await update.message.reply_text(
            "⏳ У тебя уже есть активный спринт!\n"
            "Дождись его завершения или отмени командой /cancel",
            reply_markup=main_keyboard
        )
        return
    
    if user_id not in user_sprints:
        user_sprints[user_id] = {'current_task': '', 'sprint_count': 0, 'last_sprint': None, 'active_jobs': []}
    
    # Предлагаем выбрать или ввести задачу
    keyboard = [[KeyboardButton(start)] for start in MICRO_STARTS[:4]]
    keyboard.append([KeyboardButton("✏️ Ввести свою задачу")])
    keyboard.append([KeyboardButton("⬅️ Назад")])
    
    start_keyboard = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "🎯 **Выбери готовый старт или введи свою задачу:**\n\n"
        "Ты можешь:\n"
        "• Выбрать из списка микро-стартов\n"
        "• Написать свою задачу (например: 'написать введение к отчету')\n\n"
        "Помни: не нужно выполнить задачу целиком — просто поработай над ней 5 минут!",
        reply_markup=start_keyboard
    )

async def cancel_sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего спринта"""
    user_id = update.effective_user.id
    
    if user_id not in active_sprints:
        await update.message.reply_text(
            "У тебя нет активного спринта.",
            reply_markup=main_keyboard
        )
        return
    
    # Отменяем все запланированные задания для этого пользователя
    if user_id in user_sprints and 'active_jobs' in user_sprints[user_id]:
        for job_name in user_sprints[user_id]['active_jobs']:
            current_jobs = context.job_queue.get_jobs_by_name(job_name)
            for job in current_jobs:
                job.schedule_removal()
    
    # Удаляем из активных спринтов
    task = active_sprints[user_id]['task']
    del active_sprints[user_id]
    
    await update.message.reply_text(
        f"❌ Спринт по задаче '{task}' отменен.\n"
        "Ты всегда можешь начать заново командой /sprint!",
        reply_markup=main_keyboard
    )

async def handle_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_input = update.message.text
    
    if user_input == "⬅️ Назад":
        await update.message.reply_text("Возвращаю в главное меню", reply_markup=main_keyboard)
        return
    
    if user_input == "✏️ Ввести свою задачу":
        await update.message.reply_text(
            "✍️ Напиши свою задачу одним предложением:\n"
            "Например: 'составить план проекта' или 'разобрать почту'",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['awaiting_custom_task'] = True
        return
    
    if user_input in MICRO_STARTS:
        task = user_input
        await start_sprint_timer(update, context, task)
    elif context.user_data.get('awaiting_custom_task'):
        task = user_input
        context.user_data['awaiting_custom_task'] = False
        await start_sprint_timer(update, context, task)
    else:
        await update.message.reply_text(
            "Пожалуйста, выбери задачу из списка или нажми '✏️ Ввести свою задачу'",
            reply_markup=main_keyboard
        )

async def start_sprint_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, task: str):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Сохраняем в активные спринты
    active_sprints[user_id] = {
        'chat_id': chat_id,
        'task': task,
        'start_time': datetime.now()
    }
    
    # Сообщение о начале спринта
    await update.message.reply_text(
        f"🚀 **Старт 5-минутного спринта!**\n\n"
        f"📌 Задача: {task}\n"
        f"⏱️ Таймер: 5:00\n"
        f"🕐 Завершится в: {(datetime.now() + timedelta(minutes=5)).strftime('%H:%M:%S')}\n\n"
        "⛔ Бот будет занят и не ответит до конца спринта!\n"
        "Сосредоточься на задаче. У тебя всё получится! 💪\n\n"
        "ℹ️ Для отмены спринта используй /cancel",
        reply_markup=ReplyKeyboardRemove()
    )
    
    logger.info(f"User {user_id} started sprint with task: {task}")
    
    # Запланировать завершение спринта через 5 минут
    sprint_job = context.job_queue.run_once(
        send_sprint_completion,
        300,  # 5 минут
        data={'user_id': user_id, 'chat_id': chat_id, 'task': task},
        name=f"sprint_{user_id}_{datetime.now().timestamp()}"
    )
    
    # Сохраняем ID работы
    if user_id not in user_sprints:
        user_sprints[user_id] = {'current_task': '', 'sprint_count': 0, 'last_sprint': None, 'active_jobs': []}
    
    user_sprints[user_id]['active_jobs'].append(sprint_job.name)

# ... остальные функции (stats, library, help_command, handle_reflection_response) остаются без изменений ...

async def handle_reflection_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_input = update.message.text
    
    if user_input == "✅ Да, стало проще":
        response = "Отлично! Инерция работает на тебя! Продолжай в том же духе! 🎯"
    elif user_input == "🤔 Нет, пока сложно":
        response = "Это нормально! Главное — ты сделал(а) первый шаг. Иногда нужно несколько спринтов, чтобы войти в поток. Попробуй ещё раз! 💪"
    elif user_input == "📊 Статистика":
        await stats(update, context)
        return
    elif user_input == "🚀 Новый спринт":
        await sprint(update, context)
        return
    else:
        response = f"Зафиксировал твой прогресс: '{user_input}'\n\nТеперь ответь на второй вопрос: стало ли проще продолжить?"
        await update.message.reply_text(response)
        return
    
    await update.message.reply_text(
        response + f"\n\n🎁 Ты получаешь +1 балл!\nВсего спринтов: {user_sprints[user_id]['sprint_count']}",
        reply_markup=main_keyboard
    )

async def set_bot_commands(application):
    await application.bot.set_my_commands(COMMANDS)
    logger.info("Bot commands menu has been set")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Извини, я не понял команду 😕\n\n"
        "Используй кнопки меню или команды через /:\n"
        "/start — главное меню\n"
        "/sprint — начать спринт\n"
        "/stats — статистика\n"
        "/help — помощь",
        reply_markup=main_keyboard
    )

# Основная функция
def main():
    TOKEN = "ВАШ_TELEGRAM_BOT_TOKEN"
    
    application = Application.builder().token(TOKEN).build()
    
    # Устанавливаем меню команд
    application.post_init = set_bot_commands
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sprint", sprint))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("library", library))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_sprint))  # Новая команда
    
    # Регистрируем обработчики сообщений для кнопок
    application.add_handler(MessageHandler(filters.Text(["🚀 SPRINT"]), sprint))
    application.add_handler(MessageHandler(filters.Text(["📊 Статистика"]), stats))
    application.add_handler(MessageHandler(filters.Text(["📋 Библиотека стартов"]), library))
    application.add_handler(MessageHandler(filters.Text(["❓ Помощь"]), help_command))
    
    # Обработчик выбора задачи
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_task_selection
    ))
    
    # Обработчик ответов на вопросы рефлексии
    application.add_handler(MessageHandler(
        filters.Text(["✅ Да, стало проще", "🤔 Нет, пока сложно", "📊 Статистика", "🚀 Новый спринт"]),
        handle_reflection_response
    ))
    
    # Обработчик неизвестных сообщений
    application.add_handler(MessageHandler(filters.ALL, unknown))
    
    # Запуск бота
    print("✅ Бот запущен и работает стабильно!")
    print("✅ Таймеры теперь работают через JobQueue")
    print("✅ Бот не будет зависать на 5 минут")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
