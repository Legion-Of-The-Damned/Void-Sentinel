import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
from supabase import create_client, Client
from config import load_config

# --- Логгер для InfoCog ---
logger = logging.getLogger("Info")

CONFIG = load_config()

# --- Подключение к Supabase через конфиг ---
supabase: Client = create_client(CONFIG["SUPABASE_URL"], CONFIG["SUPABASE_KEY"])


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def load_categories_from_db(self):
        """Загружаем категории и их содержимое из таблицы Supabase 'server_info'"""
        try:
            response = supabase.table("server_info").select("*").execute()

            if not response.data:
                logger.error("Данные из Supabase пустые или не найдены")
                return {}

            categories = {}
            for row in response.data:
                # Если content хранится как JSON-строка
                if isinstance(row['content'], str):
                    try:
                        row['content'] = json.loads(row['content'])
                    except json.JSONDecodeError:
                        logger.warning(f"Невалидный JSON в категории '{row['category']}', используем как строку")
                        row['content'] = [row['content']]  # оборачиваем в список
                categories[row['category']] = row['content']

            logger.info("Данные с Supabase успешно загружены")
            return categories

        except Exception as e:
            logger.error(f"❌ Исключение при загрузке данных из Supabase: {e}")
            return {}

    @app_commands.command(
        name="информация_о_сервере",
        description="Показывает информацию о сервере с выбором категории"
    )
    async def server_info(self, interaction: discord.Interaction):
        categories = self.load_categories_from_db()
        if not categories:
            await interaction.response.send_message(
                "Ошибка загрузки данных из базы!", ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label=name, description=f"Показать {name}")
            for name in categories.keys()
        ]

        async def select_callback(select_interaction: discord.Interaction):
            if select_interaction.user != interaction.user:
                await select_interaction.response.send_message(
                    "Это меню не для тебя!", ephemeral=True
                )
                logger.warning(f"{select_interaction.user} попытался использовать чужое меню InfoCog")
                return

            selected_category = select.values[0]
            content = categories[selected_category]
            embed = discord.Embed(
                title=f"{selected_category} сервера",
                description="\n".join(content),
                color=discord.Color.red()
            )
            await select_interaction.response.edit_message(embed=embed)
            logger.info(f"{interaction.user} выбрал категорию '{selected_category}'")

        select = discord.ui.Select(placeholder="Выберите категорию", options=options)
        select.callback = select_callback

        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message(
            "Выберите категорию информации о сервере:", view=view
        )
        logger.info(f"{interaction.user} открыл меню информации о сервере")


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
