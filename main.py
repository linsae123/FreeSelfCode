import disnake
from disnake.ext import commands
import discord
from discord.ext import commands as dcommands
import json
import os
import asyncio
import sys
import aiohttp
import datetime
from bs4 import BeautifulSoup
import platform
import re
from urllib.parse import urlparse, quote
import asyncio.subprocess as asp
import ast
import operator
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 봇 토큰 로드
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ DISCORD_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
    print("❌ .env 파일을 생성하고 DISCORD_BOT_TOKEN=your_token_here를 추가하세요.")
    sys.exit(1)

USER_DATA_FILE = "user_data.json"

# 허용된 사용자 ID (환경변수에서 로드 가능)
ALLOWED_USERS = [int(id.strip()) for id in os.getenv('ALLOWED_USERS', '1017075940460875836').split(',')]

# IP 보호 설정
PROTECTED_IPS = ['127.0.0.1', 'localhost', '0.0.0.0', '::1']
PRIVATE_NETWORKS = [
    r'^192\.168\.',
    r'^10\.',
    r'^172\.(1[6-9]|2[0-9]|3[0-1])\.'
]

# 안전한 계산기 클래스
class SafeCalculator:
    def __init__(self):
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }
    
    def safe_eval(self, expr):
        try:
            # 허용된 문자만 체크
            allowed_chars = set('0123456789+-*/(). ')
            if not all(c in allowed_chars for c in expr):
                raise ValueError("허용되지 않는 문자가 포함되어 있습니다")
            
            # AST로 파싱하여 안전성 검증
            tree = ast.parse(expr, mode='eval')
            
            # 허용된 노드 타입만 체크
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant)):
                    raise ValueError("허용되지 않는 연산이 포함되어 있습니다")
            
            return self._eval_node(tree.body)
        except Exception as e:
            raise ValueError(f"수식 계산 오류: {str(e)}")
    
    def _eval_node(self, node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self.operators.get(type(node.op))
            if op is None:
                raise ValueError("지원하지 않는 연산자입니다")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op = self.operators.get(type(node.op))
            if op is None:
                raise ValueError("지원하지 않는 연산자입니다")
            return op(operand)
        else:
            raise ValueError("지원하지 않는 수식입니다")

# 전역 계산기 인스턴스
calculator = SafeCalculator()

# 사용자 데이터 파일 초기화
if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=4)

# IP 주소 검증 함수
def is_protected_ip(ip):
    """보호된 IP 주소인지 확인"""
    if ip.lower() in [p.lower() for p in PROTECTED_IPS]:
        return True
    
    # 내부 네트워크 IP 체크
    for pattern in PRIVATE_NETWORKS:
        if re.match(pattern, ip):
            return True
    
    return False

# 토큰 검증 함수
async def validate_token(token):
    """토큰 유효성 검증"""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": token}
        try:
            async with session.get("https://discord.com/api/v9/users/@me", headers=headers) as r:
                return r.status == 200
        except:
            return False

# 토큰 정보 조회 함수
async def get_token_info(token):
    """토큰 정보 조회"""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": token}
        try:
            async with session.get("https://discord.com/api/v9/users/@me", headers=headers) as r:
                if r.status == 200:
                    user_data = await r.json()
                    return {
                        "email": user_data.get("email", "없음"),
                        "phone": user_data.get("phone", "없음"),
                        "valid": True
                    }
                return {"valid": False}
        except:
            return {"valid": False}

