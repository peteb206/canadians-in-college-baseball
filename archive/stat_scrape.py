import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import json
import time
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import os
import re
from roster_scrape import clear_sheets, format_headers, resize_columns


def main():
    # Last run:
    last_run = 'Last updated: {}'.format(datetime.datetime.now().strftime("%B %d, %Y"))
    f = open('last_updated.txt', 'w')
    f.write(last_run)
    f.close()

    # Start timer
    start_time = time.time()

    year = os.environ.get('YEAR')
    players_df = pd.read_csv(f'canadians_{year}.csv')
    stats_df_orig = pd.read_csv(f'stats_{year}.csv')

    session = requests.Session()
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    summary_dicts = list()
    full_run = False
    if len(sys.argv) == 2:
        if sys.argv[1] == 'y': # Determine if running full web scraper or just updating google sheet
            full_run = True

    if full_run == True:
        for index, player in players_df.iterrows():
            if (player['stats_link'] != '') & (type(player['stats_link']) == type('')):
                for url in player['stats_link'].split(','):
                    print('-------------------------')
                    print(index, player['division'], player['position'], ' --- ', '{} minutes elapsed'.format(str(round((time.time() - start_time) / 60, 1))))
                    stats_df = scrape_sites(session, url, player['division'], header)
                    if len(stats_df.index) > 0:
                        summary_dicts.append(collect_stats(player, stats_df))
                    else:
                        print('No stats found for {}'.format(player['name']))

        stats_df = convert_dict_list_to_df(summary_dicts)
        stats_df = stats_df[['Name', 'Position', 'School', 'Division', 'Type', 'Games Played (G)', 'At Bats (AB)', 'Runs Scored (R)', 'Hits (H)', 'Doubles (2B)', 'Triples (3B)', 'Home Runs (HR)', 'Runs Batted In (RBI)', 'Stolen Bases (SB)', 'Batting Average (AVG)', 'On-Base Percentage (OBP)','Slugging Percentage (SLG)', 'On-Base plus Slugging (OPS)', 'Appearances (G)', 'Games Started (GS)', 'Innings Pitched (IP)', 'Wins (W)', 'Losses (L)', 'Earned Runs (ER)', 'Hits Allowed (H)', 'Walks Allowed (BB)', 'Earned Run Average (ERA)', 'Saves (SV)', 'Strikeouts (K)']]
        stats_df = pd.concat([stats_df, stats_df_orig], ignore_index=True) # Add players who could not be scraped
        stats_df.drop_duplicates(subset=['Name', 'School', 'Type'], keep='first', ignore_index=True, inplace=True) # Drop duplicate names (keep player's stats from previous week if scrape failed this week)
        stats_df.sort_values(by='Name', ignore_index=True).to_csv(f'stats_{year}.csv', index=False)
    else:
        update_gsheet(pd.read_csv(f'stats_{year}.csv'), last_run)

    print('--- Total time: {} minutes ---'.format(str(round((time.time() - start_time) / 60, 1))))


def scrape_sites(session, url, division, header):
    response = ''
    attempts = 0
    while (response == '') & (attempts <= 3):
        attempts += 1
        try:
            response = session.get(url, headers=header, timeout=60).text
        except:
            pass

    table_index = 0
    if division.startswith('NCAA'):
        table_index = 2
    else: # elif (division == 'NAIA') | (division.startswith('JUCO')) | (division == 'California CC') | (division == 'NW Athletic Conference'):
        table_index = 1
    return find_table(division, response, table_index)


def find_table(division, html, table_index):
    try:
        if division.startswith('NCAA'):
            df = pd.read_html(html)[table_index]
            new_header = df.iloc[1] # grab the first row for the header
            df = df[2:] # take the data less the header row
            df.columns = new_header # set the header row as the df header
        else: # elif (division == 'NAIA') | (division.startswith('JUCO')) | (division == 'California CC') | (division == 'NW Athletic Conference'):
            df = pd.read_html(html)[table_index]
            df['count'] = df.groupby('Statistics category').cumcount()
            df['Statistics category'] = np.where(df['count'] == 1, df['Statistics category'] + '.1', df['Statistics category'])
    except:
        return pd.DataFrame()
    return df


def collect_stats(player, df):
    out_dict = dict()

    # Standardize tables
    stat_type = 'A'
    if 'Year' in df.columns:
        out_dict, stat_type = read_ncaa_table(df)
    elif 'Opponent' in df.columns:
        out_dict, stat_type = read_naia_table(df)
    else:
        out_dict = read_table(df)

    out_dict['Name'] = player['name']
    out_dict['Position'] = player['position']
    out_dict['School'] = player['school']
    out_dict['Division'] = player['division']
    out_dict['Type'] = stat_type
    return out_dict


