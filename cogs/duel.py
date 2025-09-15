import discord
from discord.ext import commands
from discord.ui import Button, View, Select
from discord import app_commands
import asyncio
import logging

from data import active_duels, save_active_duels, update_stats, load_data
from cogs.voting import VotingView

# --- Настройка логгера ---
logger = logging.getLogger("DuelCog")


class Duel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="дуэль", description="Вызвать пользователя на дуэль")
    async def duel(self, ctx: commands.Context, user: discord.Member, game: str, time: str):
        challenger = ctx.author
        opponent = user
        duel_channel = ctx.channel

        embed = discord.Embed(
            title="⚔️ Дуэль вызвана!",
            description=(f"{challenger.mention} вызвал {opponent.mention} на дуэль!\n"
                         f"**Игра**: {game}\n"
                         f"**Время**: {time}\n"
                         f"{opponent.mention}, примете ли вы вызов?"),
            color=discord.Color.dark_red()
        )

        view = AcceptDuelView(challenger, opponent, duel_channel, self.bot)
        await ctx.send(embed=embed, view=view)
        logger.info(f"{challenger} вызвал {opponent} на дуэль ({game} в {time}) в канале {duel_channel.name}")

        try:
            dm_embed = discord.Embed(
                title="📬 Тебя вызвали на дуэль!",
                description=(f"Тебя вызвал на дуэль: **{challenger.display_name}**\n"
                             f"**Игра:** {game}\n"
                             f"**Время:** {time}\n"
                             f"Место дуэли: {duel_channel.mention}\n\n"
                             f"Прими или отклони вызов прямо в чате!"),
                color=discord.Color.orange()
            )
            dm_embed.set_footer(text="Не забудь заглянуть в чат и принять решение ⚔️")
            await opponent.send(embed=dm_embed)
            logger.info(f"Отправлено ЛС {opponent} о дуэли с {challenger}")
        except discord.Forbidden:
            await ctx.send(f"⚠️ {opponent.mention}, я не смог отправить тебе ЛС. Проверь настройки приватности.")
            logger.warning(f"Не удалось отправить ЛС {opponent} о дуэли с {challenger}")


class AcceptDuelView(View):
    def __init__(self, challenger, opponent, duel_channel, bot, timeout=600):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.opponent = opponent
        self.duel_channel = duel_channel
        self.bot = bot

        self.add_item(self.AcceptButton(self))
        self.add_item(self.DeclineButton(self))

    class AcceptButton(Button):
        def __init__(self, duel_view):
            super().__init__(label="Принять", style=discord.ButtonStyle.success, emoji="✔️")
            self.duel_view = duel_view

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.duel_view.opponent.id:
                await interaction.response.send_message("Только вызванный может принять вызов!", ephemeral=True)
                logger.warning(f"{interaction.user} попытался принять чужую дуэль")
                return

            duel_id = f"{self.duel_view.challenger.id}-{self.duel_view.opponent.id}"
            active_duels[duel_id] = {
                "challenger_id": self.duel_view.challenger.id,
                "opponent_id": self.duel_view.opponent.id
            }
            await save_active_duels()
            logger.info(f"Дуэль принята: {self.duel_view.challenger} vs {self.duel_view.opponent} (ID {duel_id})")

            await interaction.response.send_message(
                f"Дуэль принята! {self.duel_view.opponent.mention} против {self.duel_view.challenger.mention}!",
                ephemeral=False
            )

            webhook = await self.duel_view.duel_channel.create_webhook(name="Duel Voting")
            view = VotingView(
                challenger=self.duel_view.challenger,
                opponent=self.duel_view.opponent,
                channel=self.duel_view.duel_channel,
                webhook=webhook
            )

            embed = discord.Embed(
                title="⚔️ Голосование началось!",
                description=f"Кто победит?\n🟥 {self.duel_view.challenger.mention}\n🟦 {self.duel_view.opponent.mention}",
                color=discord.Color.gold()
            )
            await webhook.send(embed=embed, view=view)
            logger.info(f"Создано голосование для дуэли {duel_id} через вебхук {webhook.id}")

    class DeclineButton(Button):
        def __init__(self, duel_view):
            super().__init__(label="Отклонить", style=discord.ButtonStyle.danger, emoji="✖️")
            self.duel_view = duel_view

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.duel_view.opponent.id:
                await interaction.response.send_message("Только вызванный может отклонить вызов!", ephemeral=True)
                logger.warning(f"{interaction.user} попытался отклонить чужую дуэль")
                return

            await interaction.response.send_message(
                f"{self.duel_view.opponent.mention} отклонил дуэль с {self.duel_view.challenger.mention}.",
                ephemeral=False
            )
            logger.info(f"{self.duel_view.opponent} отклонил дуэль с {self.duel_view.challenger}")


