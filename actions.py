import scrape
from google_sheets import update_canadians_sheet

def players(fetch = False, update_google_sheet = False):
    if fetch:
        scrape.players()
    if update_google_sheet:
        update_canadians_sheet()