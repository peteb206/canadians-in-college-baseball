import cbn_utils
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import pandas as pd

class GoogleSpreadsheet:
    def __init__(self):
        # get API key
        self.__set_api_key__('canadians-in-college-baseball-c74c89028d45.json')

        # authorize the clientsheet
        self.__client__: gspread.Client = gspread.authorize(
            ServiceAccountCredentials.from_json_keyfile_dict(
                json.loads(os.environ.get('GOOGLE_CLOUD_API_KEY')),
                [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
        )

    def __set_api_key__(self, file_name: str):
        if os.path.isfile(file_name):
            with open(file_name) as f:
                os.environ['GOOGLE_CLOUD_API_KEY'] = f.read()

    def spreadsheet(self, name: str = '') -> gspread.Spreadsheet:
        # Check types
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)

        # Check values
        cbn_utils.check_string_arg(name = 'name', value = name, disallowed_values = [''])

        spreadsheet = self.__client__.open(name)
        print(f'Connected to {name} spreadsheet...')
        return spreadsheet

def df(worksheet: gspread.Worksheet) -> pd.DataFrame:
    all_values = worksheet.get_values()
    if len(all_values) > 0:
        return pd.DataFrame(all_values[1:], columns = all_values[0])
    return pd.DataFrame()

google_spreadsheet = GoogleSpreadsheet()
hub_spreadsheet = google_spreadsheet.spreadsheet(name = 'Canadians in College Baseball Hub')
config = {row['key']: row['value'] for _, row in df(hub_spreadsheet.worksheet('Configuration')).iterrows()}

def set_sheet_header(worksheet: gspread.Worksheet, sort_by: list = [], with_filter: bool = True, freeze_cols: int = 0):
    worksheet.clear_basic_filter() # Remove previous data filter
    df_ = df(worksheet)
    row_count = len(df_.index) + 1
    worksheet.resize(row_count) # Size so that there are no blank rows
    if with_filter:
        worksheet.freeze(rows = 1, cols = freeze_cols) # Freeze header and x cols
        worksheet.set_basic_filter(f'1:{row_count}') # Add data filter to first row
    elif freeze_cols > 0:
        worksheet.freeze(cols = freeze_cols) # Freeze x cols
    columns = list(df_.columns)
    if (row_count > 0) & (len(sort_by) > 0):
        worksheet.sort(*tuple((columns.index(col) + 1, 'asc') for col in sort_by if col in columns), range = f'A2:{gspread.utils.rowcol_to_a1(row_count, len(columns))}')
    worksheet.columns_auto_resize(start_column_index = 0, end_column_index = len(columns) - 1) # Resize column

def update_canadians_sheet():
    col_widths = {'Name': 160, 'Position': 83, 'School': 295, 'State': 40, 'Hometown': 340}
    blank_row = ['' for _ in col_widths.keys()]

    players_worksheet = hub_spreadsheet.worksheet('Players')
    players_manual_spreadsheet = hub_spreadsheet.worksheet('Players (Manual)')
    schools_worksheet = hub_spreadsheet.worksheet('Schools')
    players_df = pd.merge(
        pd.concat(
            [
                df(players_worksheet),
                df(players_manual_spreadsheet)
            ],
            ignore_index = True
        ),
        df(schools_worksheet),
        how = 'inner',
        left_on = 'school',
        right_on = 'stats_url'
    )

    players_df.drop_duplicates(subset = ['roster_url', 'last_name', 'first_name'], inplace = True) # keep first (highest league for a school)
    players_df.rename({'positions': 'Position', 'name': 'School', 'state': 'State'}, axis = 1, inplace = True)
    players_df.sort_values(by = ['last_name', 'first_name'], ignore_index = True, inplace = True)
    players_df['Name'] = players_df.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)
    players_df['Hometown'] = players_df.apply(lambda row: f'{row["city"]}, {row["province"]}' if (row['city'] != '') & (row['province'] != '') else row['city'] if row['city'] != '' else row['province'], axis = 1)

    # initialize summary data
    now = datetime.now()
    summary_data = [
        ['Canadian Baseball Network', '', '', '', f'Last updated: {now.strftime("%B %d, %Y")}'],
        ['Pete Berryman', '', '', '', '' if str(now.year) == config['YEAR'] else (u'\u26A0' + ' If a player is missing from this list, it could be because')],
        ['', '', '', '', '' if str(now.year) == config['YEAR'] else f'many schools have not yet posted their {config["YEAR"]} rosters.'],
        ['Total', f'{len(players_df.index)} players', '', '', ''],
        blank_row
    ]

    coach_data = [
        ['Coaches', '', '', '', ''],
        blank_row
    ]
    coaches_worksheet = hub_spreadsheet.worksheet('Coaches')
    coaches_df = pd.merge(
        df(coaches_worksheet),
        df(schools_worksheet),
        how = 'inner',
        left_on = 'school',
        right_on = 'roster_url'
    )
    coaches_df.rename({'positions': 'Position', 'name': 'School', 'state': 'State'}, axis = 1, inplace = True)
    coaches_df['Name'] = coaches_df.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)
    coaches_df['Hometown'] = coaches_df.apply(lambda row: f'{row["city"]}, {row["province"]}' if (row['city'] != '') & (row['province'] != '') else row['city'] if row['city'] != '' else row['province'], axis = 1)

    # Loop through divisions
    player_data = list()
    for league in cbn_utils.leagues:
        league, division, label = league['league'], league['division'], league['label']
        # Subset dataframe
        df_split_div = players_df[players_df['league'] == league].copy()
        if league != 'NAIA': # Ignore NAIA divisions but use for other leagues
            df_split_div = df_split_div[df_split_div['division'] == division].copy()
        df_split_div.drop(['league', 'division'], axis = 1, inplace = True)
        if len(df_split_div.index) > 0:
            # Row/Division Header
            player_data.append([label, '', '', '', ''])

        for class_year in ['Freshman', 'Sophomore', 'Junior', 'Senior']:
            df_split_class = pd.DataFrame()
            if class_year == 'Freshman':
                df_split_class = df_split_div[df_split_div['year'].isin([class_year, ''])].drop(['year'], axis=1)
                class_year = 'Freshmen'
            else:
                df_split_class = df_split_div[df_split_div['year'] == class_year].drop(['year'], axis=1)
                if len(df_split_class.index) > 0:
                    player_data.append(blank_row)
                class_year += 's'
            if len(df_split_class.index) > 0:
                player_data += [[class_year, '', '', '', ''], list(col_widths.keys())] + df_split_class[list(col_widths.keys())].values.tolist()

        # Compile data rows
        if len(df_split_div.index) > 0:
            player_data.append(blank_row)
            summary_data.append([label + ' ', f'{len(df_split_div.index)} players', '', '', ''])

        coaches_split_div = coaches_df[coaches_df['league'] == league].copy()
        if league != 'NAIA': # Ignore NAIA divisions but use for other leagues
            coaches_split_div = coaches_split_div[coaches_split_div['division'] == division].copy()
        coaches_split_div.drop(['league', 'division'], axis = 1, inplace = True)
        if len(coaches_split_div.index) > 0:
            coach_data += [[label, '', '', '', ''], list(col_widths.keys())] + coaches_split_div[list(col_widths.keys())].values.tolist() + [blank_row]

    # Add data to sheets
    data = summary_data + [blank_row] + player_data + coach_data
    data.pop()
    try:
        canadians_in_college_worksheet = hub_spreadsheet.worksheet('Canadians in College')
        hub_spreadsheet.del_worksheet(canadians_in_college_worksheet)
    except:
        pass
    canadians_in_college_worksheet = hub_spreadsheet.add_worksheet('Canadians in College', rows = 1, cols = 1)
    canadians_in_college_worksheet.insert_rows(data)

    # Visual formatting
    cbn_utils.leagues.append({'league': '', 'division': '', 'label': 'Coaches'})
    format_sheet(hub_spreadsheet, canadians_in_college_worksheet, total_rows = len(data), summary_data_rows = len(summary_data), col_widths_dict = col_widths)

    # Copy sheet from Hub to Shared sheet
    year_spreadsheet = google_spreadsheet.spreadsheet(name = f'Canadians in College {config["YEAR"]}')
    # year_spreadsheet = google_spreadsheet.spreadsheet(name = 'Test - Canadians in College')
    year_worksheet = year_spreadsheet.get_worksheet(0)
    copy_and_paste_sheet(year_spreadsheet, canadians_in_college_worksheet, year_worksheet)

