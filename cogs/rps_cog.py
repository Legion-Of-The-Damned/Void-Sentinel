import random
import asyncio
import logging
import uuid
import discord
from discord.ext import commands
from discord.ui import View, Button
from data import active_duels, save_active_duels, update_stats

# === Константы ===
MAX_PLAYERS = 5
CHOICES = ["камень", "ножницы", "бумага"]
BEATS = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}

logger = logging.getLogger("RPSCog")
duel_lock = asyncio.Lock()


# === Ког с командой ===
class RPSCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="камень-ножницы-бумага",
        description="Вызвать до 4 игроков на камень, ножницы, бумага"
    )
    async def rps(
        self,
        ctx: commands.Context,
        user1: discord.Member,
        user2: discord.Member = None,
        user3: discord.Member = None,
        user4: discord.Member = None
    ):
        challenger = ctx.author
        participants = [challenger, user1]

        for user in (user2, user3, user4):
            if user and user not in participants:
                participants.append(user)

        if len(participants) > MAX_PLAYERS:
            await ctx.send(f"❌ Максимум {MAX_PLAYERS} игроков (включая тебя).")
            return

        if len(set(p.id for p in participants)) != len(participants):
            await ctx.send("❌ Нельзя вызывать одного и того же игрока несколько раз или самого себя.")
            return

        duel_id = f"rps-multi-{uuid.uuid4()}"  # уникальный ID

        async with duel_lock:
            active_duels[duel_id] = {
                "participants_ids": [p.id for p in participants],
                "channel_id": ctx.channel.id
            }
            await save_active_duels()

        mentions = ", ".join(p.mention for p in participants[1:])
        embed = discord.Embed(
            title="🎮 Вызов на КНБ!",
            description=(f"{challenger.mention} вызывает {mentions} на **Камень, Ножницы, Бумага**!\n"
                         "Каждый должен принять вызов, нажав кнопку ниже."),
            color=discord.Color.green()
        )

        view = MultiRPSAcceptView(challenger, participants, duel_id, self.bot)
        await ctx.send(embed=embed, view=view)

        # Авто-принятие за ботов
        for p in participants[1:]:
            if p.bot:
                view.accepted.add(p.id)
                logger.debug(f"{p.display_name} (бот) автоматически принял дуэль {duel_id}")

        # Если все приняли сразу
        needed = {p.id for p in participants[1:]}
        if needed <= view.accepted:
            await view.start_game(ctx.channel)


