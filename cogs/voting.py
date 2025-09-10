import discord
from discord.ext import commands
from discord.ui import Button, View

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

    class VoteButton(Button):
        def __init__(self, label, member, vote_key):
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.member = member
            self.vote_key = vote_key

        async def callback(self, interaction: discord.Interaction):
            parent_view: VotingView = self.view
            if interaction.user.id in [parent_view.challenger.id, parent_view.opponent.id]:
                return await interaction.response.send_message(
                    "Вы не можете голосовать за свою дуэль!", ephemeral=True
                )

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
            else:
                await self.channel.send(embed=embed)
        except Exception as e:
            print(f"Ошибка при отправке итогов голосования: {e}")

class VotingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot: commands.Bot):
    await bot.add_cog(VotingCog(bot))
