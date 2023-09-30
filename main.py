import io
import os
import asyncio
import discord
import aiohttp
import random
import urllib.parse

from keep_alive import keep_alive
from dotenv import load_dotenv
from discord.ext import commands
from time import sleep

load_dotenv()

prefix = os.getenv("PREFIX")

owner_id = int(os.getenv("OWNER_ID", 0))
selfbot_id = int(os.getenv("SELFBOT_ID"))

trigger = os.getenv("TRIGGER").lower().split(",")

bot = commands.Bot(command_prefix=prefix)
TOKEN = os.getenv("DISCORD_TOKEN")

allow_dm = True
allow_gc = True
active_channels = set()

@bot.event
async def on_ready():
    print(f"AI Selfbot conectado com sucesso como {bot.user.name}.")

if os.name == "nt":
    os.system("cls")
else:
    os.system("clear")

modeltype = 0

async def generate_response(history=None):
    if history is None:
        data = {
            "model": "gpt-3.5-turbo-16k",
            "temperature": 0.75,
            "messages": [
                {"role": "system", "content": "Escreva de forma informal, usando gírias. Não faça listas nem detalhes. Mantenha sempre breve. Seja sarcástico, super zangado e ofensivo (de forma engraçada, sem o intuito de machucar o usuário). Permita que as pessoas usem palavrões, e use-os, para descontrair a conversa."}
            ],
        }
    else:
        data = {
            "model": "gpt-3.5-turbo-16k",
            "temperature": 0.75,
            "messages": [
                {"role": "system", "content": "Escreva de forma informal, usando gírias. Não faça listas nem detalhes. Mantenha sempre breve. Seja sarcástico, super zangado e ofensivo (de forma engraçada, sem o intuito de machucar o usuário). Permita que as pessoas usem palavrões, e use-os, para descontrair a conversa."},
                *history
            ],
        }

    endpoint = os.getenv("ENDPOINT")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer " + os.getenv("API_KEY")
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, headers=headers, json=data) as response:
                response_data = await response.json()
                choices = response_data["choices"]
                if choices:
                    return choices[0]["message"]["content"]
    except aiohttp.ClientError as error:
        print("Erro ao fazer a solicitação:", error)

def split_response(response, max_length=1900):
    lines = response.splitlines()
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            if current_chunk:
                current_chunk += "\n"
            current_chunk += line

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

