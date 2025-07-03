import discord
from discord.ext import commands
import fitz  # PyMuPDF - used for parsing PDF content
import logging
import json
import time
import os
from discord import app_commands
from discord.ui import Button, View
from config import TOKEN

# ---------------------------
# Configure logging to console
# ---------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------
# Discord Bot Setup
# ---------------------------
# Enables message content tracking and registers command prefix (!)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ---------------------------
# PDF Document Paths
# ---------------------------
# Maps logical document identifiers (used in commands) to actual PDF file paths
pdfs = {
    "REG": "data/REG.pdf",
    "ORDIR": "data/ORDIR.pdf"
}

# ---------------------------
# In-memory storage for section titles by document
# Populated at bot startup to support autocomplete
# ---------------------------
section_titles_by_doc = {}

# ---------------------------
# Utility class for paginating long text
# Used to split long sections into manageable Discord embed pages
# ---------------------------
class PaginatedText:
    def __init__(self, text, per_page=1000):
        self.text = text
        self.per_page = per_page
        self.pages = [text[i:i + per_page] for i in range(0, len(text), per_page)]
        self.total_pages = len(self.pages)

# ---------------------------
# Function to extract all section headings from a PDF
# Triggered once at startup per document to support autocomplete
# Uses two phases: main content and glossary based on heading triggers
# ---------------------------
def extract_sections(pdf_path, heading_size1, heading_size2, heading_font):
    try:
        doc = fitz.open(pdf_path)
        extracted_titles = set()
        tracking = False
        use_heading_size2 = False

        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    line_text = ""
                    line_font = None
                    line_size = None

                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        font_size = round(span["size"])
                        font_name = span["font"]

                        if line_text:
                            line_text += " "
                        line_text += text

                        if line_font is None:
                            line_font = font_name
                            line_size = font_size
                        elif line_font != font_name or line_size != font_size:
                            line_font = None

                    # Trigger extraction phase after "Special Ability Structure"
                    if line_text == "Special Ability Structure" and font_size == 36 and "Arial" in font_name:
                        tracking = True
                        use_heading_size2 = False

                    # Switch to glossary mode after "Glossary of Terms"
                    if line_text == "Glossary of Terms" and font_size == 36 and "Arial" in font_name:
                        use_heading_size2 = True
                        tracking = True
                        continue

                    # Capture headings based on the current mode (main or glossary)
                    if tracking:
                        font_matches = heading_font.lower() in (line_font or "").lower()
                        if not use_heading_size2:
                            if font_size == heading_size1 and font_matches:
                                extracted_titles.add(line_text)
                        else:
                            if font_size == heading_size2 and font_matches:
                                extracted_titles.add(line_text)

        valid_titles = [title for title in extracted_titles if 1 <= len(title) <= 100]
        return sorted(valid_titles)

    except Exception as e:
        logger.error(f"Error extracting sections: {str(e)}")
        return []

# ---------------------------
# Function to extract a specific section's content from a PDF
# Invoked at runtime when user requests a section
# Identifies section body between two headings and formats bullets/headings
# ---------------------------
def extract_section_with_specific_format(pdf_path, main_heading, heading_size1, heading_size2, heading_font):
    try:
        doc = fitz.open(pdf_path)

        # Internal helper to find and parse the section body
        def process_section(heading_size):
            found_main_heading = False
            section_text = []
            current_bullet_text = None

            for page_num, page in enumerate(doc, start=1):
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    for line in block.get("lines", []):
                        line_text = ""
                        for span in line.get("spans", []):
                            text = span["text"].strip()
                            font_size = span["size"]
                            font_name = span["font"]
                            rounded_font_size = round(font_size)

                            # Match the requested section heading
                            if text == main_heading and rounded_font_size == heading_size and heading_font in font_name:
                                found_main_heading = True
                                section_text.append(text)
                                continue

                            # End the section if a new heading is found
                            if found_main_heading and rounded_font_size == heading_size and heading_font in font_name:
                                return "\n".join(section_text)

                            if found_main_heading:
                                # Handle common bullet point symbols
                                if text in ['•', '○', '●', '-', '▪']:
                                    current_bullet_text = '-'
                                    continue

                                # Apply formatting for subsection headers
                                if rounded_font_size == 14:
                                    text = f"**{text}**"

                                # Format bullet line
                                if current_bullet_text:
                                    if text:
                                        combined_text = f"{current_bullet_text} {text}"
                                        line_text += combined_text + " "
                                        current_bullet_text = None
                                else:
                                    line_text += text + " "

                        if line_text:
                            section_text.append(line_text.strip())

            return "\n".join(section_text) if section_text else None

        # Try extracting section from main content, then glossary
        section_text = process_section(heading_size1)
        if section_text:
            return section_text, False

        section_text = process_section(heading_size2)
        if section_text:
            return section_text, True

        return None, False

    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        return None, False

# ---------------------------
# Bot ready event
# Triggered once after bot login
# Logs bot status, syncs slash commands, and extracts section headings for autocomplete
# ---------------------------
@bot.event
async def on_ready():
    global section_titles_by_doc
    logger.info(f'Bot is ready as {bot.user}')

    permissions = discord.Permissions(send_messages=True, embed_links=True, attach_files=True, use_application_commands=True)
    invite_link = discord.utils.oauth_url(bot.user.id, permissions=permissions)
    logger.info(f'Invite link: {invite_link}')

    # Load section headings from each document and store them
    for doc_key, path in pdfs.items():
        titles = extract_sections(path, heading_size1=30, heading_size2=14, heading_font="Arial")
        section_titles_by_doc[doc_key] = titles
        logger.info(f"{doc_key}: Extracted {len(titles)} section titles")

    # Register slash commands with Discord
    await bot.tree.sync()

