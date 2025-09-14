import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from github import Github

# Список вопросов для вступления
QUESTIONS = [
    "Какой стиль игры тебе больше всего нравится (агрессивный, стратегический, поддержка и т. д.)?",
    "Есть ли у тебя опыт командной работы и как ты решаешь конфликты в команде?",
    "Как ты предпочитаешь получать информацию о клановых активностях и новостях?",
    "Как часто ты планируешь быть активным в клане?",
    "Как ты обычно справляешься с агрессией или неудачами в игре?",
    "Ты предпочитаешь играть в одиночку или в команде? Почему?",
    "Как ты относишься к критике и каким образом ты обычно её воспринимаешь?",
    "Какие у тебя ожидания от общения с другими членами клана?",
    "В какое время тебе удобно играть?",
    "Боитесь ли вы незнакомых людей и тревожить их?",
    "Ваша цель вступления в клан?",
    "Какая ваша страна проживания и какой у вас часовой пояс?"
]

def push_to_github(user_name, answers):
    """Сохраняет заявку в репозиторий GitHub в папку applications/"""
    token = os.getenv("MY_GITHUB_TOKEN")
    repo_name = os.getenv("REPO_NAME", "Legion-Of-The-Damned/-VS-Data-Base")
    
    if not token:
        print("GitHub token не найден!")
        return
    
    g = Github(token)
    repo = g.get_repo(repo_name)
    
    folder_path = "applications"  # фиксированная папка для всех заявок
    
    # Формируем контент
    content = f"Пользователь: {user_name}\nДата: {datetime.utcnow()}\n\n"
    for i, answer in enumerate(answers, start=1):
        content += f"Вопрос {i}: {answer}\n"
    
    # Имя файла: user_метка_времени.txt
    file_name = f"{folder_path}/{user_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.txt"
    
    try:
        repo.create_file(file_name, f"Новая заявка от {user_name}", content)
        print(f"Заявка {user_name} успешно загружена на GitHub в {file_name}")
    except Exception as e:
        print(f"Ошибка при загрузке на GitHub: {e}")

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.APPLICATIONS_CHANNEL_ID = 1362357361863295199
        self.MEMBER_ROLE_NAME = "💀Легион Проклятых🔥"
        self.OLD_ROLE_NAME = "🤝Друг клана🚩"

    async def is_staff(self, interaction: discord.Interaction):
        """Проверка, является ли пользователь администратором или модератором"""
        if interaction.user.guild_permissions.administrator:
            return True
        
        staff_role = discord.utils.get(interaction.guild.roles, name="Модератор")
        if staff_role and staff_role in interaction.user.roles:
            return True
            
        raise app_commands.MissingPermissions(["administrator"])

    @app_commands.command(name="заявка", description="Подать заявку на вступление")
    async def application(self, interaction: discord.Interaction):
        """Пошаговое создание заявки через ЛС или сервер"""
        try:
            answers = []

            if isinstance(interaction.channel, discord.DMChannel) or interaction.guild is None:
                channel = interaction.user
            else:
                try:
                    channel = await interaction.user.create_dm()
                except:
                    return await interaction.response.send_message(
                        "❌ Не удалось отправить ЛС. Разрешите личные сообщения от участников сервера.",
                        ephemeral=True
                    )

            await interaction.response.send_message(
                "📩 Я отправил тебе личные сообщения с вопросами для заявки!", ephemeral=True
            )

            for question in QUESTIONS:
                await channel.send(f"{question}")

                def check(m):
                    return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=300)
                    answers.append(msg.content)
                except:
                    await channel.send("⏰ Время на ответ истекло. Пожалуйста, попробуй снова командой /заявка.")
                    return

            # Отправка заявки в канал Discord
            application_channel = self.bot.get_channel(self.APPLICATIONS_CHANNEL_ID)
            if not isinstance(application_channel, discord.TextChannel):
                return await channel.send("❌ Ошибка: канал для заявок не настроен!")

            embed = discord.Embed(
                title="📄 Новая заявка",
                description=f"**Пользователь:** {interaction.user.mention}",
                color=discord.Color.blue()
            )

            for i, answer in enumerate(answers):
                embed.add_field(name=f"Вопрос {i+1}", value=answer, inline=False)

            embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

            msg = await application_channel.send(embed=embed)
            await msg.add_reaction('✅')
            await msg.add_reaction('❌')

            await channel.send("✅ Ваша заявка отправлена на рассмотрение!")

            # Отправка заявки в GitHub
            push_to_github(str(interaction.user), answers)
        
        except Exception as e:
            print(f"Ошибка в команде заявка: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке заявки.", ephemeral=True
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Обработка реакций на заявки"""
        try:
            if payload.channel_id != self.APPLICATIONS_CHANNEL_ID:
                return
            
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
            
            member = guild.get_member(payload.user_id)
            if not member or member.bot:
                return
            
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return
            
            message = await channel.fetch_message(payload.message_id)
            if not message.embeds:
                return
            
            if not (member.guild_permissions.administrator or 
                   any(role.name == "Модератор" for role in member.roles)):
                return
            
            embed = message.embeds[0]
            if not embed.footer or not embed.footer.text:
                return
                
            footer_parts = embed.footer.text.split("ID пользователя: ")
            if len(footer_parts) < 2:
                return
                
            try:
                user_id = int(footer_parts[1])
            except ValueError:
                return
                
            target_member = guild.get_member(user_id)
            if not target_member:
                return

            old_role = discord.utils.get(guild.roles, name=self.OLD_ROLE_NAME)
            new_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE_NAME)
            
            if str(payload.emoji) == '✅':
                if old_role in target_member.roles:
                    await target_member.remove_roles(old_role)
                if new_role:
                    await target_member.add_roles(new_role)

                await message.delete()
                try:
                    await target_member.send('🎉 Ваша заявка была одобрена! Добро пожаловать в клан!')
                except:
                    pass
            
            elif str(payload.emoji) == '❌':
                try:
                    await target_member.send('😕 Ваша заявка была отклонена модератором.')
                except:
                    pass
                
        except Exception as e:
            print(f"Ошибка в обработке реакций: {e}")

async def setup(bot):
    await bot.add_cog(Applications(bot))
