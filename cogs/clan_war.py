import asyncio
import random
import json
import os
from datetime import datetime

import discord
from discord.ext import commands, tasks
import logging


logger = logging.getLogger("bot.clan_war")
logger.setLevel(logging.INFO)
logger.propagate = True


class CWNotificationView(discord.ui.View):
    def __init__(self, cog, cw_id: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.cw_id = cw_id

    @discord.ui.button(
        label="📩 Получить уведомление о КВ",
        style=discord.ButtonStyle.green,
        custom_id="cw_subscribe_button"
    )
    async def subscribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        user_id = interaction.user.id

        if user_id not in self.cog.subscribed_users:
            self.cog.subscribed_users[user_id] = set()

        if self.cw_id in self.cog.subscribed_users[user_id]:
            await interaction.response.send_message(
                "ℹ️ Ты уже подписан на это КВ.",
                ephemeral=True
            )
            return

        self.cog.subscribed_users[user_id].add(self.cw_id)
        self.cog.save_subs()

        await interaction.response.send_message(
            "✅ Ты записан на это КВ.",
            ephemeral=True
        )

    @discord.ui.button(
        label="❌ Отписаться",
        style=discord.ButtonStyle.red,
        custom_id="cw_unsubscribe_button"
    )
    async def unsubscribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        user_id = interaction.user.id

        if user_id not in self.cog.subscribed_users:
            await interaction.response.send_message(
                "ℹ️ Ты не записан.",
                ephemeral=True
            )
            return

        if self.cw_id in self.cog.subscribed_users[user_id]:
            self.cog.subscribed_users[user_id].remove(self.cw_id)

        self.cog.save_subs()

        await interaction.response.send_message(
            "❌ Ты отписался от этого КВ.",
            ephemeral=True
        )


class ClanWarNotifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.guild_id = 1472318342663507988
        self.announcements_channel_id = 1368378026466738300
        self.role_id = 1472318342663507988

        self.subscribed_users = {}
        self.subs_file = "data/cw_subs.json"

        self.sent_events = set()

        self.images = [
            "https://cdn.discordapp.com/attachments/1355929392072753262/1502054043780911175/929cfe4e32658036984c4de7b3446343.jpg?ex=6a078ad6&is=6a063956&hm=950f7d12140f88ff6a06758476e0e3c5c87d031041109500e4b00b6b37214153&",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1502053634643591188/22.png?ex=6a078a75&is=6a0638f5&hm=f728b6ae3f67f3c075d1fd9bfd22309c9b4e27caf5dc29dd3ec078281b2e041b&",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1502042817957204079/image3_wide-01-05-krdnfkfaw9.jpg?ex=6a078062&is=6a062ee2&hm=57b0899f5622f57739e785b7f09488f8d9d43273dbe66308ecac7214e65e075c&",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1502042817344831578/-Photoroom.png?ex=6a078062&is=6a062ee2&hm=c4068fef95ed5374f7f7cf4d4ba176fc54dfe5028eb17b577f1843ad64e4ea3c&",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1502042816816218122/ssd_destroyed_by_ultramarines__gloriana_class_by_hexanity_dja8asr-pre.jpg?ex=6a078062&is=6a062ee2&hm=0ed3a524c5982a436d3f5bc77181ee958aab2d897d988709ceb70f27b381f708&",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1502042815641948260/LoD_Battle.webp?ex=6a078061&is=6a062ee1&hm=57d8094349a7c714be026e03ff1c67ee7f6000d62a6c40f57be518a991eaf360&",
            "https://cdn.discordapp.com/attachments/1355929392072753262/1502042814068822206/hq720.jpg?ex=6a078061&is=6a062ee1&hm=b2e7636600524eb405f6d7653ed1bc94f2cfd496c2571a56237f59ccd1707658&",
        ]

        self.thumbnail_url = (
            "https://cdn.discordapp.com/attachments/1297692294878859314/1427698466267599021/-__.png"
        )

        self.load_subs()
        self.cleanup_old_subs()

        self.daily_announcement.start()
        self.cw_notifications.start()

        logger.info("⚔️ ClanWarNotifications загружен")

    def load_subs(self):
        try:
            if not os.path.exists(self.subs_file):
                self.subscribed_users = {}
                return

            with open(self.subs_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.subscribed_users = {
                int(uid): set(cw_ids)
                for uid, cw_ids in data.items()
            }

        except Exception as e:
            logger.error(f"❌ ошибка загрузки подписок: {e}")
            self.subscribed_users = {}

    def save_subs(self):
        try:
            os.makedirs(os.path.dirname(self.subs_file), exist_ok=True)

            data = {
                str(uid): list(cw_ids)
                for uid, cw_ids in self.subscribed_users.items()
            }

            with open(self.subs_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ ошибка сохранения подписок: {e}")

    def cleanup_old_subs(self):
        today = datetime.now().strftime("%Y-%m-%d")
        changed = False

        for uid in list(self.subscribed_users.keys()):
            cw_ids = self.subscribed_users[uid]

            new_set = {cw for cw in cw_ids if cw >= today}

            if new_set != cw_ids:
                self.subscribed_users[uid] = new_set
                changed = True

            if not self.subscribed_users[uid]:
                del self.subscribed_users[uid]
                changed = True

        if changed:
            self.save_subs()

    async def send_dm_to_members(self, cw_id: str, text: str):

        sent = 0
        failed = 0

        for uid, cw_ids in self.subscribed_users.items():

            if cw_id not in cw_ids:
                continue

            try:
                user = await self.bot.fetch_user(uid)
                await user.send(f"{user.mention} {text}")

                sent += 1
                await asyncio.sleep(0.25)

            except Exception:
                failed += 1

        logger.info(f"📊 DM {cw_id} | sent={sent} failed={failed}")

    async def before_daily(self):
        await self.bot.wait_until_ready()

    async def before_cw(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=10)
    async def daily_announcement(self):

        now = datetime.now()
        cw_id = now.strftime("%Y-%m-%d")

        key = f"daily:{cw_id}"

        if key in self.sent_events:
            return

        if now.hour != 12 or now.minute != 0:
            return

        channel = self.bot.get_channel(self.announcements_channel_id)
        if not channel:
            return

        weekday = now.weekday()
        status = "🟥 Обязательное КВ" if weekday in [3, 4, 5] else "🟩 Необязательное КВ"

        embed = discord.Embed(
            title="⚔️ Legion Of The Damned - Клановые Битвы",
            description=f"{status}\n\n🕗 Сетка: 20:30\n🔥 Начало: 21:00",
            color=discord.Color.red()
        )

        embed.set_image(url=random.choice(self.images))
        embed.set_thumbnail(url=self.thumbnail_url)

        view = CWNotificationView(self, cw_id)

        await channel.send(
            content=f"<@&{self.role_id}>",
            embed=embed,
            view=view
        )

        self.sent_events.add(key)

    @tasks.loop(seconds=10)
    async def cw_notifications(self):

        now = datetime.now()
        cw_id = now.strftime("%Y-%m-%d")

        events = [
            (20, 30, "start", "⚔️ Сетка КВ началась!"),
            (20, 50, "warn", "⏳ До КВ осталось 10 минут!"),
            (21, 0, "go", "🔥 КВ НАЧАЛОСЬ!")
        ]

        for hour, minute, tag, msg in events:

            key = f"{cw_id}:{tag}"

            if key in self.sent_events:
                continue

            if now.hour == hour and now.minute == minute:
                await self.send_dm_to_members(cw_id, msg)
                self.sent_events.add(key)

    @daily_announcement.before_loop
    async def before_daily_loop(self):
        await self.bot.wait_until_ready()

    @cw_notifications.before_loop
    async def before_cw_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ClanWarNotifications(bot))