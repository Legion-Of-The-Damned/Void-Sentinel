import random
import asyncio
import logging
import uuid
from typing import List, Union

import discord
from discord.ext import commands
from discord.ui import View, Button

logger = logging.getLogger("RPS")
duel_lock = asyncio.Lock()

# === Константы ===
MAX_PLAYERS = 5
CHOICES = ["камень", "ножницы", "бумага"]
BEATS = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}
EMOJI_MAP = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}

rps_duels = {}  # хранилище текущих дуэлей


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
        user1: Union[discord.Member, discord.User],
        user2: Union[discord.Member, discord.User] = None,
        user3: Union[discord.Member, discord.User] = None,
        user4: Union[discord.Member, discord.User] = None
    ):
        challenger = ctx.author
        participants = [challenger, user1] + [u for u in (user2, user3, user4) if u]

        # Проверка на количество игроков
        if len(participants) > MAX_PLAYERS:
            await ctx.send(f"❌ Максимум {MAX_PLAYERS} игроков (включая тебя).")
            return

        # Проверка на дубли
        if len(set(p.id for p in participants)) != len(participants):
            await ctx.send("❌ Нельзя вызывать одного и того же игрока несколько раз или самого себя.")
            return

        duel_id = f"rps-multi-{uuid.uuid4()}"
        async with duel_lock:
            rps_duels[duel_id] = {
                "type": "rps",
                "participants_ids": [p.id for p in participants]
            }

        mentions = ", ".join(getattr(p, "mention", str(p)) for p in participants[1:])
        embed = discord.Embed(
            title="🎮 Вызов на КНБ!",
            description=f"{challenger.mention} вызывает {mentions} на **Камень, Ножницы, Бумага**!\n"
                        "Каждый должен принять вызов, нажав кнопку ниже.",
            color=discord.Color.green()
        )

        # Сохраняем канал отправки сообщений
        channel = ctx.channel
        view = MultiRPSAcceptView(challenger, participants, duel_id, self.bot, channel)
        await ctx.send(embed=embed, view=view)

        # Авто-принятие ботов
        for p in participants[1:]:
            if getattr(p, "bot", False):
                view.accepted.add(p.id)
                logger.debug(f"{p} (бот) автоматически принял дуэль {duel_id}")

        # Если все приняли сразу
        needed = {p.id for p in participants[1:]}
        if needed <= view.accepted:
            await view.start_game(channel)


