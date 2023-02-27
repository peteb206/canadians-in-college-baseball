import cbn_utils
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime
import re
import pandas as pd
class GoogleSpreadsheet:
    def __init__(self):
        # get API key
        self.__set_api_key('canadians-in-college-baseball-32cfc8392a02.json')

        # authorize the clientsheet
        self.__client: gspread.Client = gspread.authorize(
            ServiceAccountCredentials.from_json_keyfile_dict(
                json.loads(os.environ['GOOGLE_CLOUD_API_KEY']),
                [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
        )

    def __set_api_key(self, file_name: str):
        if os.path.isfile(file_name):
            with open(file_name) as f:
                os.environ['GOOGLE_CLOUD_API_KEY'] = f.read()

    def spreadsheet(self, name: str = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)

        return Spreadsheet(client = self.__client, name = name)

class Spreadsheet:
    def __init__(self, client: gspread.Client, name: str = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'spreadsheet', value = client, value_type = gspread.Client)
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)

        self.__spreadsheet: gspread.Spreadsheet = client.open(name)
        print(f'Connected to {name} spreadsheet...')

    def sheet(self, name: str = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)

        return Sheet(spreadsheet = self.__spreadsheet, name = name)

class Sheet:
    def __init__(self, spreadsheet: gspread.Spreadsheet, name: str = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'spreadsheet', value = spreadsheet, value_type = gspread.Spreadsheet)
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)

        self.__sheet: gspread.Worksheet = spreadsheet.worksheet(name)
        self.__columns = list()
        self.__values = list()

    def columns(self) -> list:
        self.__columns = list()
        columns = self.__sheet.get_values('1:1')
        if len(columns) == 1:
            self.__columns = columns[0]
        return self.__columns

    def to_list(self, include_header = False) -> list[list]:
        # Check types
        cbn_utils.check_arg_type(name = 'include_header', value = include_header, value_type = bool)

        self.__values = list()
        values = self.__sheet.get_all_values()
        if include_header:
            self.__values = values
        elif len(values) > 1:
            self.__values = values[1:]
        return self.__values

    def to_dict(self) -> list[dict]:
        return self.__sheet.get_all_records()

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.to_list(), columns = self.columns())

    def delete_row(self, row_number):
        self.__sheet.delete_rows(row_number)

    def update_data(self, new_data_df: pd.DataFrame, sort_by: list = [], with_filter: bool = True, freeze_cols: int = 0):
        # Check types
        cbn_utils.check_arg_type(name = 'new_data_df', value = new_data_df, value_type = pd.DataFrame)
        cbn_utils.check_arg_type(name = 'with_filter', value = with_filter, value_type = bool)
        cbn_utils.check_arg_type(name = 'freeze_cols', value = freeze_cols, value_type = int)

        # Compare existing and new data
        existing_data_df = self.to_df()[new_data_df.columns]
        existing_data_df['row_number'] = existing_data_df.index.to_series() + 2
        compare_data_df = pd.merge(existing_data_df, new_data_df, how = 'outer', indicator = 'source')
        change = False

        # Drop rows not found in new data
        rows_to_delete_df = compare_data_df[compare_data_df['source'] == 'left_only']
        number_of_rows_to_delete = len(rows_to_delete_df.index)
        if number_of_rows_to_delete > 0:
           change = True
           print(f'Deleting the following {number_of_rows_to_delete} rows:')
           print(rows_to_delete_df)
           rows_to_delete_df['row_number'].apply(lambda row_number: self.delete_row(row_number))

        # Add rows not found in existing data
        rows_to_add_df = compare_data_df[compare_data_df['source'] == 'right_only']
        number_of_rows_to_add = len(rows_to_add_df.index)
        if number_of_rows_to_add > 0:
           change = True
           print(f'Adding the following {number_of_rows_to_add} rows:')
           print(rows_to_add_df)
           self.__sheet.append_rows(rows_to_add_df.values.tolist())

        # Format the sheet
        if change:
            self.__sheet.clear_basic_filter() # Remove previous data filter
            self.__sheet.freeze(rows = 0, cols = 0) # Un-freeze header and columns
            row_count = len(existing_data_df.index) + number_of_rows_to_add - number_of_rows_to_delete + 1
            self.__sheet.resize(row_count) # Size so that there are no blank rows
            if with_filter:
                self.__sheet.freeze(rows = 1, cols = freeze_cols) # Freeze header and x cols
                self.__sheet.set_basic_filter(f'1:{row_count}') # Add data filter to first row
            elif freeze_cols > 0:
                self.__sheet.freeze(cols = freeze_cols) # Freeze x cols
            columns = self.columns()
            self.__sheet.columns_auto_resize(start_column_index = 0, end_column_index = len(columns) - 1) # Resize columns
            if len(sort_by) > 0:
                self.__sheet.sort(*tuple((columns.index(col) + 1, 'asc') for col in sort_by if col in columns))

