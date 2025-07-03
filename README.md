# RedemptionRuleBot

A Discord bot that extracts and displays sections from one or more PDF documents using slash commands and autocomplete, with pagination support for long content.

## ✨ Features

- ✅ Reads and indexes **multiple PDF documents**.
- 🔍 **/lookup** command with autocomplete to quickly find sections.
- 🧾 Distinguishes **sections vs. glossary entries** based on heading.
- 📄 Displays results in **paginated Discord embeds**.
- 🧠 Remembers user position with persistent pagination state.
- 💠 Slash and prefix (`!search`) command support.

## 🛠️ Prerequisites

- Python 3.9 or higher
- A Discord bot token (create one via the [Discord Developer Portal](https://discord.com/developers/docs/intro)).

## 🚀 Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/discord-pdf-search-bot.git
   cd discord-pdf-search-bot
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set your bot token:**

   Either:

   - Create a `.env` file with:
     ```bash
     DISCORD_TOKEN=your_token_here
     ```

   Or:

   - Set it directly in `config.py` as:
     ```python
     TOKEN = "your_token_here"
     ```

4. **Prepare your PDFs:**

   - Place your documents (e.g., `REG.pdf`, `ORDIR.pdf`) in a `data/` folder:

     ```bash
     mkdir -p data
     mv your_files.pdf data/
     ```

   - Ensure filenames match those defined in the `pdfs` dictionary in the bot code.

## 🥮 Usage

Start the bot:

```bash
python bot.py
```

### Slash Command: `/lookup`

- Autocomplete lets users select any section heading from all loaded documents.
- The result appears in an embed with pagination controls.

### Text Command: `!search`

```bash
!search <doc> <keyword>
```

Example:

```bash
!search REG Negate
```

### Optional Command: `!invite`

If implemented, this would return the bot's invite URL.

## ⚙️ Configuration

All PDF processing settings (e.g., heading font size, font name) are defined in:

- `extract_sections(...)`
- `extract_section_with_specific_format(...)`

These can be customized if your PDFs use different formatting.

## 🤩 Code Overview

- **extract\_sections()** – Extracts all headings for autocomplete.
- **extract\_section\_with\_specific\_format()** – Extracts full content of a matched heading.
- **PaginatedText** – Splits long text for Discord-friendly pagination.
- **PersistentPagination** – Handles interactive buttons for section navigation.
- **Discord Commands** – Supports `/lookup` (slash) and `!search` (text).

## 🩽 Logging

The bot uses Python’s `logging` module to display runtime info:

- Bot startup
- PDF processing issues
- Command execution

## 🤝 Contributing

Contributions are welcome! Please fork and submit a pull request.

## 🙏 Acknowledgments

- [discord.py](https://discordpy.readthedocs.io/en/stable/)
- [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/en/latest/)