class SelfBot(dcommands.Bot):
    def __init__(self, account, status, parent_bot, user_id):
        super().__init__(command_prefix="s.", self_bot=True)
        self.account = account
        self.status_message = status
        self.parent_bot = parent_bot
        self.user_id = user_id
        self.active_spam_tasks = {}
        
        # 명령어 등록
        self.setup_commands()
    
    def setup_commands(self):
        @self.command(name="도움말")
        async def help_command(ctx):
            if ctx.author != self.user:
                return
                
            help_text = """
```css
[-] - Free SelfBot (보안 강화 버전)

[+] s.핑 - 현재 핑을 출력
[+] s.계좌 - 설정해둔 계좌 출력
[+] s.상메 ( 게임중, 듣는중, 방송중 ) ( 메시지 ) - 상태메시지 변경
[+] s.계산기 ( 수식 ) - 안전한 수식 계산
[+] s.검색 ( 검색어 ) - 구글 검색 결과 표시
[+] s.아이피 ( 외부IP ) - 외부 IP 정보 조회
[+] s.유저정보 ( 유저멘션 ) - 유저 정보 확인

[+] s.청소 ( 청소할 양 ) - 메시지 청소
[+] s.도배 ( 메시지 ) ( 횟수 ) - 메시지 도배 (최대 50회)
[+] s.도배중지 - 도배 중지
```
            """
            await ctx.reply(help_text)

        @self.command(name="핑")
        async def ping_latency(ctx):
            if ctx.author == self.user:
                await ctx.reply(f"> 🏓**{round(self.latency * 1000)}ms**")

        @self.command(name="계좌")
        async def account(ctx):
            if ctx.author == self.user:
                await ctx.reply(f"> 💳 **{self.account}**")
                
        @self.command(name="상메")
        async def change_status(ctx, status_type=None, *, message=None):
            if ctx.author == self.user:
                if status_type is None or message is None:
                    activity = discord.Game(name=self.status_message)
                    await self.change_presence(activity=activity)
                    await ctx.reply(f"> ✅ **상태가 `게임중`으로 변경 되었고 메시지는 `{self.status_message}` 로 설정 되었습니다.**")
                    return

                status_type = status_type.lower()
                if status_type == "게임중":
                    activity = discord.Game(name=message)
                elif status_type == "듣는중":
                    activity = discord.Activity(type=discord.ActivityType.listening, name=message)
                elif status_type == "방송중":
                    activity = discord.Streaming(name=message, url="https://www.twitch.tv/placeholder")
                else:
                    await ctx.reply("> ❌ 올바른 상태 유형이 아닙니다. (게임중, 듣는중, 방송중)")
                    return

                await self.change_presence(activity=activity)
                await ctx.reply(f"> ✅ **상태가 `{status_type}`으로 변경 되었고 메시지는 `{message}` 로 설정 되었습니다.**")

        @self.command(name="계산기")
        async def calculator_cmd(ctx, *, expression: str):
            if ctx.author == self.user:
                try:
                    expression = expression.strip()
                    
                    if not expression:
                        await ctx.reply('⚠️ `수식을 입력해주세요.`')
                        return
                    
                    result = calculator.safe_eval(expression)
                    rounded_result = round(result, 2)
                    await ctx.reply(f'> **결과**: {rounded_result} :abacus:')
                except ValueError as e:
                    await ctx.reply(f'⚠️ `{str(e)}`')
                except Exception as e:
                    await ctx.reply(f'⚠️ `계산 중 오류가 발생했습니다: {str(e)}`')

        @self.command(name="검색")
        async def search(ctx, *, query):
            if ctx.author == self.user:
                # 입력값 검증
                if not query or len(query.strip()) == 0:
                    await ctx.reply("> ❌ 검색어를 입력해주세요.")
                    return
                
                # 검색어 길이 제한
                if len(query) > 100:
                    await ctx.reply("> ❌ 검색어가 너무 깁니다. (최대 100자)")
                    return
                
                query = query.strip()
                
                search_url = f"https://www.google.com/search?q={quote(query)}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status != 200:
                                await ctx.reply("> ❌ 검색 중 오류가 발생했습니다.")
                                return
                                
                            response_text = await response.text()
                            soup = BeautifulSoup(response_text, 'html.parser')

                            results = []
                            for result in soup.find_all('h3', limit=3):
                                parent = result.find_parent('a')
                                if parent:
                                    result_text = result.get_text()
                                    result_link = parent['href']
                                    if len(result_text) > 200:
                                        result_text = result_text[:200] + "..."
                                    results.append(f"`{result_text}`\n{result_link}")

                            if results:
                                result_message = "\n\n".join(results)
                                await ctx.reply(f"```\n{result_message}\n```")
                            else:
                                await ctx.reply("> ❌ 검색 결과를 찾을 수 없습니다.")
                except asyncio.TimeoutError:
                    await ctx.reply("> ❌ 검색 시간이 초과되었습니다.")
                except Exception as e:
                    await ctx.reply("> ❌ 검색 중 오류가 발생했습니다.")

        @self.command(name="아이피")
        async def ip_lookup(ctx, ip_address: str):
            if ctx.author == self.user:
                # 입력값 검증
                if not ip_address or len(ip_address.strip()) == 0:
                    await ctx.reply("> ❌ IP 주소를 입력해주세요.")
                    return
                
                # IP 주소 형식 검증
                ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
                if not re.match(ip_pattern, ip_address):
                    await ctx.reply("> ❌ 유효한 IP 주소 형식이 아닙니다. (예: 8.8.8.8)")
                    return
                
                # IP 주소 범위 검증
                try:
                    parts = ip_address.split('.')
                    for part in parts:
                        if not (0 <= int(part) <= 255):
                            await ctx.reply("> ❌ IP 주소 범위가 올바르지 않습니다.")
                            return
                except ValueError:
                    await ctx.reply("> ❌ 유효한 IP 주소가 아닙니다.")
                    return

                # 보호된 IP 주소 체크
                if is_protected_ip(ip_address):
                    await ctx.reply("> ❌ 보호된 IP 주소입니다. 조회할 수 없습니다.")
                    return

                url = f"http://ipinfo.io/{ip_address}/json"

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status != 200:
                                await ctx.reply("> ❌ IP 정보를 가져오는 중 오류가 발생했습니다.")
                                return
                                
                            data = await response.json()

                    ip = data.get('ip', '정보 없음')
                    city = data.get('city', '정보 없음')
                    region = data.get('region', '정보 없음')
                    country = data.get('country', '정보 없음')
                    location = data.get('loc', '정보 없음')

                    ip_info_message = (
                        f"**> IP 주소**: {ip} :satellite:\n"
                        f"**> 도시**: {city} :cityscape:\n"
                        f"**> 주/지역**: {region} :map:\n"
                        f"**> 국가**: {country} :earth_africa:\n"
                        f"**> 위치**: {location} :round_pushpin:"
                    )
                    await ctx.reply(ip_info_message)
                except asyncio.TimeoutError:
                    await ctx.reply("> ❌ IP 정보 조회 시간이 초과되었습니다.")
                except Exception as e:
                    await ctx.reply("> ❌ IP 정보를 가져오는 중 오류가 발생했습니다.")

        @self.command(name="유저정보")
        async def user_info(ctx, member: discord.Member = None):
            if ctx.author == self.user:
                try:
                    if member is None:
                        member = ctx.author
                        
                    user_name = member.name
                    user_id = member.id
                    avatar_hash = str(member.avatar).split('/')[-1].replace('.png', '') if member.avatar else None
                    avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.webp?size=80" if avatar_hash else "프로필 이미지 없음"

                    user_info_message = (
                        f"**> 유저이름**: {user_name} :bust_in_silhouette:\n"
                        f"**> 유저아이디**: {user_id} :id:\n"
                        f"**> 프로필**: ||{avatar_url}|| :frame_photo:"
                    )

                    await ctx.reply(user_info_message)
                except Exception as e:
                    await ctx.reply(f"> ❌ 오류가 발생했습니다: {str(e)}")

        @self.command(name="청소")
        async def clear_messages(ctx, amount: int):
            if ctx.author == self.user:
                if not isinstance(amount, int) or amount <= 0:
                    try:
                        await ctx.send("> ❌ 올바른 숫자를 입력해주세요.")
                    except:
                        pass
                    return

                deleted = 0
                try:
                    if ctx.guild:
                        if ctx.channel.permissions_for(ctx.author).manage_messages:
                            deleted_messages = await ctx.channel.purge(limit=amount + 1)
                            deleted = len(deleted_messages) - 1  
                        else:
                            async for message in ctx.channel.history(limit=100):
                                if message.author == ctx.author and deleted < amount:
                                    try:
                                        await message.delete()
                                        deleted += 1
                                    except:
                                        continue
                    else:  
                        async for message in ctx.channel.history(limit=100):
                            if message.author == ctx.author and deleted < amount:
                                try:
                                    await message.delete()
                                    deleted += 1
                                except:
                                    continue

                    try:
                        success_msg = await ctx.send(f"> ✅ {deleted}개의 메시지를 삭제했습니다.")
                        await asyncio.sleep(3)
                        await success_msg.delete()
                    except:
                        pass

                except Exception as e:
                    try:
                        await ctx.send("> ❌ 메시지 삭제 중 오류가 발생했습니다.")
                    except:
                        pass

        @self.command(name="도배")
        async def spam(ctx, message: str, count: int):
            if ctx.author == self.user:
                # 입력값 검증
                if not message or len(message.strip()) == 0:
                    await ctx.reply("> ❌ 도배할 메시지를 입력해주세요.")
                    return
                
                # 메시지 길이 제한
                if len(message) > 2000:
                    await ctx.reply("> ❌ 메시지가 너무 깁니다. (최대 2000자)")
                    return
                
                # 도배 횟수 제한
                if count <= 0 or count > 50:
                    await ctx.reply("> ❌ 도배 횟수는 1-50 사이여야 합니다.")
                    return
                
                message = message.strip()
                
                task_id = f"{ctx.channel.id}_{ctx.author.id}"

                if task_id in self.active_spam_tasks:
                    await ctx.send("> ❌ 도배 작업이 **이미 진행 중**입니다. !!도배중지 명령어로 중지해 주세요.")
                    return

                async def spam_task():
                    sent_count = 0
                    for _ in range(count):
                        if task_id not in self.active_spam_tasks:
                            break
                        try:
                            await ctx.send(message)
                            sent_count += 1
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"도배 메시지 전송 실패: {e}")
                            break

                self.active_spam_tasks[task_id] = True
                await ctx.send(f"> ✅ 도배 작업을 **시작합니다** :bomb: (총 {count}회)")

                await spam_task()

                if task_id in self.active_spam_tasks:
                    del self.active_spam_tasks[task_id]

        @self.command(name="도배중지")
        async def stop_spam(ctx):
            if ctx.author == self.user:
                task_id = f"{ctx.channel.id}_{ctx.author.id}"
                
                if task_id in self.active_spam_tasks:
                    del self.active_spam_tasks[task_id]
                    await ctx.reply("> ✅ 도배 작업이 **중지**되었습니다. :no_entry:")
                else:
                    await ctx.reply("> ❌ 진행 중인 도배 작업이 **없습니다**.")

    async def on_ready(self):
        print(f'Selfbot logged in as {self.user}')
        activity = discord.Game(name=self.status_message)
        await self.change_presence(activity=activity)

