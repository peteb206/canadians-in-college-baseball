# canadians-in-college-baseball
Python web scraper for the Canadian Baseball Network... [view full project description](https://peteb206.github.io/projects/canadians-in-college-baseball/)

## [Canadians in College Baseball](https://www.canadianbaseballnetwork.com/canadian-baseball-network-canadians-in-college)
[![scrape-players](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-players.yml/badge.svg)](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-players.yml)
[![update-players-sheet](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/update-players-sheet.yml/badge.svg)](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/update-players-sheet.yml)
- Scan NCAA, NJCAA, NAIA, etc. schools' baseball rosters for players whose hometown references Canada or a Canadian city or province.<br>
- Clean and format data due to differences in each school's website formats.<br>
- Export results to Google Sheets and display using gspread package.

## [Canadians in College Baseball Stats](https://www.canadianbaseballnetwork.com/canadians-in-college-stats)
[![scrape-stats](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-stats.yml/badge.svg)](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-stats.yml)
[![update-stats-sheet](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/update-stats-sheet.yml/badge.svg)](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/update-stats-sheet.yml)
- Locate the season statistics of the players found by the Canadians in College Baseball scraper.<br>
- Clean and format the data found from the NCAA, NJCAA, NAIA, etc. websites.<br>
- Export results to Google Sheets and display using gspread package.

## Python (3.11.2) Packages
[![unit-tests](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/unit-tests.yml)
### Web Scraping
- requests (2.28.1)
- beautifulsoup4 (4.11.1)
- lxml (4.9.1)
- html5lib (1.1)
- json (built-in)

### Data Manipulation
- pandas (1.4.4)
- re (built-in)

### Google Sheets API
- gspread (5.7.1)
- oauth2client (4.1.3)