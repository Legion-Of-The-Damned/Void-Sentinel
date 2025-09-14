import discord
from discord.ext import commands
from discord.ui import Button, View
import logging

logger = logging.getLogger("VotingCog")

def mention_user(user_id):
    return f"<@{user_id}>"

class VotingView(View):
    def __init__(self, challenger, opponent, channel, webhook=None, timeout=60):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.opponent = opponent
        self.votes = {"challenger": 0, "opponent": 0}
        self.voters = {}
        self.webhook = webhook
        self.channel = channel

        self.add_item(self.VoteButton("🟥 Голосовать за", self.challenger, "challenger"))
        self.add_item(self.VoteButton("🟦 Голосовать за", self.opponent, "opponent"))

        logger.info(f"💠 Создано голосование между {self.challenger} и {self.opponent} в канале {self.channel}")

    class VoteButton(Button):
        def __init__(self, label, member, vote_key):
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.member = member
            self.vote_key = vote_key

        async def callback(self, interaction: discord.Interaction):
            parent_view: VotingView = self.view
            user_id = interaction.user.id

            if user_id in [parent_view.challenger.id, parent_view.opponent.id]:
                await interaction.response.send_message(
                    "Вы не можете голосовать за свою дуэль!", ephemeral=True
                )
                logger.warning(f"{interaction.user} попытался проголосовать за свою дуэль")
                return

            if user_id in parent_view.voters:
                await interaction.response.send_message("Вы уже проголосовали!", ephemeral=True)
                logger.warning(f"{interaction.user} попытался проголосовать повторно")
                return

            parent_view.voters[user_id] = self.vote_key
            parent_view.votes[self.vote_key] += 1
            await interaction.response.send_message(
                f"Вы проголосовали за {self.member.mention}!", ephemeral=True
            )
            logger.success(f"{interaction.user} проголосовал за {self.member} ({self.vote_key})")
            logger.debug(f"Текущие голоса: {parent_view.votes}, Текущие участники: {parent_view.voters}")

    async def on_timeout(self):
        winner = (
            self.challenger if self.votes["challenger"] > self.votes["opponent"]
            else self.opponent if self.votes["challenger"] < self.votes["opponent"]
            else None
        )

        embed = discord.Embed(
            title="⚔️ Итоги голосования",
            description=f"Победитель голосования: {winner.mention}!" if winner else "Ничья! Голоса разделились поровну.",
            color=discord.Color.green()
        )

        challenger_voters = [mention_user(uid) for uid, vote in self.voters.items() if vote == "challenger"]
        opponent_voters = [mention_user(uid) for uid, vote in self.voters.items() if vote == "opponent"]

        embed.add_field(name="🟥 За", value="\n".join(challenger_voters) or "Нет", inline=True)
        embed.add_field(name="🟦 За", value="\n".join(opponent_voters) or "Нет", inline=True)

        try:
            if self.webhook:
                await self.webhook.send(embed=embed)
                await self.webhook.delete()
                logger.success(f"Итоги голосования отправлены через webhook для дуэли {self.challenger} vs {self.opponent}")
            else:
                await self.channel.send(embed=embed)
                logger.success(f"Итоги голосования отправлены в канал {self.channel} для дуэли {self.challenger} vs {self.opponent}")
        except Exception as e:
            logger.error(f"Ошибка при отправке итогов голосования: {e}")

class VotingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="start_vote")
    async def start_vote(self, ctx, challenger: discord.Member, opponent: discord.Member):
        view = VotingView(challenger, opponent, ctx.channel)
        await ctx.send(f"⚔️ Голосование между {challenger.mention} и {opponent.mention} началось!", view=view)
        logger.success(f"Голосование запущено пользователем {ctx.author} для {challenger} vs {opponent}")

async def setup(bot: commands.Bot):
    await bot.add_cog(VotingCog(bot))