class AutomationBot(commands.Bot):
    def __init__(self):
        intents = disnake.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        
        self.running_selfbots = {}

    async def start_selfbot(self, user_id: str, token: str, account: str, status: str):
        if user_id in self.running_selfbots:
            return False
        
        is_valid = await validate_token(token)
        if not is_valid:
            return False

        try:
            selfbot = SelfBot(account, status, self, user_id)
            task = asyncio.create_task(selfbot.start(token, bot=False))
            self.running_selfbots[user_id] = (selfbot, task)
            return True
        except Exception as e:
            print(f"셀프봇 시작 오류: {e}")
            return False

    async def stop_selfbot(self, user_id: str):
        if user_id not in self.running_selfbots:
            return False
        
        try:
            selfbot, task = self.running_selfbots[user_id]
            await selfbot.close()
            task.cancel()
            del self.running_selfbots[user_id]
            return True
        except Exception as e:
            print(f"셀프봇 종료 오류: {e}")
            return False

class SelfbotModal(disnake.ui.Modal):
    def __init__(self, user_data=None):
        default_values = user_data or {
            "token": "",
            "account": "",
            "status": ""
        }

        components = [
            disnake.ui.TextInput(
                label="유저 토큰",
                custom_id="token",
                placeholder="당신의 토큰을 입력하세요",
                style=disnake.TextInputStyle.paragraph,
                required=True,
                value=default_values.get("token", "")
            ),
            disnake.ui.TextInput(
                label="계좌",
                custom_id="account",
                placeholder="당신의 계좌번호를 입력하세요",
                style=disnake.TextInputStyle.short,
                required=True,
                value=default_values.get("account", "")
            ),
            disnake.ui.TextInput(
                label="상태 메시지",
                custom_id="status",
                placeholder="상태 메시지를 입력하세요",
                style=disnake.TextInputStyle.short,
                required=True,
                value=default_values.get("status", "")
            )
        ]

        super().__init__(
            title="셀프봇 설정",
            components=components
        )

    async def callback(self, inter: disnake.ModalInteraction):
        is_valid = await validate_token(inter.text_values["token"])
        if not is_valid:
            await inter.response.send_message("❌ 유효하지 않은 토큰입니다!", ephemeral=True)
            return

        try:
            if os.path.exists(USER_DATA_FILE):
                with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}

            data[str(inter.author.id)] = {
                "token": inter.text_values["token"],
                "account": inter.text_values["account"],
                "status": inter.text_values["status"]
            }

            with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            await inter.response.send_message("✅ 설정이 저장되었습니다!", ephemeral=True)
        except Exception as e:
            await inter.response.send_message("❌ 설정 저장 중 오류가 발생했습니다!", ephemeral=True)
            print(f"설정 저장 오류: {e}")

