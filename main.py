import os
import discord
from discord.ext import commands
from discord.ui import View, Button
from flask import Flask
from threading import Thread

# --- 1. Cấu hình Web Server Flask (Fix lỗi 502 Bad Gateway) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Tòa Án & Cảnh Sát đang hoạt động 24/7!"

def run():
    # Render yêu cầu bắt buộc đọc PORT từ biến môi trường
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. Cấu hình Bot Discord ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- 3. UI Buttons & Views ---

# Menu chọn người để tống giam
class PrisonerSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Chọn thành viên cần tống giam...",
            select_type=discord.ComponentType.user_select,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        # Kiểm tra quyền Admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn không có quyền sử dụng tính năng này!", ephemeral=True)
            return

        target_member = self.values[0]
        guild = interaction.guild
        prison_role = discord.utils.get(guild.roles, name="Tù Nhân")

        if not prison_role:
            await interaction.response.send_message("❌ Không tìm thấy vai trò **Tù Nhân**! Vui lòng tạo vai trò này trước.", ephemeral=True)
            return

        try:
            # Gắn role Tù Nhân & Đổi tên
            await target_member.add_roles(prison_role)
            new_nick = f"Phạm nhân - {target_member.display_name}"
            await target_member.edit(nick=new_nick[:32]) # Discord giới hạn tên 32 ký tự
            await interaction.response.send_message(f"🚨 **{target_member.mention}** đã bị tống giam và đổi tên thành `{new_nick}`!")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot thiếu quyền để tống giam/đổi tên thành viên này (Cần xếp Role của Bot cao hơn)!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Có lỗi xảy ra: {e}", ephemeral=True)

class TicketActionView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PrisonerSelect())

    @discord.ui.button(label="🔒 Đóng Phiên Tòa", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn không có quyền đóng phiên tòa!", ephemeral=True)
            return
        
        await interaction.response.send_message("⚙️ Phiên tòa sẽ tự động đóng và xóa kênh sau 5 giây...")
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

class MainPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket_channel(self, interaction: discord.Interaction, prefix: str):
        guild = interaction.guild
        member = interaction.user
        
        # Tìm hoặc tạo category Ticket
        category = discord.utils.get(guild.categories, name="TÒA ÁN & HỖ TRỢ")
        if not category:
            category = await guild.create_category("TÒA ÁN & HỖ TRỢ")

        # Cấu hình phân quyền kênh riêng
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel_name = f"{prefix}-{member.name}"
        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        embed = discord.embeds.Embed(
            title="⚖️ PHIÊN TÒA / KÊNH HỖ TRỢ DÂN SỰ",
            description=f"Xin chào {member.mention},\nAdmin/Cảnh sát sẽ làm việc với bạn tại đây.\n\n*(Chỉ Admin mới có quyền dùng các nút điều khiển bên dưới)*",
            color=discord.Color.red() if prefix == "to-cao" else discord.Color.blue()
        )

        await channel.send(embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"✅ Đã tạo kênh riêng cho bạn tại: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="⚖️ Khởi Tố / Tố Cáo", style=discord.ButtonStyle.danger, custom_id="btn_tocao")
    async def btn_tocao(self, interaction: discord.Interaction, button: Button):
        await self.create_ticket_channel(interaction, "to-cao")

    @discord.ui.button(label="🆘 Cần Hỗ Trợ", style=discord.ButtonStyle.primary, custom_id="btn_hotro")
    async def btn_hotro(self, interaction: discord.Interaction, button: Button):
        await self.create_ticket_channel(interaction, "ho-tro")

# --- 4. Lệnh Text Commands ---

@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user.name} đã kết nối thành công và đang sẵn sàng!")

@bot.command(name="panel")
@commands.has_permissions(administrator=True)
async def panel(ctx):
    embed = discord.Embed(
        title="🏛️ BẢNG ĐIỀU KHIỂN TÒA ÁN & CẢNH SÁT",
        description="Vui lòng bấm vào nút bên dưới tương ứng với nhu cầu của bạn:\n\n"
                    "• **⚖️ Khởi Tố / Tố Cáo**: Mở phiên tòa báo cáo vi phạm.\n"
                    "• **🆘 Cần Hỗ Trợ**: Yêu cầu hỗ trợ giải quyết thắc mắc.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=MainPanelView())

@bot.command(name="ratu")
@commands.has_permissions(administrator=True)
async def ratu(ctx, member: discord.Member):
    prison_role = discord.utils.get(ctx.guild.roles, name="Tù Nhân")
    
    if prison_role and prison_role in member.roles:
        await member.remove_roles(prison_role)
    
    # Khôi phục tên cũ (xóa tiền tố "Phạm nhân - ")
    if member.nick and member.nick.startswith("Phạm nhân - "):
        old_nick = member.nick.replace("Phạm nhân - ", "")
        try:
            await member.edit(nick=old_nick if old_nick else None)
        except:
            pass

    await ctx.send(f"🕊️ **{member.mention}** đã được ân xá, gỡ vai trò **Tù Nhân** và khôi phục biệt danh thành công!")

# --- 5. Khởi chạy Web Server và Bot ---
keep_alive()  # Chạy web server Flask ở luồng riêng ( Bắt buộc đứng trước bot.run )

TOKEN = os.environ.get("DISCORD_TOKEN") # Lấy Token từ Environment Variables trên Render
if not TOKEN:
    # Nếu bạn dán trực tiếp Token trong code thì thay chuỗi bên dưới:
    TOKEN = "NHẬP_TOKEN_BOT_DISCORD_CỦA_BẠN_VÀO_ĐÂY"

bot.run(TOKEN)
