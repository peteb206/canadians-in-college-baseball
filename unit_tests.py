from curl_cffi import requests
from bs4 import BeautifulSoup
import re

urls_to_try = [
    'https://smcgaels.com/sports/baseball/roster/2026',
    'https://athletics.sierracollege.edu/sports/bsb/2025-26/roster',
    'https://stats.ncaa.org/players/11216497',
    'https://njcaastats.prestosports.com/sports/bsb/2025-26/div1/players/williammerrikin4d53?serverSide',
    'https://naiastats.prestosports.com/sports/bsb/2025-26/players/tysonkilbreathnkcr',
    'https://nwacsports.com/sports/bsb/2025-26/players/domenicdipalmazyn2',
    'https://www.cccaasports.org/sports/bsb/2025-26/players/declanbarrymci9?serverSide',
    'https://uscaa.prestosports.com/sports/bsb/2025-26/players/dawsonbabineaujytv'
]

for url in urls_to_try:
    print('--------------')
    print(url)
    resp = requests.get(url, impersonate = 'chrome')
    print(resp.status_code)
    soup = BeautifulSoup(resp.text, 'html.parser')
    print(f'{len(soup.find_all("table"))} tables found')
    print(f'{len(soup.find_all("th", string = re.compile("Total")))} th found with "Total" as the text')
