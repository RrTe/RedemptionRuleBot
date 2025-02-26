import discord
from discord.ext import commands
import fitz  # PyMuPDF
import logging
import os
from discord import app_commands
from discord.ui import Button, View
from config import TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
pdf_path = "data/REG_PDF_9.0.0.pdf"

# Global list to store extracted section titles
section_titles = []


class PaginatedText:
    def __init__(self, text, per_page=1000):
        self.text = text
        self.per_page = per_page
        self.pages = [text[i:i + per_page] for i in range(0, len(text), per_page)]
        self.total_pages = len(self.pages)


def extract_sections(pdf_path, heading_size1, heading_size2, heading_font):
    """ Extracts section titles from the PDF based on font size and font type """
    try:
        doc = fitz.open(pdf_path)
        extracted_titles = set()

        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        font_size = round(span["size"])
                        font_name = span["font"]

                        # Collect sections based on main headings
                        if (font_size == heading_size1 or font_size == heading_size2) and heading_font in font_name:
                            extracted_titles.add(text)

        # Filter titles that are not empty and length is between 1 and 100 characters
        valid_titles = [title for title in extracted_titles if 1 <= len(title) <= 100]
        return sorted(valid_titles)  # Return sorted list of unique titles

    except Exception as e:
        logger.error(f"Error extracting sections: {str(e)}")
        return []


def extract_section_content(pdf_path, main_heading, heading_size1, heading_size2, heading_font):
    """ Extracts content from the PDF for the selected section """
    try:
        doc = fitz.open(pdf_path)
        found_main_heading = False
        section_text = []
        current_bullet_text = None

        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        font_size = round(span["size"])
                        font_name = span["font"]

                        # If section title matches, mark as found
                        if text == main_heading and (font_size == heading_size1 or font_size == heading_size2) and heading_font in font_name:
                            found_main_heading = True
                            section_text.append(f"**{text}**")  # Bold title
                            continue

                        # If a new section starts, stop capturing content
                        if found_main_heading and (font_size == heading_size1 or font_size == heading_size2) and heading_font in font_name:
                            return "\n".join(section_text)  # Stop at next section

                        # If we are in the correct section, capture the content
                        if found_main_heading:
                            # Handle bullet points and subheadings
                            if text in ['•', '○', '●', '-', '▪']:
                                current_bullet_text = '-'
                                continue

                            if current_bullet_text:
                                line_text += f"{current_bullet_text} {text} "
                                current_bullet_text = None
                            else:
                                line_text += text + " "

                    if line_text:
                        section_text.append(line_text.strip())

        # If no content found, return None
        return "\n".join(section_text) if section_text else None

    except Exception as e:
        logger.error(f"Error extracting section content: {str(e)}")
        return None


@bot.event
async def on_ready():
    """ Load section titles on bot startup """
    global section_titles
    logger.info(f'Bot is ready as {bot.user}')
    logger.info(f'Invite link: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands')

    # Extract section titles from the document
    section_titles = extract_sections(pdf_path, heading_size1=30, heading_size2=14, heading_font="Arial")
    logger.info(f"Extracted {len(section_titles)} section titles")

    # Ensure the section titles are successfully loaded
    if not section_titles:
        logger.error("No section titles extracted. Please check the PDF file.")
    
    # Sync tree commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands.")
    except Exception as e:
        logger.error(f"Error syncing commands: {str(e)}")


async def section_autocomplete(interaction: discord.Interaction, current: str):
    """ Autocomplete function for section selection """
    # Log and debug
    logger.info(f"Autocomplete triggered with query: {current}")

    # Filter section titles based on the current input and limit to 25 results
    filtered_titles = [title for title in section_titles if current.lower() in title.lower()][:25]
    
    # If there are no matches, log it for debugging purposes
    if not filtered_titles:
        logger.info("No matching titles found for autocomplete.")

    return [app_commands.Choice(name=title, value=title) for title in filtered_titles]


@bot.tree.command(name="extract", description="Extract a section from the PDF")
@app_commands.describe(section="Select a section from the document")
@app_commands.autocomplete(section=section_autocomplete)
async def extract(interaction: discord.Interaction, section: str):
    """ Extracts and paginates the chosen section """
    section_text = extract_section_content(pdf_path, section, heading_size1=30, heading_size2=14, heading_font="Arial")

    if not section_text:
        await interaction.response.send_message(f"'{section}' not found in the document.", ephemeral=True)
        return

    paginated = PaginatedText(section_text)

    embed = discord.Embed(title=f"Section: {section}", color=discord.Color.blue())
    embed.description = paginated.pages[0]
    embed.set_footer(text=f"Page 1/{paginated.total_pages}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

    if paginated.total_pages > 1:
        current_page = 0
        prev_button = Button(label="◀️", style=discord.ButtonStyle.primary)
        next_button = Button(label="▶️", style=discord.ButtonStyle.primary)

        async def prev_callback(interaction: discord.Interaction):
            nonlocal current_page
            if current_page > 0:
                current_page -= 1
                embed.description = paginated.pages[current_page]
                embed.set_footer(text=f"Page {current_page + 1}/{paginated.total_pages}")
                await interaction.response.edit_message(embed=embed)
            await interaction.response.defer()

        async def next_callback(interaction: discord.Interaction):
            nonlocal current_page
            if current_page < paginated.total_pages - 1:
                current_page += 1
                embed.description = paginated.pages[current_page]
                embed.set_footer(text=f"Page {current_page + 1}/{paginated.total_pages}")
                await interaction.response.edit_message(embed=embed)
            await interaction.response.defer()

        prev_button.callback = prev_callback
        next_button.callback = next_callback

        view = View(timeout=60.0)
        view.add_item(prev_button)
        view.add_item(next_button)

        await interaction.followup.send(view=view)


# Get token from environment variable
token = os.getenv('DISCORD_TOKEN')
if not token:
    token = TOKEN
    if not token:
        logger.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
        exit(1)

bot.run(token)
