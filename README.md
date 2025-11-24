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
