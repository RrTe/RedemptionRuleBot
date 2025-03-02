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


import fitz  # PyMuPDF
import logging

logger = logging.getLogger(__name__)

import fitz  # PyMuPDF
import logging

logger = logging.getLogger(__name__)

def extract_sections(pdf_path, heading_size1, heading_size2, heading_font):
    """ Extracts section titles from the PDF based on font size and font type, 
        with specific rules for scanning between 'Special Ability Structure' and 'Glossary of Terms'."""

    try:
        doc = fitz.open(pdf_path)
        extracted_titles = set()
        tracking = False  # Flag to determine when to scan for heading_size1
        use_heading_size2 = False  # Flag to switch to heading_size2 after "Glossary of Terms"

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

                        # Concatenate spans to reconstruct full heading
                        if line_text:
                            line_text += " "  # Add space between spans
                        line_text += text
                        
                        # Ensure font consistency
                        if line_font is None:
                            line_font = font_name
                            line_size = font_size
                        elif line_font != font_name or line_size != font_size:
                            line_font = None  # Reset if inconsistency found

                    # Check for "Special Ability Structure" to start tracking
                    if line_text == "Special Ability Structure" and font_size == 36 and "Arial" in font_name:
                        tracking = True
                        use_heading_size2 = False  # Reset the flag

                    # Check for "Glossary of Terms" to switch to heading_size2
                    if line_text == "Glossary of Terms" and font_size == 36 and "Arial" in font_name:
                        use_heading_size2 = True  # From this point on, only use heading_size2
                        continue  # Skip adding this as a heading

                    # Add headings based on the current phase
                    if tracking:
                        if not use_heading_size2 and font_size == heading_size1 and heading_font in font_name:
                            extracted_titles.add(line_text)
                        elif use_heading_size2 and font_size == heading_size2 and heading_font in font_name:
                            extracted_titles.add(line_text)

        # Filter valid headings
        valid_titles = [title for title in extracted_titles if 1 <= len(title) <= 100]
        return sorted(valid_titles)  # Return sorted list of unique titles

    except Exception as e:
        logger.error(f"Error extracting sections: {str(e)}")
        return []


def extract_section_with_specific_format(pdf_path, main_heading, heading_size1, heading_size2, heading_font):
    try:
        doc = fitz.open(pdf_path)

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
                            
                            #logger.info(f"Text: {main_heading} and {text}")

                            # Check if we've found the main heading and match the desired font and size
                            if text == main_heading and rounded_font_size == heading_size and heading_font in font_name:
                                found_main_heading = True
                                section_text.append(text)
                                continue

                            if found_main_heading and rounded_font_size == heading_size and heading_font in font_name:
                                return "\n".join(section_text)

                            if found_main_heading:
                                # Detect bullet points
                                if text in ['•', '○', '●', '-', '▪']:
                                    current_bullet_text = '-'
                                    continue

                                if rounded_font_size == 14:  # Assuming 14 is the subheading font size
                                    text = f"**{text}**"  # Apply bold formatting for subheadings

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

        # Process main sections
        section_text = process_section(heading_size1)
        if section_text:
            return section_text, False

        # Process glossary
        section_text = process_section(heading_size2)
        if section_text:
            return section_text, True

        return None, False

    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        return None, False


@bot.event
async def on_ready():
    """ Load section titles on bot startup """
    global section_titles
    logger.info(f'Bot is ready as {bot.user}')
    
    # Generate the bot's invite link dynamically
    permissions = discord.Permissions(send_messages=True, embed_links=True, attach_files=True, use_application_commands=True)
    invite_link = discord.utils.oauth_url(bot.user.id, permissions=permissions)
    logger.info(f'Invite link: {invite_link}')

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


@bot.tree.command(name="lookup", description="Lookup a section from the PDF")
#@app_commands.describe(section="Select a section from the document", private="Only you can see this message?")
@app_commands.describe(section="Select a section from the document")
@app_commands.autocomplete(section=section_autocomplete)
async def lookup(interaction: discord.Interaction, section: str):
#async def lookup(interaction: discord.Interaction, section: str, private: bool = False):
    # **Defer the response to prevent timeout**
    await interaction.response.defer(thinking = True)
    
    """ Extracts and paginates the chosen section """   
    section_text, is_glossary_result = extract_section_with_specific_format(pdf_path, section, heading_size1=30, heading_size2=14, heading_font="Arial")

    if not section_text:
        await interaction.response.send_message(f"'{section}' not found in the document.", ephemeral=False)
        return

    paginated = PaginatedText(section_text)
    
    embed = discord.Embed(title=f"{'Glossary' if is_glossary_result else 'Section'}: {section}", color=discord.Color.green()
        if is_glossary_result else discord.Color.blue())
    embed.description = paginated.pages[0]
    embed.set_footer(text=f"Page 1/{paginated.total_pages}")

    """ The version correlated with the defer response above """
    await interaction.followup.send(embed=embed, ephemeral=False)
    """ The following version is the 'original' one """
    #await interaction.response.send_message(embed=embed, ephemeral=False)
    """ The following version is the one where the ephemeral can be steered by a second command parameter """
    #await interaction.response.send_message(embed=embed, ephemeral=private)

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

        #await interaction.followup.send(view=view)
        await interaction.edit_original_response(view=view)


@bot.command(name='search')
async def search_pdf(ctx,
                     keyword: str,
                     section_size: int = 30,
                     glossary_size: int = 14,
                     heading_font: str = "Arial"):
    """Search for a keyword in both regular sections and glossary"""
    pdf_path = "data/REG_PDF_9.0.0.pdf"

    #logger.info(f"Searching for '{keyword}' in sections and glossary")
    section_text, is_glossary_result = extract_section_with_specific_format(pdf_path, keyword, section_size, glossary_size, heading_font)

    if not section_text:
        await ctx.send(f"'{keyword}' not found in sections or glossary.")
        return

    # Create paginated text
    paginated = PaginatedText(section_text)

    # Create embed for first page with different colors for section vs glossary
    embed = discord.Embed(
        title=f"{'Glossary' if is_glossary_result else 'Section'}: {keyword}",
        color=discord.Color.green()
        if is_glossary_result else discord.Color.blue())
    embed.description = paginated.pages[0]
    embed.set_footer(text=f"Page 1/{paginated.total_pages}")

    # Send the embed message
    message = await ctx.send(embed=embed)

    # Add pagination buttons if there's more than one page
    if paginated.total_pages > 1:
        current_page = 0

        # Create buttons
        prev_button = Button(label="◀️", style=discord.ButtonStyle.primary)
        next_button = Button(label="▶️", style=discord.ButtonStyle.primary)

        # Define button callbacks
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

        # Set the callbacks
        prev_button.callback = prev_callback
        next_button.callback = next_callback

        # Add buttons to the view
        view = View(timeout=60.0)
        view.add_item(prev_button)
        view.add_item(next_button)

        # Edit the message to add the buttons
        await message.edit(view=view)

        
# Get token from environment variable
token = os.getenv('DISCORD_TOKEN')
if not token:
    token = TOKEN
    if not token:
        logger.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
        exit(1)

bot.run(token)
