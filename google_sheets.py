from config import google_spreadsheets, hub_spreadsheet, config_values
import time
import re
import pandas as pd


def update_canadians_sheet():
    blank_row = [['', '', '', '', '']]

    coaches_worksheet, players_worksheet, last_run_worksheet = hub_spreadsheet.worksheet('Coaches'), hub_spreadsheet.worksheet('Players'), hub_spreadsheet.worksheet('Last Run')
    players_worksheet_values = players_worksheet.get_all_values()
    players_df = pd.DataFrame(players_worksheet_values[1:], columns = players_worksheet_values[0], dtype=str) # Read existing values
    players_df = players_df[players_df['last_name'] != ''].rename({'positions': 'Position', 'school': 'School', 'state': 'State'}, axis = 1) # Ignore blank row
    players_df['Name'] = players_df.apply(lambda row: f'{row["first_name"]} {row["last_name"]}', axis = 1)
    players_df['Hometown'] = players_df.apply(lambda row: f'{row["city"]}, {row["province"]}' if (row['city'] != '') & (row['province'] != '') else row['city'] if row['city'] != '' else row['province'], axis = 1)

    # clear values in sheet
    canadians_in_college_worksheet = hub_spreadsheet.worksheet('Canadians in College')
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

    division_list = [
        ('NCAA', '1', 'NCAA: Division 1'),
        ('NCAA', '2', 'NCAA: Division 2'),
        ('NAIA', '', 'NAIA'),
        ('JUCO', '1', 'JUCO: Division 1'),
        ('JUCO', '2', 'JUCO: Division 2'),
        ('JUCO', '3', 'JUCO: Division 3'),
        ('CCCAA', '', 'California CC'),
        ('NWAC', '', 'NW Athletic Conference'),
        ('USCAA', '', 'USCAA')
    ]
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
    canadians_in_college_worksheet.insert_rows(data, row=1)

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
    year_spreadsheet = google_spreadsheets.spreadsheet(name = f'Canadians in College {config_values["YEAR"]}')
    year_worksheet = year_spreadsheet.worksheet(config_values['YEAR'])
    copy_and_paste_sheet(year_spreadsheet, canadians_in_college_worksheet, year_worksheet)

    print('Google sheet updated with {} players...'.format(str(len(players_df.index))))


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