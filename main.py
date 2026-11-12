# NEXUS FORM - Python 3.11.0 - BUTTON VERSION - FINAL + OPEN/CLOSE + NO DOUBLE DECISION
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
intents.members = True  # NEW: needed for auto-roles
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- NEW: HELPER - GET MEMBER FOR ROLES ----------
async def get_member_for_roles(guild, user_id):
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        member = await guild.fetch_member(user_id)
        return member
    except:
        return None

async def get_candidate_role(guild, form_name=None):
    # 1. If form has a custom candidate role saved, use it
    if form_name:
        gid = str(guild.id)
        form = db["forms"].get(gid, {}).get(form_name)
        if form and form.get("candidate_role_id"):
            role = guild.get_role(form["candidate_role_id"])
            if role:
                return role
    # 2. Default: role named "Candidate"
    role = discord.utils.get(guild.roles, name="Candidate")
    return role

# ---------- NEW: DECISION VIEW - FIXES ACCEPT + DENY BOTH ----------
class DecisionView(discord.ui.View):
    def __init__(self, form_name, applicant_id):
        super().__init__(timeout=None)
        self.form_name = form_name
        self.applicant_id = applicant_id
        self.decided = False

    async def handle_decision(self, interaction: discord.Interaction, decision: str):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
        # BLOCK SECOND CLICK
        if self.decided:
            return await interaction.response.send_message("⚠️ This application was already decided!", ephemeral=True)
        self.decided = True

        applicant = interaction.guild.get_member(self.applicant_id)
        if not applicant:
            try: applicant = await bot.fetch_user(self.applicant_id)
            except: applicant = None

        # Disable BOTH buttons
        for child in self.children:
            child.disabled = True

        if decision == "accept":
            self.accept_btn.label = "✅ Accepted"
            msg_text = f"✅ Accepted {applicant.mention if applicant else f'<@{self.applicant_id}>'} for `{self.form_name}`!"
            dm_text = f"✅ **Accepted!** Your application for `{self.form_name}` in **{interaction.guild.name}** was accepted!"
            color = 0x22C55E
            # NEW: AUTO GIVE CANDIDATE ROLE ON ACCEPT
            member_obj = await get_member_for_roles(interaction.guild, self.applicant_id)
            if member_obj:
                candidate_role = await get_candidate_role(interaction.guild, self.form_name)
                if candidate_role:
                    try:
                        await member_obj.add_roles(candidate_role, reason=f"Accepted for {self.form_name}")
                        msg_text += f"\n🎭 Gave {candidate_role.mention}"
                        dm_text += f"\nYou are now **{candidate_role.name}**!"
                    except Exception as e:
                        msg_text += f"\n⚠️ Could not give Candidate role (move bot role higher): {e}"
                else:
                    msg_text += f"\n⚠️ No `Candidate` role found - create it or use `/form-candidate-role`"
        else:
            self.deny_btn.label = "❌ Denied"
            msg_text = f"❌ Denied {applicant.mention if applicant else f'<@{self.applicant_id}>'} for `{self.form_name}`."
            dm_text = f"❌ **Denied.** Your application for `{self.form_name}` in **{interaction.guild.name}** was denied."
            color = 0xEF4444

        # Edit original application - show decided + disabled buttons
        try:
            embed = interaction.message.embeds[0]
            embed.color = color
            embed.set_footer(text=f"NEXUS FORM • Decided by {interaction.user} • {decision.upper()} • ID: {self.applicant_id}")
            await interaction.response.edit_message(embed=embed, view=self)
        except:
            await interaction.response.defer()

        await interaction.followup.send(msg_text)
        if applicant:
            try: await applicant.send(dm_text)
            except: pass

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green, custom_id="form_accept")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_decision(interaction, "accept")

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red, custom_id="form_deny")
    async def deny_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_decision(interaction, "deny")

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
        # NEW: CLOSED CHECK IN MODAL
        if not form.get("open", True):
            return await interaction.response.send_message("🔒 **This form is CLOSED.** Applications are closed, you cannot apply right now.", ephemeral=True)
        answers = "\n\n".join([f"**Q{i+1}: {q}**\n{a.value}" for i, (q, a) in enumerate(zip(form["questions"], self.inputs))])
        embed = discord.Embed(title=f"📝 New Application - {self.form_name}", description=f"**Applicant:** {interaction.user.mention} ({interaction.user})\n\n{answers}", color=0x8B5CF6, timestamp=datetime.now())
        embed.set_footer(text=f"NEXUS FORM • ID: {interaction.user.id}")
        if form.get("image"): embed.set_image(url=form["image"])
        # NEW: Use DecisionView instead of old view
        view = DecisionView(self.form_name, interaction.user.id)
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
        # NEW: CLOSED CHECK ON BUTTON CLICK - no one can click again
        if not form.get("open", True):
            return await interaction.response.send_message("🔒 **This form is CLOSED.** Applications are closed.", ephemeral=True)
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
    # NEW: open=True by default + posted_messages list for close/open editing
    db["forms"][gid][name] = {"channel": channel.id, "questions": questions, "image": image.url if image else None, "created_by": interaction.user.display_name, "open": True, "posted_messages": []}
    save()
    await interaction.response.send_message(f"✅ Form `{name}` created! Status: 🟢 OPEN\nNow do `/form-post channel: #apply-here name: {name}` to post the button!", ephemeral=True)