# === Вьюха для принятия/отклонения ===
class MultiRPSAcceptView(View):
    def __init__(self, challenger, participants, duel_id, bot):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot
        self.accepted = set()
        self.declined = set()

        # Кнопки принятия и отклонения
        accept_btn = Button(label="Принять дуэль", style=discord.ButtonStyle.success, emoji="✔️")
        accept_btn.callback = lambda inter: asyncio.create_task(self.handle_response(inter, accept=True))
        self.add_item(accept_btn)

        decline_btn = Button(label="Отклонить дуэль", style=discord.ButtonStyle.danger, emoji="✖️")
        decline_btn.callback = lambda inter: asyncio.create_task(self.handle_response(inter, accept=False))
        self.add_item(decline_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in [p.id for p in self.participants[1:]]:
            await interaction.response.send_message("Ты не приглашён на эту дуэль.", ephemeral=True)
            logger.warning(f"{interaction.user.display_name} попытался принять не свою дуэль")
            return False
        return True

    async def on_timeout(self):
        async with duel_lock:
            active_duels.pop(self.duel_id, None)
            await save_active_duels()
        self.clear_items()
        logger.info(f"Дуэль {self.duel_id} отменена по таймауту")

    async def handle_response(self, interaction: discord.Interaction, accept: bool):
        user_id = interaction.user.id

        if accept:
            if user_id in self.accepted:
                await interaction.response.send_message("Ты уже принял вызов.", ephemeral=True)
                return
            self.accepted.add(user_id)
            await interaction.response.send_message("✅ Ты принял дуэль!", ephemeral=True)
            logger.info(f"{interaction.user.display_name} принял дуэль {self.duel_id}")
        else:
            self.declined.add(user_id)
            async with duel_lock:
                active_duels.pop(self.duel_id, None)
                await save_active_duels()
            await interaction.response.send_message("❌ Ты отклонил дуэль. Дуэль отменена.", ephemeral=False)
            self.clear_items()
            logger.warning(f"{interaction.user.display_name} отклонил дуэль {self.duel_id}")
            return

        await self.update_message(interaction)

        needed = {p.id for p in self.participants[1:]}
        if needed <= self.accepted:
            channel = self.bot.get_channel(active_duels[self.duel_id]["channel_id"])
            await self.start_game(channel)

    async def update_message(self, interaction=None):
        accepted_mentions = ", ".join(f"<@{uid}>" for uid in self.accepted) or "никто"
        declined_mentions = ", ".join(f"<@{uid}>" for uid in self.declined) or "никто"
        waiting_mentions = ", ".join(
            p.mention for p in self.participants[1:]
            if p.id not in self.accepted and p.id not in self.declined
        ) or "никого"

        description = (
            f"Ожидаются ответы от: {waiting_mentions}\n\n"
            f"✅ Приняли: {accepted_mentions}\n"
            f"❌ Отклонили: {declined_mentions}"
        )
        embed = discord.Embed(title="🎮 Вызов на КНБ!", description=description, color=discord.Color.green())

        if interaction:
            await interaction.message.edit(embed=embed, view=self)


    async def start_game(self, channel):
        self.clear_items()
        await self.update_message()
        game_view = MultiRPSGameView(self.participants, self.duel_id, self.bot)
        msg = await channel.send("🎮 Игра началась! Все участники, выберите ваш ход:", view=game_view)
        game_view.message = msg
        logger.info(f"Дуэль {self.duel_id} начата")


# === Вьюха для самой игры ===
class MultiRPSGameView(View):
    def __init__(self, participants, duel_id, bot):
        super().__init__(timeout=60)
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot
        self.choices = {}
        self.message = None

        emoji_map = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
        for choice in CHOICES:
            self.add_item(MultiRPSButton(choice, emoji_map[choice]))

        for p in participants:
            if p.bot:
                self.choices[p.id] = random.choice(CHOICES)
                logger.debug(f"Бот {p.display_name} выбрал {self.choices[p.id]}")

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id not in [p.id for p in self.participants]:
            await interaction.response.send_message("Ты не участвуешь в этой дуэли.", ephemeral=True)
            logger.warning(f"{interaction.user.display_name} попытался сыграть не свою дуэль")
            return False
        return True

    async def check_finish(self, channel):
        if len(self.choices) < len(self.participants):
            return

        scores = {p.id: 0 for p in self.participants}
        for p1 in self.participants:
            for p2 in self.participants:
                if p1.id != p2.id and BEATS[self.choices[p1.id]] == self.choices[p2.id]:
                    scores[p1.id] += 1

        max_score = max(scores.values())
        winners = [p for p in self.participants if scores[p.id] == max_score]

        embed = discord.Embed(title="📊 Результаты КНБ", color=discord.Color.blurple())
        for p in self.participants:
            embed.add_field(name=p.display_name, value=self.choices[p.id].capitalize(), inline=True)

        if len(winners) > 1:
            embed.description = f"Ничья между: {', '.join(w.display_name for w in winners)}"
            logger.info(f"Дуэль {self.duel_id} закончилась ничьей")
        else:
            winner = winners[0]
            embed.description = f"🏆 Победитель: {winner.mention}"
            for loser in self.participants:
                if loser.id != winner.id:
                    update_stats(winner.id, loser.id)
            logger.success(f"Дуэль {self.duel_id} выиграл {winner.display_name}")

        await channel.send(embed=embed)

        async with duel_lock:
            active_duels.pop(self.duel_id, None)
            await save_active_duels()

        self.clear_items()
        if self.message:
            await self.message.edit(view=None)


# === Кнопка выбора ===
class MultiRPSButton(Button):
    def __init__(self, choice: str, emoji: str):
        super().__init__(label=choice.capitalize(), style=discord.ButtonStyle.primary, emoji=emoji)
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        view: MultiRPSGameView = self.view
        user_id = interaction.user.id

        if user_id in view.choices:
            await interaction.response.send_message("Ты уже сделал свой выбор.", ephemeral=True)
            logger.warning(f"{interaction.user.display_name} пытался выбрать ход повторно")
            return

        view.choices[user_id] = self.choice
        await interaction.response.send_message(f"Ты выбрал: **{self.choice}**", ephemeral=True)
        logger.info(f"{interaction.user.display_name} выбрал {self.choice} в дуэли {view.duel_id}")

        channel_id = active_duels[view.duel_id]["channel_id"]
        channel = view.bot.get_channel(channel_id)
        await view.check_finish(channel)


# === Подключение к боту ===
async def setup(bot: commands.Bot):
    await bot.add_cog(RPSCog(bot))
