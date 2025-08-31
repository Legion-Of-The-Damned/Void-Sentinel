import discord
from discord.ext import commands
from discord.ui import Button, View

def mention_user(user_id):
    return f"<@{user_id}>"

class VotingView(View):
    def __init__(self, challenger, opponent, webhook, timeout=60):
        super().__init__(timeout=timeout)
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

        if self.webhook:
            try:
                await self.webhook.send(embed=embed)
            except discord.NotFound:
                print("Webhook не найден при отправке итогов голосования.")
            except Exception as e:
                print(f"Ошибка при отправке итогов голосования: {e}")

            try:
                await self.webhook.delete()
            except discord.NotFound:
                print("Webhook не найден при попытке удаления.")
            except Exception as e:
                print(f"Ошибка при удалении webhook: {e}")

class VotingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Можно добавить команды голосования сюда, если потребуется

async def setup(bot: commands.Bot):
    await bot.add_cog(VotingCog(bot))