def read_table(df):
    out_dict = dict()
    df_to_dict = dict(zip(df['Statistics category'], df['Overall']))
    stats_map = {
        'Games Played (G)': 'Games',
        'At Bats (AB)': 'At Bats',
        'Runs Scored (R)': 'Runs',
        'Hits (H)': 'Hits',
        'Doubles (2B)': 'Doubles',
        'Triples (3B)': 'Triples',
        'Home Runs (HR)': 'Home Runs',
        'Runs Batted In (RBI)': 'Runs Batted In',
        'Batting Average (AVG)': 'Batting Average',
        'Stolen Bases (SB)': 'Stolen Bases',
        'On-Base Percentage (OBP)': 'On Base Percentage',
        'Slugging Percentage (SLG)': 'Slugging Percentage',
        'Appearances (G)': 'Appearances',
        'Games Started (GS)': 'Games started',
        'Innings Pitched (IP)': 'Innings Pitched',
        'Wins (W)': 'Wins',
        'Losses (L)': 'Losses',
        'Earned Runs (ER)': 'Earned Runs',
        'Hits Allowed (H)': 'Hits.1',
        'Walks Allowed (BB)': 'Walks.1',
        'Earned Run Average (ERA)': 'Earned Run Average',
        'Saves (SV)': 'Saves',
        'Strikeouts (K)': 'Strikeouts.1'
    }

    for stat_out, stat_in in stats_map.items():
        if stat_in in df_to_dict.keys():
            out_dict[stat_out] = df_to_dict[stat_in]

    return out_dict


def read_ncaa_table(df):
    out_dict = dict()
    year = os.environ.get('YEAR')
    df_to_dict = df[df['Year'] == f'{int(year) - 1}-{year[2:]}'].to_dict('records')
    stats_map = {
        'Games Played (G)': 'GP',
        'At Bats (AB)': 'AB',
        'Runs Scored (R)': 'R',
        'Hits (H)': 'H',
        'Doubles (2B)': '2B',
        'Triples (3B)': '3B',
        'Home Runs (HR)': 'HR',
        'Runs Batted In (RBI)': 'RBI',
        'Batting Average (AVG)': 'BA',
        'Stolen Bases (SB)': 'SB',
        'On-Base Percentage (OBP)': 'OBPct',
        'Slugging Percentage (SLG)': 'SlgPct',
        'Appearances (G)': 'App',
        'Games Started (GS)': 'GS',
        'Innings Pitched (IP)': 'IP',
        'Wins (W)': 'W',
        'Losses (L)': 'L',
        'Earned Runs (ER)': 'ER',
        'Hits Allowed (H)': 'H',
        'Walks Allowed (BB)': 'BB',
        'Earned Run Average (ERA)': 'ERA',
        'Saves (SV)': 'SV',
        'Strikeouts (K)': 'SO'
    }

    if len(df_to_dict) > 0:
        df_to_dict = df_to_dict[0]
        for stat_out, stat_in in stats_map.items():
            if stat_in in df_to_dict.keys():
                out_dict[stat_out] = df_to_dict[stat_in]

    stat_type = 'H'
    if 'IP' in df.columns:
        stat_type = 'P'
        for key in ['Games Played (G)', 'At Bats (AB)', 'Runs Scored (R)', 'Hits (H)', 'Doubles (2B)', 'Triples (3B)', 'Home Runs (HR)']:
            out_dict[key] = 0
    else:
        for key in ['Hits Allowed (H)', 'Walks Allowed (BB)']:
            out_dict[key] = 0

    return out_dict, stat_type


