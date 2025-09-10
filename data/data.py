import json
import base64
import asyncio
from github import Github
from config import load_config

# --- Конфигурация GitHub ---
config = load_config()
GITHUB_TOKEN = config["GITHUB_TOKEN"]
REPO_NAME = config["REPO_NAME"]

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# --- Глобальные переменные ---
stats = {}
active_duels = {}

# --- Работа с GitHub ---
def load_github_json(filename):
    try:
        contents = repo.get_contents(filename)
        decoded = base64.b64decode(contents.content).decode("utf-8")
        return json.loads(decoded)
    except Exception as e:
        print(f"[ERROR] Ошибка загрузки {filename}: {e}")
        return {}

def save_github_json(filename, data, commit_message="Обновление данных"):
    json_data = json.dumps(data, indent=4, ensure_ascii=False)
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, commit_message, json_data, contents.sha)
    except Exception as e:
        if "404" in str(e) or "Not Found" in str(e):
            try:
                repo.create_file(filename, commit_message, json_data)
            except Exception as err:
                print(f"[ERROR] Ошибка создания файла {filename}: {err}")
        elif "409" in str(e):
            try:
                contents = repo.get_contents(filename)
                repo.update_file(contents.path, commit_message, json_data, contents.sha)
            except Exception as err:
                print(f"[ERROR] Ошибка повторного обновления {filename}: {err}")
        else:
            print(f"[ERROR] Ошибка сохранения {filename}: {e}")

async def async_load_json(filename):
    return await asyncio.to_thread(load_github_json, filename)

async def async_save_json(filename, data, commit_message="Обновление данных"):
    await asyncio.to_thread(save_github_json, filename, data, commit_message)

# --- Загрузка данных ---
async def load_data():
    global stats, active_duels
    new_stats = await async_load_json("duel_stats.json")
    stats.clear()
    stats.update(new_stats)

    new_active = await async_load_json("active_duels.json")
    active_duels.clear()
    active_duels.update(new_active)

# --- Сохранение данных ---
async def save_stats():
    global stats
    try:
        await async_save_json("duel_stats.json", stats, "Обновление статистики дуэлей")
    except Exception as e:
        print(f"[ERROR] Ошибка сохранения статистики: {e}")

async def save_active_duels():
    global active_duels
    try:
        await async_save_json("active_duels.json", active_duels, "Обновление активных дуэлей")
    except Exception as e:
        print(f"[ERROR] Ошибка сохранения активных дуэлей: {e}")

# --- Обновление статистики после дуэли ---
def update_stats(winner_id, loser_id):
    global stats
    winner_id = str(winner_id)
    loser_id = str(loser_id)

    if winner_id not in stats:
        stats[winner_id] = {"wins": 0, "losses": 0}
    if loser_id not in stats:
        stats[loser_id] = {"wins": 0, "losses": 0}

    stats[winner_id]["wins"] += 1
    stats[loser_id]["losses"] += 1

    # Асинхронно сохраняем статистику
    asyncio.create_task(save_stats())
