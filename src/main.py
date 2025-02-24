import discord
from discord.ext import commands
import fitz  # PyMuPDF
import logging
import os
from discord.ui import Button, View
from config import TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


class PaginatedText:
    def __init__(self, text, per_page=1000):
        self.text = text
        self.per_page = per_page
        self.pages = [
            text[i:i + per_page] for i in range(0, len(text), per_page)
        ]
        self.total_pages = len(self.pages)


def extract_section_with_specific_format(pdf_path, main_heading, heading_size1, heading_size2, heading_font):
    try:
        doc = fitz.open(pdf_path)

        def process_section(heading_size):
            found_main_heading = False
            section_text = []
            current_bullet_text = None

            count = 0
            for page_num, page in enumerate(doc, start=1):
                blocks = page.get_text("dict")["blocks"]
                for block_num, block in enumerate(blocks, start=1):
                    for line_num, line in enumerate(block.get("lines", []), start=1):
                        line_text = ""
                        for span_num, span in enumerate(line.get("spans", []), start=1):
                            text = span["text"].strip()
                            font_size = span["size"]
                            font_name = span["font"]
                            rounded_font_size = round(font_size)

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
                                    text = f"**{text}**"  # Apply bold formatting

                                #logger.info(f"Count: '{count}' Line text before is '{line_text}' + Current Bullet text is '{current_bullet_text}''")
                                if current_bullet_text:
                                    if text:
                                        combined_text = f"{current_bullet_text} {text}"
                                        line_text += combined_text + " "
                                        current_bullet_text = None
                                else:
                                    line_text += text + " "
                                #logger.info(f"Count: '{count}' Line text after is '{line_text}'")
                            count += 1

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
    logger.info(f'Bot is ready as {bot.user}')
    logger.info(
        f'Invite link: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands'
    )


@bot.tree.command(name="invite", description="Get the bot's invite link")
async def invite(interaction: discord.Interaction):
    invite_link = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    await interaction.response.send_message(
        f"Invite me to your server using this link:\n{invite_link}")


@bot.command(name='search')
async def search_pdf(ctx,
                     keyword: str,
                     section_size: int = 30,
                     glossary_size: int = 14,
                     heading_font: str = "Arial"):
    """Search for a keyword in both regular sections and glossary"""
    pdf_path = "data/REG_PDF_9.0.0.pdf"

    #logger.info(f"Searching for '{keyword}' in sections and glossary")
    section_text, is_glossary_result = extract_section_with_specific_format(
        pdf_path, keyword, section_size, glossary_size, heading_font)

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
        prev_button = Button(label="⬅️", style=discord.ButtonStyle.primary)
        next_button = Button(label="➡️", style=discord.ButtonStyle.primary)

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
        logger.error(
            "No Discord token found. Please set the DISCORD_TOKEN environment variable."
        )
        exit(1)

bot.run(token)
