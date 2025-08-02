import discord
from discord.ext import commands
from discord.ui import Button, View, Select
from discord import app_commands
import asyncio

from data import active_duels, save_active_duels, update_stats, load_data
from cogs.voting import VotingView  # твой внешний ког для голосований

# --- Основной класс дуэлей ---
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

        try:
            dm_embed = discord.Embed(
                title="📬 Тебя вызвали на дуэль!",
                description=(
                    f"Тебя вызвал на дуэль: **{challenger.display_name}**\n"
                    f"**Игра:** {game}\n"
                    f"**Время:** {time}\n"
                    f"Место дуэли: {duel_channel.mention}\n\n"
                    f"Прими или отклони вызов прямо в чате!"
                ),
                color=discord.Color.orange()
            )
            dm_embed.set_footer(text="Не забудь заглянуть в чат и принять решение ⚔️")
            await opponent.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.send(
                f"⚠️ {opponent.mention}, я не смог отправить тебе ЛС. Проверь настройки приватности.",
                ephemeral=True
            )

# --- Views и кнопки ---

class AcceptDuelView(View):
    def __init__(self, challenger, opponent, duel_channel, bot):
        super().__init__(timeout=None)
        self.challenger = challenger
        self.opponent = opponent
        self.duel_channel = duel_channel
        self.bot = bot
        self.add_item(self.AcceptButton(self))
        self.add_item(self.DeclineButton(self))

    class AcceptButton(Button):
        def __init__(self, parent):
            super().__init__(label="Принять", style=discord.ButtonStyle.success, emoji="✔️")
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            if interaction.user != self.parent.opponent:
                return await interaction.response.send_message("Только вызванный может принять вызов!", ephemeral=True)

            duel_id = f"{self.parent.challenger.id}-{self.parent.opponent.id}"
            active_duels[duel_id] = {
                "challenger_id": self.parent.challenger.id,
                "opponent_id": self.parent.opponent.id
            }
            await save_active_duels()

            await interaction.response.send_message(
                f"Дуэль принята! {self.parent.opponent.mention} против {self.parent.challenger.mention}!",
                ephemeral=False
            )

            embed = discord.Embed(
                title="⚔️ Голосование началось!",
                description=(f"Кто победит?\n\n🟥 {self.parent.challenger.mention}\n🟦 {self.parent.opponent.mention}"),
                color=discord.Color.gold()
            )

            webhook = await self.parent.duel_channel.create_webhook(name="Duel Voting")
            view = VotingView(
                challenger=self.parent.challenger,
                opponent=self.parent.opponent,
                webhook=webhook
            )
            await webhook.send(embed=embed, view=view)
            await webhook.delete()

    class DeclineButton(Button):
        def __init__(self, parent):
            super().__init__(label="Отклонить", style=discord.ButtonStyle.danger, emoji="✖️")
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            if interaction.user != self.parent.opponent:
                return await interaction.response.send_message("Только вызванный может отклонить вызов!", ephemeral=True)

            await interaction.response.send_message(
                f"{self.parent.opponent.mention} отклонил дуэль с {self.parent.challenger.mention}.",
                ephemeral=False
            )

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
            return await interaction.response.send_message("Только инициатор может выбрать дуэль.", ephemeral=True)

        duel_id = self.select.values[0]
        duel = active_duels.get(duel_id)
        if not duel:
            return await interaction.response.send_message("Дуэль не найдена.", ephemeral=True)

        guild = interaction.guild
        challenger = guild.get_member(duel["challenger_id"])
        opponent = guild.get_member(duel["opponent_id"])

        await interaction.response.send_message(
            f"Выбрана дуэль между {challenger.mention} и {opponent.mention}.\n"
            f"Кто победил?",
            view=WinnerButtonsView(duel_id),
            ephemeral=True
        )

class WinnerButtonsView(View):
    def __init__(self, duel_id):
        super().__init__(timeout=30)
        self.duel_id = duel_id
        duel = active_duels.get(duel_id)
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
                return await interaction.response.send_message("Дуэль уже завершена.", ephemeral=True)

            loser_id = duel["opponent_id"] if self.winner_id == duel["challenger_id"] else duel["challenger_id"]
            update_stats(self.winner_id, loser_id)
            await save_active_duels()

            winner = interaction.guild.get_member(self.winner_id)
            loser = interaction.guild.get_member(loser_id)

            await interaction.response.send_message(
                f"🎉 Победитель: {winner.mention if winner else self.winner_id}!\nПроигравший: {loser.mention if loser else loser_id}.",
                ephemeral=False
            )

# --- Загрузка и запуск ---

async def setup(bot: commands.Bot):
    await load_data()
    await bot.add_cog(Duel(bot))