google_spreadsheet = GoogleSpreadsheet()
hub_spreadsheet = google_spreadsheet.spreadsheet(name = 'Canadians in College Baseball Hub V2')
config = {x[0]: x[1] for x in hub_spreadsheet.sheet(name = 'Configuration').to_list()}

# TODO: create this by getting unique values from teams list
division_list = [
    ('NCAA', '1', 'NCAA: Division 1'),
    ('NCAA', '2', 'NCAA: Division 2'),
    ('NCAA', '3', 'NCAA: Division 3'),
    ('NAIA', '', 'NAIA'),
    ('JUCO', '1', 'JUCO: Division 1'),
    ('JUCO', '2', 'JUCO: Division 2'),
    ('JUCO', '3', 'JUCO: Division 3'),
    ('CCCAA', '', 'California CC'),
    ('NWAC', '', 'NW Athletic Conference'),
    ('USCAA', '', 'USCAA')
]

def update_canadians_sheet(copy_to_production = False):
    blank_row = [['', '', '', '', '']]

    coaches_worksheet, players_worksheet, last_run_worksheet = hub_spreadsheet.sheet('Coaches'), hub_spreadsheet.sheet('Players'), hub_spreadsheet.sheet('Last Run')
    players_worksheet_values = players_worksheet.get_all_values()
    players_df = pd.DataFrame(players_worksheet_values[1:], columns = players_worksheet_values[0], dtype=str) # Read existing values
    players_df = players_df[players_df['last_name'] != ''].rename({'positions': 'Position', 'school': 'School', 'state': 'State'}, axis = 1) # Ignore blank row
    players_df['Name'] = players_df.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)
    players_df['Hometown'] = players_df.apply(lambda row: f'{row["city"]}, {row["province"]}' if (row['city'] != '') & (row['province'] != '') else row['city'] if row['city'] != '' else row['province'], axis = 1)

    # clear values in sheet
    canadians_in_college_worksheet = hub_spreadsheet.sheet('Canadians in College')
    clear_sheets(hub_spreadsheet, [canadians_in_college_worksheet])

    # initialize summary data
    summary_data = [['Canadian Baseball Network', '', '', '', last_run_worksheet.acell('A4').value], ['Pete Berryman', '', '', '', '']] + blank_row
    summary_data += ([['Total', '{} players'.format(str(len(players_df.index))), '', '', '']] + blank_row)

    # Add title row
    col_headers = ['Name', 'Position', 'School', 'State', 'Hometown']
    player_data = list()
    coach_data = [['Coaches', '', '', '', '']] + blank_row
    coaches_values = coaches_worksheet.get_all_values()
    coaches_df = pd.DataFrame(coaches_values[1:], columns = coaches_values[0], dtype=str) # Read existing values
    coaches_df = coaches_df[coaches_df['last_name'] != ''].rename({'positions': 'Position', 'school': 'School', 'state': 'State'}, axis = 1) # Ignore blank row
    coaches_df['Name'] = coaches_df.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)
    coaches_df['Hometown'] = coaches_df.apply(lambda row: f'{row["city"]}, {row["province"]}' if (row['city'] != '') & (row['province'] != '') else row['city'] if row['city'] != '' else row['province'], axis = 1)

    class_list = ['Freshman', 'Sophomore', 'Junior', 'Senior']

    # Loop through divisions
    for division in division_list:
        league, division, label = division
        # Subset dataframe
        df_split_div = players_df[(players_df['league'] == league) & (players_df['division'] == division)].drop(['league', 'division'], axis=1)
        if len(df_split_div.index) > 0:
            # Row/Division Header
            player_data += [[label, '', '', '', '']]

        for class_year in class_list:
            df_split_class = pd.DataFrame()
            if class_year == 'Freshman':
                df_split_class = df_split_div[df_split_div['year'].isin([class_year, ''])].drop(['year'], axis=1)
                class_year = 'Freshmen'
            else:
                df_split_class = df_split_div[df_split_div['year'] == class_year].drop(['year'], axis=1)
                if len(df_split_class.index) > 0:
                    player_data += blank_row
                class_year += 's'
            if len(df_split_class.index) > 0:
                player_data += [[class_year, '', '', '', ''], col_headers] + df_split_class[col_headers].values.tolist()

        # Compile data rows
        if len(df_split_div.index) > 0:
            player_data += blank_row
            summary_data.append([label + ' ', '{} players'.format(str(len(df_split_div.index))), '', '', ''])

        coaches_split_div = coaches_df[(coaches_df['league'] == league) & (coaches_df['division'] == division)].drop(['league', 'division'], axis=1)
        if len(coaches_split_div.index) > 0:
            coach_data += [[label, '', '', '', ''], col_headers] + coaches_split_div[col_headers].values.tolist() + blank_row

    # Add data to sheets
    data = summary_data + blank_row + player_data + coach_data
    canadians_in_college_worksheet.insert_rows(data, row = 1)

    # Format division/class headers
    division_list.append('Coaches')
    format_headers(hub_spreadsheet, canadians_in_college_worksheet, canadians_in_college_worksheet.findall(re.compile(r'^(' + '|'.join([x[2] for x in division_list]) + r')$')), True, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    format_headers(hub_spreadsheet, canadians_in_college_worksheet, canadians_in_college_worksheet.findall(re.compile(r'^(' + '|'.join(['Freshmen', 'Sophomores', 'Juniors', 'Seniors']) + r')$')), False, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    canadians_in_college_worksheet.format('A1:A{}'.format(len(summary_data)), {'textFormat': {'bold': True}}) # bold Summary text
    canadians_in_college_worksheet.format('E1:E1', {'backgroundColor': {'red': 1, 'green': 0.95, 'blue': 0.8}}) # light yellow background color
    canadians_in_college_worksheet.format('A4:B4', {'backgroundColor': {'red': 0.92, 'green': 0.92, 'blue': 0.92}}) # light grey background color
    canadians_in_college_worksheet.format('A{}:E{}'.format(len(summary_data) + 1, len(data)), {'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE'}) # center all cells
    canadians_in_college_worksheet.format('E1:E1', {'horizontalAlignment': 'CENTER'}) # center some other cells

    # Resize columns and re-size sheets
    canadians_in_college_worksheet.resize(rows=len(data))
    resize_columns(hub_spreadsheet, canadians_in_college_worksheet, {'Name': 160, 'Position': 81, 'School': 295, 'State': 40, 'Hometown': 340})
    canadians_in_college_worksheet.format('B:B', {'wrapStrategy': 'WRAP'})

    # Copy sheet from Hub to Shared sheet
    if copy_to_production:
        year_spreadsheet = google_spreadsheet.sheet(name = f'Canadians in College {config["YEAR"]}')
        year_worksheet = year_spreadsheet.sheet(config['YEAR'])
        copy_and_paste_sheet(year_spreadsheet, canadians_in_college_worksheet, year_worksheet)
        resize_columns(year_spreadsheet, year_worksheet, {'Name': 160, 'Position': 81, 'School': 295, 'State': 40, 'Hometown': 340})

    print('Google sheet updated with {} players...'.format(str(len(players_df.index))))

def update_stats_sheet(copy_to_production = False):
    blank_row = [['', '', '', '', '']]

    canadians_in_college_stats_worksheet = hub_spreadsheet.sheet('Canadians in College Stats')

    stats_worksheet = hub_spreadsheet.sheet('Stats')
    stats_worksheet_values = stats_worksheet.get_all_values()
    stats_df = pd.DataFrame(stats_worksheet_values[1:], columns = stats_worksheet_values[0]) # Read existing values
    stats_df = stats_df[stats_df['stats_id'] != ''] # Ignore blank row
    stats_df = stats_df.astype({col: str if col == 'stats_id' else float if col in ['AVG', 'OBP', 'SLG', 'OPS', 'IP', 'ERA'] else int for col in stats_df.columns})
    stats_df[['AVG', 'OBP', 'SLG', 'OPS']] = stats_df[['AVG', 'OBP', 'SLG', 'OPS']].round(3)
    stats_df['ERA'] = stats_df['ERA'].round(2)
    stats_df['IP'] = stats_df['IP'].round(1)

    players_worksheet = hub_spreadsheet.sheet('Players')
    players_worksheet_values = players_worksheet.get_all_values()
    players_df = pd.DataFrame(players_worksheet_values[1:], columns = players_worksheet_values[0], dtype=str) # Read existing values
    players_df = players_df[players_df['stats_id'] != ''].rename({'school': 'School'}, axis = 1) # Ignore blank row
    players_df = pd.merge(players_df, stats_df, how = 'inner', on = 'stats_id')

    # clear values in sheet
    clear_sheets(hub_spreadsheet, [canadians_in_college_stats_worksheet])

    # initialize summary data
    summary_data = [
        ['Canadian Baseball Network', '', '', '', 'Last updated: {}'.format(datetime.now().strftime("%B %d, %Y"))],
        ['Pete Berryman', '', '', '', '']
    ]

    stats_data = list()

    batting_stats, batting_labels, pitching_stats, pitching_labels = list(), list(), list(), list()
    for stat_category, stat_value_label_dict in cbn_utils.stats_labels.items():
        for stat, label in stat_value_label_dict.items():
            if stat_category == 'batting':
                batting_stats.append(stat)
                batting_labels.append(f'{label} ({stat})')
            elif stat not in ['GS', 'L', 'ER', 'HA', 'BB']:
                pitching_stats.append(stat)
                pitching_labels.append(f'{label} ({"G" if stat == "APP" else stat})')

    for division in division_list:
        league, division, label = division
        added_league_header = False
        df_split_div = players_df[(players_df['league'] == league) & (players_df['division'] == division)]
        for i, stat in enumerate(batting_stats + pitching_stats):
            avg_flg = stat in ['AVG', 'OBP', 'SLG', 'OPS']
            df_filtered = df_split_div.rename({'positions': 'Position'}, axis = 1)
            ascending_flg = False
            if avg_flg == True:
                df_filtered = df_filtered[(df_filtered['AB'] >= 30) & (df_filtered[stat] > 0)] # At least 30 At Bats
            elif stat == 'ERA':
                df_filtered = df_filtered[df_filtered['IP'] >= 20] # At least 20 Innings Pitched
                ascending_flg = True
            else:
                df_filtered = df_filtered[df_filtered[stat] > 0] # Eliminate 0's

            if len(df_filtered.index) > 0:
                df_filtered.sort_values(by = stat, ascending = ascending_flg, ignore_index = True, inplace = True)

                cutoff = df_filtered[stat].iloc[9] if len(df_filtered.index) >= 10 else df_filtered[stat].iloc[-1]
                df_filtered = df_filtered[df_filtered[stat] <= cutoff] if stat == 'ERA' else df_filtered[df_filtered[stat] >= cutoff]
                df_filtered['Rank'] = df_filtered[stat].rank(method = 'min', ascending = ascending_flg).astype(int)
                df_filtered['tied'] = df_filtered['Rank'] == df_filtered['Rank'].shift()
                df_filtered['Rank'] = df_filtered.apply(lambda row: None if row['tied'] else row['Rank'], axis = 1)
                df_filtered['Name'] = df_filtered.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)
                stat_label = (batting_labels + pitching_labels)[i]
                df_filtered = df_filtered[['Rank', 'Name', 'Position', 'School', stat]]
                if stat == 'APP':
                    df_filtered.rename({stat: 'G'}, inplace = True)

                if len(df_filtered.index) > 0:
                    if added_league_header == False:
                        stats_data += [[label, '', '', '', '']]
                        added_league_header = True
                    if avg_flg == True:
                        df_filtered[stat] = df_filtered[stat].apply(lambda x: '{0:.3f}'.format(x) if x >= 1 else '{0:.3f}'.format(x)[1:])
                    elif stat == 'ERA':
                        df_filtered[stat] = df_filtered[stat].apply(lambda x: '{0:.2f}'.format(x))
                    stats_data += [[stat_label, '', '', '', ''], df_filtered.columns.values.tolist()] + df_filtered.fillna('').values.tolist() + blank_row

    # Add data to sheets
    data = summary_data + blank_row + stats_data
    canadians_in_college_stats_worksheet.insert_rows(data, row = 1)

    # Format division/class headers
    print('Formatting division headers...')
    format_headers(hub_spreadsheet, canadians_in_college_stats_worksheet, canadians_in_college_stats_worksheet.findall(re.compile(r'^(' + '|'.join([x[2] for x in division_list]) + r')$')), True, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    print('Formatting stat headers...')
    format_headers(hub_spreadsheet, canadians_in_college_stats_worksheet, canadians_in_college_stats_worksheet.findall(re.compile(r'^(' + '|'.join([stat_label.replace('(', '\(').replace(')', '\)') for stat_label in batting_labels + pitching_labels]) + r')$'), in_column=1), False, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    print('Miscellaneous formatting...')
    canadians_in_college_stats_worksheet.format('A1:A{}'.format(len(summary_data)), {'textFormat': {'bold': True}}) # bold Summary text
    canadians_in_college_stats_worksheet.format('E1:E1', {'backgroundColor': {'red': 1, 'green': 0.95, 'blue': 0.8}}) # light yellow background color
    canadians_in_college_stats_worksheet.format('A{}:E{}'.format(len(summary_data) + 1, len(data)), {'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE'}) # center all cells
    canadians_in_college_stats_worksheet.format('E1:E1', {'horizontalAlignment': 'CENTER'}) # center some other cells

    # Resize columns and re-size sheets
    canadians_in_college_stats_worksheet.resize(rows = len(data))
    resize_columns(hub_spreadsheet, canadians_in_college_stats_worksheet, {'Rank': 50, 'Name': 170, 'Position': 75, 'School': 295, 'Stat': 280})

    # Copy sheet from Hub to Shared sheet
    if copy_to_production:
        year_spreadsheet = google_spreadsheet.sheet(name = f'Canadians in College Stats: {config["YEAR"]}')
        year_worksheet = year_spreadsheet.sheet(config['YEAR'])
        copy_and_paste_sheet(year_spreadsheet, canadians_in_college_stats_worksheet, year_worksheet)
        resize_columns(year_spreadsheet, year_worksheet, {'Rank': 50, 'Name': 170, 'Position': 75, 'School': 295, 'Stat': 280})
    print('Done!')

def clear_sheets(spreadsheet, worksheets):
    body = dict()
    requests = list()
    for worksheet in worksheets:
        request = dict()
        update_cells_dict = dict()
        range_dict = dict()
        range_dict['sheetId'] = worksheet._properties['sheetId']
        update_cells_dict['range'] = range_dict
        update_cells_dict['fields'] = '*'
        request['updateCells'] = update_cells_dict
        requests.append(request)
    body['requests'] = requests
    spreadsheet.batch_update(body)

def resize_columns(spreadsheet, worksheet, col_widths_dict):
    col = 0
    for width in col_widths_dict.values():
        body = {
            'requests': [
                {
                    'update_dimension_properties' : {
                        'range': {
                            'sheetId': worksheet._properties['sheetId'],
                            'dimension': 'COLUMNS',
                            'startIndex': col,
                            'endIndex': col + 1
                        },
                        'properties': {
                            'pixelSize': width
                        },
                        'fields': 'pixelSize'
                    }
                }
            ]
        }
        spreadsheet.batch_update(body)
        col += 1

def format_headers(spreadsheet, worksheet, occurrences, division_header, number_of_cols):
    color = 0.8
    font_size = 20
    if division_header == False:
        color = 0.92
        font_size = 14

    range = {
        'sheetId': worksheet._properties['sheetId'],
        'startColumnIndex': 0,
        'endColumnIndex': number_of_cols
    }

    body = dict()
    requests = list()
    for occurrence in occurrences:
        row = occurrence.row
        # merge cells and format header
        range['startRowIndex'] = row - 1
        range['endRowIndex'] = row
        requests += [
            {
                'mergeCells': {
                    'mergeType': 'MERGE_ALL',
                    'range': range
                }
            }, {
                'repeatCell': {
                    'range': range,
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {
                                'red': color,
                                'green': color,
                                'blue': color
                            },
                            'textFormat': {
                                'fontSize': font_size,
                                'bold': True
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)',
                }
            }
        ]
        body['requests'] = requests
        spreadsheet.batch_update(body)

        # format column headers
        range['startRowIndex'] = row
        range['endRowIndex'] = row + 1
        body['requests'] = [
            {
                'repeatCell': {
                    'range': range,
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': True
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(textFormat)',
                }
            }
        ]
        spreadsheet.batch_update(body)
        time.sleep(2.5)

def copy_and_paste_sheet(destination_spreadsheet, source_worksheet, destination_worksheet):
    copied_worksheet = source_worksheet.copy_to(destination_spreadsheet._properties['id'])
    destination_spreadsheet.batch_update(
        {
            'requests': [
                {
                    'copyPaste': {
                        'source': {
                            'sheetId': copied_worksheet['sheetId']
                        },
                        'destination': {
                            'sheetId': destination_worksheet._properties['sheetId'],
                        },
                        'pasteType': 'PASTE_NORMAL'
                    }
                }, {
                    'deleteSheet': {
                        'sheetId': copied_worksheet['sheetId']
                    }
                }
            ]
        }
    )