def update_stats_sheet():
    col_widths = {'Rank': 50, 'Name': 170, 'Position': 75, 'School': 295, 'Stat': 200}
    blank_row = ['' for _ in col_widths.keys()]

    players_worksheet = hub_spreadsheet.worksheet('Players')
    players_manual_spreadsheet = hub_spreadsheet.worksheet('Players (Manual)')
    schools_worksheet = hub_spreadsheet.worksheet('Schools')
    players_df = pd.merge(
        pd.concat(
            [
                df(players_worksheet),
                df(players_manual_spreadsheet)
            ],
            ignore_index = True
        ),
        df(schools_worksheet),
        how = 'inner',
        left_on = 'school',
        right_on = 'stats_url'
    )
    players_df.rename({'positions': 'Position', 'name': 'School', 'state': 'State'}, axis = 1, inplace = True)
    players_df['Name'] = players_df.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)

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
    players_df[batting_stats + pitching_stats] = players_df[batting_stats + pitching_stats].replace('', 0)

    for league in cbn_utils.leagues:
        league, division, label = league['league'], league['division'], league['label']
        added_league_header = False
        # Subset dataframe
        df_split_div = players_df[players_df['league'] == league].copy()
        if league != 'NAIA': # Ignore NAIA divisions but use for other leagues
            df_split_div = df_split_div[df_split_div['division'] == division]
        df_split_div.drop(['league', 'division'], axis = 1, inplace = True)
        df_split_div.rename({'positions': 'Position'}, axis = 1, inplace = True)
        for i, stat in enumerate(batting_stats + pitching_stats):
            avg_flg = stat in ['AVG', 'OBP', 'SLG', 'OPS']
            df_filtered = df_split_div.copy()
            if avg_flg == True:
                df_filtered[stat] = df_filtered[stat].astype(float).round(3)
                df_filtered = df_filtered[(df_filtered['AB'].astype(float) >= 30) & (df_filtered[stat] > 0)] # At least 30 At Bats
            elif stat == 'ERA':
                df_filtered[stat] = df_filtered[stat].astype(float).round(2)
                df_filtered = df_filtered[df_filtered['IP'].astype(float) >= 20] # At least 20 Innings Pitched
            else:
                if stat == 'IP':
                    df_filtered[stat] = df_filtered[stat].astype(float).round(1)
                else:
                    df_filtered[stat] = df_filtered[stat].astype(int)
                df_filtered = df_filtered[df_filtered[stat] > 0] # Eliminate 0's

            if len(df_filtered.index) > 0:
                df_filtered.sort_values(by = [stat, 'last_name', 'first_name'], ascending = [stat == 'ERA', True, True], ignore_index = True, inplace = True)

                cutoff = df_filtered[stat].iloc[9] if len(df_filtered.index) >= 10 else df_filtered[stat].iloc[-1]
                df_filtered = df_filtered[df_filtered[stat] <= cutoff] if stat == 'ERA' else df_filtered[df_filtered[stat] >= cutoff]
                df_filtered['Rank'] = df_filtered[stat].rank(method = 'min', ascending = (stat == 'ERA')).astype(int)
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
                    stats_data += [[stat_label, '', '', '', ''], df_filtered.columns.values.tolist()] + df_filtered.fillna('').values.tolist() + [blank_row]

    # Add data to sheets
    data = summary_data + [blank_row] + stats_data
    data.pop()
    try:
        canadians_in_college_stats_worksheet = hub_spreadsheet.worksheet('Canadians in College Stats')
        hub_spreadsheet.del_worksheet(canadians_in_college_stats_worksheet)
    except:
        pass
    canadians_in_college_stats_worksheet = hub_spreadsheet.add_worksheet('Canadians in College Stats', rows = 1, cols = 1)
    canadians_in_college_stats_worksheet.insert_rows(data)

    # Visual formatting
    format_sheet(hub_spreadsheet, canadians_in_college_stats_worksheet, total_rows = len(data), summary_data_rows = len(summary_data), col_widths_dict = col_widths)

    # Copy sheet from Hub to Shared sheet
    year_spreadsheet = google_spreadsheet.spreadsheet(name = f'Canadians in College Stats: {config["YEAR"]}')
    # year_spreadsheet = google_spreadsheet.spreadsheet(name = 'Test - Canadians in College Stats')
    year_worksheet = year_spreadsheet.get_worksheet(0)
    copy_and_paste_sheet(year_spreadsheet, canadians_in_college_stats_worksheet, year_worksheet)

