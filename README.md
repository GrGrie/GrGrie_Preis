# Project_Groceries: Smart Flyer Analyzer

## 💡 The Idea
We all want to find the best deals, but manually checking every supermarket flyer is time-consuming. **Project_Groceries** automates this process. It acts as a smart assistant that visits supermarket websites, reads their weekly flyers, and automatically identifies discounted products.

Think of it as a search engine for your local grocery sales—turning static images of flyers into searchable, useful data.

## 🔄 How It Works
The system follows a simple 4-step process to turn a flyer into data:

1.  **Scrape (Fetch)**: The "robot" visits supermarket websites (like Lidl, Netto, Aldi) and downloads the digital images of this week's flyers.
2.  **Detect (See)**: Using Artificial Intelligence (Computer Vision), it looks at the flyer images and draws a box around every individual product it sees, separating the milk from the apples.
3.  **Read (Understand)**: It then "reads" the text inside each box to figure out the product name and price (using Optical Character Recognition).
4.  **Show (Present)**: Finally, it presents all the found products in a clean, easy-to-use web interface for you to browse.

## 🛠️ Under the Hood
This project leverages modern technology to bridge the gap between web scraping and AI:

*   **Python**: The core programming language powering the logic.
*   **FastAPI**: Provides the web interface and API.
*   **Selenium**: The tool used to navigate websites and download flyers automatically.
*   **YOLOv11 (AI)**: A state-of-the-art object detection model trained to recognize products in complex flyer layouts.
*   **PaddleOCR**: Advanced text recognition to read prices and descriptions from images.

---

## 💻 Usage

To scrape Lidl flyers and choose which prospect to download, use the `--num-prospekt` argument (1 = first flyer):

```bash
python scraper.py --site lidl --num-prospekt 2
```

This downloads the second available flyer instead of the default first one.

### Common Commands
*   **Scrape a specific site**: `python scraper.py --site lidl`
*   **Scrape all supported sites**: `python scraper.py --site all`
*   **Scrape a custom URL**: `python scraper.py --url 'https://angebote.com/lidl/archives?page=1'`

### Layout Detection Training
To train the YOLO model for Name/Price detection:
1.  Place images and `.txt` labels in a single folder (e.g., `my_dataset`).
2.  Run:
    ```bash
    python utils/train_layout.py --source my_dataset --epochs 50
    ```

## 📲 Telegram Bot Automation
You can let the scraper run automatically and send filtered products (crop image + OCR name/price) straight to a Telegram chat.

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and invite it to your chat/channel. Note the bot token and the `chat_id` (use [@userinfobot](https://t.me/userinfobot) or the Telegram API to retrieve it).
2. Export the credentials (or place them in a `.env` file):
   ```bash
   export TELEGRAM_BOT_TOKEN="123456:abcdef"
   export TELEGRAM_CHAT_ID="987654321"
   # Optional default filters (comma separated substrings)
   export TELEGRAM_FILTERS="Fettarme, Bio"
   ```
   By default the runner also looks for `filters/keywords.txt` (one keyword per line, `#` comments allowed). Edit that file once and you never have to pass `--filters`. Override the path with `--filter-file custom.txt` or `TELEGRAM_FILTER_FILE=/path/to/file`.
3. Run the automation once immediately:
   ```bash
   python telegram_runner.py --site lidl --conf 0.75 --filters Fettarme
   ```
4. Or schedule it daily (local time) and also send the aggregated CSV:
   ```bash
   python telegram_runner.py --run-at 07:30 --send-csv
   ```

The runner executes the entire pipeline (scrape → crop → OCR), filters OCR rows whose name contains any of the provided keywords, sends every matching crop as a Telegram photo (captioned with the OCR output), and optionally attaches the `ocr_results.csv` file. Use `--max-results N` if you only need the first *N* matches per run.

Already have a run and just want to re-send its OCR output? Pass `--reuse-run latest` (or a specific folder name) and the runner will skip scraping/OCR, load the existing `ocr_results.csv`, and push those matches to Telegram.

> **Scheduling tip:** `--run-at` keeps the script alive so it can wake up at the chosen time. If you prefer not to keep a terminal open, run `python telegram_runner.py ...` from a cron/systemd job (on any always-on machine or VPS) at the cadence you need.
