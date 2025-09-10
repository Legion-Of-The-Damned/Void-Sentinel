import random
import discord
from discord.ext import commands
from discord.ui import View, Button
from data import active_duels, save_active_duels, update_stats

MAX_PLAYERS = 5  # вместе с инициатором

class RPSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="камень-ножницы-бумага",
        description="Вызвать до 4 игроков на камень, ножницы, бумага"
    )
    async def rps(
        self, ctx: commands.Context,
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

        # Проверка на дубли или вызов самого себя
        if len(set(p.id for p in participants)) != len(participants):
            await ctx.send("❌ Нельзя вызывать одного и того же игрока несколько раз или самого себя.")
            return

        duel_id = f"rps-multi-" + "-".join(str(p.id) for p in participants)

        if duel_id in active_duels:
            await ctx.send("⚔️ Дуэль уже активна!")
            return

        active_duels[duel_id] = {
            "participants_ids": [p.id for p in participants],
            "channel_id": ctx.channel.id,
            "accepted": [],
            "declined": []
        }
        await save_active_duels()

        mentions = ", ".join(p.mention for p in participants[1:])  # кроме вызвавшего

        embed = discord.Embed(
            title="🎮 Вызов на КНБ!",
            description=(
                f"{challenger.mention} вызывает {mentions} на **Камень, Ножницы, Бумага**!\n"
                "Каждый должен принять вызов, нажав кнопку ниже."
            ),
            color=discord.Color.green()
        )

        view = MultiRPSAcceptView(challenger, participants, duel_id, self.bot)
        message = await ctx.send(embed=embed, view=view)

        # Отправляем ЛС оппонентам (кроме ботов и вызвавшего)
        for p in participants[1:]:
            if not p.bot:
                try:
                    dm_embed = discord.Embed(
                        title="📬 Тебя вызвали на КНБ!",
                        description=(
                            f"Игрок **{challenger.display_name}** вызывает тебя на игру!\n"
                            f"Место дуэли: {ctx.channel.mention}\n"
                            f"Прими вызов в канале!"
                        ),
                        color=discord.Color.orange()
                    )
                    await p.send(embed=dm_embed)
                except discord.Forbidden:
                    await ctx.send(f"⚠️ {p.mention}, я не смог отправить тебе ЛС.", ephemeral=True)

        # Авто-принятие за ботов
        for p in participants[1:]:
            if p.bot:
                view.accepted.add(p.id)

        # Если все приняли — стартуем игру
        if set(p.id for p in participants[1:]) <= view.accepted:
            await view.start_game(ctx.channel)


class MultiRPSAcceptView(View):
    def __init__(self, challenger, participants, duel_id, bot):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot

        self.accepted = set()
        self.declined = set()

        self.add_item(self.AcceptButton(self))
        self.add_item(self.DeclineButton(self))

    async def update_message(self, interaction=None):
        accepted_mentions = ", ".join(f"<@{uid}>" for uid in self.accepted)
        declined_mentions = ", ".join(f"<@{uid}>" for uid in self.declined)
        waiting_mentions = ", ".join(
            p.mention for p in self.participants[1:]
            if p.id not in self.accepted and p.id not in self.declined
        )
        description = (
            f"Ожидаются ответы от: {waiting_mentions if waiting_mentions else 'никого'}\n\n"
            f"✅ Приняли: {accepted_mentions if accepted_mentions else 'никто'}\n"
            f"❌ Отклонили: {declined_mentions if declined_mentions else 'никто'}"
        )
        embed = discord.Embed(
            title="🎮 Вызов на КНБ!",
            description=description,
            color=discord.Color.green()
        )
        if interaction:
            await interaction.message.edit(embed=embed, view=self)
        else:
            channel = self.bot.get_channel(active_duels[self.duel_id]["channel_id"])
            messages = [m async for m in channel.history(limit=10)]
            for m in messages:
                if m.author == self.bot.user and m.embeds:
                    if m.embeds[0].title == "🎮 Вызов на КНБ!":
                        await m.edit(embed=embed, view=self)
                        break

    async def start_game(self, channel):
        self.clear_items()
        await self.update_message()

        game_view = MultiRPSGameView(self.participants, self.duel_id, self.bot)
        msg = await channel.send(
            f"🎮 Игра началась! Все участники, выберите ваш ход:",
            view=game_view
        )
        game_view.message = msg

    class AcceptButton(Button):
        def __init__(self, parent):
            super().__init__(label="Принять дуэль", style=discord.ButtonStyle.success, emoji="✔️")
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            user_id = interaction.user.id
            if user_id not in [p.id for p in self.parent.participants[1:]]:
                await interaction.response.send_message("Ты не приглашён на эту дуэль.", ephemeral=True)
                return
            if user_id in self.parent.accepted:
                await interaction.response.send_message("Ты уже принял вызов.", ephemeral=True)
                return
            if user_id in self.parent.declined:
                await interaction.response.send_message("Ты уже отклонил вызов.", ephemeral=True)
                return

            self.parent.accepted.add(user_id)
            await interaction.response.send_message("✅ Ты принял дуэль!", ephemeral=True)
            await self.parent.update_message(interaction)

            needed = set(p.id for p in self.parent.participants[1:])
            if needed <= self.parent.accepted:
                channel = self.parent.bot.get_channel(active_duels[self.parent.duel_id]["channel_id"])
                await self.parent.start_game(channel)

    class DeclineButton(Button):
        def __init__(self, parent):
            super().__init__(label="Отклонить дуэль", style=discord.ButtonStyle.danger, emoji="✖️")
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            user_id = interaction.user.id
            if user_id not in [p.id for p in self.parent.participants[1:]]:
                await interaction.response.send_message("Ты не приглашён на эту дуэль.", ephemeral=True)
                return
            if user_id in self.parent.declined:
                await interaction.response.send_message("Ты уже отклонил вызов.", ephemeral=True)
                return
            if user_id in self.parent.accepted:
                await interaction.response.send_message("Ты уже принял вызов.", ephemeral=True)
                return

            self.parent.declined.add(user_id)
            active_duels.pop(self.parent.duel_id, None)
            await save_active_duels()

            await interaction.response.send_message("❌ Ты отклонил дуэль. Дуэль отменена.", ephemeral=False)
            self.parent.clear_items()
            await self.parent.update_message(interaction)


class MultiRPSGameView(View):
    def __init__(self, participants, duel_id, bot):
        super().__init__(timeout=60)
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot
        self.choices = {}
        self.message = None

        self.add_item(MultiRPSButton("камень"))
        self.add_item(MultiRPSButton("ножницы"))
        self.add_item(MultiRPSButton("бумага"))

        for p in participants:
            if p.bot:
                self.choices[p.id] = random.choice(["камень", "ножницы", "бумага"])

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in [p.id for p in self.participants]:
            await interaction.response.send_message("Ты не участвуешь в этой дуэли.", ephemeral=True)
            return False
        return True

    async def check_finish(self, channel):
        if len(self.choices) < len(self.participants):
            return

        scores = {p.id: 0 for p in self.participants}
        beats = {
            "камень": "ножницы",
            "ножницы": "бумага",
            "бумага": "камень"
        }

        for p1 in self.participants:
            for p2 in self.participants:
                if p1.id == p2.id:
                    continue
                c1 = self.choices[p1.id]
                c2 = self.choices[p2.id]
                if beats[c1] == c2:
                    scores[p1.id] += 1

        max_score = max(scores.values())
        winners = [p for p in self.participants if scores[p.id] == max_score]

        embed = discord.Embed(title="📊 Результаты КНБ", color=discord.Color.blurple())
        for p in self.participants:
            embed.add_field(name=p.display_name, value=self.choices[p.id].capitalize(), inline=True)

        if len(winners) > 1:
            embed.description = f"Ничья между: {', '.join(w.display_name for w in winners)}"
        else:
            winner = winners[0]
            embed.description = f"🏆 Победитель: {winner.mention}"
            for loser in self.participants:
                if loser.id != winner.id:
                    update_stats(winner.id, loser.id)

        await channel.send(embed=embed)
        active_duels.pop(self.duel_id, None)
        await save_active_duels()

        self.clear_items()
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass


class MultiRPSButton(Button):
    def __init__(self, choice: str):
        emoji_map = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
        super().__init__(label=choice.capitalize(), style=discord.ButtonStyle.primary, emoji=emoji_map[choice])
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        view: MultiRPSGameView = self.view
        user_id = interaction.user.id

        if user_id in view.choices:
            await interaction.response.send_message("Ты уже сделал свой выбор.", ephemeral=True)
            return

        view.choices[user_id] = self.choice
        await interaction.response.send_message(f"Ты выбрал: **{self.choice}**", ephemeral=True)

        channel_id = active_duels[view.duel_id]["channel_id"]
        channel = view.bot.get_channel(channel_id)
        await view.check_finish(channel)


async def setup(bot: commands.Bot):
    await bot.add_cog(RPSCog(bot))
import random
import discord
from discord.ext import commands
from discord.ui import View, Button
from data import active_duels, save_active_duels, update_stats
import logging

MAX_PLAYERS = 5  # вместе с инициатором
logger = logging.getLogger("RPSCog")


class RPSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="камень-ножницы-бумага",
        description="Вызвать до 4 игроков на камень, ножницы, бумага"
    )
    async def rps(
        self, ctx: commands.Context,
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

        # Проверка на дубли или вызов самого себя
        if len(set(p.id for p in participants)) != len(participants):
            await ctx.send("❌ Нельзя вызывать одного и того же игрока несколько раз или самого себя.")
            return

        duel_id = f"rps-multi-" + "-".join(str(p.id) for p in participants)

        if duel_id in active_duels:
            await ctx.send("⚔️ Дуэль уже активна!")
            return

        active_duels[duel_id] = {
            "participants_ids": [p.id for p in participants],
            "channel_id": ctx.channel.id,
            "accepted": [],
            "declined": []
        }
        await save_active_duels()
        logger.info(f"Создана новая дуэль {duel_id} в канале {ctx.channel.name}")

        mentions = ", ".join(p.mention for p in participants[1:])  # кроме вызвавшего
        embed = discord.Embed(
            title="🎮 Вызов на КНБ!",
            description=(f"{challenger.mention} вызывает {mentions} на **Камень, Ножницы, Бумага**!\n"
                         "Каждый должен принять вызов, нажав кнопку ниже."),
            color=discord.Color.green()
        )

        view = MultiRPSAcceptView(challenger, participants, duel_id, self.bot)
        message = await ctx.send(embed=embed, view=view)

        # Отправляем ЛС оппонентам (кроме ботов и вызвавшего)
        for p in participants[1:]:
            if not p.bot:
                try:
                    dm_embed = discord.Embed(
                        title="📬 Тебя вызвали на КНБ!",
                        description=(f"Игрок **{challenger.display_name}** вызывает тебя на игру!\n"
                                     f"Место дуэли: {ctx.channel.mention}\n"
                                     f"Прими вызов в канале!"),
                        color=discord.Color.orange()
                    )
                    await p.send(embed=dm_embed)
                    logger.info(f"Отправлено ЛС {p.display_name} о дуэли {duel_id}")
                except discord.Forbidden:
                    logger.warning(f"Не удалось отправить ЛС {p.display_name} о дуэли {duel_id}")

        # Авто-принятие за ботов
        for p in participants[1:]:
            if p.bot:
                view.accepted.add(p.id)
                logger.info(f"{p.display_name} (бот) автоматически принял дуэль {duel_id}")

        # Если все приняли — стартуем игру
        if set(p.id for p in participants[1:]) <= view.accepted:
            await view.start_game(ctx.channel)


class MultiRPSAcceptView(View):
    def __init__(self, challenger, participants, duel_id, bot):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot

        self.accepted = set()
        self.declined = set()

        self.add_item(self.AcceptButton(self))
        self.add_item(self.DeclineButton(self))

    async def update_message(self, interaction=None):
        accepted_mentions = ", ".join(f"<@{uid}>" for uid in self.accepted)
        declined_mentions = ", ".join(f"<@{uid}>" for uid in self.declined)
        waiting_mentions = ", ".join(
            p.mention for p in self.participants[1:]
            if p.id not in self.accepted and p.id not in self.declined
        )
        description = (f"Ожидаются ответы от: {waiting_mentions if waiting_mentions else 'никого'}\n\n"
                       f"✅ Приняли: {accepted_mentions if accepted_mentions else 'никто'}\n"
                       f"❌ Отклонили: {declined_mentions if declined_mentions else 'никто'}")
        embed = discord.Embed(title="🎮 Вызов на КНБ!", description=description, color=discord.Color.green())
        if interaction:
            await interaction.message.edit(embed=embed, view=self)
        else:
            channel = self.bot.get_channel(active_duels[self.duel_id]["channel_id"])
            messages = [m async for m in channel.history(limit=10)]
            for m in messages:
                if m.author == self.bot.user and m.embeds:
                    if m.embeds[0].title == "🎮 Вызов на КНБ!":
                        await m.edit(embed=embed, view=self)
                        break

    async def start_game(self, channel):
        self.clear_items()
        await self.update_message()
        game_view = MultiRPSGameView(self.participants, self.duel_id, self.bot)
        msg = await channel.send(f"🎮 Игра началась! Все участники, выберите ваш ход:", view=game_view)
        game_view.message = msg
        logger.info(f"Дуэль {self.duel_id} начата")


    class AcceptButton(Button):
        def __init__(self, parent):
            super().__init__(label="Принять дуэль", style=discord.ButtonStyle.success, emoji="✔️")
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            user_id = interaction.user.id
            if user_id not in [p.id for p in self.parent.participants[1:]]:
                await interaction.response.send_message("Ты не приглашён на эту дуэль.", ephemeral=True)
                return
            if user_id in self.parent.accepted:
                await interaction.response.send_message("Ты уже принял вызов.", ephemeral=True)
                return
            if user_id in self.parent.declined:
                await interaction.response.send_message("Ты уже отклонил вызов.", ephemeral=True)
                return

            self.parent.accepted.add(user_id)
            logger.info(f"{interaction.user.display_name} принял дуэль {self.parent.duel_id}")
            await interaction.response.send_message("✅ Ты принял дуэль!", ephemeral=True)
            await self.parent.update_message(interaction)

            needed = set(p.id for p in self.parent.participants[1:])
            if needed <= self.parent.accepted:
                channel = self.parent.bot.get_channel(active_duels[self.parent.duel_id]["channel_id"])
                await self.parent.start_game(channel)


    class DeclineButton(Button):
        def __init__(self, parent):
            super().__init__(label="Отклонить дуэль", style=discord.ButtonStyle.danger, emoji="✖️")
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            user_id = interaction.user.id
            if user_id not in [p.id for p in self.parent.participants[1:]]:
                await interaction.response.send_message("Ты не приглашён на эту дуэль.", ephemeral=True)
                return
            if user_id in self.parent.declined:
                await interaction.response.send_message("Ты уже отклонил вызов.", ephemeral=True)
                return
            if user_id in self.parent.accepted:
                await interaction.response.send_message("Ты уже принял вызов.", ephemeral=True)
                return

            self.parent.declined.add(user_id)
            active_duels.pop(self.parent.duel_id, None)
            await save_active_duels()
            logger.info(f"{interaction.user.display_name} отклонил дуэль {self.parent.duel_id}")

            await interaction.response.send_message("❌ Ты отклонил дуэль. Дуэль отменена.", ephemeral=False)
            self.parent.clear_items()
            await self.parent.update_message(interaction)


class MultiRPSGameView(View):
    def __init__(self, participants, duel_id, bot):
        super().__init__(timeout=60)
        self.participants = participants
        self.duel_id = duel_id
        self.bot = bot
        self.choices = {}
        self.message = None

        self.add_item(MultiRPSButton("камень"))
        self.add_item(MultiRPSButton("ножницы"))
        self.add_item(MultiRPSButton("бумага"))

        for p in participants:
            if p.bot:
                self.choices[p.id] = random.choice(["камень", "ножницы", "бумага"])
                logger.info(f"Бот {p.display_name} выбрал {self.choices[p.id]} для дуэли {duel_id}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in [p.id for p in self.participants]:
            await interaction.response.send_message("Ты не участвуешь в этой дуэли.", ephemeral=True)
            return False
        return True

    async def check_finish(self, channel):
        if len(self.choices) < len(self.participants):
            return

        scores = {p.id: 0 for p in self.participants}
        beats = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}

        for p1 in self.participants:
            for p2 in self.participants:
                if p1.id == p2.id:
                    continue
                c1 = self.choices[p1.id]
                c2 = self.choices[p2.id]
                if beats[c1] == c2:
                    scores[p1.id] += 1

        max_score = max(scores.values())
        winners = [p for p in self.participants if scores[p.id] == max_score]

        embed = discord.Embed(title="📊 Результаты КНБ", color=discord.Color.blurple())
        for p in self.participants:
            embed.add_field(name=p.display_name, value=self.choices[p.id].capitalize(), inline=True)

        if len(winners) > 1:
            embed.description = f"Ничья между: {', '.join(w.display_name for w in winners)}"
            logger.info(f"Дуэль {self.duel_id} закончилась ничьей между: {', '.join(w.display_name for w in winners)}")
        else:
            winner = winners[0]
            embed.description = f"🏆 Победитель: {winner.mention}"
            for loser in self.participants:
                if loser.id != winner.id:
                    update_stats(winner.id, loser.id)
            logger.info(f"Дуэль {self.duel_id} выиграл {winner.display_name}")

        await channel.send(embed=embed)
        active_duels.pop(self.duel_id, None)
        await save_active_duels()
        self.clear_items()
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass


class MultiRPSButton(Button):
    def __init__(self, choice: str):
        emoji_map = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
        super().__init__(label=choice.capitalize(), style=discord.ButtonStyle.primary, emoji=emoji_map[choice])
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        view: MultiRPSGameView = self.view
        user_id = interaction.user.id

        if user_id in view.choices:
            await interaction.response.send_message("Ты уже сделал свой выбор.", ephemeral=True)
            return

        view.choices[user_id] = self.choice
        logger.info(f"{interaction.user.display_name} выбрал {self.choice} для дуэли {view.duel_id}")
        await interaction.response.send_message(f"Ты выбрал: **{self.choice}**", ephemeral=True)

        channel_id = active_duels[view.duel_id]["channel_id"]
        channel = view.bot.get_channel(channel_id)
        await view.check_finish(channel)


async def setup(bot: commands.Bot):
    await bot.add_cog(RPSCog(bot))
