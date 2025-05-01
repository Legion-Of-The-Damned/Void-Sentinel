import discord
import logging
from discord.ext import commands

class ClanInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("✅ Cog ClanInfo загружен.")

    @discord.app_commands.command(name="клан", description="Отправить информацию о членах клана.")
    async def clan_info(self, interaction: discord.Interaction):
        await send_clan_member_info(self.bot, interaction)

async def send_clan_member_info(bot: commands.Bot, interaction: discord.Interaction):
    guild = interaction.guild
    channel = interaction.channel

    clan_roles = [
        "⚡Неофит🔥", "💀Проклятый Новобранец💀", "🔶Огненный Боец💀",
        "🔻Теневой Страж💀", "🟣Вечный Охотник💀", "🟡Пламенный Предвестник💀",
        "💠Тёмный Клинок💀", "🟢Призрачный Мастер☠️", "⚠️Pyro Mortis⚠️",
        "Администратор", "⚫Капелан💀", "🔧Технокузнец Машин⚙️",
        "⚠️Заместитель Легиона💀", "🔥Огненный Магистр🎩"
    ]

    if not channel.permissions_for(guild.me).manage_webhooks:
        await interaction.response.send_message("❌ У меня нет прав на создание вебхуков в этом канале.", ephemeral=True)
        return

    try:
        webhook = await channel.create_webhook(name=bot.user.name)
        logging.info(f'📡 Webhook создан в канале: {channel.name} для сервера {guild.name}')

        members_by_role = {role: [] for role in clan_roles}
        for member in guild.members:
            for role in member.roles:
                if role.name in members_by_role:
                    members_by_role[role.name].append(member)

        member_info = []
        for role in reversed(clan_roles):
            if members_by_role[role]:
                member_info.append(f"**{role}**")
                member_info.extend(f"- [LOTD] {str(m)}" for m in members_by_role[role])
                member_info.append("")

        total_members = sum(len(v) for v in members_by_role.values())
        info_message = (
            f"**Количество участников клана:** {total_members}\n"
            f"**Участники клана:**\n" + "\n".join(member_info).strip()
        )

        embed = discord.Embed(
            title="Информация о членах клана",
            description=info_message,
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Запрошено: {interaction.user}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.timestamp = discord.utils.utcnow()

        avatar_url = bot.user.avatar.url if bot.user.avatar else None
        await webhook.send(embed=embed, avatar_url=avatar_url)
        await webhook.delete()

        await interaction.response.send_message("✅ Информация о клане отправлена через вебхук.", ephemeral=True)
        logging.info(f"✅ Информация отправлена ({total_members} участников).")
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке вебхука: {e}")
        await interaction.response.send_message("❌ Не удалось отправить информацию.", ephemeral=True)

# Регистрация Cog
async def setup(bot: commands.Bot):
    await bot.add_cog(ClanInfo(bot))
