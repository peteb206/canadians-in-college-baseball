# canadians-in-college-baseball
Python web scraper for the Canadian Baseball Network

<a href="https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/unit-tests.yml" target="_blank">
    <img src="https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/unit-tests.yml/badge.svg" alt="unit-tests" style="max-width: 100%;">
</a>
<a href="https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-schools.yml" target="_blank">
    <img src="https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-schools.yml/badge.svg" alt="scrape-schools" style="max-width: 100%;">
</a>
<a href="https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-players.yml" target="_blank">
    <img src="https://github.com/peteb206/canadians-in-college-baseball/actions/workflows/scrape-players.yml/badge.svg" alt="scrape-players" style="max-width: 100%;">
</a>

## <a href="https://www.canadianbaseballnetwork.com/canadian-baseball-network-canadians-in-college" target="_blank">Canadians in College Baseball</a>
Scan NCAA, NJCAA, NAIA, etc. schools' baseball rosters for players whose hometown references Canada or a Canadian city or province.<br>
Clean and format data due to differences in each school's website formats.<br>
Export results to Google Sheets and display using gspread package.

## <a href="https://www.canadianbaseballnetwork.com/canadians-in-college-stats" target="_blank">Canadians in College Baseball Stats</a>
Locate the season statistics of the players found by the Canadians in College Baseball scraper.<br>
Clean and format the data found from the NCAA, NJCAA, NAIA, etc. websites.<br>
Export results to Google Sheets and display using gspread package.

## Technical Details: Python Packages
### Web Scraping
- requests (2.28.1)
- beautifulsoup4 (4.11.1)
- lxml (4.9.1)
- html5lib (1.1)
- json

### Data Manipulation
- pandas (1.4.4)
- re

### Google Sheets API
- gspread (5.7.1)
- oauth2client (4.1.3)