@bot.tree.command(name="form-post", description="Post form with Apply button")
async def form_post(interaction: discord.Interaction, channel: discord.TextChannel, name: str, title: str = None, description: str = None):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
    gid = str(interaction.guild.id)
    form = db["forms"].get(gid, {}).get(name)
    if not form: return await interaction.response.send_message("❌ Form not found!", ephemeral=True)
    status_text = "🟢 OPEN - Click below to apply!" if form.get("open", True) else "🔒 CLOSED - Applications closed"
    embed = discord.Embed(title=title or f"📝 Apply - {name}", description=description or f"Click the button below to apply for **{name}**!\n\n**Questions:**\n" + "\n".join([f"{i+1}. {q}" for i,q in enumerate(form["questions"])]) + f"\n\nStatus: {status_text}\nResults go to: <#{form['channel']}>", color=0x8B5CF6)
    if form.get("image"): embed.set_image(url=form["image"])
    embed.set_footer(text="NEXUS FORM • Click Apply Now")
    # If closed, post with disabled button
    view = ApplyButtonView(name)
    if not form.get("open", True):
        for c in view.children: c.disabled = True
        view.children[0].label = "🔒 Applications Closed"
    msg = await channel.send(embed=embed, view=view)
    # Save message so /form-close can update it later
    form.setdefault("posted_messages", []).append({"channel": channel.id, "message": msg.id})
    save()
    await interaction.response.send_message(f"✅ Form `{name}` posted to {channel.mention} with Apply button!", ephemeral=True)

# ---------- NEW: OPEN / CLOSE ----------
@bot.tree.command(name="form-close", description="Close a form - no one can apply")
async def form_close(interaction: discord.Interaction, name: str):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
    gid = str(interaction.guild.id)
    form = db["forms"].get(gid, {}).get(name)
    if not form: return await interaction.response.send_message("❌ Form not found!", ephemeral=True)
    if not form.get("open", True): return await interaction.response.send_message(f"🔒 `{name}` is already CLOSED.", ephemeral=True)
    form["open"] = False
    save()
    # Update all posted Apply buttons to CLOSED + disabled
    for pm in form.get("posted_messages", []):
        try:
            ch = bot.get_channel(pm["channel"])
            if ch:
                msg = await ch.fetch_message(pm["message"])
                view = ApplyButtonView(name)
                for c in view.children: c.disabled = True
                view.children[0].label = "🔒 Applications Closed"
                view.children[0].style = discord.ButtonStyle.gray
                embed = msg.embeds[0]
                embed.description = embed.description.replace("🟢 OPEN - Click below to apply!", "🔒 CLOSED - Applications closed")
                if "🔒 CLOSED" not in embed.description: embed.description += "\n\n🔒 CLOSED - Applications closed"
                embed.color = 0xEF4444
                await msg.edit(embed=embed, view=view)
        except: pass
    await interaction.response.send_message(f"🔒 **Form `{name}` is now CLOSED.**\nThe Apply button is now disabled and says 'Applications Closed'. If someone clicks it, they get 'This form is CLOSED.'\nRe-open with `/form-open name: {name}`")

@bot.tree.command(name="form-open", description="Open a closed form")
async def form_open(interaction: discord.Interaction, name: str):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
    gid = str(interaction.guild.id)
    form = db["forms"].get(gid, {}).get(name)
    if not form: return await interaction.response.send_message("❌ Form not found!", ephemeral=True)
    if form.get("open", True): return await interaction.response.send_message(f"🟢 `{name}` is already OPEN.", ephemeral=True)
    form["open"] = True
    save()
    # Re-enable all posted Apply buttons
    for pm in form.get("posted_messages", []):
        try:
            ch = bot.get_channel(pm["channel"])
            if ch:
                msg = await ch.fetch_message(pm["message"])
                view = ApplyButtonView(name)
                embed = msg.embeds[0]
                embed.description = embed.description.replace("🔒 CLOSED - Applications closed", "🟢 OPEN - Click below to apply!")
                embed.color = 0x8B5CF6
                await msg.edit(embed=embed, view=view)
        except: pass
    await interaction.response.send_message(f"🢢 **Form `{name}` is now OPEN.**\nApply button is working again. Members can apply.")

