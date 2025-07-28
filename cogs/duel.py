import discord
from discord.ext import commands
from discord.ui import Button, View, Select
from discord import app_commands
import json
import base64
import asyncio
from github import Github

# --- GitHub настройки ---
GITHUB_TOKEN = "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"
REPO_NAME = "Legion-Of-The-Damned/duel-stats-public"  # замените на свой репозиторий

# Инициализация GitHub
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# --- Асинхронные функции для работы с GitHub ---

def load_github_json(filename):
    try:
        contents = repo.get_contents(filename)
        decoded = base64.b64decode(contents.content).decode("utf-8")
        return json.loads(decoded)
    except Exception as e:
        print(f"Ошибка загрузки {filename}: {e}")
        return {}

def save_github_json(filename, data, commit_message="Обновление данных"):
    json_data = json.dumps(data, indent=4, ensure_ascii=False)
    try:
        # Получаем актуальный sha непосредственно перед обновлением
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, commit_message, json_data, contents.sha)
    except Exception as e:
        # Если файл не найден — создаём
        if "404" in str(e) or "Not Found" in str(e):
            try:
                repo.create_file(filename, commit_message, json_data)
            except Exception as err:
                print(f"Ошибка создания файла {filename}: {err}")
        # Если конфликт — попробуем повторить обновление после повторного получения sha
        elif "409" in str(e):
            try:
                contents = repo.get_contents(filename)  # заново получить
                repo.update_file(contents.path, commit_message, json_data, contents.sha)
            except Exception as err:
                print(f"Ошибка повторного обновления {filename}: {err}")
        else:
            print(f"Ошибка сохранения {filename}: {e}")

async def async_load_json(filename):
    return await asyncio.to_thread(load_github_json, filename)

async def async_save_json(filename, data, commit_message="Обновление данных"):
    await asyncio.to_thread(save_github_json, filename, data, commit_message)

# --- Глобальные данные ---
active_duels = {}
stats = {}

# --- Функции загрузки и сохранения ---
async def load_data():
    global active_duels, stats
    active_duels = await async_load_json("active_duels.json")
    stats = await async_load_json("duel_stats.json")

async def save_active_duels():
    await async_save_json("active_duels.json", active_duels, "Обновление активных дуэлей")

async def save_stats():
    await async_save_json("duel_stats.json", stats, "Обновление статистики дуэлей")

def update_stats(winner_id, loser_id):
    global stats
    for user_id in (str(winner_id), str(loser_id)):
        if user_id not in stats:
            stats[user_id] = {"wins": 0, "losses": 0}
    stats[str(winner_id)]["wins"] += 1
    stats[str(loser_id)]["losses"] += 1
    # Сохраняем асинхронно — без await, чтобы не блокировать
    asyncio.create_task(save_stats())

# --- Вспомогательная функция для упоминания по ID ---
def mention_user(user_id):
    return f"<@{user_id}>"

# --- Основной класс дуэлей ---
class Duel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="победа", description="Выбрать дуэль и присудить победу (только для админов)")
    async def assign_winner_select(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.kick_members:
            return await ctx.send("❌ У вас нет прав для назначения победителя. Необходимы права на кик участников.", ephemeral=True)

        if not active_duels:
            return await ctx.send("Нет активных дуэлей.", ephemeral=True)

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
    async def stats_command(self, ctx: commands.Context, user: discord.Member):
        user_stats = stats.get(str(user.id), {"wins": 0, "losses": 0})
        await ctx.send(
            f"📊 Статистика {user.mention}:\n"
            f"Победы: {user_stats['wins']}\n"
            f"Поражения: {user_stats['losses']}"
        )

    @app_commands.command(name="общая_статистика", description="Показать статистику по всем участникам")
    async def all_stats(self, interaction: discord.Interaction):
        if not stats:
            await interaction.response.send_message("📉 Пока нет данных о боях.")
            return

        guild = interaction.guild
        stats_list = []
        for user_id_str, data in stats.items():
            user_id = int(user_id_str)
            member = guild.get_member(user_id)
            name = member.display_name if member else f"Пользователь {user_id}"
            wins = data.get("wins", 0)
            losses = data.get("losses", 0)
            total = wins + losses
            stats_list.append((name, wins, losses, total))

        stats_list.sort(key=lambda x: x[1], reverse=True)

        lines = ["**🏆 Общая статистика дуэлей:**\n"]
        for i, (name, wins, losses, total) in enumerate(stats_list, 1):
            lines.append(f"{i}. **{name}** — 🟢 Побед: {wins}, 🔴 Поражений: {losses}, ⚔ Всего: {total}")

        embed = discord.Embed(
            title="📊 Статистика дуэлей",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Запрошено: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

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
            # Сохраняем ID участников, а не объекты Discord
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
            pass

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
            # Нужно получить объекты участников по ID, если они онлайн на сервере
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
        guild = None
        # Тут предполагается, что будет вызван из контекста гильдии
        # Но т.к. у нас только duel_id, оставим это так
        # Для безопасности лучше передать объекты участников прямо в конструктор
        self.challenger_id = duel["challenger_id"]
        self.opponent_id = duel["opponent_id"]

        # Добавим кнопки с метками
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
