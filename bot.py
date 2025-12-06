import os
import logging
import random
import sqlite3
from datetime import date
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ ОШИБКА: BOT_TOKEN не найден!")
    print("❌ ОШИБКА: BOT_TOKEN не найден!")
    exit(1)

# Система мотивационных сообщений
MOTIVATION_PHRASES = [
    "💫 Ты можешь больше, чем думаешь! Просто сделай ещё один маленький шаг.",
    "🚀 Помни о своей цели! Каждые 5 минут работы приближают тебя к ней.",
    "🌟 Не перфекционизм, а прогресс! Лучше сделать неидеально, чем не сделать вообще.",
    "💪 Ты уже прошёл часть пути! Осталось только продолжить.",
    "🎯 Разбей большую задачу на маленькие шаги — и она перестанет пугать.",
    "🔥 Ты справился с началом — самое сложное уже позади!"
]

# Система похвалы по количеству спринтов
PRAISE_BY_SPRINTS = {
    1: "Первый спринт — самый важный! Ты начал, и это главное! 🎯",
    2: "Уже два спринта! Ты набираешь обороты! 💪",
    3: "Три спринта! Ты вошёл в ритм — так держать! 🚀",
    5: "Пять спринтов! Ты — машина продуктивности! 🔥",
    10: "Десять спринтов! Ты просто неостановим! 🌟"
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('sprints.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sprints (
            user_id INTEGER,
            date TEXT,
            sprint_count INTEGER,
            PRIMARY KEY (user_id, date)
        )
    ''')
    conn.commit()
    conn.close()

def save_sprint(user_id):
    today = date.today().isoformat()
    conn = sqlite3.connect('sprints.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO user_sprints (user_id, date, sprint_count)
        VALUES (?, ?, COALESCE((SELECT sprint_count FROM user_sprints WHERE user_id=? AND date=?), 0) + 1)
    ''', (user_id, today, user_id, today))
    
    conn.commit()
    conn.close()

