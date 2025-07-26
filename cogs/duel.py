import discord
from discord.ext import commands
from discord.ui import Button, View, Select
from discord import app_commands
import json
import os

STATS_FILE = "duel_stats.json"
active_duels = {}

def load_stats():
    if not os.path.exists(STATS_FILE):
        with open(STATS_FILE, "w") as file:
            json.dump({}, file)
    with open(STATS_FILE, "r") as file:
        return json.load(file)

def save_stats(stats):
    with open(STATS_FILE, "w") as file:
        json.dump(stats, file, indent=4)

def update_stats(winner_id, loser_id):
    stats = load_stats()
    for user_id in (str(winner_id), str(loser_id)):
        if user_id not in stats:
            stats[user_id] = {"wins": 0, "losses": 0}
    stats[str(winner_id)]["wins"] += 1
    stats[str(loser_id)]["losses"] += 1
    save_stats(stats)

class Duel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="победа", description="Выбрать дуэль и присудить победу (только для админов)")
    async def assign_winner_select(self, ctx: commands.Context):
    # Проверка на право кикать участников
        if not ctx.author.guild_permissions.kick_members:
            return await ctx.send("❌ У вас нет прав для назначения победителя. Необходимы права на кик участников.", ephemeral=True)

        if not active_duels:
            return await ctx.send("Нет активных дуэлей.")

        view = DuelSelectionView(ctx)
        await ctx.send("Выберите дуэль, чтобы назначить победителя:", view=view, ephemeral=True)

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

        # 📨 Попытка отправить ЛС вызванному
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

    @commands.hybrid_command(name="статистика", description="Показать статистику участника")
    async def stats(self, ctx: commands.Context, user: discord.Member):
        stats = load_stats()
        user_stats = stats.get(str(user.id), {"wins": 0, "losses": 0})
        await ctx.send(
            f"📊 Статистика {user.mention}:\n"
            f"Победы: {user_stats['wins']}\n"
            f"Поражения: {user_stats['losses']}"
        )

    @app_commands.command(name="общая_статистика", description="Показать статистику по всем участникам")
    async def all_stats(self, interaction: discord.Interaction):
        stats_data = load_stats()
        if not stats_data:
            await interaction.response.send_message("📉 Пока нет данных о боях.")
            return

        guild = interaction.guild
        stats_list = []
        for user_id_str, stats in stats_data.items():
            user_id = int(user_id_str)
            member = guild.get_member(user_id)
            name = member.display_name if member else f"Пользователь {user_id}"
            wins = stats.get("wins", 0)
            losses = stats.get("losses", 0)
            total = wins + losses
            stats_list.append((name, wins, losses, total))

        stats_list.sort(key=lambda x: x[1], reverse=True)

        lines = ["**🏆 Общая статистика дуэлей:**\n"]
        for i, (name, wins, losses, total) in enumerate(stats_list, start=1):
            lines.append(f"`{i}.` **{name}** — 🟢 Побед: `{wins}`, 🔴 Поражений: `{losses}`, ⚔ Всего: `{total}`")

        embed = discord.Embed(
            title="📊 Статистика дуэлей",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Запрошено: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

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
                "challenger": self.parent.challenger,
                "opponent": self.parent.opponent
            }

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
            await webhook.send(embed=embed, view=view, avatar_url=self.parent.challenger.avatar.url)
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

class VotingView(View):
    def __init__(self, challenger, opponent, webhook):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.votes = {"challenger": 0, "opponent": 0}
        self.voters = {}
        self.webhook = webhook

        self.add_item(self.VoteButton("🟥 Голосовать за", self.challenger, "challenger"))
        self.add_item(self.VoteButton("🟦 Голосовать за", self.opponent, "opponent"))

    class VoteButton(Button):
        def __init__(self, label, member, vote_key):
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.member = member
            self.vote_key = vote_key

        async def callback(self, interaction: discord.Interaction):
            parent_view: VotingView = self.view
            if interaction.user.bot:
                return await interaction.response.defer()

            if interaction.user in [parent_view.challenger, parent_view.opponent]:
                return await interaction.response.send_message("Вы не можете голосовать в своей дуэли!", ephemeral=True)

            if interaction.user.id in parent_view.voters:
                return await interaction.response.send_message("Вы уже проголосовали!", ephemeral=True)

            parent_view.voters[interaction.user.id] = self.vote_key
            parent_view.votes[self.vote_key] += 1
            await interaction.response.send_message(f"Вы проголосовали за {self.member.mention}!", ephemeral=True)

    async def on_timeout(self):
        winner = (
            self.challenger if self.votes["challenger"] > self.votes["opponent"]
            else self.opponent if self.votes["challenger"] < self.votes["opponent"]
            else None
        )

        embed = discord.Embed(
            title="⚔️ Итоги голосования",
            description=(f"Победитель голосования: {winner.mention}!" if winner else "Ничья! Голоса разделились поровну."),
            color=discord.Color.green()
        )

        challenger_voters = [mention_user(uid) for uid, vote in self.voters.items() if vote == "challenger"]
        opponent_voters = [mention_user(uid) for uid, vote in self.voters.items() if vote == "opponent"]

        embed.add_field(name="🟥 За", value="\n".join(challenger_voters) or "Нет", inline=True)
        embed.add_field(name="🟦 За", value="\n".join(opponent_voters) or "Нет", inline=True)

        try:
            await self.webhook.send(embed=embed)
        except discord.NotFound:
            pass  # Вебхук уже удалён или недоступен

        try:
            await self.webhook.delete()
        except discord.NotFound:
            pass

class DuelSelectionView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.select = Select(placeholder="Выберите дуэль", min_values=1, max_values=1)
        for duel_id, duel in active_duels.items():
            challenger = duel["challenger"]
            opponent = duel["opponent"]
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

        await interaction.response.send_message(
            f"Выбрана дуэль между {duel['challenger'].mention} и {duel['opponent'].mention}.\n"
            f"Кто победил?",
            view=WinnerButtonsView(duel_id),
            ephemeral=True
        )

class WinnerButtonsView(View):
    def __init__(self, duel_id):
        super().__init__(timeout=30)
        self.duel_id = duel_id
        duel = active_duels.get(duel_id)
        self.add_item(self.WinnerButton(duel_id, duel["challenger"], label="Победил Challenger 🟥"))
        self.add_item(self.WinnerButton(duel_id, duel["opponent"], label="Победил Opponent 🟦"))

    class WinnerButton(Button):
        def __init__(self, duel_id, winner, label):
            super().__init__(label=label, style=discord.ButtonStyle.success)
            self.duel_id = duel_id
            self.winner = winner

        async def callback(self, interaction: discord.Interaction):
            duel = active_duels.pop(self.duel_id, None)
            if not duel:
                return await interaction.response.send_message("Дуэль уже завершена.", ephemeral=True)

            loser = duel["opponent"] if self.winner == duel["challenger"] else duel["challenger"]
            update_stats(self.winner.id, loser.id)

            await interaction.response.send_message(
                f"🎉 Победитель: {self.winner.mention}!\nПроигравший: {loser.mention}.",
                ephemeral=False
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Duel(bot))
