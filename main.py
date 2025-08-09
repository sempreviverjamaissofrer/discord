import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import os
import aiosqlite

# Conectar ou criar banco de dados
conn = sqlite3.connect("call_times.db")
c = conn.cursor()

# Tabela para armazenar o tempo total
c.execute('''
CREATE TABLE IF NOT EXISTS call_times (
    guild_id TEXT,
    user_id TEXT,
    total_seconds INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
''')

# Tabela para armazenar sessões ativas
c.execute('''
CREATE TABLE IF NOT EXISTS active_sessions (
    guild_id TEXT,
    user_id TEXT,
    start_time TEXT,
    PRIMARY KEY (guild_id, user_id)
)
''')

conn.commit()

# Configuração do bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="mg!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    # Setar atividade do bot Ouvindo
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="O ZZ BH É NOIS MANO!"))

@bot.event
async def on_voice_state_update(member, before, after):
    async with aiosqlite.connect("call_times.db") as db:
        guild_id = str(member.guild.id)
        user_id = str(member.id)

        # Entrou na call
        if after.channel and not before.channel:
            c.execute("INSERT OR REPLACE INTO active_sessions VALUES (?, ?, ?)",
                    (guild_id, user_id, datetime.utcnow().isoformat()))
            conn.commit()

        # Saiu da call
        elif before.channel and not after.channel:
            c.execute("SELECT start_time FROM active_sessions WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id))
            row = c.fetchone()
            if row:
                start_time = datetime.fromisoformat(row[0])
                tempo_na_call = int((datetime.utcnow() - start_time).total_seconds())

                c.execute("INSERT OR IGNORE INTO call_times (guild_id, user_id, total_seconds) VALUES (?, ?, 0)",
                        (guild_id, user_id))
                c.execute("UPDATE call_times SET total_seconds = total_seconds + ? WHERE guild_id = ? AND user_id = ?",
                        (tempo_na_call, guild_id, user_id))
                c.execute("DELETE FROM active_sessions WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id))
                conn.commit()

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    # 1️⃣ Pega o tempo total acumulado
    c.execute("SELECT total_seconds FROM call_times WHERE guild_id = ? AND user_id = ?",
              (guild_id, user_id))
    row = c.fetchone()
    total_seconds = row[0] if row else 0

    # 2️⃣ Se a pessoa está em call, soma o tempo desde que entrou
    c.execute("SELECT start_time FROM active_sessions WHERE guild_id = ? AND user_id = ?",
              (guild_id, user_id))
    active_row = c.fetchone()
    if active_row:
        start_time = datetime.fromisoformat(active_row[0])
        total_seconds += int((datetime.utcnow() - start_time).total_seconds())

    # 3️⃣ Formata para horas/minutos/segundos
    horas = total_seconds // 3600
    minutos = (total_seconds % 3600) // 60
    segundos = total_seconds % 60

    embed = discord.Embed(title=f"Informações de {member}", color=discord.Color.blue())
    embed.add_field(name="Tempo total em call", value=f"{horas}h {minutos}m {segundos}s")

    await ctx.send(embed=embed)

bot.run(os.getenv("TOKEN"))