# === Вьюха для принятия/отклонения дуэли ===
class MultiRPSAcceptView(View):
    def __init__(self, challenger, participants, duel_id, bot, channel: discord.abc.Messageable):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot
        self.channel = channel
        self.accepted = set()
        self.declined = set()

        self.add_item(AcceptButton(self))
        self.add_item(DeclineButton(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in [p.id for p in self.participants[1:]]:
            await interaction.response.send_message("Ты не приглашён на эту дуэль.", ephemeral=True)
            return False
        return True

    async def handle_response(self, interaction: discord.Interaction, accept: bool):
        user_id = interaction.user.id
        if accept:
            if user_id in self.accepted:
                await interaction.response.send_message("Ты уже принял вызов.", ephemeral=True)
                return
            self.accepted.add(user_id)
            await interaction.response.send_message("✅ Ты принял дуэль!", ephemeral=True)
        else:
            self.declined.add(user_id)
            async with duel_lock:
                rps_duels.pop(self.duel_id, None)
            self.clear_items()
            await interaction.response.send_message("❌ Ты отклонил дуэль. Дуэль отменена.", ephemeral=False)
            return

        await self.update_message(interaction)
        needed = {p.id for p in self.participants[1:]}
        if needed <= self.accepted:
            await self.start_game(self.channel)

    async def update_message(self, interaction=None):
        accepted_mentions = ", ".join(f"<@{uid}>" for uid in self.accepted) or "никто"
        declined_mentions = ", ".join(f"<@{uid}>" for uid in self.declined) or "никто"
        waiting_mentions = ", ".join(
            getattr(p, "mention", str(p)) for p in self.participants[1:] if p.id not in self.accepted and p.id not in self.declined
        ) or "никого"

        description = (f"Ожидаются ответы от: {waiting_mentions}\n\n"
                       f"✅ Приняли: {accepted_mentions}\n"
                       f"❌ Отклонили: {declined_mentions}")
        embed = discord.Embed(title="🎮 Вызов на КНБ!", description=description, color=discord.Color.green())

        if interaction:
            await interaction.message.edit(embed=embed, view=self)

    async def start_game(self, channel: discord.abc.Messageable):
        self.clear_items()
        await self.update_message()
        game_view = MultiRPSGameView(self.participants, self.duel_id, self.bot, channel)
        msg = await channel.send("🎮 Игра началась! Все участники, выберите ваш ход:", view=game_view)
        game_view.message = msg


# === Кнопки для принятия/отклонения ===
class AcceptButton(Button):
    def __init__(self, parent_view: MultiRPSAcceptView):
        super().__init__(label="Принять дуэль", style=discord.ButtonStyle.success, emoji="✔️")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.handle_response(interaction, accept=True)


class DeclineButton(Button):
    def __init__(self, parent_view: MultiRPSAcceptView):
        super().__init__(label="Отклонить дуэль", style=discord.ButtonStyle.danger, emoji="✖️")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.handle_response(interaction, accept=False)


# === Вьюха для игры ===
class MultiRPSGameView(View):
    def __init__(self, participants: List[Union[discord.Member, discord.User]], duel_id: str, bot: commands.Bot, channel: discord.abc.Messageable):
        super().__init__(timeout=60)
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot
        self.channel = channel
        self.choices = {}
        self.message = None

        for choice in CHOICES:
            self.add_item(MultiRPSButton(choice, EMOJI_MAP[choice]))

        # Авто-выбор для ботов
        for p in participants:
            if getattr(p, "bot", False):
                self.choices[p.id] = random.choice(CHOICES)
                logger.debug(f"Бот {p} выбрал {self.choices[p.id]}")

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id not in [p.id for p in self.participants]:
            await interaction.response.send_message("Ты не участвуешь в этой дуэли.", ephemeral=True)
            return False
        return True

    async def check_finish(self):
        if len(self.choices) < len(self.participants):
            return

        scores = {p.id: sum(BEATS[self.choices[p.id]] == self.choices[p2.id] for p2 in self.participants if p.id != p2.id)
                  for p in self.participants}
        max_score = max(scores.values())
        winners = [p for p in self.participants if scores[p.id] == max_score]

        embed = discord.Embed(title="📊 Результаты КНБ", color=discord.Color.blurple())
        for p in self.participants:
            embed.add_field(name=getattr(p, "display_name", str(p)), value=self.choices[p.id].capitalize(), inline=True)

        if len(winners) > 1:
            embed.description = f"Ничья между: {', '.join(getattr(w, 'display_name', str(w)) for w in winners)}"
        else:
            winner = winners[0]
            embed.description = f"🏆 Победитель: {getattr(winner, 'mention', str(winner))}"

        await self.channel.send(embed=embed)
        self.clear_items()
        if self.message:
            await self.message.edit(view=None)
        async with duel_lock:
            rps_duels.pop(self.duel_id, None)


# === Кнопка выбора хода ===
class MultiRPSButton(Button):
    def __init__(self, choice: str, emoji: str):
        super().__init__(label=choice.capitalize(), style=discord.ButtonStyle.primary, emoji=emoji)
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        view: MultiRPSGameView = self.view
        user_id = interaction.user.id

        if user_id in view.choices:
            await interaction.response.send_message("Ты уже сделал свой выбор.", ephemeral=True)
            return

        view.choices[user_id] = self.choice
        await interaction.response.send_message(f"Ты выбрал: **{self.choice}**", ephemeral=True)

        await view.check_finish()


# === Подключение к боту ===
async def setup(bot: commands.Bot):
    await bot.add_cog(RPSCog(bot))
