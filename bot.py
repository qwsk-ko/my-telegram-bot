import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
import sqlite3
import asyncio
from datetime import datetime, date

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота (ЗАМЕНИТЕ НА ВАШ ТОКЕН)
BOT_TOKEN = "8434110078:AAEeXoKBAmmiWucygF8xiDUNMzbmEbI9vZE"

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

# Функция для сохранения спринта в БД
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

# Функция для получения статистики
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
/help - Помощь

*Как это работает?*
Просто нажми /sprint и потрать всего 5 минут на свою задачу. Не нужно делать всё сразу — просто НАЧНИ!

Готов сделать первый шаг? 🎯
"""
    await update.message.reply_text(welcome_text)

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **Как пользоваться ботом:**

1. **Начать спринт** - отправь /sprint
2. **Работай 5 минут** - сфокусируйся на задаче
3. **Ответь на вопросы** - после спринта расскажи о своих успехах

💡 **Советы:**
- Не думай о всей задаче, думай только о 5 минутах
- Выбери самую маленькую часть работы
- Если трудно начать — просто подготовь рабочее место

*Помни: главное — НАЧАТЬ!*
"""
    await update.message.reply_text(help_text)

async def start_sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Очищаем предыдущие состояния для этого пользователя
    context.user_data.clear()
    
    # Спрашиваем, какую задачу будет делать пользователь
    await update.message.reply_text(
        "🎯 *Какую задачу ты будешь делать эти 5 минут?*\n\n"
        "Например: 'написать 3 предложения', 'разобрать бумаги на столе', 'создать структуру документа'\n\n"
        "Опиши её в одном сообщении:",
        parse_mode='Markdown'
    )
    
    # Устанавливаем состояние ожидания описания задачи ДЛЯ ЭТОГО ПОЛЬЗОВАТЕЛЯ
    context.user_data['waiting_for_task'] = True
    
    # Устанавливаем состояние ожидания описания задачи
    context.user_data['waiting_for_task'] = True

# Обработчик описания задачи и запуск таймера
async def handle_task_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_task'):
        task_description = update.message.text
        user_id = update.effective_user.id
        
        # Сохраняем описание задачи
        context.user_data['current_task'] = task_description
        
        # Запускаем спринт
        await update.message.reply_text(
            f"⏱️ *Отлично! Запускаю 5-минутный спринт!*\n\n"
            f"*Задача:* {task_description}\n"
            f"*Время:* 5 минут\n\n"
            f"⏰ Таймер пошёл! Сфокусируйся на задаче. Я напомню, когда время выйдет.\n"
            f"_Не открывай Telegram до сигнала!_",
            parse_mode='Markdown'
        )
        
        # Сбрасываем состояние ожидания
        context.user_data['waiting_for_task'] = False
        
        # Устанавливаем статус "занят"
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Ждем 5 минут (300 секунд)
        await asyncio.sleep(300)
        
        # Сохраняем спринт в базу данных
        save_sprint(user_id)
        
        # Отправляем сообщение об окончании
        await update.message.reply_text(
            "🔔 *Время вышло! 5 минут прошли!*\n\n"
            "Отлично сработано! Теперь ответь на два вопроса:\n\n"
            "1. *Что тебе удалось сделать за эти 5 минут?* (Опиши кратко)\n"
            "2. *Стало ли сейчас проще продолжить?* (Да/Нет)",
            parse_mode='Markdown'
        )
        
        # Устанавливаем состояние ожидания ответа на вопросы
        context.user_data['waiting_for_reflection'] = True

# Обработчик рефлексии после спринта
# Функция анализа достижений
def analyze_achievements(text):
    text_lower = text.lower()
    achievements = []
    
    if any(word in text_lower for word in ['написал', 'сделал', 'закончил', 'готов']):
        achievements.append("completion")
    if any(word in text_lower for word in ['начал', 'создал', 'подготовил', 'организовал']):
        achievements.append("progress") 
    if any(word in text_lower for word in ['попробовал', 'подумал', 'изучил', 'посмотрел']):
        achievements.append("start")
        
    return achievements if achievements else ["start"]

# Функция определения уровня мотивации
def get_motivation_level(text):
    text_lower = text.lower()
    if any(word in text_lower for word in ['да', 'легче', 'проще', 'продолжу', 'сделаю']):
        return "high"
    elif any(word in text_lower for word in ['немного', 'чуть', 'пока нет', 'не очень']):
        return "medium"
    else:
        return "low"

# Функция подбора похвалы
def get_praise_message(sprints_count, achievements, motivation_level):
    # Похвала за количество спринтов
    sprint_praise = PRAISE_BY_SPRINTS.get(sprints_count, "")
    
    # Похвала за тип достижений
    achievement_praise = ""
    if "completion" in achievements:
        achievement_praise = "Завершение этапа — это круто! Ты видишь результат своих усилий! 🏆"
    elif "progress" in achievements:
        achievement_praise = "Прогресс ощущается! Ты движешься вперёд — это важно! 💫"
    else:
        achievement_praise = "Ты начал — это уже 50% успеха! Первый шаг сделан! 🌟"
    
    # Мотивация продолжать
    continuation_motivation = ""
    if motivation_level == "high":
        continuation_motivation = "\n\n🎯 *Отличный настрой!* Используй этот импульс и продолжай прямо сейчас!"
    elif motivation_level == "medium":
        continuation_motivation = "\n\n💪 *Ты на правильном пути!* Сделай ещё один маленький шаг — следующий будет легче!"
    else:
        continuation_motivation = "\n\n🌟 *Не сдавайся!* Иногда нужно просто продолжать, даже если трудно. Ты справишься!"
    
    return f"{sprint_praise}\n\n{achievement_praise}{continuation_motivation}"