def read_naia_table(df):
    out_dict = dict()
    df_to_dict = df[df['Opponent'] == 'TOTALS'].to_dict('records')
    stats_map = {
        'Games Played (G)': 'G',
        'At Bats (AB)': 'AB',
        'Runs Scored (R)': 'R',
        'Hits (H)': 'H',
        'Doubles (2B)': '2B',
        'Triples (3B)': '3B',
        'Home Runs (HR)': 'HR',
        'Runs Batted In (RBI)': 'RBI',
        'Batting Average (AVG)': 'Avg',
        'Stolen Bases (SB)': 'SB',
        'Slugging Percentage (SLG)': 'Slg%',
        'Appearances (G)': 'G',
        'Games Started (GS)': 'GS',
        'Innings Pitched (IP)': 'IP',
        'Wins (W)': 'W',
        'Losses (L)': 'L',
        'Earned Runs (ER)': 'ER',
        'Hits Allowed (H)': 'H',
        'Walks Allowed (BB)': 'BB',
        'Earned Run Average (ERA)': 'ERA',
        'Saves (SV)': 'SV',
        'Strikeouts (K)': 'K'
    }

    # Ensure logs are the right year
    year = os.environ.get('YEAR')
    if len(df[df['Date'].str.endswith(str(year), na=False)].index) == 0:
        print(f'Not showing {year} stats...')
        return dict()

    if len(df_to_dict) > 0:
        df_to_dict = df_to_dict[0]
        for stat_out, stat_in in stats_map.items():
            if stat_in in df_to_dict.keys():
                out_dict[stat_out] = df_to_dict[stat_in]

    if 'Slg%' in df_to_dict.keys(): # manually calculate OBP
        out_dict['Appearances (G)'] = 0 # make sure position players are not credited with Appearances
        hits, walks, hbp, ab, sf = int(df_to_dict['H']), int(df_to_dict['BB']), int(df_to_dict['HBP']), int(df_to_dict['AB']), int(df_to_dict['SF'])
        numerator, denominator = hits + walks + hbp, ab + walks + hbp + sf
        if denominator > 0:
            out_dict['On-Base Percentage (OBP)'] = str(round(numerator / denominator, 3))

    stat_type = 'H'
    if 'IP' in df.columns:
        stat_type = 'P'
        for key in ['Games Played (G)', 'At Bats (AB)', 'Runs Scored (R)', 'Hits (H)', 'Doubles (2B)', 'Triples (3B)', 'Home Runs (HR)']:
            out_dict[key] = 0
    else:
        for key in ['Hits Allowed (H)', 'Walks Allowed (BB)']:
            out_dict[key] = 0

    return out_dict, stat_type


def convert_dict_list_to_df(dict_list):
    df = pd.DataFrame(dict_list)
    df.replace(r'^-$', 0, regex=True, inplace=True)
    for col in ['Games Played (G)', 'At Bats (AB)', 'Runs Scored (R)', 'Hits (H)', 'Doubles (2B)', 'Triples (3B)', 'Home Runs (HR)', 'Runs Batted In (RBI)', 'Stolen Bases (SB)', 'Appearances (G)', 'Games Started (GS)', 'Wins (W)', 'Losses (L)', 'Earned Runs (ER)', 'Saves (SV)', 'Strikeouts (K)']:
        df[col] = df[col].fillna(0).astype(int, errors='ignore')
    for col in ['Innings Pitched (IP)', 'Earned Run Average (ERA)', 'Batting Average (AVG)', 'On-Base Percentage (OBP)', 'Slugging Percentage (SLG)']:
        df[col] = df[col].astype(float, errors='ignore')
    df['On-Base plus Slugging (OPS)'] = (df['On-Base Percentage (OBP)'] + df['Slugging Percentage (SLG)']).round(3)
    return df


