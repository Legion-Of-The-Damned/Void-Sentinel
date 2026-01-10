import asyncio
import logging
from datetime import datetime
from supabase import create_client, Client
from config import load_config
import re

logger = logging.getLogger("supabase_data")

# --- Конфигурация Supabase ---
config = load_config()
SUPABASE_URL = config["SUPABASE_URL"]
SUPABASE_KEY = config["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Глобальные переменные ---
stats = {}          # ключи — нормализованные имена (без префиксов)
active_duels = {}   # ключи — "player1ID-player2ID"

# --- Вспомогательные функции ---
def key_from_name(name: str) -> str:
    """Возвращает ключ для stats без префиксов, в нижнем регистре"""
    return re.sub(r"\[.*?\]\s*", "", name).lower()

async def get_username_by_id(bot, user_id: int) -> str:
    try:
        user = await bot.fetch_user(user_id)
        return str(user)  # username#discriminator
    except Exception:
        return str(user_id)

# --- Загрузка данных из Supabase ---
async def load_data():
    global stats, active_duels
    try:
        # --- Активные дуэли ---
        resp_duels = supabase.table("active_duels").select("*").execute()
        for duel in resp_duels.data:
            player1_name = duel.get("Игрок 1")
            player2_name = duel.get("Игрок 2")
            player1_id = duel.get("Игрок 1 ID")
            player2_id = duel.get("Игрок 2 ID")

            duel_id = f"{player1_id or player1_name}-{player2_id or player2_name}"

            active_duels[duel_id] = {
                # универсальные ключи для старого и нового кода
                "player1": player1_name,
                "player2": player2_name,
                "challenger_id": int(player1_id) if player1_id else None,
                "opponent_id": int(player2_id) if player2_id else None,
                "game": duel.get("Игра"),
                "time": duel.get("Время"),
                "status": duel.get("Статус"),
                "start_time": duel.get("Время начала")
            }

        # --- Статистика ---
        resp_stats = supabase.table("duel_stats").select("*").execute()
        for row in resp_stats.data:
            user_name = row["Игрок"]
            user_key = key_from_name(user_name)
            stats[user_key] = {
                "display_name": user_name,
                "wins": int(row["Побед"]),
                "losses": int(row["Поражений"]),
                "total": int(row["Всего"])
            }

        logger.info("✅ Данные из Supabase загружены")
    except Exception as e:
        logger.error(f"⚠️ Ошибка загрузки данных из Supabase: {e}")

async def save_duel_to_db(duel, bot):
    player1_name = duel.get("player1") or str(duel.get("challenger_id"))
    player2_name = duel.get("player2") or str(duel.get("opponent_id"))

    if not player1_name or not player2_name:
        logger.error(f"⚠️ Недостаточно игроков для сохранения дуэли: {duel}")
        return

    status = duel.get("status", "active")
    start_time_raw = duel.get("start_time")
    try:
        start_time = datetime.fromisoformat(start_time_raw).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        start_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    data_to_save = {
        "Игрок 1": player1_name,
        "Игрок 2": player2_name,
        "Игра": duel.get("game", "Не указано"),
        "Время": duel.get("time", "Не указано"),
        "Статус": status,
        "Время начала": start_time
    }

    try:
        supabase.table("active_duels").upsert(
            data_to_save,
            on_conflict=["Игрок 1", "Игрок 2"]
        ).execute()
        logger.info(f"💾 Дуэль {player1_name} vs {player2_name} сохранена в Supabase")
    except Exception as e:
        logger.error(f"⚠️ Ошибка при сохранении дуэли в Supabase: {e}")

# --- Обновление статистики после дуэли ---
def update_stats(winner_name, loser_name):
    global stats
    winner_key = key_from_name(winner_name)
    loser_key = key_from_name(loser_name)

    # Инициализация при необходимости
    if winner_key not in stats:
        stats[winner_key] = {"display_name": winner_name, "wins": 0, "losses": 0, "total": 0}
    if loser_key not in stats:
        stats[loser_key] = {"display_name": loser_name, "wins": 0, "losses": 0, "total": 0}

    # Обновление счетчиков
    stats[winner_key]["wins"] = int(stats[winner_key]["wins"]) + 1
    stats[loser_key]["losses"] = int(stats[loser_key]["losses"]) + 1
    stats[winner_key]["total"] = stats[winner_key]["wins"] + stats[winner_key]["losses"]
    stats[loser_key]["total"] = stats[loser_key]["wins"] + stats[loser_key]["losses"]

    # Асинхронное сохранение в Supabase
    asyncio.create_task(save_stats_to_db(winner_key, loser_key))

# --- Сохранение статистики ---
async def save_stats_to_db(winner_key, loser_key):
    winner = stats[winner_key]
    loser = stats[loser_key]

    try:
        supabase.table("duel_stats").upsert({
            "Игрок": winner["display_name"],
            "Побед": int(winner["wins"]),
            "Поражений": int(winner["losses"]),
            "Всего": int(winner["total"])
        }, on_conflict=["Игрок"]).execute()

        supabase.table("duel_stats").upsert({
            "Игрок": loser["display_name"],
            "Побед": int(loser["wins"]),
            "Поражений": int(loser["losses"]),
            "Всего": int(loser["total"])
        }, on_conflict=["Игрок"]).execute()

        logger.info(f"💾 Статистика игроков {winner['display_name']} и {loser['display_name']} сохранена в Supabase")
    except Exception as e:
        logger.error(f"⚠️ Ошибка сохранения статистики в Supabase: {e}")

# --- Совместимость: функция save_active_duels ---
async def save_active_duels(bot):
    """
    Совместимость для старых модулей.
    Сохраняет все активные дуэли в базу данных Supabase.
    """
    from .data import active_duels, save_duel_to_db

    for duel in list(active_duels.values()):
        try:
            await save_duel_to_db(duel, bot)
        except Exception as e:
            print(f"[save_active_duels] Ошибка при сохранении дуэли {duel.get('id', 'unknown')}: {e}")

# --- Получение статистики ---
async def get_stats():
    return stats

async def get_active_duels():
    return active_duels
