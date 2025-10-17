import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button
import random
import logging
import asyncio
from config import load_config
from supabase import create_client, Client

CONFIG = load_config()
logger = logging.getLogger("QuizCog")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def fetch_questions_from_supabase():
    try:
        # Синхронный вызов execute в отдельном потоке
        response = await asyncio.to_thread(lambda: supabase.table("quiz_questions").select("*").execute())

        data = response.data  # тут уже список записей
        if not data:
            logger.error("❌ Данных из Supabase нет.")
            return []

        valid_questions = []
        for q in data:
            if all(k in q for k in ("Категория", "вопрос", "вариант_1", "вариант_2", "вариант_3", "вариант_4", "ответ")):
                q_dict = {
                    "category": q["Категория"],
                    "question": q["вопрос"],
                    "options": [q["вариант_1"], q["вариант_2"], q["вариант_3"], q["вариант_4"]],
                    "answer": int(q["ответ"])
                }
                valid_questions.append(q_dict)

        logger.info(f"✅ Загружено {len(valid_questions)} вопросов из Supabase")
        return valid_questions

    except Exception as e:
        logger.error(f"❌ Ошибка при получении данных из Supabase: {e}")
        return []

# --- QuizView, CategorySelect, CategoryView остаются без изменений ---
class QuizView(View):
    def __init__(self, question_data):
        super().__init__(timeout=None)
        self.question = question_data
        self.answered_users = set()
        for idx, option in enumerate(self.question['options'], start=1):
            button = Button(label=str(idx), style=discord.ButtonStyle.primary)
            button.callback = self.make_callback(idx)
            self.add_item(button)

    def make_callback(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.answered_users:
                await interaction.response.send_message("Вы уже отвечали на этот вопрос.", ephemeral=True)
                return
            self.answered_users.add(interaction.user.id)
            correct = self.question['answer']
            if idx == correct:
                await interaction.response.send_message("🎉 Правильно!", ephemeral=True)
                await interaction.channel.send(f"✅ {interaction.user.mention} дал правильный ответ!")
                logger.info(f"{interaction.user} ответил правильно на вопрос: {self.question['question']}")
            else:
                await interaction.response.send_message("❌ Неправильно.", ephemeral=True)
                logger.info(f"{interaction.user} ответил неправильно на вопрос: {self.question['question']}")
        return callback

class CategorySelect(Select):
    def __init__(self, categories, questions):
        options = [discord.SelectOption(label=cat.capitalize(), value=cat) for cat in categories]
        super().__init__(placeholder="Выберите категорию", min_values=1, max_values=1, options=options)
        self.questions = questions

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        filtered = [q for q in self.questions if q['category'].lower() == selected_category.lower()]
        if not filtered:
            await interaction.response.send_message(f"❌ В категории `{selected_category}` нет вопросов.", ephemeral=True)
            logger.warning(f"{interaction.user} выбрал пустую категорию: {selected_category}")
            return

        question = random.choice(filtered)
        options_text = "\n".join(f"{idx}. {opt}" for idx, opt in enumerate(question["options"], start=1))

        embed = discord.Embed(
            title="🧠 Вопрос Викторины",
            description=f"**Категория:** `{question['category']}`\n\n{question['question']}\n\n{options_text}",
            color=discord.Color.red()
        )
        embed.set_footer(text="Нажмите кнопку ниже, чтобы выбрать ответ.")
        avatar_url = CONFIG.get("AVATAR_URL")
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        view = QuizView(question)
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"{interaction.user} начал викторину в категории: {selected_category}")

class CategoryView(View):
    def __init__(self, categories, questions):
        super().__init__(timeout=60)
        self.add_item(CategorySelect(categories, questions))

class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="викторина", description="Выберите категорию для начала викторины")
    async def quiz(self, interaction: discord.Interaction):
        questions = await fetch_questions_from_supabase()
        if not questions:
            await interaction.response.send_message("❌ Вопросы не найдены или повреждены.", ephemeral=True)
            logger.error(f"{interaction.user} попытался запустить викторину, но вопросы не найдены")
            return

        categories = list({q['category'].lower() for q in questions})
        if not categories:
            await interaction.response.send_message("❌ Нет доступных категорий.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался запустить викторину, но категории отсутствуют")
            return

        embed = discord.Embed(
            title="🧠 Викторина",
            description="Пожалуйста, выберите категорию из меню ниже.",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, view=CategoryView(categories, questions), ephemeral=True)
        logger.info(f"{interaction.user} открыл меню выбора категории для викторины")

async def setup(bot: commands.Bot):
    await bot.add_cog(QuizCog(bot))