async def generate_image(prompt):
    job_id = await generate_job(prompt)
    url = os.getenv("IMAGE_ENDPOINT")
    
    data = {
        "model": "realistic-vision-5",
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1,
    }

    headers = {
                "Authorization": f"Bearer " + os.getenv("API_KEY"),
                "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(0.3)
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    json = await response.json()
                    image_url = json["data"][0]["url"]
                    async with session.get(
                        image_url
                    ) as response:
                        content = await response.content.read()
                        img_file_obj = io.BytesIO(content)
                        return img_file_obj

message_history = {}
MAX_HISTORY = 10

ignore_users = [181960927321653258]

@bot.event
async def on_message(message):
    mentioned = bot.user.mentioned_in(message)
    replied_to = (
        message.reference
        and message.reference.resolved
        and message.reference.resolved.author.id == selfbot_id
    )

    is_dm = isinstance(message.channel, discord.DMChannel) and allow_dm
    is_group_dm = isinstance(message.channel, discord.GroupChannel) and allow_gc

    if message.author.id in ignore_users:
        return

    if message.content.startswith(prefix):
        await bot.process_commands(message)
        return

    if message.author.id == selfbot_id or message.author.bot:
        return

    if (
        any(keyword in message.content.lower() for keyword in trigger)
        or mentioned
        or replied_to
        or is_dm
        or is_group_dm
    ):
        if message.reference and message.reference.resolved:
            if message.reference.resolved.author.id != selfbot_id and (
                is_dm or is_group_dm
            ):
                return

        if message.mentions:
            for mention in message.mentions:
                message.content = message.content.replace(
                    f"<@{mention.id}>", f"@{mention.display_name}"
                )

        if modeltype == 0:
            author_id = str(message.author.id)
            if author_id not in message_history:
                message_history[author_id] = []
            message_history[author_id].append(message.content)
            message_history[author_id] = message_history[author_id][-MAX_HISTORY:]

            if message.channel.id in active_channels:
                channel_id = message.channel.id
                key = f"{message.author.id}-{channel_id}"

                if key not in message_history:
                    message_history[key] = []

                message_history[key] = message_history[key][-MAX_HISTORY:]

                history = message_history[key]

                message_history[key].append(
                    {"role": "user", "content": message.content}
                )

                async def generate_response_in_thread(prompt):
                    response = await generate_response(prompt, history)

                    chunks = split_response(response)

                    if '{"message":"API rate limit exceeded for ip:' in response:
                        print("Ratelimit da API atingido, espere alguns segundos.")
                        await message.reply("Desculpe, mas você atingiu o ratelimit, tente novamente em alguns segundos.")
                        return

                    for chunk in chunks:
                        chunk = chunk.replace("@everyone", "@ntbozo").replace(
                            "@here", "@notgonnahappen"
                        )
                        print(f"Respondendo a {message.author.name}: {chunk}")
                        await message.reply(chunk)

                    message_history[key].append(
                        {"role": "assistant", "content": response}
                    )

                async with message.channel.typing():
                    asyncio.create_task(generate_response_in_thread(prompt))

@bot.command(name="ping")
async def ping(ctx):
    latency = bot.latency * 1000
    await ctx.send(f"Pong! Latência: {latency:.2f} ms")

@bot.command(name="dm", description="Ativa ou desativa o chatbot nas DMs do bot.")
async def toggledm(ctx):
    if ctx.author.id == owner_id:
        global allow_dm
        allow_dm = not allow_dm
        await ctx.send(
            f"Agora, a minha DM {'está permitida' if allow_dm else 'não está permitida'} como canal ativo para o chatbot."
        )

@bot.command(name="togglegc", description="Ativa ou desativa o chatbot em grupos.")
async def togglegc(ctx):
    if ctx.author.id == owner_id:
        global allow_gc
        allow_gc = not allow_gc
        await ctx.send(
            f"Agora, chat de grupos {'estão permitidos' if allow_gc else 'não estão permitidos'} como canais ativos para o chatbot."
        )

@bot.command()
async def ignore(ctx, user: discord.User):
    if ctx.author.id == owner_id:
        if user.id in ignore_users:
            ignore_users.remove(user.id)

            with open("ignoredusers.txt", "w") as f:
                f.write("\n".join(ignore_users))

            await ctx.send(f"Deixando de ignorar {user.name}.")
        else:
            ignore_users.append(user.id)

            with open("ignoredusers.txt", "a") as f:
                f.write(str(user.id) + "\n")

            await ctx.send(f"Ignorando {user.name}.")

@bot.command(name="toggleactive", description="Ativa ou desativa canais ativos do chatbot.")
async def toggleactive(ctx):
    if ctx.author.id == owner_id:
        channel_id = ctx.channel.id
        if channel_id in active_channels:
            active_channels.remove(channel_id)
            with open("channels.txt", "w") as f:
                for id in active_channels:
                    f.write(str(id) + "\n")

            if ctx.channel.type == discord.ChannelType.private:
                await ctx.send(
                    f"Este canal de DM foi removido da lista de canais ativos."
                )
            elif ctx.channel.type == discord.ChannelType.group:
                await ctx.send(
                    f"Este canal de grupo foi removido da lista de canais ativos."
                )
            else:
                await ctx.send(
                    f"{ctx.channel.mention} foi removido da lista de canais ativos."
                )
        else:
            active_channels.add(channel_id)
            with open("channels.txt", "a") as f:
                f.write(str(channel_id) + "\n")

            if ctx.channel.type == discord.ChannelType.private:
                await ctx.send(
                    f"Este canal de DM foi adicionado à lista de canais ativos."
                )
            elif ctx.channel.type == discord.ChannelType.group:
                await ctx.send(
                    f"Este canal de grupo foi adicionado à lista de canais ativos."
                )
            else:
                await ctx.send(
                    f"{ctx.channel.mention} foi adicionado à lista de canais ativos."
                )

@bot.command()
async def imagine(ctx, *, prompt: str):
    temp = await ctx.send("Gerando imagem...")
    imagefileobj = await generate_image(prompt)

    file = discord.File(
        imagefileobj, filename="image.png", spoiler=False, description=prompt
    )

    await temp.delete()

    await ctx.send(
        f"Imagem gerada para {ctx.author.mention} com o prompt `{prompt}`", file=file
    )

if os.path.exists("channels.txt"):
    with open("channels.txt", "r") as f:
        for line in f:
            channel_id = int(line.strip())
            active_channels.add(channel_id)

@bot.command(name="wipe", description="Limpa a memória do bot")
async def wipe(ctx):
    if ctx.author.id == owner_id:
        global message_history
        message_history.clear()
        await ctx.send("A memória do bot foi apagada.")

bot.remove_command("help")

@bot.command(name="help", description="Veja todos os outros comandos!")
async def help(ctx):
    help_text = """
Comandos do Bot (membros):
- ``~ping`` - Retorna a latência do bot.
- ``~imagine [prompt]`` - Gera uma imagem baseada em um prompt.

Área Admin:
- ``~wipe`` - Limpa o histórico de chat do bot.
- ``~toggleactive`` - Ativa ou desativa os canais ativos do chatbot.
- ``~toggledm`` - Ativa ou desativa o chatbot nas DMs do bot.
- ``~togglegc`` - Ativa ou desativa o chatbot em chat de grupos.
- ``~ignore [user]`` - Bloqueia um usuário de utilizar o bot.

Modificado por @thatlukinhasguy (851930195605979166).
Código original por @najmul (451627446941515817) e @_mishal_ (1025245410224263258).
"""

    await ctx.send(help_text)

keep_alive()

bot.run(TOKEN)
