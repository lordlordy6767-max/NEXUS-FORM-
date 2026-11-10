# NEXUS FORM - Python 3.11.0 - BUTTON VERSION - FINAL
import os, json, threading
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
@app.route('/')
def home(): return "NEXUS FORM is online!", 200
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000))), daemon=True).start()

OWNER_ID = os.getenv('OWNER_ID', '')
OWNER_USERNAME = os.getenv('OWNER_USERNAME', '@starrlightz12')
RECOVERY_KEY = os.getenv('RECOVERY_KEY', 'change-me')

DB_FILE = 'db.json'
db = {"forms": {}}
if os.path.exists(DB_FILE):
    try: db.update(json.load(open(DB_FILE)))
    except: pass
def save(): json.dump(db, open(DB_FILE, 'w'), indent=2)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class ApplyModal(discord.ui.Modal):
    def __init__(self, form_name, questions):
        super().__init__(title=f"Apply: {form_name}")
        self.form_name = form_name
        self.inputs = []
        for q in questions[:5]:
            inp = discord.ui.TextInput(label=q[:45], placeholder="Type your answer...", style=discord.TextStyle.paragraph, required=True, max_length=1000)
            self.inputs.append(inp)
            self.add_item(inp)
    async def on_submit(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        form = db["forms"].get(gid, {}).get(self.form_name)
        if not form: return await interaction.response.send_message("❌ Form not found!", ephemeral=True)
        answers = "\n\n".join([f"**Q{i+1}: {q}**\n{a.value}" for i, (q, a) in enumerate(zip(form["questions"], self.inputs))])
        embed = discord.Embed(title=f"📝 New Application - {self.form_name}", description=f"**Applicant:** {interaction.user.mention} ({interaction.user})\n\n{answers}", color=0x8B5CF6, timestamp=datetime.now())
        embed.set_footer(text=f"NEXUS FORM • ID: {interaction.user.id}")
        if form.get("image"): embed.set_image(url=form["image"])
        view = discord.ui.View(timeout=None)
        async def accept_cb(inter: discord.Interaction):
            if not inter.user.guild_permissions.manage_messages: return await inter.response.send_message("❌ Need Manage Messages!", ephemeral=True)
            await inter.response.send_message(f"✅ Accepted {interaction.user.mention} for `{self.form_name}`!", ephemeral=False)
            try: await interaction.user.send(f"✅ **Accepted!** Your application for `{self.form_name}` in **{inter.guild.name}** was accepted!")
            except: pass
        async def deny_cb(inter: discord.Interaction):
            if not inter.user.guild_permissions.manage_messages: return await inter.response.send_message("❌ Need Manage Messages!", ephemeral=True)
            await inter.response.send_message(f"❌ Denied {interaction.user.mention} for `{self.form_name}`.", ephemeral=False)
            try: await interaction.user.send(f"❌ **Denied.** Your application for `{self.form_name}` in **{inter.guild.name}** was denied.")
            except: pass
        b1 = discord.ui.Button(label="✅ Accept", style=discord.ButtonStyle.green); b1.callback = accept_cb
        b2 = discord.ui.Button(label="❌ Deny", style=discord.ButtonStyle.red); b2.callback = deny_cb
        view.add_item(b1); view.add_item(b2)
        ch = bot.get_channel(form["channel"])
        if ch: await ch.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Application for `{self.form_name}` submitted! Staff will review.", ephemeral=True)

# --- BUTTON VIEW ---
class ApplyButtonView(discord.ui.View):
    def __init__(self, form_name):
        super().__init__(timeout=None)
        self.form_name = form_name
    @discord.ui.button(label="📝 Apply Now", style=discord.ButtonStyle.blurple, custom_id="apply_button")
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = str(interaction.guild.id)
        form = db["forms"].get(gid, {}).get(self.form_name)
        if not form: return await interaction.response.send_message("❌ Form not found!", ephemeral=True)
        await interaction.response.send_modal(ApplyModal(self.form_name, form["questions"]))

@bot.event
async def on_ready():
    try: await bot.tree.sync()
    except Exception as e: print("SYNC FAIL:", e)
    print(f"✅ NEXUS FORM logged in as {bot.user}")

@bot.tree.command(name="form-create", description="Create application form")
async def form_create(interaction: discord.Interaction, name: str, channel: discord.TextChannel, q1: str, q2: str = None, q3: str = None, q4: str = None, q5: str = None, image: discord.Attachment = None):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
    gid = str(interaction.guild.id)
    if gid not in db["forms"]: db["forms"][gid] = {}
    questions = [q for q in [q1,q2,q3,q4,q5] if q]
    db["forms"][gid][name] = {"channel": channel.id, "questions": questions, "image": image.url if image else None, "created_by": interaction.user.display_name}
    save()
    await interaction.response.send_message(f"✅ Form `{name}` created! Now do `/form-post channel: #apply-here name: {name}` to post the button!", ephemeral=True)

@bot.tree.command(name="form-post", description="Post form with Apply button")
async def form_post(interaction: discord.Interaction, channel: discord.TextChannel, name: str, title: str = None, description: str = None):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
    gid = str(interaction.guild.id)
    form = db["forms"].get(gid, {}).get(name)
    if not form: return await interaction.response.send_message("❌ Form not found!", ephemeral=True)
    embed = discord.Embed(title=title or f"📝 Apply - {name}", description=description or f"Click the button below to apply for **{name}**!\n\n**Questions:**\n" + "\n".join([f"{i+1}. {q}" for i,q in enumerate(form["questions"])]) + f"\n\nResults go to: <#{form['channel']}>", color=0x8B5CF6)
    if form.get("image"): embed.set_image(url=form["image"])
    embed.set_footer(text="NEXUS FORM • Click Apply Now")
    await channel.send(embed=embed, view=ApplyButtonView(name))
    await interaction.response.send_message(f"✅ Form `{name}` posted to {channel.mention} with Apply button!", ephemeral=True)

@bot.tree.command(name="form-list", description="List all forms")
async def form_list(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    forms = db["forms"].get(gid, {})
    txt = "\n".join([f"**{k}** - {len(v['questions'])} questions → <#{v['channel']}>" for k,v in forms.items()]) or "No forms yet."
    await interaction.response.send_message(f"📋 **Forms:**\n{txt}", ephemeral=True)

@bot.tree.command(name="form-delete", description="Delete a form")
async def form_delete(interaction: discord.Interaction, name: str):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
    gid = str(interaction.guild.id)
    if name in db["forms"].get(gid, {}):
        del db["forms"][gid][name]; save()
        await interaction.response.send_message(f"✅ Deleted `{name}`", ephemeral=True)
    else: await interaction.response.send_message("❌ Not found!", ephemeral=True)

@bot.tree.command(name="form-help", description="Show FORM commands")
async def form_help(interaction: discord.Interaction):
    embed = discord.Embed(title="📝 NEXUS FORM - Commands", description=f"Owner: {OWNER_USERNAME}", color=0x8B5CF6)
    embed.add_field(name="Staff - 2 Steps", value="**1.** `/form-create name: staff channel: #applications q1: Why join? q2: Age?`\n**2.** `/form-post channel: #apply-here name: staff title: Join Staff`", inline=False)
    embed.add_field(name="Members", value="Just click **📝 Apply Now** button - no command needed!", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="claim-owner", description="Claim owner")
async def claim_owner(interaction: discord.Interaction, key: str):
    global OWNER_ID
    if key == RECOVERY_KEY:
        OWNER_ID = str(interaction.user.id)
        await interaction.response.send_message("✅ You are now Owner!", ephemeral=True)
    else: await interaction.response.send_message("❌ Wrong key", ephemeral=True)

TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN.strip() if TOKEN else '')
