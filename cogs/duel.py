import discord
from discord.ext import commands
from discord.ui import Button, View, Select
from datetime import datetime
import asyncio

from data import active_duels, save_active_duels, update_stats, load_data, stats
from cogs.voting import VotingView  # внешний ког для голосований

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

        view = AcceptDuelView(challenger, opponent, duel_channel, self.bot, game, time)
        await ctx.send(embed=embed, view=view)

        # Отправляем ЛС вызванному игроку
        try:
            dm_embed = discord.Embed(
                title="📬 Тебя вызвали на дуэль!",
                description=(f"Тебя вызвал: **{challenger.display_name}**\n"
                             f"**Игра:** {game}\n"
                             f"**Время:** {time}\n"
                             f"Место дуэли: {duel_channel.mention}\n\n"
                             f"Прими или отклони вызов прямо в чате!"),
                color=discord.Color.orange()
            )
            dm_embed.set_footer(text="Не забудь заглянуть в чат и принять решение ⚔️")
            await opponent.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.send(f"⚠️ {opponent.mention}, я не смог отправить ЛС. Проверь настройки приватности.")

# --- Views и кнопки ---
class AcceptDuelView(View):
    def __init__(self, challenger, opponent, duel_channel, bot, game, time):
        super().__init__(timeout=None)
        self.challenger = challenger
        self.opponent = opponent
        self.duel_channel = duel_channel
        self.bot = bot
        self.game = game
        self.time = time

        self.add_item(self.AcceptButton(self))
        self.add_item(self.DeclineButton(self))

    class AcceptButton(Button):
        def __init__(self, parent_view):
            super().__init__(label="Принять", style=discord.ButtonStyle.success, emoji="✔️")
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            challenger = self.parent_view.challenger
            opponent = self.parent_view.opponent
            duel_channel = self.parent_view.duel_channel
            bot = self.parent_view.bot
            game = self.parent_view.game
            time = self.parent_view.time

            if interaction.user != opponent:
                return await interaction.response.send_message(
                    "Только вызванный может принять вызов!", ephemeral=True
                )

            duel_id = f"{challenger.display_name}-{opponent.display_name}"
            active_duels[duel_id] = {
                "player1": challenger.display_name,
                "player2": opponent.display_name,
                "game": game,
                "time": time,
                "status": "active",
                "start_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            }

            # Сохраняем дуэль в базе
            await save_active_duels(bot)

            await interaction.response.send_message(
                f"Дуэль принята! {opponent.mention} против {challenger.mention}!",
                ephemeral=False
            )

            embed = discord.Embed(
                title="⚔️ Голосование началось!",
                description=f"Кто победит?\n\n🟥 {challenger.mention}\n🟦 {opponent.mention}",
                color=discord.Color.gold()
            )

            view = VotingView(challenger, opponent, duel_channel, bot)
            await duel_channel.send(embed=embed, view=view)

    class DeclineButton(Button):
        def __init__(self, parent_view):
            super().__init__(label="Отклонить", style=discord.ButtonStyle.danger, emoji="✖️")
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            challenger = self.parent_view.challenger
            opponent = self.parent_view.opponent

            if interaction.user != opponent:
                return await interaction.response.send_message(
                    "Только вызванный может отклонить вызов!", ephemeral=True
                )

            await interaction.response.send_message(
                f"{opponent.mention} отклонил дуэль с {challenger.mention}.",
                ephemeral=False
            )

# --- Selection View для админов ---
class DuelSelectionView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.select = Select(placeholder="Выберите дуэль", min_values=1, max_values=1)
        guild = ctx.guild

        for duel_id, duel in active_duels.items():
            challenger_name = duel.get("player1")
            opponent_name = duel.get("player2")
            if not challenger_name or not opponent_name:
                continue
            challenger = discord.utils.get(guild.members, name=challenger_name)
            opponent = discord.utils.get(guild.members, name=opponent_name)
            label = f"{challenger.display_name if challenger else challenger_name} vs {opponent.display_name if opponent else opponent_name}"
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
        challenger_name = duel.get("player1")
        opponent_name = duel.get("player2")
        challenger = discord.utils.get(guild.members, name=challenger_name)
        opponent = discord.utils.get(guild.members, name=opponent_name)

        await interaction.response.send_message(
            f"Выбрана дуэль между {challenger.mention if challenger else challenger_name} и {opponent.mention if opponent else opponent_name}.\nКто победил?",
            view=WinnerButtonsView(duel_id, interaction.client),
            ephemeral=True
        )

# --- Кнопки выбора победителя ---
class WinnerButtonsView(View):
    def __init__(self, duel_id, bot):
        super().__init__(timeout=30)
        self.duel_id = duel_id
        self.bot = bot
        duel = active_duels.get(duel_id)
        if not duel:
            return

        self.player1 = duel.get("player1")
        self.player2 = duel.get("player2")

        self.add_item(self.WinnerButton(duel_id, self.player1, bot, label=f"Победил {self.player1} 🟥"))
        self.add_item(self.WinnerButton(duel_id, self.player2, bot, label=f"Победил {self.player2} 🟦"))

    class WinnerButton(Button):
        def __init__(self, duel_id, winner_name, bot, label):
            super().__init__(label=label, style=discord.ButtonStyle.success)
            self.duel_id = duel_id
            self.winner_name = winner_name
            self.bot = bot

        async def callback(self, interaction: discord.Interaction):
            duel = active_duels.pop(self.duel_id, None)
            if not duel:
                return await interaction.response.send_message("Дуэль уже завершена.", ephemeral=True)

            loser_name = duel["player2"] if self.winner_name == duel["player1"] else duel["player1"]

            update_stats(self.winner_name, loser_name)
            await save_active_duels(self.bot)

            # Получаем участников для упоминаний
            guild = interaction.guild
            winner_member = discord.utils.get(guild.members, name=self.winner_name)
            loser_member = discord.utils.get(guild.members, name=loser_name)

            await interaction.response.send_message(
                f"🎉 Победитель: {winner_member.mention if winner_member else self.winner_name}!\n"
                f"Проигравший: {loser_member.mention if loser_member else loser_name}.",
                ephemeral=False
            )

# --- Загрузка и запуск ---
async def setup(bot: commands.Bot):
    await load_data()
    await bot.add_cog(Duel(bot))