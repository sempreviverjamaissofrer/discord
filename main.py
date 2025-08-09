import os
import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime
from aiohttp import web
import threading

DATABASE = "call_times.db"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="mg!", intents=intents)

# ----- Banco de dados: criar tabelas async -----
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS call_times (
                guild_id TEXT,
                user_id TEXT,
                total_seconds INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS active_sessions (
                guild_id TEXT,
                user_id TEXT,
                start_time TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.commit()

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="O ZZ BH É NOIS MANO!"))

@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = str(member.guild.id)
    user_id = str(member.id)

    async with aiosqlite.connect(DATABASE) as db:
        if after.channel and not before.channel:
            # Entrou na call
            await db.execute("INSERT OR REPLACE INTO active_sessions VALUES (?, ?, ?)",
                             (guild_id, user_id, datetime.utcnow().isoformat()))
            await db.commit()

        elif before.channel and not after.channel:
            # Saiu da call
            async with db.execute("SELECT start_time FROM active_sessions WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    start_time = datetime.fromisoformat(row[0])
                    tempo_na_call = int((datetime.utcnow() - start_time).total_seconds())

                    await db.execute("INSERT OR IGNORE INTO call_times (guild_id, user_id, total_seconds) VALUES (?, ?, 0)", (guild_id, user_id))
                    await db.execute("UPDATE call_times SET total_seconds = total_seconds + ? WHERE guild_id = ? AND user_id = ?", (tempo_na_call, guild_id, user_id))
                    await db.execute("DELETE FROM active_sessions WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
                    await db.commit()

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    async with aiosqlite.connect(DATABASE) as db:
        # Pega tempo total acumulado
        async with db.execute("SELECT total_seconds FROM call_times WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cursor:
            row = await cursor.fetchone()
            total_seconds = row[0] if row else 0

        # Se está em call, soma tempo atual
        async with db.execute("SELECT start_time FROM active_sessions WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cursor:
            active_row = await cursor.fetchone()
            if active_row:
                start_time = datetime.fromisoformat(active_row[0])
                total_seconds += int((datetime.utcnow() - start_time).total_seconds())

    horas = total_seconds // 3600
    minutos = (total_seconds % 3600) // 60
    segundos = total_seconds % 60

    embed = discord.Embed(title=f"Informações de {member}", color=discord.Color.blue())
    embed.add_field(name="Tempo total em call", value=f"{horas}h {minutos}m {segundos}s")

    await ctx.send(embed=embed)

# ----- Servidor HTTP simples para "ping" -----
async def handle_ping(request):
    return web.Response(text="pong")

app = web.Application()
app.router.add_get('/', handle_ping)

def run_web():
    web.run_app(app, port=int(os.environ.get("PORT", 8080)))

# Rodar o servidor HTTP numa thread separada
threading.Thread(target=run_web, daemon=True).start()

# Inicializar banco antes de rodar o bot
import asyncio
asyncio.run(init_db())

bot.run(os.getenv("TOKEN"))