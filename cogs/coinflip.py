import discord
import logging
from discord.ext import commands
import random

# --- Настройка логгера ---
logger = logging.getLogger("CoinFlipCog")


class CoinFlipButton(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, bot, play_vs_bot=False, timeout=30):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.opponent = opponent
        self.bot = bot
        self.choices = {}
        self.play_vs_bot = play_vs_bot
        self.result_msg = None
        logger.info(f"Создана игра Монетка: {challenger} vs {opponent}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.challenger.id:
            await interaction.response.send_message("❌ Только инициатор игры может делать выбор.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Орёл", style=discord.ButtonStyle.primary, emoji="🦅")
    async def eagle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "орёл")

    @discord.ui.button(label="Решка", style=discord.ButtonStyle.secondary, emoji="💰")
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "решка")

    async def make_choice(self, interaction: discord.Interaction, choice: str):
        if self.challenger.id in self.choices:
            await interaction.response.send_message("❗ Ты уже сделал выбор.", ephemeral=True)
            logger.warning(f"{interaction.user} попытался выбрать {choice} повторно")
            return

        self.choices[self.challenger.id] = choice
        await interaction.response.send_message(f"✅ Ты выбрал: **{choice}**", ephemeral=True)
        logger.info(f"{interaction.user} выбрал {choice}")

        if self.play_vs_bot:
            self.choices[self.bot.user.id] = "решка" if choice == "орёл" else "орёл"
            logger.info(f"{self.bot.user} автоматически выбрал {self.choices[self.bot.user.id]}")
            await self.reveal_result()
        else:
            await interaction.followup.send(f"Ожидаем выбор от {self.opponent.mention}...", ephemeral=True)

    async def reveal_result(self):
        result = random.choice(["орёл", "решка"])
        result_emoji = "🦅" if result == "орёл" else "💰"

        winner = None
        if self.choices.get(self.challenger.id) != self.choices.get(self.opponent.id):
            for user_id, choice in self.choices.items():
                if choice == result:
                    winner = user_id
                    break

        description = f"🪙 Монета подброшена... Выпало: **{result.upper()}** {result_emoji}\n\n"
        if winner:
            if winner == self.challenger.id:
                description += f"🎉 Побеждает {self.challenger.mention}!"
                logger.success(f"{self.challenger} победил в игре Монетка ({result})")
            elif winner == self.bot.user.id:
                description += f"🤖 Побеждает {self.bot.user.mention}!"
                logger.success(f"{self.bot.user} победил в игре Монетка ({result})")
            else:
                description += f"🎉 Победил <@{winner}>!"
                logger.success(f"Победитель ID {winner} в игре Монетка ({result})")
        else:
            description += "⚖️ Ничья! У обоих одинаковый выбор."
            logger.info(f"Ничья в игре Монетка: результат {result}")

        embed = discord.Embed(title="🎲 Монетка: Орёл или Решка", description=description, color=0xFFD700)
        for child in self.children:
            child.disabled = True
        try:
            await self.result_msg.edit(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Ошибка при отправке результата броска: {e}")


class CoinFlip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="монетка", description="Вызвать игрока или бота на Орёл или Решка!")
    async def coinflip(self, ctx: commands.Context, opponent: discord.Member = None):
        opponent = opponent or self.bot.user

        if opponent.id == ctx.author.id:
            await ctx.send("❌ Нельзя играть с самим собой.")
            logger.warning(f"{ctx.author} попытался сыграть с самим собой")
            return

        play_vs_bot = opponent.bot
        view = CoinFlipButton(ctx.author, opponent, self.bot, play_vs_bot=play_vs_bot)

        title = "🪙 Монетка: Орёл или Решка!"
        if play_vs_bot:
            description = (
                f"{ctx.author.mention} бросает вызов {self.bot.user.mention}!\n\n"
                f"Выбери сторону монеты. Побеждает тот, чья сторона выпадет!"
            )
        else:
            description = (
                f"{ctx.author.mention} вызвал {opponent.mention} на бросок монеты!\n\n"
                f"Оба игрока должны выбрать сторону.\n"
                f"Побеждает тот, чья сторона выпадет!"
            )

        embed = discord.Embed(title=title, description=description, color=0x00BFFF)
        msg = await ctx.send(embed=embed, view=view)
        view.result_msg = msg
        logger.info(f"Игра создана: {ctx.author} vs {opponent}, сообщение {msg.id}")


async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
