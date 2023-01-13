import scrape
from google_sheets import update_canadians_sheet, update_stats_sheet

def players(fetch = False, update_google_sheet = False, copy_to_production = True):
    if fetch:
        scrape.players()
    if update_google_sheet:
        update_canadians_sheet(copy_to_production = copy_to_production)

def stats(fetch = False, update_google_sheet = False, copy_to_production = True):
    if fetch:
        scrape.stats()
    if update_google_sheet:
        update_stats_sheet(copy_to_production = copy_to_production)