import discord
from discord.ext import commands
import fitz  # PyMuPDF
import logging
import json
import time
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
pdf_path = "data/REG.pdf"

# Global list to store extracted section titles
section_titles = []


class PaginatedText:
    def __init__(self, text, per_page=1000):
        self.text = text
        self.per_page = per_page
        self.pages = [text[i:i + per_page] for i in range(0, len(text), per_page)]
        self.total_pages = len(self.pages)


def extract_sections(pdf_path, heading_size1, heading_size2, heading_font):
    """ Extracts section titles from the PDF based on font size and font type, 
        with specific rules for scanning between 'Special Ability Structure' and 'Glossary of Terms."""

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


# Define the path to store user progress
PROGRESS_FILE = "pagination_progress.json"

# Load stored progress from file
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}

# Save progress to file
def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Load existing progress
user_progress = load_progress()

class PersistentPagination(View):
    def __init__(self, paginated, embed, message, user_id, query):
        super().__init__(timeout=None)  
        self.paginated = paginated
        self.embed = embed
        self.message = message
        self.user_id = str(user_id)
        
        # Generate a unique key for each search instance
        query_hash = hash(query)  # Simple hash to distinguish queries
        self.progress_key = f"{self.user_id}_{query_hash}_{int(time.time() * 1000)}"

        # Start at the first page for a new search instance
        self.current_page = 0  

        # Initialize buttons
        self.prev_button = Button(label="◀️", style=discord.ButtonStyle.primary)
        self.next_button = Button(label="▶️", style=discord.ButtonStyle.primary)

        self.prev_button.callback = self.prev_callback
        self.next_button.callback = self.next_callback

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        # Ensure progress is stored
        user_progress[self.progress_key] = self.current_page
        save_progress(user_progress)

        self.update_embed_and_buttons()

    async def prev_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_embed_and_buttons()
            user_progress[self.progress_key] = self.current_page  # Save progress
            save_progress(user_progress)
            await interaction.response.edit_message(embed=self.embed, view=self)

    async def next_callback(self, interaction: discord.Interaction):
        if self.current_page < self.paginated.total_pages - 1:
            self.current_page += 1
            self.update_embed_and_buttons()
            user_progress[self.progress_key] = self.current_page  # Save progress
            save_progress(user_progress)
            await interaction.response.edit_message(embed=self.embed, view=self)

    def update_embed_and_buttons(self):
        """ Updates the embed description and enables/disables buttons as needed. """
        self.embed.description = self.paginated.pages[self.current_page]
        self.embed.set_footer(text=f"Page {self.current_page + 1}/{self.paginated.total_pages}")

        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.paginated.total_pages - 1


@bot.tree.command(name="lookup", description="Lookup a section from the PDF")
@app_commands.describe(section="Select a section from the document")
@app_commands.autocomplete(section=section_autocomplete)
async def lookup(interaction: discord.Interaction, section: str):
    await interaction.response.defer(thinking=True)

    section_text, is_glossary_result = extract_section_with_specific_format(
        pdf_path, section, heading_size1=30, heading_size2=14, heading_font="Arial"
    )

    if not section_text:
        await interaction.followup.send(f"'{section}' not found in the document.", ephemeral=False)
        return

    paginated = PaginatedText(section_text)

    embed = discord.Embed(
        title=f"{'Glossary' if is_glossary_result else 'Section'}: {section}",
        color=discord.Color.green() if is_glossary_result else discord.Color.blue()
    )
    embed.description = paginated.pages[0]
    embed.set_footer(text=f"Page 1/{paginated.total_pages}")

    message = await interaction.followup.send(embed=embed, ephemeral=False)

    if paginated.total_pages > 1:
        view = PersistentPagination(paginated, embed, message, interaction.user.id, section)
        await message.edit(view=view)


@bot.command(name='search')
async def search_pdf(ctx,
                     keyword: str,
                     section_size: int = 30,
                     glossary_size: int = 14,
                     heading_font: str = "Arial"):

    section_text, is_glossary_result = extract_section_with_specific_format(
        pdf_path, keyword, section_size, glossary_size, heading_font
    )

    if not section_text:
        await ctx.send(f"'{keyword}' not found in sections or glossary.")
        return

    paginated = PaginatedText(section_text)

    embed = discord.Embed(
        title=f"{'Glossary' if is_glossary_result else 'Section'}: {keyword}",
        color=discord.Color.green() if is_glossary_result else discord.Color.blue()
    )
    embed.description = paginated.pages[0]
    embed.set_footer(text=f"Page 1/{paginated.total_pages}")

    message = await ctx.send(embed=embed)

    if paginated.total_pages > 1:
        view = PersistentPagination(paginated, embed, message, ctx.author.id, keyword)
        await message.edit(view=view)

        
# Get token from environment variable
token = os.getenv('DISCORD_TOKEN')
if not token:
    token = TOKEN
    if not token:
        logger.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
        exit(1)

bot.run(token)