def update_gsheet(df, last_run):
    blank_row = [['', '', '', '', '']]

    # define the scope
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']

    # add credentials to the account
    keyfile_dict = json.loads(os.environ.get('KEYFILE'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)

    # authorize the clientsheet 
    client = gspread.authorize(creds)

    # get the instance of the spreadsheet
    spreadsheet_name, worksheet_name = os.environ.get('SHEET_NAME'), 'Stats'
    if spreadsheet_name == 'Canadians in College Stats':
        spreadsheet_name += f': {os.environ.get("YEAR")}'
        worksheet_name = 'CBN'
    sheet = client.open(spreadsheet_name)

    # get the sheets of the Spreadsheet
    stats_sheet = sheet.worksheet(worksheet_name)
    stats_sheet_id = stats_sheet._properties['sheetId']

    # clear values in sheet
    clear_sheets(sheet, [stats_sheet_id])

    # initialize summary data
    summary_data = [['Canadian Baseball Network', '', '', '', last_run], ['Pete Berryman', '', '', '', '']]

    # Add title row
    stats_data = list()

    division_list = ['NCAA: Division 1', 'NCAA: Division 2', 'NCAA: Division 3', 'NAIA', 'JUCO: Division 1', 'JUCO: Division 2', 'JUCO: Division 3', 'California CC', 'NW Athletic Conference', 'USCAA']
    stat_list = ['Games Played (G)', 'Hits (H)', 'Doubles (2B)', 'Triples (3B)', 'Home Runs (HR)', 'Runs Scored (R)', 'Runs Batted In (RBI)', 'Stolen Bases (SB)', 'Batting Average (AVG)', 'On-Base Percentage (OBP)', 'Slugging Percentage (SLG)', 'On-Base plus Slugging (OPS)', 'Appearances (G)', 'Innings Pitched (IP)', 'Wins (W)', 'Earned Run Average (ERA)', 'Saves (SV)', 'Strikeouts (K)']

    for division in division_list:
        added_division_header = False
        df_by_division = df[df['Division'] == division].copy()
        for stat in stat_list:
            avg_flg = (stat in ['Batting Average (AVG)', 'On-Base Percentage (OBP)', 'Slugging Percentage (SLG)', 'On-Base plus Slugging (OPS)'])
            era_flg = (stat == 'Earned Run Average (ERA)')
            df_filtered = df_by_division.copy()
            ascending_flg = False
            if avg_flg == True:
                df_filtered = df_filtered[(df_filtered['At Bats (AB)'] >= 30) & (df_filtered[stat] > 0)] # At least 30 At Bats
            elif era_flg == True:
                df_filtered = df_filtered[df_filtered['Innings Pitched (IP)'] >= 20] # At least 20 Innings Pitched
                ascending_flg = True
            else:
                df_filtered = df_filtered[df_filtered[stat] > 0] # Eliminate 0's

            if len(df_filtered.index) > 0:
                df_filtered.sort_values(by=stat, ascending=ascending_flg, ignore_index=True, inplace=True)

                cutoff = df_filtered[stat].iloc[9] if len(df_filtered.index) >= 10 else df_filtered[stat].iloc[-1] # TBD: thresholds like AVG > 0.250 or ERA < 5.00 (Don't want to flaunt bad stats)
                df_filtered = df_filtered[df_filtered[stat] <= cutoff] if stat == 'Earned Run Average (ERA)' else df_filtered[df_filtered[stat] >= cutoff]
                df_filtered['Rank'] = df_filtered[stat].rank(method='min', ascending=ascending_flg).astype(int)
                df_filtered['Rank'] = np.where(df_filtered['Rank'].eq(df_filtered['Rank'].shift()), np.nan, df_filtered['Rank'])
                df_filtered = df_filtered[['Rank', 'Name', 'Position', 'School', stat]]

                if len(df_filtered.index) > 0:
                    if added_division_header == False:
                        stats_data += [[division, '', '', '', '']]
                        added_division_header = True
                    if avg_flg == True:
                        df_filtered[stat] = df_filtered[stat].apply(lambda x: '{0:.3f}'.format(x))
                        df_filtered[stat] = np.where(df_filtered[stat].str[0] == '0', df_filtered[stat].str[1:], df_filtered[stat])
                    elif era_flg == True:
                        df_filtered[stat] = df_filtered[stat].apply(lambda x: '{0:.2f}'.format(x))
                    stats_data += ([[stat, '', '', '', '']] + [df_filtered.columns.values.tolist()] + df_filtered.fillna('').values.tolist() + blank_row)

    # Add data to sheets
    data = summary_data + blank_row + stats_data
    stats_sheet.insert_rows(data, row=1)

    # Format division/class headers
    print('Formatting division headers...')
    format_headers(sheet, stats_sheet_id, stats_sheet.findall(re.compile(r'^(' + '|'.join(division_list) + r')$')), True, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    print('Formatting stat headers...')
    format_headers(sheet, stats_sheet_id, stats_sheet.findall(re.compile(r'^(' + '|'.join([stat.replace('(', '\(').replace(')', '\)') for stat in stat_list]) + r')$'), in_column=1), False, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    print('Miscellaneous formatting...')
    stats_sheet.format('A1:A{}'.format(len(summary_data)), {'textFormat': {'bold': True}}) # bold Summary text
    stats_sheet.format('E1:E1', {'backgroundColor': {'red': 1, 'green': 0.95, 'blue': 0.8}}) # light yellow background color
    stats_sheet.format('A{}:E{}'.format(len(summary_data) + 1, len(data)), {'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE'}) # center all cells
    stats_sheet.format('E1:E1', {'horizontalAlignment': 'CENTER'}) # center some other cells

    # Resize columns and re-size sheets
    stats_sheet.resize(rows=len(data))
    resize_columns(sheet, stats_sheet_id, {'Rank': 50, 'Name': 160, 'Position': 75, 'School': 295, 'Stat': 280})

    print('Done!\n')


# Run main function
if __name__ == "__main__":
    main()