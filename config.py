from model import GoogleSpreadsheet
import os

# Canadians in College Hub Google Sheet
keyfile = 'canadians-in-college-baseball-32cfc8392a02.json'
if os.path.isfile(keyfile):
    with open(keyfile) as f:
        os.environ['GOOGLE_CLOUD_API_KEY'] = f.read()
google_spreadsheets = GoogleSpreadsheet(keyfile = os.environ.get('GOOGLE_CLOUD_API_KEY'))
hub_spreadsheet = google_spreadsheets.spreadsheet(name = 'Canadians in College Baseball Hub')
print('Connected to Canadians in College Baseball Hub spreadsheet...')
config_values = {key_value_pair[0]: key_value_pair[1] for key_value_pair in hub_spreadsheet.worksheet('Configuration').get_all_values() if key_value_pair[0] not in ['', 'key']}