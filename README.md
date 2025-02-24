# RedemptionRuleBot

A Discord bot that extracts and searches specific sections within a PDF document based on user-provided keywords.

## Features

- Searches for sections in a PDF by main heading.
- Supports pagination for lengthy sections.
- Differentiates between regular sections and glossary entries.

## Prerequisites

- Python 3.9 or higher
- A Discord bot token. You can create one by following the [Discord Developer Portal](https://discord.com/developers/docs/intro).

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/discord-pdf-search-bot.git
   ```

2. Navigate to the project directory:

   ```bash
   cd discord-pdf-search-bot
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set Up Environment Variables:

   Create a .env file in the root directory of the project and add your Discord bot token:

   ```bash
   DISCORD_TOKEN=your_discord_bot_token_here
   ```
   
   Alternatively, you can set the environment variable directly in your system.

5. Prepare the PDF Document:

   Place the current version of the Redemption Exegesis Guide (z.B. REG_PDF_9.0.0.pdf) file into the data directory. If the directory doesn't exist, create it:

   ```bash
   mkdir data
   ```
   
   Then, move your PDF file into this directory.

## Usage

To start the bot, run:

   ```bash
   python bot.py
   ```

Once the bot is running, you can use the following commands in your Discord server:

   ```bash
   !search <keyword>: Searches for the specified keyword in the PDF and displays the relevant section or glossary entry.
   ```

   Example:

   ```bash
   !search installation
   ```

   This command will search for the term "installation" in the PDF and display the corresponding section or glossary entry in a paginated embed.

## Bot Commands

   ```bash
   !invite: Provides the invite link to add the bot to other servers.
   ```

## Code Overview

The bot is built using the discord.py library and utilizes the PyMuPDF library (fitz) to handle PDF processing. The main components include:

    PDF Extraction: The extract_section_with_specific_format function opens the PDF and searches for sections matching the given keyword based on font size and name.
    Pagination: The PaginatedText class divides lengthy text into smaller chunks for paginated display within Discord embeds.
    Discord Commands: The bot defines commands such as !search to handle user interactions and display results.

## Logging

The bot uses Python's built-in logging module to provide informative logs during operation. Logs include details about the bot's status and any errors encountered during PDF processing.

## Contributing

Contributions are welcome! If you'd like to contribute, please fork the repository and create a pull request with your changes.

## Acknowledgments

    discord.py: An API wrapper for Discord written in Python.
    PyMuPDF: A Python binding for MuPDF, a lightweight PDF viewer.
