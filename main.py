import os
import discord
from discord.ext import commands
from discord.ui import View, Button
from flask import Flask
from threading import Thread

# --- Web server Flask giữ Bot online 24/7 ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Tòa Án & Cảnh Sát đang hoạt động 24/7!"

def run():
    # Lấy port từ biến môi trường của Render
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

keep_alive()

# --- Cấu hình Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True  # Đọc tin nhắn/lệnh
intents.members = True          # Quản lý member & vai trò

bot = commands.Bot(command_prefix="!", intents=intents)


# ==========================================
# TÍNH NĂNG TÒA ÁN & HỖ TRỢ & ĐI TÙ
# ==========================================
class CourtTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Đóng Phiên Tòa", style=discord.ButtonStyle.secondary, custom_id="btn_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ Admin mới có quyền đóng kênh này!", ephemeral=True)
            return
        
        await interaction.response.send_message("⚖️ Phiên tòa kết thúc! Kênh này sẽ tự xóa sau 5 giây...")
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="⛓️ Bỏ Tù Người Vi Phạm", style=discord.ButtonStyle.danger, custom_id="btn_jail_user")
    async def jail_user(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ Admin mới có quyền tống giam!", ephemeral=True)
            return

        jail_role = discord.utils.get(interaction.guild.roles, name="Tù Nhân")
        if not jail_role:
            jail_role = await interaction.guild.create_role(name="Tù Nhân", color=discord.Color.dark_gray())

        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in interaction.guild.members if not m.bot
        ][:25]

        select = discord.ui.Select(placeholder="Chọn bị cáo để tống giam...", options=options)

        async def select_callback(select_interaction: discord.Interaction):
            target_id = int(select.values[0])
            target_member = select_interaction.guild.get_member(target_id)

            if target_member:
                try:
                    await target_member.add_roles(jail_role)
                except discord.Forbidden:
                    await select_interaction.response.send_message("❌ Lỗi: Role của Bot phải đứng CAO HƠN Role Tù Nhân!", ephemeral=True)
                    return

                original_name = target_member.display_name
                new_nick = f"Phạm nhân - {original_name}"
                if len(new_nick) > 32:
                    new_nick = new_nick[:32]
                
                try:
                    await target_member.edit(nick=new_nick)
                except discord.Forbidden:
                    pass

                await select_interaction.response.send_message(
                    f"🚨 **TÒA TUYÊN ÁN:** Bị cáo {target_member.mention} đã bị tống giam và đổi tên thành **{new_nick}**!"
                )
            else:
                await select_interaction.response.send_message("❌ Không tìm thấy người dùng này!", ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("⚖️ **HỘI ĐỒNG XÉT XỬ:** Chọn người vi phạm bên dưới:", view=view, ephemeral=True)


class MainCourtView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_private_channel(self, interaction: discord.Interaction, category_name: str, prefix: str):
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)

        channel_name = f"{prefix}-{user.name}"
        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        embed = discord.Embed(
            title=f"⚖️ PHÒNG XỬ LÝ: {prefix.upper()}",
            description=f"Chào {user.mention}! Vui lòng trình bày rõ lý do / bằng chứng tại đây.\nBan Quản Trị sẽ vào làm việc ngay.",
            color=discord.Color.red() if prefix == "to-cao" else discord.Color.blue()
        )
        await channel.send(content=f"{user.mention} | Admin Notification", embed=embed, view=CourtTicketView())
        await interaction.response.send_message(f"✅ Đã mở phòng riêng cho bạn tại: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="⚖️ Khởi Tố / Tố Cáo", style=discord.ButtonStyle.danger, custom_id="btn_to_cao")
    async def to_cao_button(self, interaction: discord.Interaction, button: Button):
        await self.create_private_channel(interaction, "🏛️ PHIÊN TÒA XÉT XỬ", "to-cao")

    @discord.ui.button(label="🆘 Cần Hỗ Trợ", style=discord.ButtonStyle.primary, custom_id="btn_ho_tro")
    async def ho_tro_button(self, interaction: discord.Interaction, button: Button):
        await self.create_private_channel(interaction, "🆘 TRUNG TÂM HỖ TRỢ", "ho-tro")


# -------------------------------------------------------------
# CÁC LỆNH GÕ TRỰC TIẾP TRONG DISCORD
# -------------------------------------------------------------

@bot.command(name="panel")
@commands.has_permissions(administrator=True)
async def court_panel(ctx):
    """Tạo bảng Tòa Án & Cần Hỗ Trợ"""
    embed = discord.Embed(
        title="🏛️ TÒA ÁN & TRUNG TÂM HỖ TRỢ SERVER 🏛️",
        description=(
            "Nơi giải quyết các vi phạm, tranh chấp và hỗ trợ thành viên trong Server!\n\n"
            "📌 **HƯỚNG DẪN:**\n"
            "• Bấm **`⚖️ Khởi Tố / Tố Cáo`**: Cần tòa án xét xử.\n"
            "• Bấm **`🆘 Cần Hỗ Trợ`**: Cần Ban Quản Trị giải đáp."
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=MainCourtView())


@bot.command(name="ratu")
@commands.has_permissions(administrator=True)
async def ratu_user(ctx, member: discord.Member = None):
    """Lệnh Ra Tù (Ân Xá): !ratu @Member"""
    if member is None:
        await ctx.send("⚠️ Bạn cần tag người muốn cho ra tù! Ví dụ: `!ratu @Phạm nhân - Mika`")
        return

    jail_role = discord.utils.get(ctx.guild.roles, name="Tù Nhân")
    
    # 1. Gỡ Role Tù Nhân
    if jail_role and jail_role in member.roles:
        try:
            await member.remove_roles(jail_role)
        except discord.Forbidden:
            await ctx.send("❌ Bot thiếu quyền! Hãy kéo Role của Bot lên cao hơn Role 'Tù Nhân'.")
            return

    # 2. Khôi phục lại tên gốc (Bỏ chữ 'Phạm nhân - ')
    if member.display_name.startswith("Phạm nhân - "):
        clean_nick = member.display_name.replace("Phạm nhân - ", "")
        try:
            await member.edit(nick=clean_nick)
        except discord.Forbidden:
            pass

    await ctx.send(f"🕊️ **Ân Xá:** Thành viên {member.mention} đã được ra tù và phục hồi tên cũ!")

@ratu_user.error
async def ratu_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn cần quyền Administrator để dùng lệnh Ra Tù!")


@bot.event
async def on_ready():
    print(f'✅ Bot Tòa Án & Cảnh Sát đã đăng nhập thành công: {bot.user}')

# Chạy Bot an toàn
token = os.getenv('TOKEN')
if token:
    bot.run(token)
else:
    print("❌ LỖI: Chưa có biến môi trường TOKEN!")