@bot.tree.command(name="form-list", description="List all forms")
async def form_list(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    forms = db["forms"].get(gid, {})
    txt = "\n".join([f"**{k}** - {len(v['questions'])} questions → <#{v['channel']}> - {'🟢 OPEN' if v.get('open', True) else '🔒 CLOSED'}" for k,v in forms.items()]) or "No forms yet."
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
    embed.add_field(name="Open / Close", value="`/form-close name: staff` - Close, button becomes 🔒 Closed\n`/form-open name: staff` - Open again\n`/form-list` - See OPEN / CLOSED", inline=False)
    embed.add_field(name="Members", value="Just click **📝 Apply Now** button - no command needed!", inline=False)
    embed.add_field(name="NEW - Roles", value="`/form-candidate-role name: staff role: @Candidate` - Set what role Accept gives\n`/pass user: @user role: @Staff` - Pass interview, removes Candidate, gives role\n`!pass @user @Staff` - Same, with prefix", inline=False)
    await interaction.response.send_message(embed=embed)

# ---------- NEW: CANDIDATE ROLE SETTING + PASS SYSTEM ----------
@bot.tree.command(name="form-candidate-role", description="Set which role Accept button gives (Candidate)")
async def form_candidate_role(interaction: discord.Interaction, name: str, role: discord.Role):
    if not interaction.user.guild_permissions.manage_messages: return await interaction.response.send_message("❌ Need Manage Messages!", ephemeral=True)
    gid = str(interaction.guild.id)
    form = db["forms"].get(gid, {}).get(name)
    if not form: return await interaction.response.send_message("❌ Form not found!", ephemeral=True)
    form["candidate_role_id"] = role.id
    save()
    await interaction.response.send_message(f"✅ For form `{name}`, **Accept** button will now auto-give {role.mention}", ephemeral=True)

async def do_pass(guild, staff_user, target_member, give_role):
    # Shared logic for /pass and !pass
    # Remove Candidate role if they have it
    candidate_role = None
    # Try to find Candidate from any form in this guild, else by name
    for f in db["forms"].get(str(guild.id), {}).values():
        if f.get("candidate_role_id"):
            r = guild.get_role(f["candidate_role_id"])
            if r and r in target_member.roles:
                candidate_role = r
                break
    if not candidate_role:
        candidate_role = discord.utils.get(guild.roles, name="Candidate")
    try:
        await target_member.add_roles(give_role, reason=f"Passed interview by {staff_user}")
        if candidate_role and candidate_role in target_member.roles:
            await target_member.remove_roles(candidate_role, reason="Passed interview - remove Candidate")
        return True, candidate_role
    except Exception as e:
        return False, str(e)

@bot.tree.command(name="pass", description="Pass interview - give role + remove Candidate")
async def pass_slash(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_messages and not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message("❌ Need Manage Messages / Manage Roles!", ephemeral=True)
    ok, info = await do_pass(interaction.guild, interaction.user, user, role)
    if ok:
        txt = f"✅ {user.mention} PASSED interview! Gave {role.mention}"
        if info:
            txt += f" + removed {info.mention}"
        await interaction.response.send_message(txt)
        try: await user.send(f"✅ You PASSED interview in **{interaction.guild.name}**! You got **{role.name}** 🎉")
        except: pass
    else:
        await interaction.response.send_message(f"❌ Could not give role - move NEXUS bot role HIGHER than {role.mention} in Server Settings > Roles. Error: {info}", ephemeral=True)

@bot.command(name="pass")
async def pass_prefix(ctx, user: discord.Member, role: discord.Role):
    if not ctx.author.guild_permissions.manage_messages and not ctx.author.guild_permissions.manage_roles:
        return await ctx.send("❌ Need Manage Messages / Manage Roles!")
    ok, info = await do_pass(ctx.guild, ctx.author, user, role)
    if ok:
        txt = f"✅ {user.mention} PASSED interview! Gave {role.mention}"
        if info:
            txt += f" + removed {info.mention}"
        await ctx.send(txt)
        try: await user.send(f"✅ You PASSED interview in **{ctx.guild.name}**! You got **{role.name}** 🎉")
        except: pass
    else:
        await ctx.send(f"❌ Could not give role - move NEXUS bot role HIGHER than {role.mention}. Error: {info}")

@bot.tree.command(name="claim-owner", description="Claim owner")
async def claim_owner(interaction: discord.Interaction, key: str):
    global OWNER_ID
    if key == RECOVERY_KEY:
        OWNER_ID = str(interaction.user.id)
        await interaction.response.send_message("✅ You are now Owner!", ephemeral=True)
    else: await interaction.response.send_message("❌ Wrong key", ephemeral=True)

TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN.strip() if TOKEN else '')
