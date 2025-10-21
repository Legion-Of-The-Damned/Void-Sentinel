import discord
from discord.ext import commands
from discord.ui import Button, View
import logging

logger = logging.getLogger("Voting")

def mention_user(user_id):
    return f"<@{user_id}>"

class VotingView(View):
    def __init__(self, challenger, opponent, channel, bot, timeout=60):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.opponent = opponent
        self.channel = channel
        self.bot = bot
        self.votes = {"challenger": 0, "opponent": 0}
        self.voters = {}  # user_id -> "challenger"/"opponent"

        # Кнопки голосования
        self.add_item(self.VoteButton(f"🟥 Голосовать за {challenger.display_name}", challenger, "challenger"))
        self.add_item(self.VoteButton(f"🟦 Голосовать за {opponent.display_name}", opponent, "opponent"))

        logger.info(f"💠 Создано голосование: {challenger} vs {opponent} в канале {channel}")

    class VoteButton(Button):
        def __init__(self, label, member, vote_key):
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.member = member
            self.vote_key = vote_key

        async def callback(self, interaction: discord.Interaction):
            view: VotingView = self.view
            user_id = interaction.user.id

            # Проверка: нельзя голосовать за свою дуэль
            if user_id in [view.challenger.id, view.opponent.id]:
                await interaction.response.send_message("❌ Вы не можете голосовать за свою дуэль!", ephemeral=True)
                logger.warning(f"{interaction.user} попытался проголосовать за свою дуэль")
                return

            # Проверка: нельзя голосовать дважды
            if user_id in view.voters:
                await interaction.response.send_message("❌ Вы уже проголосовали!", ephemeral=True)
                logger.warning(f"{interaction.user} попытался проголосовать повторно")
                return

            # Считаем голос
            view.voters[user_id] = self.vote_key
            view.votes[self.vote_key] += 1

            await interaction.response.send_message(f"✅ Вы проголосовали за {self.member.mention}!", ephemeral=True)
            logger.info(f"{interaction.user} проголосовал за {self.member} ({self.vote_key})")
            logger.debug(f"Текущие голоса: {view.votes}, текущие участники: {view.voters}")

    async def on_timeout(self):
        # Определяем победителя
        if self.votes["challenger"] > self.votes["opponent"]:
            winner = self.challenger
        elif self.votes["challenger"] < self.votes["opponent"]:
            winner = self.opponent
        else:
            winner = None  # ничья

        embed = discord.Embed(
            title="⚔️ Итоги голосования",
            description=f"Победитель голосования: {winner.mention}!" if winner else "Ничья! Голоса разделились поровну.",
            color=discord.Color.green()
        )

        # Списки проголосовавших
        challenger_voters = [mention_user(uid) for uid, vote in self.voters.items() if vote == "challenger"]
        opponent_voters = [mention_user(uid) for uid, vote in self.voters.items() if vote == "opponent"]

        embed.add_field(name=f"🟥 За {self.challenger.display_name}", value="\n".join(challenger_voters) or "Нет", inline=True)
        embed.add_field(name=f"🟦 За {self.opponent.display_name}", value="\n".join(opponent_voters) or "Нет", inline=True)

        # Пытаемся отправить через временный webhook
        try:
            webhook = await self.channel.create_webhook(name="Duel Voting Result")
            await webhook.send(embed=embed, username=self.bot.user.name, avatar_url=self.bot.user.avatar.url)
            await webhook.delete()
            logger.info(f"Итоги голосования отправлены через webhook для дуэли {self.challenger} vs {self.opponent}")
        except Exception as e:
            logger.error(f"Ошибка при отправке итогов через webhook: {e}")
            # fallback: отправка обычным сообщением
            await self.channel.send(embed=embed)
            logger.info(f"Итоги голосования отправлены в канал {self.channel} (без webhook)")

# --- Ког для команды start_vote ---
class VotingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="start_vote")
    async def start_vote(self, ctx, challenger: discord.Member, opponent: discord.Member):
        view = VotingView(challenger, opponent, ctx.channel, self.bot)
        await ctx.send(f"⚔️ Голосование между {challenger.mention} и {opponent.mention} началось!", view=view)
        logger.info(f"Голосование запущено пользователем {ctx.author} для {challenger} vs {opponent}")

# --- Загрузка когов ---
async def setup(bot: commands.Bot):
    await bot.add_cog(VotingCog(bot))