def create_ballot_sheet():
    players_worksheet = hub_spreadsheet.worksheet('Players')
    players_manual_spreadsheet = hub_spreadsheet.worksheet('Players (Manual)')
    schools_worksheet = hub_spreadsheet.worksheet('Schools')
    players_df = pd.merge(
        pd.concat([df(players_worksheet), df(players_manual_spreadsheet)]),
        df(schools_worksheet), how = 'inner', left_on = 'school', right_on = 'stats_url'
    ) \
        .drop_duplicates(subset = ['last_name', 'first_name', 'roster_url']) \
        .sort_values(by = ['last_name', 'first_name'], ignore_index = True) \
        .rename({'name': 'School'}, axis = 1)
    players_df['Name'] = players_df.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)

    pitchers_df = players_df[(players_df['APP'].replace('', 0).astype(int) > 0) & (players_df['IP'].replace('', 0).astype(float) >= 10)]
    hitters_df = players_df[players_df['G.C'] != ''].copy()
    hitters_df['primaryPosition'] = hitters_df[['G.C', 'G.1B', 'G.2B', 'G.3B', 'G.SS', 'G.OF', 'G.DH']] \
        .astype(int).idxmax(axis = 1, numeric_only = True).apply(lambda x: x.replace('G.', ''))

    ballot_groups = [
        ('Right-handers', (pitchers_df['throws'] == 'R') & (pitchers_df['GS'].astype(int) / pitchers_df['APP'].astype(int) >= 0.5)),
        ('Left-handers', (pitchers_df['throws'] == 'L') & (pitchers_df['GS'].astype(int) / pitchers_df['APP'].astype(int) >= 0.5)),
        ('Relievers', pitchers_df['GS'].astype(int) / pitchers_df['APP'].astype(int) < 0.5),
        ('Catchers', hitters_df['primaryPosition'] == 'C'),
        ('First basemen', hitters_df['primaryPosition'] == '1B'),
        ('Second basemen', hitters_df['primaryPosition'] == '2B'),
        ('Third basemen', hitters_df['primaryPosition'] == '3B'),
        ('Shortstops', hitters_df['primaryPosition'] == 'SS'),
        ('Outfielders', hitters_df['primaryPosition'] == 'OF'),
        ('Designated hitters', hitters_df['primaryPosition'] == 'DH')
    ]
    pitcher_cols = ['Name', 'School'] + list(cbn_utils.stats_labels['pitching'].keys())
    hitter_cols = ['Name', 'School'] + list(cbn_utils.stats_labels['batting'].keys())

    data = list()
    for ballot_group, mask in ballot_groups:
        data.append([ballot_group])
        if ballot_group in ['Right-handers', 'Left-handers', 'Relievers']: # Pitchers
            data.append(['G' if col == 'APP' else 'H' if col == 'HA' else col for col in pitcher_cols])
            data += pitchers_df[mask][pitcher_cols].values.tolist()
        else: # Hitters
            data.append(hitter_cols)
            data += hitters_df[mask][hitter_cols].values.tolist()
        if ballot_group == 'Outfielders':
            data += [[], ['9 Choices'], ['3 1st'], ['3 2nd'], ['3 3rd'], ['Write-in'], [], [], []]
        else:
            data += [[], ['3 Choices'], ['1'], ['2'], ['3'], ['Write-in'], [], [], []]
    data.pop()

    ballot_spreadsheet = google_spreadsheet.spreadsheet(name = f'All-Canadian Ballot {config["YEAR"]}')
    ballot_worksheet = ballot_spreadsheet.add_worksheet('New', rows = 1, cols = 1)
    old_worksheet = ballot_spreadsheet.get_worksheet(0)
    ballot_spreadsheet.del_worksheet(old_worksheet)
    ballot_worksheet.update_title('Ballot')
    ballot_worksheet.insert_rows(data)

    # Formatting
    ballot_worksheet.columns_auto_resize(start_column_index = 0, end_column_index = 2) # Resize column
    requests = [{
        'updateDimensionProperties': {
            'range': {
                'sheetId': ballot_worksheet._properties['sheetId'],
                'dimension': 'COLUMNS',
                'startIndex': 2,
                'endIndex': 15
            },
            'properties': {
                'pixelSize': 50
            },
            'fields': 'pixelSize'
        }
    }]

    for header in ballot_worksheet.findall(re.compile(r'^(' + '|'.join([x[0] for x in ballot_groups]) + r')$')):
        # Position group
        range_ = {
            'sheetId': ballot_worksheet._properties['sheetId'],
            'startColumnIndex': 0,
            'endColumnIndex': 1,
            'startRowIndex': header.row - 1,
            'endRowIndex': header.row
        }
        requests.append({
            'repeatCell': {
                'range': range_.copy(),
                'cell': {
                    'userEnteredFormat': {
                        'backgroundColor': {
                            'red': 0.92,
                            'green': 0.92,
                            'blue': 0.92
                        },
                        'textFormat': {
                            'bold': True
                        }
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat)',
            }
        })
        # Stats column headers
        range_['startRowIndex'] += 1
        range_['endRowIndex'] += 1
        range_['endColumnIndex'] = 15
        requests.append({
            'repeatCell': {
                'range': range_.copy(),
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {
                            'bold': True
                        }
                    }
                },
                'fields': 'userEnteredFormat(textFormat)',
            }
        })

    for cell in ballot_worksheet.findall(re.compile(r'^(3 Choices|9 Choices|Write-in)$')):
        # 3 Choices / Write-in
        requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': ballot_worksheet._properties['sheetId'],
                    'startColumnIndex': 0,
                    'endColumnIndex': 1,
                    'startRowIndex': cell.row - 1,
                    'endRowIndex': cell.row
                },
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {
                            'bold': True
                        }
                    }
                },
                'fields': 'userEnteredFormat(textFormat)',
            }
        })

    ballot_spreadsheet.batch_update({
        'requests': requests
    })