class DuelSelectionView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.select = Select(placeholder="Выберите дуэль", min_values=1, max_values=1)
        for duel_id, duel in active_duels.items():
            guild = ctx.guild
            challenger = guild.get_member(duel["challenger_id"])
            opponent = guild.get_member(duel["opponent_id"])
            if challenger and opponent:
                label = f"{challenger.display_name} vs {opponent.display_name}"
                self.select.add_option(label=label, value=duel_id)
        self.select.callback = self.duel_selected
        self.add_item(self.select)

    async def duel_selected(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Только инициатор может выбрать дуэль.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался выбрать чужую дуэль")
            return

        duel_id = self.select.values[0]
        duel = active_duels.get(duel_id)
        if not duel:
            await interaction.response.send_message("Дуэль не найдена.", ephemeral=True)
            logger.warning(f"Выбор несуществующей дуэли ID {duel_id}")
            return

        guild = interaction.guild
        challenger = guild.get_member(duel["challenger_id"])
        opponent = guild.get_member(duel["opponent_id"])
        if not challenger or not opponent:
            await interaction.response.send_message("Один из участников больше не в сервере.", ephemeral=True)
            logger.warning(f"Один из участников дуэли {duel_id} отсутствует на сервере")
            return

        await interaction.response.send_message(
            f"Выбрана дуэль между {challenger.mention} и {opponent.mention}.\nКто победил?",
            view=WinnerButtonsView(duel_id),
            ephemeral=True
        )
        logger.info(f"Дуэль {duel_id} выбрана для назначения победителя")


class WinnerButtonsView(View):
    def __init__(self, duel_id):
        super().__init__(timeout=30)
        self.duel_id = duel_id
        duel = active_duels.get(duel_id)
        if not duel:
            return
        self.challenger_id = duel["challenger_id"]
        self.opponent_id = duel["opponent_id"]

        self.add_item(self.WinnerButton(duel_id, self.challenger_id, label="Победил Challenger 🟥"))
        self.add_item(self.WinnerButton(duel_id, self.opponent_id, label="Победил Opponent 🟦"))

    class WinnerButton(Button):
        def __init__(self, duel_id, winner_id, label):
            super().__init__(label=label, style=discord.ButtonStyle.success)
            self.duel_id = duel_id
            self.winner_id = winner_id

        async def callback(self, interaction: discord.Interaction):
            duel = active_duels.pop(self.duel_id, None)
            if not duel:
                await interaction.response.send_message("Дуэль уже завершена.", ephemeral=True)
                logger.warning(f"Попытка завершить уже завершённую дуэль {self.duel_id}")
                return

            loser_id = duel["opponent_id"] if self.winner_id == duel["challenger_id"] else duel["challenger_id"]
            update_stats(self.winner_id, loser_id)
            await save_active_duels()

            winner = interaction.guild.get_member(self.winner_id)
            loser = interaction.guild.get_member(loser_id)

            await interaction.response.send_message(
                f"🎉 Победитель: {winner.mention if winner else self.winner_id}!\nПроигравший: {loser.mention if loser else loser_id}.",
                ephemeral=False
            )
            logger.success(f"Дуэль {self.duel_id} завершена: Победитель {winner}, Проигравший {loser}")


async def setup(bot: commands.Bot):
    await load_data()
    await bot.add_cog(Duel(bot))