class ControlButtons(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="셀프봇 세팅", style=disnake.ButtonStyle.primary)
    async def setup_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                user_data = data.get(str(inter.author.id))
        except:
            user_data = None

        modal = SelfbotModal(user_data)
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="셀프봇 시작", style=disnake.ButtonStyle.success)
    async def start_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            user_data = data.get(str(inter.author.id))
        except:
            user_data = None

        if not user_data:
            await inter.response.send_message("먼저 셀프봇을 설정해주세요!", ephemeral=True)
            return

        success = await bot.start_selfbot(
            str(inter.author.id),
            user_data["token"],
            user_data["account"],
            user_data["status"]
        )

        if success:
            await inter.response.send_message("셀프봇이 시작되었습니다!", ephemeral=True)
        else:
            await inter.response.send_message("이미 실행 중이거나 토큰이 유효하지 않습니다!", ephemeral=True)

    @disnake.ui.button(label="셀프봇 종료", style=disnake.ButtonStyle.danger)
    async def stop_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        success = await bot.stop_selfbot(str(inter.author.id))
        if success:
            await inter.response.send_message("셀프봇이 종료되었습니다!", ephemeral=True)
        else:
            await inter.response.send_message("실행 중인 셀프봇이 없습니다!", ephemeral=True)

def is_allowed_user():
    async def predicate(inter: disnake.ApplicationCommandInteraction):
        if inter.author.id not in ALLOWED_USERS:
            return False
        return True
    return commands.check(predicate)

bot = AutomationBot()

@bot.slash_command(name="셀봇자동화", guild_ids=[1385290986649026640], sync=False)
@is_allowed_user()
async def selfbot_control(inter: disnake.AppCmdInter):
    embed = disnake.Embed(
        title="**무료 셀프봇 ㅣ 샤이전자**",
        description="아래 버튼을 사용해 무료 셀프봇을 이용하세요.",
        color=disnake.Color.green()
    )
    embed.set_footer(text="Free Selfbot Service - Secure Version")
    
    await inter.response.send_message(embed=embed, view=ControlButtons())

@bot.event
async def on_ready():
    await bot.change_presence(
        status=disnake.Status.idle,
        activity=disnake.Game(name="!잼민이 ㅣ Gemini")
    )
    print(f'Automation Bot ready: {bot.user}')
    
    # 자동으로 저장된 셀프봇들 시작
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for user_id, user_data in data.items():
            await bot.start_selfbot(
                user_id,
                user_data["token"],
                user_data["account"],
                user_data["status"]
            )
    except Exception as e:
        print(f"자동 시작 오류: {e}")

# 봇 실행
bot.run(BOT_TOKEN) 
