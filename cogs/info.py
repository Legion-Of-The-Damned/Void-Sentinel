# cogs/info.py
import discord
from discord import app_commands
from discord.ext import commands
import requests
import json
from base64 import b64decode
from config import load_config
import logging

# --- Логгер для InfoCog ---
logger = logging.getLogger("InfoCog")

CONFIG = load_config()

GITHUB_API_URL = f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/contents/server_info.json"
HEADERS = {"Authorization": f"token {CONFIG['GITHUB_TOKEN']}"}


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def load_categories_from_github(self):
        """Загружаем JSON с категориями и их содержимым из GitHub."""
        try:
            response = requests.get(GITHUB_API_URL, headers=HEADERS)
            if response.status_code != 200:
                logger.error(f"Ошибка загрузки данных с GitHub: статус {response.status_code}")
                return {}
            data = response.json()
            content = b64decode(data['content']).decode('utf-8')
            logger.info("Данные с GitHub успешно загружены")
            return json.loads(content)
        except Exception as e:
            logger.error(f"❌ Исключение при загрузке данных с GitHub: {e}")
            return {}

    @app_commands.command(name="информация_о_сервере", description="Показывает информацию о сервере с выбором категории")
    async def server_info(self, interaction: discord.Interaction):
        categories = self.load_categories_from_github()
        if not categories:
            await interaction.response.send_message("Ошибка загрузки данных с GitHub!", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=name, description=f"Показать {name}")
            for name in categories.keys()
        ]

        async def select_callback(select_interaction: discord.Interaction):
            if select_interaction.user != interaction.user:
                await select_interaction.response.send_message("Это меню не для тебя!", ephemeral=True)
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

        await interaction.response.send_message("Выберите категорию информации о сервере:", view=view)
        logger.info(f"{interaction.user} открыл меню информации о сервере")


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))