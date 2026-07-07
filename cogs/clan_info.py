import discord
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("ClanInfo")

CLAN_ROLE_ID = 1151988594148376709

# Список ID ролей командования (рангов) – порядок определяет вывод
RANK_IDS = [
    828749920411713588,  # 🔥Огненный Магистр🎩
    1491133532796354581, # 💀Заместитель Магистра⚠️
    1491445605040394423, # 💀Полковник🏴‍☠️
    1482830190496452801  # ☠️Капелан⚜️
]

# Список ID ролей отрядов – порядок определяет вывод
SQUAD_IDS = [
    1524156355446050916, # Нова-штурмы 2
    1477393602836693175, # Нова-штурмы
    1463902948265562194, # Растаманы
    1462462544500494366, # Кабанчики
    1462462580181303337, # Барашки
    1481814155433607249, # Синички
    1463902788122837023, # Котятки
    1494718879761694781  # Резерв
]

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

        # Группировка по ID ролей
        rank_groups = {rid: [] for rid in RANK_IDS}
        squad_groups = {sid: [] for sid in SQUAD_IDS}

        undefined = []
        total = 0

        # --- СБОР ДАННЫХ ---
        for m in guild.members:
            if m.bot:
                continue

            if not discord.utils.get(m.roles, id=CLAN_ROLE_ID):
                continue

            # Формируем имя с пометкой AFK, если есть
            base_name = m.display_name
            if discord.utils.get(m.roles, id=AFK_ROLE_ID):
                display_name = f"{base_name} (AFK)"
            else:
                display_name = base_name

            # РАНГ (только одна роль ранга) – добавляем в командование
            has_rank = False
            for rid in RANK_IDS:
                if discord.utils.get(m.roles, id=rid):
                    rank_groups[rid].append(display_name)
                    has_rank = True
                    break

            # ОТРЯД – добавляем ВСЕХ, у кого есть роль отряда (независимо от ранга)
            assigned = False
            for sid in SQUAD_IDS:
                if discord.utils.get(m.roles, id=sid):
                    squad_groups[sid].append(m)  # сохраняем объект участника для проверки офицер/зам
                    assigned = True
                    break  # каждый участник только в одном отряде (первая найденная роль)

            # Если нет ни ранга, ни отряда – в Легион Проклятых
            if not has_rank and not assigned:
                undefined.append(display_name)

            total += 1

        embed.description = f"👥 Всего бойцов: **{total}**"

        # --- КОМАНДОВАНИЕ ---
        top_lines = []

        for rid in RANK_IDS:
            members = rank_groups[rid]
            if members:
                members.sort()
                rank_name = guild.get_role(rid).name  # берём имя роли из Discord
                top_lines.append(rank_name)
                top_lines += [f"• {x}" for x in members]
                top_lines.append("")

        if top_lines:
            embed.add_field(
                name="Командование",
                value="\n".join(top_lines).strip()[:1024],
                inline=False
            )

        # --- ОТРЯДЫ ---
        for sid in SQUAD_IDS:
            members = squad_groups[sid]
            if not members:
                continue

            officers = []
            deputies = []
            players = []

            for m in members:
                # Формируем имя с пометкой AFK для отряда
                base_name = m.display_name
                if discord.utils.get(m.roles, id=AFK_ROLE_ID):
                    name = f"{base_name} (AFK)"
                else:
                    name = base_name

                if discord.utils.get(m.roles, id=OFFICER_ROLE_ID):
                    officers.append(f"🔸 Офицер: {name}")
                elif discord.utils.get(m.roles, id=DEPUTY_ROLE_ID):
                    deputies.append(f"🔺 Зам: {name}")
                else:
                    players.append(f"• {name}")

            officers.sort()
            deputies.sort()
            players.sort()

            squad_name = guild.get_role(sid).name  # берём имя роли из Discord
            lines = [
                "━━━━━━━━━━━━━━━",
                f"🪖 **{squad_name.upper()}**",
                "━━━━━━━━━━━━━━━"
            ]

            # строго по порядку: офицеры, замы, рядовые
            lines.extend(officers)
            lines.extend(deputies)
            lines.extend(players)

            embed.add_field(
                name="‎",
                value="\n".join(lines)[:1024],
                inline=False
            )

        # --- ЛЕГИОН ПРОКЛЯТЫХ (только те, у кого нет ни ранга, ни отряда) ---
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