def get_stats(user_id):
    today = date.today().isoformat()
    conn = sqlite3.connect('sprints.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT sprint_count FROM user_sprints 
        WHERE user_id=? AND date=?
    ''', (user_id, today))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 0

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🚀 Привет! Я твой «5-минутный Стартер»!

Я помогу тебе начать делать то, что ты давно откладываешь. 

Вот что я умею:
/sprint - Начать 5-минутный спринт
/stats - Посмотреть статистику
/motivate - Получить мотивацию
/progress - Узнать прогресс
/help - Помощь

Готов сделать первый шаг? 🎯
"""
    await update.message.reply_text(welcome_text)

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Как пользоваться ботом:

1. Начать спринт - /sprint
2. Работай 5 минут - сфокусируйся на задаче  
3. Расскажи о успехах - после спринта поделись результатом

Советы:
- Не думай о всей задаче, думай только о 5 минутах
- Выбери самую маленькую часть работы
- Главное — НАЧАТЬ!
"""
    await update.message.reply_text(help_text)

# Команда /sprint
async def start_sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['waiting_for_task'] = True
    
    await update.message.reply_text(
        "🎯 Какую задачу ты будешь делать эти 5 минут?\n\n"
        "Например: 'написать 3 предложения', 'разобрать бумаги на столе', 'создать структуру документа'\n\n"
        "Опиши её в одном сообщении:"
    )

# Команда /motivate
async def motivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    motivation = random.choice(MOTIVATION_PHRASES)
    await update.message.reply_text(motivation)

# Команда /progress
async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_sprints = get_stats(user_id)
    
    if today_sprints == 0:
        message = "📊 Давай начнём! У тебя ещё не было спринтов сегодня.\n\nНачни первый: /sprint"
    elif today_sprints <= 2:
        message = f"📊 Отличное начало! {today_sprints} спринта — это {today_sprints * 5} минут продуктивной работы! \n\nПродолжай в том же духе! 💪"
    elif today_sprints <= 5:
        message = f"📊 Отлично работаешь! {today_sprints} спринтов — ты явно вошёл в ритм! \n\nТак держать! 🚀"
    else:
        message = f"📊 Восхитительно! {today_sprints} спринтов — ты просто машина продуктивности! \n\nПродолжаешь? /sprint 🔥"
    
    await update.message.reply_text(message)

# Умная система анализа достижений
def analyze_achievements(text):
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['написал', 'сделал', 'закончил', 'готов', 'завершил']):
        return "completion"
    elif any(word in text_lower for word in ['начал', 'создал', 'подготовил', 'организовал', 'продвинулся']):
        return "progress"
    else:
        return "start"

def get_praise_message(sprints_count, achievement_type):
    sprint_praise = PRAISE_BY_SPRINTS.get(sprints_count, "")
    
    if achievement_type == "completion":
        achievement_praise = "Завершение этапа — это круто! Ты видишь результат своих усилий! 🏆"
    elif achievement_type == "progress":
        achievement_praise = "Прогресс ощущается! Ты движешься вперёд — это важно! 💫"
    else:
        achievement_praise = "Ты начал — это уже 50% успеха! Первый шаг сделан! 🌟"
    
    if sprint_praise:
        return f"{sprint_praise}\n\n{achievement_praise}"
    return achievement_praise

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_task'):
        # Обработка описания задачи
        task_description = update.message.text
        context.user_data['current_task'] = task_description
        context.user_data['waiting_for_task'] = False
        context.user_data['waiting_for_reflection'] = True
        
        await update.message.reply_text(
            f"⏱️ Отлично! Запускаю 5-минутный спринт!\n\n"
            f"Задача: {task_description}\n"
            f"Время: 5 минут\n\n"
            f"⏰ Таймер пошёл! Сфокусируйся на задаче. Я напомню, когда время выйдет."
        )
        
        # Сохраняем данные для таймера
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Запускаем таймер (10 секунд для теста)
        context.job_queue.run_once(
            send_timer_notification, 
            10,
            data={
                'chat_id': chat_id,
                'user_id': user_id
            }
        )
    
    elif context.user_data.get('waiting_for_reflection'):
        # Обработка отчёта о спринте
        reflection_text = update.message.text
        user_id = update.effective_user.id
        today_sprints = get_stats(user_id)
        
        # Анализируем достижения
        achievement_type = analyze_achievements(reflection_text)
        praise = get_praise_message(today_sprints, achievement_type)
        
        # Формируем ответ
        emoji = "🏆" if achievement_type == "completion" else "🚀" if achievement_type == "progress" else "🎯"
        
        response = f"""
{emoji} Отличная работа!

{praise}

Статистика на сегодня: {today_sprints} спринтов • {today_sprints * 5} минут в работе

Что дальше?
/sprint - Сделать ещё один спринт
/stats - Посмотреть статистику
/motivate - Получить мотивацию

Помни: каждый спринт приближает тебя к цели! ✨
"""
        await update.message.reply_text(response)
        context.user_data['waiting_for_reflection'] = False
    else:
        await update.message.reply_text(
            "Используйте команды для работы с ботом:\n"
            "/sprint - начать 5-минутный спринт\n"
            "/stats - посмотреть статистику\n"
            "/motivate - получить мотивацию"
        )

# Функция для отправки уведомления по таймеру
async def send_timer_notification(context):
    job = context.job
    chat_id = job.data['chat_id']
    user_id = job.data['user_id']
    
    # Сохраняем спринт в БД
    save_sprint(user_id)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="🔔 Время вышло! 5 минут прошли!\n\n"
             "Отлично сработано! Теперь ответь на вопрос:\n\n"
             "Что тебе удалось сделать за эти 5 минут? (Опиши кратко)"
    )

# Команда /stats
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_sprints = get_stats(user_id)
    
    if today_sprints > 0:
        message = (
            f"📊 Ваша статистика\n\n"
            f"Спринтов сегодня: {today_sprints}\n"
            f"Всего времени в работе: {today_sprints * 5} минут\n\n"
        )
        
        if today_sprints >= 3:
            message += "🔥 Вы просто машина продуктивности! Продолжайте в том же духе!"
        elif today_sprints >= 1:
            message += "💪 Отличное начало! Каждый спринт приближает вас к цели."
    else:
        message = "📊 У вас ещё не было спринтов сегодня.\n\nНачните первый: /sprint"
    
    await update.message.reply_text(message)

def main():
    logger.info("🚀 Запуск бота...")
    
    try:
        init_db()
        
        # Создание Application для версии 20.0+
        application = Application.builder() \
            .token(BOT_TOKEN) \
            .build()
        
        # Обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("sprint", start_sprint))
        application.add_handler(CommandHandler("stats", show_stats))
        application.add_handler(CommandHandler("motivate", motivate))
        application.add_handler(CommandHandler("progress", progress))
        
        # Обработчик сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("✅ Бот запущен и работает 24/7! 🚀")
        print("✅ Бот запущен и работает 24/7! 🚀")
        
        # Запуск бота
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске: {e}")
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
