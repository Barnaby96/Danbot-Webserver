import os

import discord


from cogs.AdminCog import AdminCog
from cogs.SubmitRequestCog import SubmitRequestCog
from cogs.UserCog import UserCog
from discord.ext import commands

approved_guilds = {
    int(guild_id.strip())
    for guild_id in os.getenv("APPROVED_GUILD_IDS", "").split(",")
    if guild_id.strip()
}

bot = discord.Bot(debug_guilds=list(approved_guilds))
token = os.getenv('DISCORD_BOT_TOKEN')


@bot.event
async def on_guild_join(guild):
    if guild.id not in approved_guilds:
        await guild.leave()




def run():
    bot.add_cog(UserCog(bot))
    bot.add_cog(AdminCog(bot))
    bot.add_cog(SubmitRequestCog(bot))
    bot.run(token)

