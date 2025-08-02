import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
import random
import aiohttp
import json
from config import load_config

CONFIG = load_config()

async def fetch_questions_from_github():
    url = f"https://raw.githubusercontent.com/{CONFIG['REPO_NAME']}/main/{CONFIG['QUIZ_QUESTIONS_PATH']}"
    headers = {}
    if CONFIG.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {CONFIG['GITHUB_TOKEN']}"
        headers["Accept"] = "application/vnd.github.v3.raw"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            raw_text = await resp.text()
            if resp.status == 200:
                try:
                    data = json.loads(raw_text)
                    # Проверяем, что каждый вопрос содержит нужные поля
                    return [q for q in data if all(k in q for k in ("category", "question", "options", "answer"))]
                except json.JSONDecodeError:
                    print("❌ Ошибка при разборе JSON.")
                    return []
            else:
                print(f"Ошибка загрузки с GitHub: {resp.status}")
                return []

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
            else:
                await interaction.response.send_message("❌ Неправильно.", ephemeral=True)
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
            return

        question = random.choice(filtered)
        options_text = "\n".join(f"{idx}. {opt}" for idx, opt in enumerate(question["options"], start=1))

        embed = discord.Embed(
            title="🧠 Вопрос Викторины",
            description=f"**Категория:** `{question['category']}`\n\n{question['question']}\n\n{options_text}",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Нажмите кнопку ниже, чтобы выбрать ответ.")
        avatar_url = CONFIG.get("AVATAR_URL")
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        view = QuizView(question)
        await interaction.response.send_message(embed=embed, view=view)

class CategoryView(View):
    def __init__(self, categories, questions):
        super().__init__(timeout=60)
        self.add_item(CategorySelect(categories, questions))

class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="викторина", description="Выберите категорию для начала викторины")
    async def quiz(self, interaction: discord.Interaction):
        questions = await fetch_questions_from_github()
        if not questions:
            await interaction.response.send_message("❌ Вопросы не найдены или повреждены.", ephemeral=True)
            return

        categories = list({q['category'].lower() for q in questions})
        if not categories:
            await interaction.response.send_message("❌ Нет доступных категорий.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🧠 Викторина",
            description="Пожалуйста, выберите категорию из меню ниже.",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, view=CategoryView(categories, questions), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(QuizCog(bot))
