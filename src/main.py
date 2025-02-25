import discord
from discord.ext import commands
import fitz  # PyMuPDF
import logging
import os
from discord.ui import Button, View
from config import TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Global variable to store extracted sections
extracted_sections = {}

class PaginatedText:
    def __init__(self, text, per_page=1000):
        self.text = text
        self.per_page = per_page
        self.pages = [text[i:i + per_page] for i in range(0, len(text), per_page)]
        self.total_pages = len(self.pages)

def extract_headings(pdf_path, heading_size_threshold=18):
    """Extracts all section titles from the PDF based on font size."""
    try:
        doc = fitz.open(pdf_path)
        section_titles = {}

        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        font_size = span["size"]

                        if font_size >= heading_size_threshold:  # Headings usually have larger font sizes
                            section_titles[text] = page_num

        return section_titles
    except Exception as e:
        logger.error(f"Error extracting headings: {e}")
        return {}

def extract_section_text(pdf_path, start_page, end_page=None):
    """Extracts text from the given page range in the PDF."""
    try:
        doc = fitz.open(pdf_path)
        text = []

        end_page = end_page if end_page else start_page + 1

        for page_num in range(start_page - 1, end_page):  # Convert to zero-based index
            text.append(doc[page_num].get_text("text"))

        return "\n".join(text).strip()
    except Exception as e:
        logger.error(f"Error extracting section text: {e}")
        return None

@bot.event
async def on_ready():
    logger.info(f'Bot is ready as {bot.user}')
    logger.info(f'Invite link: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands')

    # Extract sections and store them globally
    global extracted_sections
    pdf_path = "data/REG_PDF_9.0.0.pdf"
    extracted_sections = extract_headings(pdf_path)

    logger.info(f"Extracted {len(extracted_sections)} sections from the PDF.")

@bot.tree.command(name="invite", description="Get the bot's invite link")
async def invite(interaction: discord.Interaction):
    invite_link = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    await interaction.response.send_message(f"Invite me to your server using this link:\n{invite_link}")

@bot.tree.command(name="search", description="Search for a section in the document")
async def search(interaction: discord.Interaction, section: str):
    """Search for a section by title and return it paginated."""
    pdf_path = "data/REG_PDF_9.0.0.pdf"

    if section not in extracted_sections:
        await interaction.response.send_message(f"Section '{section}' not found.")
        return

    start_page = extracted_sections[section]
    section_text = extract_section_text(pdf_path, start_page)

    if not section_text:
        await interaction.response.send_message(f"Could not retrieve text for '{section}'.")
        return

    # Paginate text
    paginated = PaginatedText(section_text)

    # Create embed for first page
    embed = discord.Embed(title=f"Section: {section}", color=discord.Color.blue())
    embed.description = paginated.pages[0]
    embed.set_footer(text=f"Page 1/{paginated.total_pages}")

    message = await interaction.response.send_message(embed=embed)

    if paginated.total_pages > 1:
        current_page = 0

        # Create buttons
        prev_button = Button(label="◀️", style=discord.ButtonStyle.primary)
        next_button = Button(label="▶️", style=discord.ButtonStyle.primary)

        async def prev_callback(interaction: discord.Interaction):
            nonlocal current_page
            if current_page > 0:
                current_page -= 1
                embed.description = paginated.pages[current_page]
                embed.set_footer(text=f"Page {current_page + 1}/{paginated.total_pages}")
                await message.edit(embed=embed)
            await interaction.response.defer()

        async def next_callback(interaction: discord.Interaction):
            nonlocal current_page
            if current_page < paginated.total_pages - 1:
                current_page += 1
                embed.description = paginated.pages[current_page]
                embed.set_footer(text=f"Page {current_page + 1}/{paginated.total_pages}")
                await message.edit(embed=embed)
            await interaction.response.defer()

        prev_button.callback = prev_callback
        next_button.callback = next_callback

        view = View(timeout=60.0)
        view.add_item(prev_button)
        view.add_item(next_button)

        await message.edit(view=view)

@search.autocomplete("section")
async def search_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete function to suggest sections based on user input."""
    suggestions = [name for name in extracted_sections.keys() if current.lower() in name.lower()]
    return [discord.app_commands.Choice(name=name, value=name) for name in suggestions[:25]]

# Get token from environment variable
token = os.getenv('DISCORD_TOKEN')
if not token:
    token = TOKEN
    if not token:
        logger.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
        exit(1)

bot.run(token)
