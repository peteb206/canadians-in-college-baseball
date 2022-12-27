from config import hub_spreadsheet
from model import School, Page
from cbn_utils import strikethrough
import requests
import pandas as pd
from datetime import datetime
import time


def players():
    last_run = 'Last updated: {}'.format(datetime.now().strftime("%B %d, %Y"))

    schools_worksheet = hub_spreadsheet.worksheet('Schools')
    schools_df = pd.DataFrame(schools_worksheet.get_all_records(), dtype=str)
    schools_df = schools_df[schools_df['scrape'] == 'TRUE'].drop('scrape', axis=1).reset_index(drop=True)
    schools_df['success'] = False

    # Set up logging
    index_col_length, school_col_length, players_col_length, canadians_col_length, roster_link_col_length = len(str(len(schools_df.index))), int(max(schools_df['school'].str.len())), 7, 9, 11
    print()
    print('Reading the rosters of {} schools...'.format(str(len(schools_df.index))))
    print()
    border_row = f'|{"-" * (index_col_length + 2)}|{"-" * (school_col_length + 2)}|{"-" * (players_col_length + 2)}|{"-" * (canadians_col_length + 2)}|{"-" * (roster_link_col_length + 2)}'
    print(border_row)
    print(f'| {"#".ljust(index_col_length)} | {"school".ljust(school_col_length)} | {"players".ljust(players_col_length)} | {"canadians".ljust(canadians_col_length)} | {"roster_link".ljust(roster_link_col_length)}')
    print(border_row)

    all_canadians, session = list(), requests.Session()

    # Start timer
    start_time = time.time()

    for i, school_series in schools_df.iterrows():
        school = School(
            name = school_series['school'],
            league = school_series['league'],
            division = str(school_series['division']),
            state = school_series['state'],
            roster_page = Page(url=school_series['roster_link'], session = session)
        )

        players, canadians = list(), list()
        try:
            players = school.players()
        except Exception as e:
            print(f'ERROR: {school.name} - {school.roster_page.url} - {str(e)}')

        canadians = [player for player in players if player.canadian]
        if not school.roster_page.redirect: # correct url in Google Sheet
            all_canadians += canadians
            schools_df.at[i, 'success'] = len(players) > 0

        print(f'| {str(i + 1).ljust(index_col_length)} | {school.name.ljust(school_col_length)} | {strikethrough(len(players)).ljust(players_col_length + (1 if len(players) < 10 else 2 if len(players) < 100 else 3)) if school.roster_page.redirect else str(len(players)).ljust(players_col_length)} | {strikethrough(len(canadians)).ljust(canadians_col_length + (1 if len(canadians) < 10 else 2)) if school.roster_page.redirect else str(len(canadians)).ljust(canadians_col_length)} | {school.roster_page.url} {school.roster_page.status}')
        time.sleep(0.8)

    print(border_row)

    new_players_df = pd.DataFrame([canadian.to_dict() for canadian in all_canadians]).drop('canadian', axis=1)
    new_players_df['positions'] = new_players_df['positions'].apply(lambda x: '/'.join(x)) # Convert list to "/" delimited string

    # Get existing values
    players_worksheet = hub_spreadsheet.worksheet('Players')
    players_worksheet_values = players_worksheet.get_all_values()
    players_worksheet_columns = players_worksheet_values[0]
    existing_players_df = pd.DataFrame(players_worksheet_values[1:], columns = players_worksheet_columns, dtype=str) # Read existing values
    existing_players_df = existing_players_df[existing_players_df['last_name'] != ''] # Ignore blank row
    existing_players_df['positions'] = existing_players_df['positions'].str.upper() # INF is converted to inf

    # Combine existing and new values based on success of scrape
    existing_players_df = pd.merge(existing_players_df, schools_df, how = 'left', on = ['school', 'league', 'division', 'state'])
    combined_players_df = pd.concat([existing_players_df[~existing_players_df['success'].fillna(False)], new_players_df], ignore_index = True).drop(['roster_link', 'success'], axis = 1)
    combined_players_df.sort_values(by = ['last_name', 'first_name'], inplace = True)

    # Output to Canadians in College Hub Google Sheet
    players_worksheet.resize(2) # Delete existing data
    players_worksheet.resize(3)
    players_worksheet.insert_rows(combined_players_df[players_worksheet_columns].values.tolist(), row = 3) # Add updated data

    # Last Run
    diff_df = pd.merge(existing_players_df, combined_players_df, on = ['last_name', 'first_name', 'school'], how='outer', suffixes = ['_', ''], indicator = 'diff')[players_worksheet_columns + ['diff']]
    diff_df = diff_df[diff_df['diff'] != 'both']
    diff_df['diff'] = diff_df['diff'].apply(lambda x: 'dropped' if x == 'left_only' else 'added')

    last_run_worksheet = hub_spreadsheet.worksheet('Last Run')
    last_run_worksheet.resize(2) # Delete existing data
    last_run_worksheet.resize(3)
    blank_row = ['' for _ in range(len(players_worksheet_columns))]
    last_run_data = [
        blank_row,
        [last_run] + ['' for _ in range(len(players_worksheet_columns) - 1)],
        blank_row,
        ['Added'] + ['' for _ in range(len(players_worksheet_columns) - 1)],
        blank_row
    ]
    last_run_data += diff_df[diff_df['diff'] == 'added'][players_worksheet_columns].fillna('').values.tolist()
    last_run_data += [
        blank_row,
        blank_row,
        ['Dropped'] + ['' for _ in range(len(players_worksheet_columns) - 1)],
        blank_row
    ]
    last_run_data += diff_df[diff_df['diff'] == 'dropped'][players_worksheet_columns].fillna('').values.tolist()
    last_run_worksheet.insert_rows(last_run_data, row = 3) # Add updated data

    # Print results
    print()
    print(f'{len(schools_df[schools_df["success"]].index)} successes... {len(schools_df[~schools_df["success"]].index)} empty rosters/failures...')
    print()
    print(f'--- Total time: {round((time.time() - start_time) / 60, 1)} minutes ---')