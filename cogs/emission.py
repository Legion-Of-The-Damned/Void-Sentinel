import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger("emission")
logger.setLevel(logging.DEBUG)
logger.propagate = True


class Stalcraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.BASE_URL = "https://dapi.stalcraft.net"
        self.TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwibmJmIjoxNjczNzk3ODM4LCJleHAiOjQ4MjczOTc4MzgsImlhdCI6MTY3Mzc5NzgzOCwianRpIjoiYXhwbzAzenJwZWxkMHY5dDgzdzc1N2x6ajl1MmdyeHVodXVlb2xsZ3M2dml1YjVva3NwZTJ3eGFrdjJ1eWZxaDU5ZDE2ZTNlN2FqdW16Z3gifQ.ZNSsvwAX72xT5BzLqqYABuH2FGbOlfiXMK5aYO1H5llG51ZjcPvOYBDRR4HUoPZVLFY8jyFUsEXNM7SYz8qL9ePmLjJl6pib8FEtqVPmf9ldXvKkbaaaSp4KkJzsIEMY_Z5PejB2Vr-q-cL13KPgnLGUaSW-2X_sHPN7VZJNMjRgjw4mPiRZTe4CEpQq0BEcPrG6OLtU5qlZ6mLDJBjN2xtK0DI6xgmYriw_5qW1mj1nqF_ewtUiQ1KTVhDgXnaNUdkGsggAGqyicTei0td6DTKtnl3noD5VkipWn_CwSqb2Mhm16I9BPfX_d5ARzWrnrwPRUf6PA_7LipNU6KkkW0mhZfmwEPTm_sXPus0mHPENoVZArdFT3L5sOYBcpqwvVIEtxRUTdcsKp-y-gSzao5muoyPVoCc2LEeHEWx0cIi9spsZ46SPRQpN4baVFp7y5rp5pjRsBKHQYUJ0lTmh1_vyfzOzbtNN2v6W_5w9JTLrN1U6fhmifvKHppFSEqD6DameL1TC59kpIdufRkEU9HE4O-ErEf1GuJFRx-Dew6XDvb_ExhvEqcw31yNvKzpVqLYJfLazqn6tUbVuAiPwpy6rP9tYO2taT1vj5TGn_vxwDu9zoLWe796tFMPS-kmbCglxB5C9L4EbpfWNbWxYjUkTvjT2Ml9OnrB0UbYo1jI"

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.TOKEN}"
        }

        self.EMISSION_CHANNEL_ID = 1501578292636024860
        self.last_message_id = None

        self.update_emission.start()

    async def get_emission(self, region="eu"):
        try:
            url = f"{self.BASE_URL}/{region}/emission"
            r = requests.get(url, headers=self.headers, timeout=10)

            if r.status_code != 200:
                logger.error(f"API ошибка: {r.status_code} | {r.text}")
                return None

            return r.json()

        except Exception as e:
            logger.critical(f"Ошибка API: {e}")
            return None

    def iso_to_dt(self, iso_str):
        try:
            if not iso_str:
                return None
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def parse_emission(self, data):
        try:
            last_emission = self.iso_to_dt(data.get("previousStart"))
            last_end = self.iso_to_dt(data.get("previousEnd"))
            current_start = self.iso_to_dt(data.get("currentStart"))
            return last_emission, last_end, current_start
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return None, None, None

    def convert_tz(self, dt, tz_name):
        if not dt:
            return None
        return dt.astimezone(ZoneInfo(tz_name))

    def build_multi_line(self, dt):
        if not dt:
            return "—"

        server = dt.strftime("%d.%m.%Y %H:%M")

        kyiv = self.convert_tz(dt, "Europe/Kyiv")
        moscow = self.convert_tz(dt, "Europe/Moscow")

        return (
            f"{server} (Сервер)\n"
            f"{kyiv.strftime('%H:%M') if kyiv else '—'} 🇺🇦 | "
            f"{moscow.strftime('%H:%M') if moscow else '—'} 🇷🇺"
        )

    def build_embed(self, data):
        last_emission, last_end, current_start = self.parse_emission(data)
        now = datetime.now(timezone.utc)

        # статус
        if last_emission and last_end and last_emission <= now <= last_end:
            status_text = "🟢 ИДЁТ ВЫБРОС"
            color = discord.Color.red()
        elif current_start:
            status_text = "🟡 ОЖИДАНИЕ ВЫБРОСА"
            color = discord.Color.orange()
        else:
            status_text = "❓ НЕТ ДАННЫХ"
            color = discord.Color.dark_grey()

        embed = discord.Embed(
            title="☢️ STALCRAFT — Выброс",
            description=f"**Статус:** {status_text}",
            color=color
        )

        embed.add_field(
            name="🕒 Последний выброс",
            value=f"```{self.build_multi_line(last_emission)}```",
            inline=False
        )

        embed.add_field(
            name="⏳ Следующий выброс",
            value=f"```{self.build_multi_line(current_start)}```",
            inline=False
        )

        # до начала
        if current_start:
            diff = (current_start - now).total_seconds()
            if diff > 0:
                hours = int(diff // 3600)
                minutes = int((diff % 3600) // 60)

                embed.add_field(
                    name="⏱ До начала",
                    value=f"> {hours}ч {minutes}м",
                    inline=False
                )

        # длительность
        if last_emission and last_end:
            duration = (last_end - last_emission).total_seconds()
            if duration > 0:
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)

                embed.add_field(
                    name="⏱ Длительность выброса",
                    value=f"> {hours}ч {minutes}м",
                    inline=False
                )

        embed.set_footer(text="Void Sentinel • Emission Tracker")
        embed.timestamp = now

        return embed

    @tasks.loop(seconds=30)
    async def update_emission(self):
        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(self.EMISSION_CHANNEL_ID)
        if not channel:
            logger.error("Канал не найден")
            return

        data = await self.get_emission()
        if not data:
            return

        embed = self.build_embed(data)

        try:
            if self.last_message_id:
                try:
                    msg = await channel.fetch_message(self.last_message_id)
                    await msg.edit(embed=embed)
                except discord.NotFound:
                    msg = await channel.send(embed=embed)
                    self.last_message_id = msg.id
            else:
                msg = await channel.send(embed=embed)
                self.last_message_id = msg.id

            logger.info("Выброс обновлён (live)")

        except Exception as e:
            logger.error(f"Ошибка обновления: {e}")

    @app_commands.command(name="выброс", description="Показать выброс")
    async def emission(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = await self.get_emission()

        if not data:
            return await interaction.followup.send("❌ Ошибка API")

        embed = self.build_embed(data)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Stalcraft(bot))