import os
import asyncio
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

keep_alive()

# --- Cấu hình Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Hàm hỗ trợ tìm hoặc tạo danh mục an toàn (tránh lỗi emoji)
async def get_or_create_category(guild, category_name):
    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        for cat in guild.categories:
            if category_name in cat.name or cat.name in category_name:
                category = cat
                break
    if not category:
        category = await guild.create_category(category_name)
    return category

# Hàm kiểm tra quyền Admin hoặc Thẩm Phán
def is_admin_or_judge(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
        return True
    judge_role = discord.utils.get(interaction.guild.roles, name="Thẩm Phán")
    if judge_role and judge_role in interaction.user.roles:
        return True
    return False

# ==========================================
# TÍNH NĂNG TÒA ÁN & HỖ TRỢ & ĐI TÙ
# ==========================================
class CourtTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Đóng Phiên Tòa", style=discord.ButtonStyle.secondary, custom_id="btn_close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if not is_admin_or_judge(interaction):
            await interaction.response.send_message("❌ **Truy cập bị từ chối:** Chỉ Admin hoặc Thẩm Phán mới có quyền đóng phiên tòa này!", ephemeral=True)
            return
         
        await interaction.response.send_message("⚖️ **Phiên tòa khép lại!** Kênh này sẽ tự động tiêu hủy sau 5 giây...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="⛓️ Tống Giam Bị Cáo", style=discord.ButtonStyle.danger, custom_id="btn_jail_user", emoji="⛓️")
    async def jail_user(self, interaction: discord.Interaction, button: Button):
        if not is_admin_or_judge(interaction):
            await interaction.response.send_message("❌ **Truy cập bị từ chối:** Chỉ Thẩm Phán hoặc Admin mới có quyền tống giam!", ephemeral=True)
            return

        jail_role = discord.utils.get(interaction.guild.roles, name="Tù Nhân")
        if not jail_role:
            jail_role = await interaction.guild.create_role(name="Tù Nhân", color=discord.Color.dark_gray())

        # Đảm bảo có kênh ngục-tù để phạm nhân chat
        jail_channel = discord.utils.get(interaction.guild.text_channels, name="ngục-tù")
        if not jail_channel:
            jail_overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                jail_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            jail_channel = await interaction.guild.create_text_channel(name="ngục-tù", overwrites=jail_overwrites)
        else:
            await jail_channel.set_permissions(jail_role, read_messages=True, send_messages=True)

        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id), emoji="👤")
            for m in interaction.guild.members if not m.bot
        ][:25]

        select_member = discord.ui.Select(placeholder="🔍 Chọn bị cáo cần định đoạt hình phạt...", options=options)

        async def member_callback(select_interaction: discord.Interaction):
            target_id = int(select_member.values[0])
            target_member = select_interaction.guild.get_member(target_id)

            if not target_member:
                await select_interaction.response.send_message("❌ Không tìm thấy đối tượng này trong server!", ephemeral=True)
                return

            # Bước tiếp theo: Chọn thời gian tù với giao diện icon đẹp mắt
            duration_options = [
                discord.SelectOption(label="1 Phút (Chế độ Test nhanh)", value="60", emoji="⏱️"),
                discord.SelectOption(label="30 Phút", value="1800", emoji="⏳"),
                discord.SelectOption(label="1 Giờ", value="3600", emoji="⌛"),
                discord.SelectOption(label="1 Ngày", value="86400", emoji="📅"),
                discord.SelectOption(label="Vĩnh Viễn (Cần ân xá thủ công)", value="0", emoji="♾️")
            ]
            
            select_duration = discord.ui.Select(placeholder=f"⏳ Chọn thời hạn tù cho: {target_member.display_name}", options=duration_options)

            async def duration_callback(duration_interaction: discord.Interaction):
                duration_seconds = int(select_duration.values[0])

                try:
                    await target_member.add_roles(jail_role)
                except discord.Forbidden:
                    await duration_interaction.response.send_message("❌ **Lỗi hệ thống:** Role của Bot phải đứng CAO HƠN Role 'Tù Nhân' trong danh sách vai trò!", ephemeral=True)
                    return

                original_name = target_member.display_name
                new_nick = f"Phạm nhân - {original_name}"
                if len(new_nick) > 32:
                    new_nick = new_nick[:32]
                 
                try:
                    await target_member.edit(nick=new_nick)
                except discord.Forbidden:
                    pass

                # Thông báo thời gian tù
                time_str = "Vĩnh viễn (Chờ ân xá)"
                if duration_seconds == 60: time_str = "1 phút"
                elif duration_seconds == 1800: time_str = "30 phút"
                elif duration_seconds == 3600: time_str = "1 giờ"
                elif duration_seconds == 86400: time_str = "1 ngày"

                await duration_interaction.response.send_message(
                    f"🚨 **BẢN ÁN ĐÃ TUYÊN:** Bị cáo {target_member.mention} đã bị tống giam!\n"
                    f"🏷️ **Danh hiệu mới:** `{new_nick}`\n"
                    f"⏰ **Thời hạn thi hành:** `{time_str}`\n"
                    f"💬 **Khu vực giam giữ:** {jail_channel.mention}"
                )

                # Thiết lập tác vụ ngầm tự động mãn hạn tù nếu không phải vĩnh viễn
                if duration_seconds > 0:
                    bot.loop.create_task(auto_unveil(target_member, jail_role, original_name, duration_seconds, jail_channel))

            select_duration.callback = duration_callback
            view_duration = View()
            view_duration.add_item(select_duration)
            await select_interaction.response.edit_message(content=f"⚖️ Đã chọn bị cáo: **{target_member.display_name}**. Hãy chọn mức án thời gian bên dưới:", view=view_duration)

        select_member.callback = member_callback
        view_member = View()
        view_member.add_item(select_member)
        await interaction.response.send_message("⚖️ **HỘI ĐỒNG TÒA ÁN:** Chọn người vi phạm bên dưới:", view=view_member, ephemeral=True)

    @discord.ui.button(label="👥 Mời Nhân Chứng", style=discord.ButtonStyle.primary, custom_id="btn_invite_witness", emoji="👥")
    async def invite_witness(self, interaction: discord.Interaction, button: Button):
        if not is_admin_or_judge(interaction):
            await interaction.response.send_message("❌ **Truy cập bị từ chối:** Chỉ Thẩm Phán hoặc Admin mới có quyền triệu tập nhân chứng!", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id), emoji="🛡️")
            for m in interaction.guild.members if not m.bot
        ][:25]

        select = discord.ui.Select(placeholder="🔍 Chọn nhân chứng để triệu tập...", options=options)

        async def select_callback(select_interaction: discord.Interaction):
            target_id = int(select.values[0])
            target_member = select_interaction.guild.get_member(target_id)
            if target_member:
                await interaction.channel.set_permissions(target_member, read_messages=True, send_messages=True)
                await select_interaction.response.send_message(
                    f"✅ Đã triệu tập nhân chứng {target_member.mention} vào phòng xử án bảo mật này!", ephemeral=True
                )
                await interaction.channel.send(f"👥 **Triệu tập:** Nhân chứng {target_member.mention} đã chính thức tham gia phiên tòa.")
            else:
                await select_interaction.response.send_message("❌ Không tìm thấy người dùng này!", ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("👥 **BẢNG TRIỆU TẬP:** Chọn nhân chứng bên dưới:", view=view, ephemeral=True)


# Tác vụ chạy ngầm tự động thả tù nhân khi hết giờ
async def auto_unveil(member, jail_role, original_name, delay, jail_channel):
    await asyncio.sleep(delay)
    
    # Kiểm tra xem người đó còn giữ role tù nhân không
    if jail_role in member.roles:
        try:
            await member.remove_roles(jail_role)
        except discord.Forbidden:
            pass

    if member.display_name.startswith("Phạm nhân - "):
        try:
            await member.edit(nick=original_name)
        except discord.Forbidden:
            pass

    if jail_channel:
        await jail_channel.send(f"🕊️ **MÃN HẠN TÙ TỰ ĐỘNG:** Phạm nhân {member.mention} đã hoàn thành án phạt, được trả tự do và khôi phục tên cũ!")


class MainCourtView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_private_channel(self, interaction: discord.Interaction, category_name: str, prefix: str):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        # Tự động tạo role Thẩm Phán nếu chưa có
        judge_role = discord.utils.get(guild.roles, name="Thẩm Phán")
        if not judge_role:
            judge_role = await guild.create_role(name="Thẩm Phán", color=discord.Color.gold())

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            judge_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = await get_or_create_category(guild, category_name)

        channel_name = f"{prefix}-{user.name}"
        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        embed = discord.Embed(
            title=f"⚖️ PHÒNG XỬ LÝ BẢO MẬT: {prefix.upper()}",
            description=f"Chào {user.mention}!\n📋 Vui lòng trình bày rõ nội dung, khiếu nại hoặc bằng chứng tại đây.\n\n🛡️ **Thẩm Phán** và **Ban Quản Trị** đã được triệu tập và sẽ vào làm việc ngay lập tức.",
            color=discord.Color.red() if prefix == "to-cao" else discord.Color.blue()
        )
        embed.set_footer(text="Hệ thống Tư Pháp Server 24/7", icon_url=guild.icon.url if guild.icon else None)
        
        ping_text = f"{user.mention} | {judge_role.mention} | @Admin"
        await channel.send(content=ping_text, embed=embed, view=CourtTicketView())
        await interaction.followup.send(f"✅ Đã khởi tạo phòng riêng tư thành công tại: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="Khởi Tố / Tố Cáo", style=discord.ButtonStyle.danger, custom_id="btn_to_cao", emoji="⚖️")
    async def to_cao_button(self, interaction: discord.Interaction, button: Button):
        await self.create_private_channel(interaction, "PHIÊN TÒA XÉT XỬ🏢", "to-cao")

    @discord.ui.button(label="Yêu Cầu Hỗ Trợ", style=discord.ButtonStyle.primary, custom_id="btn_ho_tro", emoji="🆘")
    async def ho_tro_button(self, interaction: discord.Interaction, button: Button):
        await self.create_private_channel(interaction, "TRUNG TÂM HỖ TRỢ🧰", "ho-tro")


# -------------------------------------------------------------
# CÁC LỆNH GÕ TRỰC TIẾP TRONG DISCORD
# -------------------------------------------------------------

@bot.command(name="panel")
@commands.has_permissions(administrator=True)
async def court_panel(ctx):
    embed = discord.Embed(
        title="🏛️ HỆ THỐNG TÒA ÁN & TRUNG TÂM HỖ TRỢ 🏛️",
        description=(
            "Nơi giải quyết triệt để các tranh chấp, vi phạm và hỗ trợ thành viên trong Server một cách chuyên nghiệp!\n\n"
            "📌 **HƯỚNG DẪN SỬ DỤNG:**\n"
            "• Bấm **`⚖️ Khởi Tố / Tố Cáo`**: Mở phiên tòa xét xử vi phạm.\n"
            "• Bấm **`🆘 Yêu Cầu Hỗ Trợ`**: Cần Thẩm Phán và BQT giải đáp thắc mắc."
        ),
        color=discord.Color.gold()
    )
    embed.set_image(url="https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=600&q=80") # Ảnh minh họa tòa án sang trọng
    await ctx.send(embed=embed, view=MainCourtView())


@bot.command(name="ratu")
@commands.has_permissions(administrator=True)
async def ratu_user(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("⚠️ **Cú pháp sai:** Bạn cần tag người muốn ân xá! Ví dụ: `!ratu @Phạm nhân - Mika`")
        return

    jail_role = discord.utils.get(ctx.guild.roles, name="Tù Nhân")
     
    if jail_role and jail_role in member.roles:
        try:
            await member.remove_roles(jail_role)
        except discord.Forbidden:
            await ctx.send("❌ **Lỗi phân quyền:** Bot thiếu quyền! Hãy kéo Role của Bot lên cao hơn Role 'Tù Nhân'.")
            return

    if member.display_name.startswith("Phạm nhân - "):
        clean_nick = member.display_name.replace("Phạm nhân - ", "")
        try:
            await member.edit(nick=clean_nick)
        except discord.Forbidden:
            pass

    await ctx.send(f"🕊️ **ÂN XÁ THÀNH CÔNG:** Thành viên {member.mention} đã được tha tù trước thời hạn và phục hồi tên cũ!")

@bot.event
async def on_ready():
    bot.add_view(MainCourtView())
    bot.add_view(CourtTicketView())
    print(f'✅ Bot Tòa Án & Cảnh Sát đã đăng nhập thành công: {bot.user}')

token = os.getenv('DISCORD_TOKEN')
if token:
    bot.run(token)
else:
    print("❌ LỖI: Chưa có biến môi trường DISCORD_TOKEN!")
