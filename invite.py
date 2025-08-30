import discord
from discord import app_commands
from discord.ext import commands

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.APPLICATIONS_CHANNEL_ID = 1362357361863295199
        self.MEMBER_ROLE_ID = 1151988594148376709

    async def is_staff(self, interaction: discord.Interaction):
        """Проверка, является ли пользователь администратором или модератором"""
        if interaction.user.guild_permissions.administrator:
            return True
        
        staff_role = discord.utils.get(interaction.guild.roles, name="Модератор")
        if staff_role and staff_role in interaction.user.roles:
            return True
            
        raise app_commands.MissingPermissions(["administrator"])

    @app_commands.command(name="заявка", description="Подать заявку на вступление")
    async def application(self, interaction: discord.Interaction, сообщение: str = "Хочу присоединиться!"):
        """Отправляет заявку на рассмотрение"""
        try:
            application_channel = self.bot.get_channel(self.APPLICATIONS_CHANNEL_ID)
            
            if not isinstance(application_channel, discord.TextChannel):
                return await interaction.response.send_message("Ошибка: канал для заявок не настроен!", ephemeral=True)
            
            if interaction.channel == application_channel:
                return await interaction.response.send_message("Вы уже находитесь в канале для заявок!", ephemeral=True)
            
            embed = discord.Embed(
                title="📄 Новая заявка",
                description=f"**Пользователь:** {interaction.user.mention}\n**Сообщение:** {сообщение}",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
            
            msg = await application_channel.send(embed=embed)
            await msg.add_reaction('✅')
            await msg.add_reaction('❌')
            await interaction.response.send_message("✅ Ваша заявка отправлена на рассмотрение!", ephemeral=True)
            
        except Exception as e:
            print(f"Ошибка в команде заявка: {e}")
            await interaction.response.send_message("Произошла ошибка при отправке заявки", ephemeral=True)

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
            
            # Проверка прав пользователя
            if not (member.guild_permissions.administrator or 
                   any(role.name == "Модератор" for role in member.roles)):
                return
            
            embed = message.embeds[0]
            if not embed.footer or not embed.footer.text:
                return
                
            # Извлечение ID пользователя
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
            
            role = guild.get_role(self.MEMBER_ROLE_ID)
            if not role:
                return
            
            if str(payload.emoji) == '✅':
                await target_member.add_roles(role)
                await message.delete()
                try:
                    await target_member.send('🎉 Ваша заявка была одобрена! Добро пожаловать на сервер!')
                except:
                    pass
            
            elif str(payload.emoji) == '❌':
                try:
                    await target_member.send('😕 Ваша заявка была отклонена модератором.')
                except:
                    pass
                # Убрано удаление сообщения при отклонении
                
        except Exception as e:
            print(f"Ошибка в обработке реакций: {e}")

async def setup(bot):
    await bot.add_cog(Applications(bot))