# Функция создания мотивационного ответа
def create_motivational_response(praise, achievements, today_sprints):
    # Эмодзи в зависимости от достижений
    if "completion" in achievements:
        emoji = "🏆"
    elif "progress" in achievements:
        emoji = "🚀" 
    else:
        emoji = "🎯"
    
    base_response = f"""
{emoji} *Отличная работа!*

{praise}

*Статистика на сегодня:* {today_sprints} спринтов • {today_sprints * 5} минут в работе

*Что дальше?*
/sprint - Сделать ещё один спринт
/stats - Посмотреть подробную статистику
/help - Напомнить о возможностях

*Помни: каждый спринт приближает тебя к цели!* ✨
"""
    return base_response

# Обработчик рефлексии после спринта (УЛУЧШЕННАЯ ВЕРСИЯ)
async def handle_reflection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_reflection'):
        reflection_text = update.message.text
        user_id = update.effective_user.id
        today_sprints = get_stats(user_id)
        
        # Анализируем ответ пользователя
        user_achievements = analyze_achievements(reflection_text)
        motivation_level = get_motivation_level(reflection_text)
        
        # Подбираем похвалу
        praise = get_praise_message(today_sprints, user_achievements, motivation_level)
        
        # Формируем персонализированный ответ
        response = create_motivational_response(praise, user_achievements, today_sprints)
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
        # Сбрасываем состояние ожидания рефлексии
        context.user_data['waiting_for_reflection'] = False

# Команда /stats
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_sprints = get_stats(user_id)
    
    if today_sprints > 0:
        message = (
            f"📊 *Ваша статистика*\n\n"
            f"*Спринтов сегодня:* {today_sprints}\n"
            f"*Всего времени в работе:* {today_sprints * 5} минут\n\n"
        )
        
        if today_sprints >= 3:
            message += "🔥 Вы просто машина продуктивности! Продолжайте в том же духе!"
        elif today_sprints >= 1:
            message += "💪 Отличное начало! Каждый спринт приближает вас к цели."
    else:
        message = "📊 У вас ещё не было спринтов сегодня.\n\nНачните первый: /sprint"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Умный обработчик всех сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, в каком состоянии пользователь
    if context.user_data.get('waiting_for_task'):
        await handle_task_description(update, context)
    elif context.user_data.get('waiting_for_reflection'):
        await handle_reflection(update, context)
    else:
        # Если не в особом состоянии, просто игнорируем или отправляем подсказку
        await update.message.reply_text(
            "Используйте команды для работы с ботом:\n"
            "/sprint - начать 5-минутный спринт\n"
            "/stats - посмотреть статистику\n"
            "/motivate - получить мотивацию",
            parse_mode='Markdown'
        )

# Умный обработчик всех сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, в каком состоянии пользователь
    if context.user_data.get('waiting_for_task'):
        await handle_task_description(update, context)
    elif context.user_data.get('waiting_for_reflection'):
        await handle_reflection(update, context)
    else:
        # Если не в особом состоянии, просто игнорируем или отправляем подсказку
        await update.message.reply_text(
            "Используйте команды для работы с ботом:\n"
            "/sprint - начать 5-минутный спринт\n"
            "/stats - посмотреть статистику\n"
            "/motivate - получить мотивацию",
            parse_mode='Markdown'
        )

# Улучшенная функция начала спринта
async def start_sprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Очищаем предыдущие состояния для этого пользователя
    context.user_data.clear()
    
    # Спрашиваем, какую задачу будет делать пользователь
    await update.message.reply_text(
        "🎯 *Какую задачу ты будешь делать эти 5 минут?*\n\n"
        "Например: 'написать 3 предложения', 'разобрать бумаги на столе', 'создать структуру документа'\n\n"
        "Опиши её в одном сообщении:",
        parse_mode='Markdown'
    )
    
    # Устанавливаем состояние ожидания описания задачи ДЛЯ ЭТОГО ПОЛЬЗОВАТЕЛЯ
    context.user_data['waiting_for_task'] = True

async def motivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import random
    motivations = [
        "💫 *Ты можешь больше, чем думаешь!* Просто сделай ещё один маленький шаг.",
        "🚀 *Помни о своей цели!* Каждые 5 минут работы приближают тебя к ней.",
        "🌟 *Не перфекционизм, а прогресс!* Лучше сделать неидеально, чем не сделать вообще.",
        "💪 *Ты уже прошёл часть пути!* Осталось только продолжить.",
        "🎯 *Разбей большую задачу на маленькие шаги* — и она перестанет пугать.",
        "🔥 *Ты справился с началом* — самое сложное уже позади!"
    ]
    await update.message.reply_text(random.choice(motivations), parse_mode='Markdown')

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_sprints = get_stats(user_id)
    
    if today_sprints == 0:
        message = "📊 *Давай начнём!* У тебя ещё не было спринтов сегодня.\n\nНачни первый: /sprint"
    elif today_sprints <= 2:
        message = f"📊 *Отличное начало!* {today_sprints} спринта — это {today_sprints * 5} минут продуктивной работы! \n\nПродолжай в том же духе! 💪"
    elif today_sprints <= 5:
        message = f"📊 *Отлично работаешь!* {today_sprints} спринтов — ты явно вошёл в ритм! \n\nТак держать! 🚀"
    else:
        message = f"📊 *Восхитительно!* {today_sprints} спринтов — ты просто машина продуктивности! \n\nПродолжаешь? /sprint 🔥"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Основная функция
def main():
    # Инициализация базы данных
    init_db()
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("sprint", start_sprint))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("motivate", motivate))
    application.add_handler(CommandHandler("progress", progress))
    
    # Раздельные обработчики для разных состояний
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    application.run_polling()
    print("Бот запущен!")

if __name__ == '__main__':
    main()