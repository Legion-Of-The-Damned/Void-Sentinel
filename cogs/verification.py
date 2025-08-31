import discord
from discord.ext import commands
import json
import os
import aiohttp
from config import load_config  # импортируем функцию load_config

config = load_config()


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Настройки верификации из конфига
        self.verify_channel_id = config.get("VERIFY_CHANNEL_ID")
        self.verified_role_id = config.get("VERIFIED_ROLE_ID")
        self.verify_emoji = config.get("VERIFY_EMOJI", "✅")
        self.msg_file = "data/verify_message.json"
        self.avatar_url = config.get("AVATAR_URL")

    async def get_avatar_bytes(self, url):
        if not url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            print(f"[Verification] Не удалось загрузить аватар: {e}")
        return None

    def save_message_id(self, msg_id):
        try:
            with open(self.msg_file, "w") as f:
                json.dump({"message_id": msg_id}, f)
        except Exception as e:
            print(f"[Verification] Ошибка при сохранении message_id: {e}")

    def load_message_id(self):
        if os.path.exists(self.msg_file):
            try:
                with open(self.msg_file, "r") as f:
                    return json.load(f).get("message_id")
            except Exception as e:
                print(f"[Verification] Ошибка при чтении message_id: {e}")
        return None

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(self.verify_channel_id)
        if not channel:
            print(f"[Verification] Канал с ID {self.verify_channel_id} не найден!")
            return

        msg_id = self.load_message_id()
        if msg_id:
            try:
                await channel.fetch_message(msg_id)
                print("[Verification] Сообщение верификации найдено, создание не требуется.")
                return
            except discord.NotFound:
                print("[Verification] Сообщение было удалено, создаём новое.")
            except Exception as e:
                print(f"[Verification] Ошибка при получении сообщения: {e}")
                msg_id = None

        # Создаём сообщение через вебхук, если его нет
        try:
            webhooks = await channel.webhooks()
            avatar_bytes = await self.get_avatar_bytes(self.avatar_url)
            if webhooks:
                webhook = webhooks[0]
            else:
                webhook = await channel.create_webhook(
                    name="VerificationWebhook",
                    avatar=avatar_bytes
                )

            embed = discord.Embed(
                title="Верификация на сервере",
                description=f"Нажмите на реакцию {self.verify_emoji}, чтобы получить доступ к серверу!",
                color=discord.Color.red()  # красная полоска слева
            )
            msg = await webhook.send(
                embed=embed,
                wait=True,
                username="Void Sentinel",
                avatar_url=self.avatar_url
            )
            await msg.add_reaction(self.verify_emoji)
            self.save_message_id(msg.id)
            print(f"[Verification] Сообщение верификации создано и реакция добавлена.")
        except Exception as e:
            print(f"[Verification] Ошибка при создании сообщения через вебхук: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        if payload.channel_id != self.verify_channel_id:
            return
        msg_id = self.load_message_id()
        if payload.message_id != msg_id:
            return
        if str(payload.emoji) != self.verify_emoji:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            print(f"[Verification] Сервер с ID {payload.guild_id} не найден!")
            return

        member = guild.get_member(payload.user_id)
        if not member:
            print(f"[Verification] Участник с ID {payload.user_id} не найден!")
            return

        role = guild.get_role(self.verified_role_id)
        if not role:
            print(f"[Verification] Роль с ID {self.verified_role_id} не найдена!")
            return

        if role not in member.roles:
            try:
                await member.add_roles(role)
                print(f"[Verification] Роль {role.name} выдана пользователю {member}.")
            except discord.Forbidden:
                print(f"[Verification] Нет прав для выдачи роли {role.name} пользователю {member}.")
            except Exception as e:
                print(f"[Verification] Ошибка при выдаче роли: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.channel_id != self.verify_channel_id:
            return
        msg_id = self.load_message_id()
        if payload.message_id != msg_id:
            return
        if str(payload.emoji) != self.verify_emoji:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        role = guild.get_role(self.verified_role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
                print(f"[Verification] Роль {role.name} снята с пользователя {member}.")
            except discord.Forbidden:
                print(f"[Verification] Нет прав для снятия роли {role.name} с пользователя {member}.")
            except Exception as e:
                print(f"[Verification] Ошибка при снятии роли: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Verification(bot))
