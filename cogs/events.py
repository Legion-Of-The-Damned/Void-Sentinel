import discord
import logging
from discord.ext import commands

class Events(commands.Cog):
    def __init__(self, bot, avatar_url, image_url):
        self.bot = bot
        self.avatar_url = avatar_url
        self.image_url = image_url

    async def send_welcome_message(self, member, webhook):
        guild = member.guild
        message_content = f"Добро пожаловать на сервер {guild.name}, {member.mention}!"
        embed = discord.Embed(
            color=15597568,
            title="Мы рады видеть тебя в нашем сообществе! Надеемся, что тебе здесь понравится!"
        )

        guild_icon_url = guild.icon.url if guild.icon else None
        if guild_icon_url:
            embed.set_thumbnail(url=guild_icon_url)

        embed.add_field(
            name="Пожалуйста, ознакомься с правилами, чтобы избежать недоразумений!",
            value="",
        )
        embed.set_image(url=self.image_url)

        try:
            await webhook.send(
                content=message_content,
                embed=embed,
                avatar_url=self.avatar_url
            )
            logging.info(f"Отправил приветственное сообщение для {member.name}.")
        except Exception as e:
            logging.error(f"Не удалось отправить приветственное сообщение для {member.name}: {e}")

    async def send_farewell_message(self, member, webhook):
        guild = member.guild
        message_content = f"{member.name} покинул сервер {guild.name}."
        embed = discord.Embed(
            color=0xFF0000,
            title="Участник покинул сервер",
            description=f"{member.name} больше не с нами."
        )

        guild_icon_url = guild.icon.url if guild.icon else None
        if guild_icon_url:
            embed.set_thumbnail(url=guild_icon_url)

        # Удалил строку с gif_url

        try:
            await webhook.send(
                content=message_content,
                embed=embed,
                avatar_url=self.avatar_url
            )
            logging.info(f"Отправил сообщение об уходе {member.name}.")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение об уходе для {member.name}: {e}")

    async def create_webhook_and_send_message(self, channel, member, message_func):
        try:
            webhook = await channel.create_webhook(name="Void Sentinel")
            logging.info(f'Webhook создан в канале: {channel.name}')
            await message_func(member, webhook)
            await webhook.delete()
        except Exception as e:
            logging.error(f"Не удалось создать вебхук или отправить сообщение в канале {channel.name}: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        welcome_channel = guild.system_channel or next(
            (channel for channel in guild.text_channels if channel.permissions_for(guild.me).send_messages),
            None
        )

        if welcome_channel:
            await self.create_webhook_and_send_message(welcome_channel, member, self.send_welcome_message)
        else:
            logging.error(f"Нет доступного текстового канала на сервере {guild.name} для отправки приветственного сообщения.")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        farewell_channel = guild.system_channel or next(
            (channel for channel in guild.text_channels if channel.permissions_for(guild.me).send_messages),
            None
        )

        if farewell_channel:
            await self.create_webhook_and_send_message(farewell_channel, member, self.send_farewell_message)
        else:
            logging.error(f"Нет доступного текстового канала на сервере {guild.name} для отправки сообщения об уходе.")

async def setup(bot):
    from config import load_config
    config = load_config()
    await bot.add_cog(Events(bot, config["AVATAR_URL"], config["IMAGE_URL"]))
