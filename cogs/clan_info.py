import discord
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("ClanInfo")

CLAN_ROLE_ID = 1151988594148376709

RANKS = {
    "🔥Огненный Магистр🎩": 828749920411713588,
    "💀Заместитель Магистра⚠️": 1491133532796354581,
    "💀Полковник🏴‍☠️": 1491445605040394423,
    "☠️Капелан⚜️": 1482830190496452801
}

SQUADS = {
    "Растаманы": 1462462544500494366,
    "Подпивасы": 1488193467351044298,
    "Биошники": 1463902948265562194,
    "Берсерки": 1477393602836693175,
    "Рапторы": 1481814155433607249,
    "Беркуты": 1462462580181303337,
    "Галики": 1463902788122837023,
    "Резерв": 1494718879761694781
}

OFFICER_ROLE_ID = 1491133766448578570
DEPUTY_ROLE_ID = 1463901614019711070
AFK_ROLE_ID = 1470135285277786175


class ClanInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="состав_клана", description="Состав клана")
    async def clan_info(self, interaction: discord.Interaction):

        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("❌ Только сервер")

        embed = discord.Embed(
            title="⚔️ Legion Of The Damned",
            color=discord.Color.red()
        )

        rank_groups = {k: [] for k in RANKS}
        squad_groups = {k: [] for k in SQUADS}

        afk = []
        undefined = []
        total = 0

        # --- СБОР ДАННЫХ ---
        for m in guild.members:
            if m.bot:
                continue

            if not discord.utils.get(m.roles, id=CLAN_ROLE_ID):
                continue

            name = m.display_name

            # AFK
            if discord.utils.get(m.roles, id=AFK_ROLE_ID):
                afk.append(name)
                continue

            # РАНГ (1 шт)
            has_rank = False
            for r, rid in RANKS.items():
                if discord.utils.get(m.roles, id=rid):
                    rank_groups[r].append(name)
                    has_rank = True
                    break

            # ОТРЯД
            assigned = False
            for s, sid in SQUADS.items():
                if discord.utils.get(m.roles, id=sid):
                    squad_groups[s].append(m)
                    assigned = True
                    break

            if not assigned and not has_rank:
                undefined.append(name)

            total += 1

        embed.description = f"👥 Всего бойцов: **{total}**"

        # --- КОМАНДОВАНИЕ ---
        top_lines = []

        for r in RANKS:
            if rank_groups[r]:
                rank_groups[r].sort()

                top_lines.append(r)
                top_lines += [f"• {x}" for x in rank_groups[r]]
                top_lines.append("")

        if top_lines:
            embed.add_field(
                name="🔥 Командование",
                value="\n".join(top_lines).strip()[:1024],
                inline=False
            )

        # --- ОТРЯДЫ ---
        for squad, members in squad_groups.items():
            if not members:
                continue

            officers = []
            deputies = []
            players = []

            for m in members:
                name = m.display_name

                if discord.utils.get(m.roles, id=OFFICER_ROLE_ID):
                    officers.append(f"🔸 Офицер: {name}")
                elif discord.utils.get(m.roles, id=DEPUTY_ROLE_ID):
                    deputies.append(f"🔺 Зам: {name}")
                else:
                    players.append(f"• {name}")

            officers.sort()
            deputies.sort()
            players.sort()

            lines = [
                "━━━━━━━━━━━━━━━",
                f"🪖 **{squad.upper()}**",
                "━━━━━━━━━━━━━━━"
            ]

            # строго по порядку
            lines.extend(officers)
            lines.extend(deputies)
            lines.extend(players)

            embed.add_field(
                name="‎",
                value="\n".join(lines)[:1024],
                inline=False
            )

        # --- AFK ---
        if afk:
            afk.sort()
            embed.add_field(
                name="💤 AFK",
                value="\n".join(afk)[:1024],
                inline=False
            )

        # --- ЛЕГИОН ПРОКЛЯТЫХ ---
        if undefined:
            undefined.sort()
            embed.add_field(
                name="💀 Легион Проклятых",
                value="\n".join(undefined)[:1024],
                inline=False
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClanInfo(bot))