def format_sheet(spreadsheet: gspread.Spreadsheet, worksheet: gspread.Worksheet, total_rows: int, summary_data_rows: int, col_widths_dict: dict[str, int]):
    requests = list()

    # Resize columns
    for i, width in enumerate(col_widths_dict.values()):
        requests.append({
            'updateDimensionProperties': {
                'range': {
                    'sheetId': worksheet._properties['sheetId'],
                    'dimension': 'COLUMNS',
                    'startIndex': i,
                    'endIndex': i + 1
                },
                'properties': {
                    'pixelSize': width
                },
                'fields': 'pixelSize'
            }
        })

    # Wrap text
    requests.append({
        'repeatCell': {
            'range': {
                'sheetId': worksheet._properties['sheetId'],
                'startColumnIndex': 0,
                'endColumnIndex': len(col_widths_dict.keys()),
                'startRowIndex': summary_data_rows + 1,
                'endRowIndex': total_rows
            },
            'cell': {
                'userEnteredFormat': {
                    'wrapStrategy': 'WRAP'
                }
            },
            'fields': 'userEnteredFormat(wrapStrategy)',
        }
    })

    # Total X Players
    # light grey background color
    requests.append({
        'repeatCell': {
            'range': {
                'sheetId': worksheet._properties['sheetId'],
                'startColumnIndex': 0,
                'endColumnIndex': 2,
                'startRowIndex': 3,
                'endRowIndex': 4
            },
            'cell': {
                'userEnteredFormat': {
                    'backgroundColor': {
                        'red': 0.92,
                        'green': 0.92,
                        'blue': 0.92
                    }
                }
            },
            'fields': 'userEnteredFormat(backgroundColor)',
        }
    })

    # Summary Data
    requests.append({
        'repeatCell': {
            'range': {
                'sheetId': worksheet._properties['sheetId'],
                'startColumnIndex': 0,
                'endColumnIndex': 1,
                'startRowIndex': 0,
                'endRowIndex': summary_data_rows
            },
            'cell': {
                'userEnteredFormat': {
                    'textFormat': {
                        'bold': True
                    }
                }
            },
            'fields': 'userEnteredFormat(textFormat)',
        }
    })

    # Center cells
    requests.append({
        'repeatCell': {
            'range': {
                'sheetId': worksheet._properties['sheetId'],
                'startColumnIndex': 0,
                'endColumnIndex': len(col_widths_dict.keys()),
                'startRowIndex': summary_data_rows + 1,
                'endRowIndex': total_rows
            },
            'cell': {
                'userEnteredFormat': {
                    'horizontalAlignment': 'CENTER',
                    'verticalAlignment': 'MIDDLE'
                }
            },
            'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment)',
        }
    })

    # Format headers & subheaders
    headers = worksheet.findall(re.compile(r'^(' + '|'.join([x['label'] for x in cbn_utils.leagues]) + r')$'))
    subheaders = worksheet.findall(
        re.compile(r'^(' + '|'.join(['Freshmen', 'Sophomores', 'Juniors', 'Seniors']) + r')$')
    ) + worksheet.findall(
        re.compile(r'^(' + '|'.join(list(cbn_utils.stats_labels['batting'].values()) + list(cbn_utils.stats_labels['pitching'].values())) + r') \(.*\)$')
    )
    for i, header in enumerate(headers + subheaders):
        color = 0.8 if i < len(headers) else 0.92
        range_ = {
            'sheetId': worksheet._properties['sheetId'],
            'startColumnIndex': 0,
            'endColumnIndex': len(col_widths_dict.keys()),
            'startRowIndex': header.row - 1,
            'endRowIndex': header.row
        }
        requests.append({
            'repeatCell': {
                'range': range_,
                'cell': {
                    'userEnteredFormat': {
                        'backgroundColor': {
                            'red': color,
                            'green': color,
                            'blue': color
                        },
                        'textFormat': {
                            'fontSize': 20 if i < len(headers) else 14,
                            'bold': True
                        }
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat)',
            }
        })
        requests.append({
            'mergeCells': {
                'mergeType': 'MERGE_ALL',
                'range': range_
            }
        })
        # Column headers
        requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': worksheet._properties['sheetId'],
                    'startColumnIndex': 0,
                    'endColumnIndex': len(col_widths_dict.keys()),
                    'startRowIndex': header.row,
                    'endRowIndex': header.row + 1
                },
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {
                            'bold': True
                        }
                    }
                },
                'fields': 'userEnteredFormat(textFormat)',
            }
        })

    # Resize number of rows
    requests.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': worksheet._properties['sheetId'],
                'gridProperties': {
                    'rowCount': total_rows
                },
            },
            'fields': 'gridProperties(rowCount)',
        }
    })

    # Last Updated
    requests.append({
        'repeatCell': {
            'range': {
                'sheetId': worksheet._properties['sheetId'],
                'startColumnIndex': 4,
                'endColumnIndex': len(col_widths_dict.keys()),
                'startRowIndex': 0,
                'endRowIndex': 1
            },
            'cell': {
                'userEnteredFormat': {
                    'backgroundColor': { # light yellow
                        'red': 1,
                        'green': 0.95,
                        'blue': 0.8
                    },
                    'horizontalAlignment': 'CENTER'
                }
            },
            'fields': 'userEnteredFormat(backgroundColor,horizontalAlignment)',
        }
    })

    spreadsheet.batch_update({
        'requests': requests
    })

def copy_and_paste_sheet(destination_spreadsheet: gspread.Spreadsheet, source_worksheet: gspread.Worksheet, destination_worksheet: gspread.Worksheet):
    copied_worksheet = source_worksheet.copy_to(destination_spreadsheet._properties['id']) # Copy to new, temporary sheet
    destination_spreadsheet.batch_update(
        {
            'requests': [
                { # Copy from temporary sheet to permanent sheet
                    'copyPaste': {
                        'source': {
                            'sheetId': copied_worksheet['sheetId']
                        },
                        'destination': {
                            'sheetId': destination_worksheet._properties['sheetId'],
                        },
                        'pasteType': 'PASTE_NORMAL'
                    }
                }, { # Resize number of rows
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': destination_worksheet._properties['sheetId'],
                            'gridProperties': {
                                'rowCount': len(source_worksheet.get_all_values())
                            },
                        },
                        'fields': 'gridProperties(rowCount)',
                    }
                }, { # Delete temporary sheet
                    'deleteSheet': {
                        'sheetId': copied_worksheet['sheetId']
                    }
                }
            ]
        }
    )

# if __name__ == '__main__':
#     update_canadians_sheet()
#     update_stats_sheet()
#     create_ballot_sheet()