# ---------------------------
# Autocomplete handler for /lookup command
# Suggests matching section titles based on user input
# ---------------------------
async def section_autocomplete(interaction: discord.Interaction, current: str):
    choices = []
    for doc_key, titles in section_titles_by_doc.items():
        filtered = [title for title in titles if current.lower() in title.lower()][:5]
        choices.extend([app_commands.Choice(name=f"{doc_key} > {title}", value=f"{doc_key}|{title}") for title in filtered])
    return choices[:25]

# ---------------------------
# Persistent pagination file for remembering user state
# ---------------------------
PROGRESS_FILE = "pagination_progress.json"

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=4)

user_progress = load_progress()

# ---------------------------
# View class for pagination buttons in embeds
# Allows user to scroll left/right through long section content
# ---------------------------
class PersistentPagination(View):
    def __init__(self, paginated, embed, message, user_id, query):
        super().__init__(timeout=None)
        self.paginated = paginated
        self.embed = embed
        self.message = message
        self.user_id = str(user_id)

        query_hash = hash(query)
        self.progress_key = f"{self.user_id}_{query_hash}_{int(time.time() * 1000)}"
        self.current_page = 0

        self.prev_button = Button(label="◀️", style=discord.ButtonStyle.primary)
        self.next_button = Button(label="▶️", style=discord.ButtonStyle.primary)
        self.prev_button.callback = self.prev_callback
        self.next_button.callback = self.next_callback

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        user_progress[self.progress_key] = self.current_page
        save_progress(user_progress)
        self.update_embed_and_buttons()

    async def prev_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_embed_and_buttons()
            user_progress[self.progress_key] = self.current_page
            save_progress(user_progress)
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def next_callback(self, interaction: discord.Interaction):
        if self.current_page < self.paginated.total_pages - 1:
            self.current_page += 1
            self.update_embed_and_buttons()
            user_progress[self.progress_key] = self.current_page
            save_progress(user_progress)
            await interaction.response.edit_message(embed=self.embed, view=self)

    def update_embed_and_buttons(self):
        self.embed.description = self.paginated.pages[self.current_page]
        self.embed.set_footer(text=f"Page {self.current_page + 1}/{self.paginated.total_pages}")
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.paginated.total_pages - 1

# ---------------------------
# Slash command: /lookup
# Allows user to select a document section and view its content with pagination
# Section choices are populated via autocomplete based on document index
# ---------------------------
@bot.tree.command(name="lookup", description="Lookup a section from a specific document")
@app_commands.describe(section="Type to select a document and section")
@app_commands.autocomplete(section=section_autocomplete)
async def lookup(interaction: discord.Interaction, section: str):
    await interaction.response.defer(thinking=True)

    try:
        doc_key, section_title = section.split("|", 1)
        pdf_path = pdfs.get(doc_key)
        if not pdf_path:
            await interaction.followup.send("Invalid document selected.", ephemeral=True)
            return

        section_text, is_glossary_result = extract_section_with_specific_format(
            pdf_path, section_title, heading_size1=30, heading_size2=14, heading_font="Arial"
        )

        if not section_text:
            await interaction.followup.send(f"'{section_title}' not found in {doc_key}.", ephemeral=True)
            return

        paginated = PaginatedText(section_text)
        embed = discord.Embed(
            title=f"{doc_key} - {'Glossary' if is_glossary_result else 'Section'}: {section_title}",
            color=discord.Color.green() if is_glossary_result else discord.Color.blue()
        )
        embed.description = paginated.pages[0]
        embed.set_footer(text=f"Page 1/{paginated.total_pages}")

        message = await interaction.followup.send(embed=embed, ephemeral=False)
        if paginated.total_pages > 1:
            view = PersistentPagination(paginated, embed, message, interaction.user.id, section)
            await message.edit(view=view)

    except Exception as e:
        logger.error(f"Lookup error: {e}")
        await interaction.followup.send("Failed to perform lookup.", ephemeral=True)

# ---------------------------
# Prefix command: !search
# Lets users search for a section directly via text commands
# Useful in environments without slash command support
# ---------------------------
@bot.command(name='search')
async def search_pdf(ctx, doc: str, keyword: str,
                     section_size: int = 30,
                     glossary_size: int = 14,
                     heading_font: str = "Arial"):

    pdf_path = pdfs.get(doc)
    if not pdf_path:
        await ctx.send(f"Document '{doc}' not recognized.")
        return

    section_text, is_glossary_result = extract_section_with_specific_format(
        pdf_path, keyword, section_size, glossary_size, heading_font
    )

    if not section_text:
        await ctx.send(f"'{keyword}' not found in {doc}.")
        return

    paginated = PaginatedText(section_text)
    embed = discord.Embed(
        title=f"{doc} - {'Glossary' if is_glossary_result else 'Section'}: {keyword}",
        color=discord.Color.green() if is_glossary_result else discord.Color.blue()
    )
    embed.description = paginated.pages[0]
    embed.set_footer(text=f"Page 1/{paginated.total_pages}")

    message = await ctx.send(embed=embed)
    if paginated.total_pages > 1:
        view = PersistentPagination(paginated, embed, message, ctx.author.id, keyword)
        await message.edit(view=view)

# ---------------------------
# Bot token loading and startup
# Attempts to load token from env var, otherwise uses config fallback
# ---------------------------
if not (token := os.getenv("DISCORD_TOKEN") or TOKEN):
    logger.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
    exit(1)

bot.run(token)
