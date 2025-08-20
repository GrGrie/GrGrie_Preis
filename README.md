# Project_Groceries
My personal project, where I want to write a groceries scraper using python and then train a model to identify different sales on this week.

## Usage

To scrape Lidl flyers and choose which prospect to download, use the `--num-prospekt` argument (1 = first flyer):

```
python scraper.py --site lidl --num-prospekt 2
```

This downloads the second available flyer instead of the default first one.
