import sqlite3
import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "8485922325:AAFXd9XVl53dIuD3g2Z0sDses-tKCyfu6N8"

# Подключение к БД
conn = sqlite3.connect("kursach.db", check_same_thread=False)
cursor = conn.cursor()

# ============== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==============
def init_database():
    """Инициализация базы данных"""
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diary (
        user_id INTEGER,
        date TEXT,
        text TEXT,
        mood INTEGER,
        PRIMARY KEY (user_id, date)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        registered_date TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        time TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)
    
    conn.commit()
    logger.info("✅ База данных инициализирована")

init_database()

# ============== КЛАВИАТУРЫ ==============
def get_main_menu_keyboard():
    """Главное меню"""
    keyboard = [
        [KeyboardButton("📖 Мои записи"), KeyboardButton("✏️ Новая запись")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📈 График настроения")],
        [KeyboardButton("⏰ Напоминания"), KeyboardButton("⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_mood_keyboard():
    """Кнопки для выбора настроения"""
    keyboard = [
        [
            InlineKeyboardButton("😢 1", callback_data="mood_1"),
            InlineKeyboardButton("😔 2", callback_data="mood_2"),
            InlineKeyboardButton("😐 3", callback_data="mood_3"),
            InlineKeyboardButton("🙂 4", callback_data="mood_4"),
            InlineKeyboardButton("😊 5", callback_data="mood_5")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard():
    """Кнопка для возврата в меню"""
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]]
    return InlineKeyboardMarkup(keyboard)

# ============== КОМАНДА /START ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    
    cursor.execute(
        """INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, registered_date) 
        VALUES (?, ?, ?, ?, ?)""",
        (user.id, user.username, user.first_name, user.last_name, datetime.datetime.now().isoformat())
    )
    conn.commit()
    
    welcome_text = f"""
✨ *Добро пожаловать, {user.first_name}!* ✨

🧠 *Дневник ментального здоровья* поможет вам:
• 📖 Вести дневник мыслей и эмоций
• 📊 Отслеживать динамику настроения
• ⏰ Получать напоминания о записях
• 📈 Анализировать статистику

Выберите действие из меню ниже:
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

# ============== НОВАЯ ЗАПИСЬ ==============
async def new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало новой записи"""
    # Используем сегодняшнюю дату
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Сохраняем дату в контексте
    context.user_data["current_date"] = today
    context.user_data["waiting_for_text"] = True
    
    await update.message.reply_text(
        f"📅 *Сегодня: {today}*\n\n"
        f"📝 *Напишите свою запись:*",
        parse_mode="Markdown"
    )

# ============== СОХРАНЕНИЕ ТЕКСТА ==============
async def save_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение текста и запрос настроения"""
    
    # Проверяем, ожидаем ли мы текст
    if not context.user_data.get("waiting_for_text", False):
        await handle_menu_selection(update, context)
        return
    
    # Получаем текст
    text = update.message.text
    
    # Сохраняем текст во временное хранилище
    context.user_data["current_text"] = text
    context.user_data["waiting_for_text"] = False
    context.user_data["waiting_for_mood"] = True
    
    # Запрашиваем настроение
    await update.message.reply_text(
        f"📝 *Запись принята!*\n\n"
        f"📊 *Оцените ваше настроение за этот день:*",
        parse_mode="Markdown",
        reply_markup=get_mood_keyboard()
    )

# ============== ОБРАБОТЧИК ЭМОЦИЙ (ИСПРАВЛЕННЫЙ) ==============
async def mood_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора настроения"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Получаем оценку настроения
        mood = int(query.data.split("_")[1])
        
        # Проверяем наличие всех необходимых данных
        if not all(k in context.user_data for k in ["current_date", "current_text"]):
            # Если данных нет, отправляем новое сообщение
            await query.message.reply_text(
                "❌ Ошибка: данные записи утеряны. Начните заново.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Получаем данные
        date = context.user_data["current_date"]
        text = context.user_data["current_text"]
        user_id = query.from_user.id
        
        # Сохраняем в БД
        cursor.execute(
            "INSERT OR REPLACE INTO diary (user_id, date, text, mood) VALUES (?, ?, ?, ?)",
            (user_id, date, text, mood)
        )
        conn.commit()
        
        # Получаем эмодзи для настроения
        mood_emoji = ["😢", "😔", "😐", "🙂", "😊"][mood-1]
        
        # Отправляем подтверждение НОВЫМ сообщением
        await query.message.reply_text(
            f"✅ *Запись сохранена!*\n\n"
            f"📅 *Дата:* {date}\n"
            f"😊 *Настроение:* {mood}/5 {mood_emoji}\n"
            f"📝 *Запись:* {text}\n\n"
            f"_Для новой записи нажмите '✏️ Новая запись' в меню_",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        
        # Очищаем временные данные
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка в mood_handler: {e}")
        await query.message.reply_text(
            "❌ Ошибка при сохранении. Попробуйте снова.",
            reply_markup=get_main_menu_keyboard()
        )

# ============== ПОСМОТРЕТЬ ЗАПИСИ ==============
async def view_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр всех записей"""
    user_id = update.effective_user.id
    
    try:
        cursor.execute(
            "SELECT date, text, mood FROM diary WHERE user_id=? ORDER BY date DESC LIMIT 10",
            (user_id,)
        )
        entries = cursor.fetchall()
        
        if not entries:
            await update.message.reply_text(
                "📭 *У вас пока нет записей.*\n\n"
                "Создайте первую запись через меню ✏️ Новая запись",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        text = "📚 *Ваши последние записи:*\n\n"
        for date, entry_text, mood in entries:
            mood_emoji = f" {'😢😔😐🙂😊'[mood-1] if mood else '❓'}"
            preview = entry_text[:100] + "..." if len(entry_text) > 100 else entry_text
            text += f"📅 *{date}* {mood_emoji}\n{preview}\n\n"
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в view_entries: {e}")
        await update.message.reply_text(
            "❌ Ошибка при загрузке записей.",
            reply_markup=get_main_menu_keyboard()
        )

# ============== СТАТИСТИКА ==============
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    user_id = update.effective_user.id
    
    try:
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM diary WHERE user_id=?", (user_id,))
        total = cursor.fetchone()[0]
        
        if total == 0:
            await update.message.reply_text(
                "📊 У вас пока нет записей.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Статистика по настроению
        cursor.execute(
            "SELECT mood, COUNT(*) FROM diary WHERE user_id=? AND mood IS NOT NULL GROUP BY mood",
            (user_id,)
        )
        stats = cursor.fetchall()
        
        text = "📊 *Статистика настроения:*\n\n"
        
        if stats:
            mood_total = sum(count for _, count in stats)
            avg_mood = sum(mood * count for mood, count in stats) / mood_total
            
            for mood, count in sorted(stats):
                emoji = ["😢", "😔", "😐", "🙂", "😊"][mood-1]
                percentage = (count / mood_total) * 100
                bars = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
                text += f"{emoji} {mood}/5: {bars} {percentage:.1f}%\n"
            
            text += f"\n📈 Среднее настроение: {avg_mood:.2f}/5\n"
        
        text += f"\n📝 Всего записей: {total}"
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в show_stats: {e}")
        await update.message.reply_text(
            "❌ Ошибка при расчете статистики.",
            reply_markup=get_main_menu_keyboard()
        )

# ============== ГРАФИК НАСТРОЕНИЯ ==============
async def show_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Текстовый график настроения"""
    user_id = update.effective_user.id
    
    try:
        cursor.execute(
            "SELECT date, mood FROM diary WHERE user_id=? AND mood IS NOT NULL ORDER BY date DESC LIMIT 10",
            (user_id,)
        )
        data = cursor.fetchall()
        
        if len(data) < 2:
            await update.message.reply_text(
                "📈 Для графика нужно минимум 2 записи с настроением.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        text = "📈 *График настроения:*\n\n"
        
        # Простой текстовый график
        for date, mood in reversed(data):  # От старых к новым
            date_short = date[5:]  # Только месяц-день
            bars = "█" * mood + "░" * (5 - mood)
            emoji = ["😢", "😔", "😐", "🙂", "😊"][mood-1]
            text += f"{date_short}: {bars} {emoji}\n"
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в show_chart: {e}")
        await update.message.reply_text(
            "❌ Ошибка при построении графика.",
            reply_markup=get_main_menu_keyboard()
        )

# ============== ОБРАБОТЧИК КНОПОК ГЛАВНОГО МЕНЮ ==============
async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора в главном меню"""
    text = update.message.text
    
    if text == "📖 Мои записи":
        await view_entries(update, context)
        
    elif text == "✏️ Новая запись":
        await new_entry(update, context)
        
    elif text == "📊 Статистика":
        await show_stats(update, context)
        
    elif text == "📈 График настроения":
        await show_chart(update, context)
        
    elif text == "⏰ Напоминания":
        await update.message.reply_text(
            "⏰ *Напоминания*\n\n"
            "Функция напоминаний скоро будет добавлена!",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        
    elif text == "⚙️ Настройки":
        await update.message.reply_text(
            "⚙️ *Настройки*\n\n"
            "Доступные функции:\n"
            "• 📊 Статистика настроения\n"
            "• 📈 График настроения\n"
            "• 📖 Просмотр всех записей\n\n"
            "Выберите нужный пункт в главном меню.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        
    else:
        # Если сообщение не распознано, проверяем состояния
        if context.user_data.get("waiting_for_text", False):
            await save_text(update, context)
        else:
            await update.message.reply_text(
                "Выберите действие из меню ниже:",
                reply_markup=get_main_menu_keyboard()
            )

# ============== ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ==============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик сообщений"""
    try:
        # Если есть активное состояние "ожидание текста"
        if context.user_data.get("waiting_for_text", False):
            await save_text(update, context)
        else:
            await handle_menu_selection(update, context)
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_message: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте снова.",
            reply_markup=get_main_menu_keyboard()
        )

# ============== ОБРАБОТЧИК ОШИБОК ==============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error(f"❌ Необработанная ошибка: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте снова.",
                reply_markup=get_main_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")

# ============== ОСНОВНАЯ ФУНКЦИЯ ==============
def main():
    """Запуск бота"""
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Добавляем обработчик ошибок
    app.add_error_handler(error_handler)
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    
    # Обработчик кнопок настроения
    app.add_handler(CallbackQueryHandler(mood_handler))
    
    # Обработчик текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("=" * 50)
    print("✅ Бот запущен!")
    print("✨ Версия с исправленными эмоциями")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()