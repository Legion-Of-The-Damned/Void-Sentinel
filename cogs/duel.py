import discord
from discord.ext import commands
from discord.ui import Button, View
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

    @commands.hybrid_command(name="победа", description="Присудить победу участнику дуэли")
    async def assign_winner(self, ctx: commands.Context, winner: discord.Member):
        duel_id = next((k for k, v in active_duels.items() if winner.id in (v["challenger"].id, v["opponent"].id)), None)
        if not duel_id:
            return await ctx.send("Этот участник не участвовал в активной дуэли.")

        duel = active_duels.pop(duel_id)
        loser = duel["opponent"] if winner == duel["challenger"] else duel["challenger"]
        update_stats(winner.id, loser.id)

        await ctx.send(f"🎉 Победитель дуэли: {winner.mention}! Проигравший: {loser.mention}.")

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

        await self.webhook.send(embed=embed)

def mention_user(user_id):
    return f"<@{user_id}>"

async def setup(bot: commands.Bot):
    await bot.add_cog(Duel(bot))
