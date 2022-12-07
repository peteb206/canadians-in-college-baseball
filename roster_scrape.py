import requests
import pandas as pd
import re
import json
import time
import logging
import datetime
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import os
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logging.getLogger('numexpr').setLevel(logging.WARNING)
global logger
logger = logging.getLogger()
logger.addHandler(logging.FileHandler('scraper.log', 'w'))


def main():
    # Get roster sites
    year = os.environ.get('YEAR')
    schools_df = pd.read_csv(f'roster_pages_{year}.csv', dtype=str).fillna('')
    # Ask for input
    full_run = True
    if len(sys.argv) == 1:
        schools_df = get_input(schools_df)
    elif sys.argv[1] == 'n': # Determine if running full web scraper or just updating google sheet
        full_run = False

    # Last run:
    last_run = 'Last updated: {}'.format(datetime.datetime.now().strftime("%B %d, %Y"))
    logger.info('')
    logger.info(last_run)
    f = open('last_updated.txt', 'w')
    f.write(last_run)
    f.close()

    canadians_df = pd.read_csv(f'canadians_{year}.csv', dtype=str).fillna('') # Initialize canadians_df
    if full_run == True: # Run full web scraper
        # Set criteria for "Canadian" player search
        global city_strings, province_strings, country_strings, canada_strings, hometown_conversion_dict, ignore_strings
        city_strings, province_strings, country_strings, canada_strings, hometown_conversion_dict, ignore_strings = set_canadian_search_criteria()

        canadians_df_orig = canadians_df.copy()

        # Scrape players from school websites
        df_lists = iterate_over_schools(schools_df) # Iterate over schools
        canadians_dict_list = df_lists[1]
        canadians_df_new = format_df(canadians_dict_list) # Format dictionaries to dataframe
        canadians_df_new['stats_link'] = ''
        canadians_df_new['class'].fillna('Freshman', inplace=True)
        canadians_df_new['class'] = canadians_df_new['class'].str.replace(r'^\s*$', 'Freshman', regex=True)
        find_diffs(canadians_df_orig, canadians_df_new)

        # Combine new results with old results
        canadians_df = pd.concat([canadians_df_orig, pd.read_csv(f'canadians_manual_{year}.csv', dtype=str).fillna(''), canadians_df_new], ignore_index=True) # Add players who could not be scraped
        canadians_df.drop_duplicates(subset=['name', 'hometown'], keep='first', ignore_index=True, inplace=True) # Drop duplicate names (keep manually added rows if there is an "identical" scraped row)
        canadians_df.drop_duplicates(subset=['name', 'school'], keep='first', ignore_index=True, inplace=True) # Drop duplicate names part 2
        canadians_df.drop_duplicates(subset=['name', 'position', 'b', 't'], keep='first', ignore_index=True, inplace=True) # Drop duplicate names part 2

        # Organizing by class and sorting
        canadians_df['class'] = pd.Categorical(canadians_df['class'], ['Freshman','Sophomore', 'Junior', 'Senior', '']) # Create custom sort by class
        canadians_df['last_name'] = canadians_df['name'].str.replace('Š', 'S').str.split(' ').str[1]
        canadians_df = canadians_df.sort_values(by=['last_name', 'class', 'school'], ignore_index=True).drop('last_name', axis=1)

        canadians_df.astype(str).to_csv(f'canadians_{year}.csv', index=False, quoting=csv.QUOTE_NONNUMERIC) # Export to canadians_<year>.csv as a reference

    if full_run == False:
        canadians_df = canadians_df[['name', 'position', 'class', 'school', 'league', 'division', 'state', 'hometown']] # Keep only relevant columns
        update_gsheet(canadians_df, last_run) # Update Google Sheet

    # generate_html(canadians_df, 'canadians.html', last_run) # Generate HTML with DataTables

    logger.info('')
    logger.info('{} Canadian players found...'.format(str(len(canadians_df.index))))


def read_roster_norm(html, school):
    df = html[0]
    if school['school'] not in ['Arizona Christian University', 'University of Northwestern Ohio']: # Has a real roster and a prospect/JV roster... ensure real roster is chosen
        for temp_df in html:
            if len(temp_df.index) > len(df.index): # Assume largest table on page is actual roster
                df = temp_df
    if df.columns.dtype == 'int64':
        new_header = df.iloc[0] # grab the first row for the header
        df = df[1:] # take the data less the header row
        df.columns = new_header # set the header row as the df header
    elif ((school['school'] == 'Bethany College') & (school['state'] == 'WV')) | (school['school'] in [
        'Mineral Area',
        'Cowley',
        'Frank Phillips',
        'Kellogg',
        'Lincoln Trail',
        'Olivet Nazarene University',
        'Crowder',
        'Mount Mercy University',
        'Patrick & Henry',
        'Minnesota State',
        'Cochise',
        'University of Saint Francis',
        'Ohlone',
        'Western Tech',
        'Midway University',
        'Howard (TX)',
        "New Mexico"
    ]):
        # Columns in HTML table are messed up... keep an eye on these schools to see if fixed
        df.columns = ['Ignore', 'No.', 'Name', 'Pos.', 'B/T', 'Year', 'Ht.', 'Wt.', 'Hometown']
    elif school['school'] in [
        'Allan Hancock'
    ]:
        df.columns = ['Ignore', 'No.', 'Name', 'Pos.', 'B/T', 'Ht.', 'Wt.', 'Year', 'Hometown']
    elif school['school'] in [
        'McCook',
        'CCBC Essex'
    ]:
        df.columns = ['Ignore', 'No.', 'Name', 'Pos.', 'B/T', 'Year', 'Ht.', 'Hometown']
    elif school['school'] in [
        'Rivier University'
    ]:
        df.columns = ['Ignore', 'No.', 'Name', 'Year', 'Pos.', 'B/T', 'Ht.', 'Hometown']
    elif school['school'] in [
        'Morningside College'
    ]:
        df.columns = ['Ignore', 'No.', 'Name', 'Pos.', 'Year', 'Ht.', 'Hometown']
    elif school['school'] in [
        'Northeastern',
        'Cayuga',
        'Clark State'
    ]:
        df.columns = ['Ignore', 'No.', 'Name', 'Pos.', 'B/T', 'Year', 'Hometown']
    elif school['school'] in [
        'Dordt University'
    ]:
        df = df[df['Name'] != df['Year']]
    return df


def read_roster(session, school, header):
    foo = ''
    response = ''
    try_num = 1
    while try_num <= 3: # 3 tries
        try:
            return read_roster_norm(pd.read_html(school['roster_link']), school)
        except Exception as e1:
            if try_num > 1:
                print("read_roster_norm(pd.read_html(school['roster_link']), school):", str(e1))
        try:
            response = session.get(school['roster_link'], headers=header, timeout=10)
            return read_roster_norm(pd.read_html(response.text), school)
        except Exception as e2:
            if try_num > 1:
                print("read_roster_norm(pd.read_html(response.text), school):", str(e2))
        if try_num == 3:
            try:
                return str(response.text)
            except Exception as e3:
                foo = str(e3)
                # logger.info('--- e3: {} ---'.format(str(e3)))
        # logger.info('--- Failed attempt {} at {} ---'.format(str(try_num), school['roster_link']))
        try_num += 1
        time.sleep(0.5)
    return ''


def filter_canadians(df, canada_strings):
    out_list = list()
    roster_dict = df.to_dict(orient='records')
    index = 0
    while index < len(roster_dict):
        player = roster_dict[index]
        if 'Province' in player.keys(): # Applies to Canadian university
            player['__hometown'] = player['Hometown/High School'].split(':')[-1].split('/')[0].strip() + ', ' + player['Province'].split(':')[-1].strip()
            out_list.append(player)
        else: # Iterate over roster columns
            for attr in player:
                value = str(player[attr]).strip()
                if (any(canada_string.lower() in value.lower() for canada_string in canada_strings)) & (~any(ignore_string in value.lower() for ignore_string in ignore_strings)):
                    player['__hometown'] = value
                    out_list.append(player)
                    break
        index += 1
    return out_list


def set_canadian_search_criteria():
    city_strings = {
        'Quebec': ['montreal', 'saint-hilaire']
    }
    province_strings = {
        'Alberta': ['alberta', ', alta.', ', ab', 'a.b.'],
        'British Columbia': ['british columbia', ', b.c', ', bc'],
        'Manitoba': ['manitoba', ', mb', ', man.'],
        'New Brunswick': ['new brunswick', ', nb', 'n.b.'],
        'Newfoundland & Labrador': ['newfoundland', 'nfld', ', nl'],
        'Nova Scotia': ['nova scotia', ', ns', 'n.s.' ],
        'Ontario': [', ontario', ', on', ',on', '(ont)'],
        'Prince Edward Island': ['prince edward island', 'p.e.i.'],
        'Quebec': ['quebec', 'q.c.', ', qu', ', que.', ', qb'],
        'Saskatchewan': ['saskatchewan', ', sask', ', sk', 's.k.']
    }
    country_strings = {
        'Canada': ['canada', ', can']
    }
    canada_strings = list(sum(city_strings.values(), []))
    canada_strings.extend(sum(province_strings.values(), []))
    canada_strings.extend(sum(country_strings.values(), []))
    hometown_conversion_dict = {
        'ab': 'Alberta',
        'bc': 'British Columbia',
        'mb': 'Manitoba',
        'nb': 'New Brunswick',
        'nl': 'Newfoundland & Labrador',
        'ns': 'Nova Scotia',
        'on': 'Ontario',
        'ont': 'Ontario',
        'ont.': 'Ontario',
        'pei': 'Prince Edward Island',
        'qc': 'Quebec',
        'qu': 'Quebec',
        'sk': 'Saskatchewan'
    }
    for province, strings in province_strings.items():
         for string in strings:
                hometown_conversion_dict[re.sub(r'[^a-zA-Z]+', '', string)] = province
    ignore_strings = [
        'canada college',
        'west canada valley',
        'la canada',
        'australia',
        'mexico',
        'abac',
        'newfoundland, pa',
        'canada, minn',
        'new brunswick, n',
        'a.b. miller',
        ', nsw',
        'las vegas, nb',
        'ontario, california',
        ', queens'
    ]
    return city_strings, province_strings, country_strings, canada_strings, hometown_conversion_dict, ignore_strings


def get_input(schools_df):
    df_size = len(schools_df.index)
    run_all_rows = ''
    while run_all_rows not in ['y', 'n']:
        run_all_rows = input("\nRun script for all schools? Answer y/n... ")
        if run_all_rows not in ['y', 'n']:
            logger.error('Value must be "y" or "n"')
    if run_all_rows == 'n':
        start_row = '-1'
        while (int(start_row) < 0) | (int(start_row) >= df_size):
            start_row = input("\nStart with which row (>= 0 and <= {})... ".format(str(df_size - 1)))
            if int(start_row) < 0: 
                logger.error('Value must be greater than 0.')
            elif int(start_row) >= df_size:
                logger.error('Value must be less than or equal to {}.'.format(str(df_size - 1)))
        end_row = '-1'
        while (int(end_row) < 0) | (int(end_row) >= df_size) | (int(end_row) < int(start_row)):
            end_row = input("\nEnd with which row (>= 0 and <= {})... ".format(str(df_size - 1)))
            if int(end_row) < 0: 
                logger.error('Value must be greater than 0.')
            elif int(end_row) >= df_size:
                logger.error('Value must be less than or equal to {}.'.format(str(df_size - 1)))
            elif int(end_row) < int(start_row):
                logger.error('End row ({}) cannot be less than start row ({})'.format(end_row, start_row))
        schools_df = schools_df.loc[int(start_row):int(end_row)]
    return schools_df


def iterate_over_schools(schools_df):
    # Start timer
    start_time = time.time()

    # Print helpful info
    index_col_length, title_col_length, players_col_length, canadians_col_length, roster_link_col_length = 6, 52, 9, 11, 80
    logger.info('')
    logger.info('Reading the rosters of {} schools...'.format(str(len(schools_df.index))))
    logger.info('')
    border_row = '|{}|{}|{}|{}|{}|'.format('-'*index_col_length, '-'*title_col_length, '-'*players_col_length, '-'*canadians_col_length, '-'*roster_link_col_length)
    header_row = '|{}|{}|{}|{}|{}|'.format('#'.center(index_col_length), 'school'.center(title_col_length), 'players'.center(players_col_length), 'canadians'.center(canadians_col_length), 'roster_link'.center(roster_link_col_length))
    logger.info(border_row)
    logger.info(header_row)
    logger.info(border_row)

    success_count = 0
    empty_roster_count = 0
    fail_count = 0
    fail_index_list = list()
    schools_to_check_manually = list()

    # Set header for requests
    session = requests.Session()
    header = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36",
      "X-Requested-With": "XMLHttpRequest"
    }

    # Initialize roster_df_list and canadians_df_list
    roster_df_list = list()
    canadians_dict_list = list()

    # Iterate
    for index, school in schools_df.iterrows():
        print_row = '| {} | {} | {} | {} | {} |'.format(str(index).ljust(index_col_length-2), school['school'].ljust(title_col_length-2), '-'*(players_col_length-2), '-'*(canadians_col_length-2), str(school['roster_link']).ljust(roster_link_col_length-2))
        error_message = ''
        try:
            df = read_roster(session, school.copy().to_dict(), header) if school['roster_link'] != '' else pd.DataFrame()
            canadian_count = '0'
            if type(df) == type(pd.DataFrame()): # Table(s) exist in HTML
                # Add team's roster to list
                df['__school'], df['__league'], df['__division'], df['__state']  = school['school'], school['league'], school['division'], school['state']
                roster_df_list.append(df)
                canadians_dicts = filter_canadians(df, canada_strings) # Get a list of table rows that seem to have a Canadian player
                canadian_count = str(len(canadians_dicts))
            elif type(df) == type(''): # No table(s) exist in HTML... search all text for certain strings
                # if any(canada_string.lower() in df.lower() for canada_string in canada_strings):
                    # canadian_count = '*****' # String of interest found in HTML text
                    # schools_to_check_manually.append('{}: {}'.format(school['school'], school['roster_link']))
                df = pd.DataFrame()
            if (canadian_count != '0') & (canadian_count != '*****'):
                canadians_dict_list.extend(canadians_dicts)
            print_row = print_row.replace('-'*(canadians_col_length-2), canadian_count.center(canadians_col_length-2))
            print_row = print_row.replace('-'*(players_col_length-2), str(len(df.index)).center(players_col_length-2))
            if len(df.index) > 0:
                logger.info(print_row)
                success_count += 1
            else:
                # Roster exists but with no players
                logger.info(print_row)
                empty_roster_count += 1
        except Exception as e:
            error_message = str(e)
        if error_message != '':
            print_row = '| {} | {} | {} | {} | {}'.format(str(index).ljust(index_col_length-2), school['school'].ljust(title_col_length-2), '-'*(players_col_length-2), '-'*(canadians_col_length-2), str(school['roster_link']) + ': {}'.format(error_message))
            fail_index_list.append(index)
            fail_count += 1
            logger.info(print_row)
        time.sleep(0.05)
    logger.info(border_row)

    # Print results
    logger.info('')
    logger.info('{} successes... {} empty rosters... {} failures...'.format(str(success_count), str(empty_roster_count), str(fail_count)))
    if len(schools_to_check_manually) > 0:
        logger.info('')
        logger.info('Check these schools manually - could not process roster but may contain Canadians...')
        for school_and_link in schools_to_check_manually:
            logger.info('--- {}'.format(school_and_link))
    logger.info('')
    logger.info('--- Total time: {} minutes ---'.format(str(round((time.time() - start_time) / 60, 1))))
    return roster_df_list, canadians_dict_list


def find_diffs(prev_df, new_df):
    cols = ['name', 'position', 'class', 'school', 'hometown']
    compare_df = prev_df.fillna('').merge(new_df.fillna(''), on=cols, how='outer', indicator='diff')[cols + ['diff']]
    compare_df = compare_df[compare_df['diff'] != 'both']
    compare_df['diff'] = compare_df['diff'].apply(lambda x: 'inherited' if x == 'left_only' else 'scraped')
    pd.set_option('display.max_rows', None)
    pd.set_option('expand_frame_repr', False)
    logger.info('\nChanges from last scraper run:\n{}\n'.format(compare_df.sort_values(by=['name', 'diff'])))


def print_cols(roster_df_list):
    players_df = pd.concat(roster_df_list, ignore_index=True)
    all_columns = [str(i) for i in list(players_df.columns.values)]
    all_columns.sort()
    for col in all_columns:
        logger.info(col)


def format_player_name(string):
    full_name =  ' '.join(string.split(',')[::-1]).strip() # Format as "First Last"
    if full_name == full_name.upper(): # All caps... Set to proper case
        full_name = ' '.join([name_part[0].upper() + name_part[1:].lower() for name_part in full_name.split()])
    full_name = re.sub(r'\s*\d+', '', full_name) # Remove digits, e.g. First Last 0
    return full_name


def format_player_class(string):
    # Output Freshman, Sophomore, Junior or Senior
    grad_year_map = {"'21": "Senior", "'22": "Junior", "'23": "Sophomore", "'24": "Freshman"}
    if string in grad_year_map.keys():
        return grad_year_map[string]

    if ('j' in string.lower()) | ('3' in string):
        return 'Junior'
    elif ('so' in string.lower()) | (string.lower() == 's') | ('2' in string):
        return 'Sophomore'
    elif ('f' in string.lower()) | ('1' in string) | ('hs' in string.lower()) | (string.lower() == 'rs.') | (string.lower() == 'rs'):
        return 'Freshman'
    elif ('sr' in string.lower()) | ('gr' in string.lower()) | ('4' in string) | ('5' in string):
        return 'Senior'
    return string


def format_player_position(string):
    # Ouput position(s) in acronym form separated by a forward slash
    substitutions = {' ': '', 'PITCHER': 'P', 'RIGHT': 'R', 'LEFT': 'L', 'HANDED': 'H', '-H': 'H', 'THP': 'HP',
                     'CATCHER': 'C', 'UTILITY': 'UTL', 'FIRSTBASE': '1B', 'SECONDBASE': '2B', 'THIRDBASE': '3B',
                     'SHORTSTOP': 'SS', 'INFIELD': 'IF', 'OUTFIELD': 'OF', 'ER': '', 'MAN': '', ',R/R': ''}
    for from_string, to_string in substitutions.items():
        string = string.replace(from_string, to_string)
    return string


def format_player_hometown(string):
    string = re.sub(r'\s*\(*(?:Canada|CANADA|Can.|CN|CAN|CA)\)*\.*', '', string) # Remove references to Canada

    parentheses_search = re.search(r'\(([^)]+)', string) # Search for text within parentheses
    if parentheses_search != None:
        if parentheses_search.group(1).count(',') == 1:
            string = parentheses_search.group(1) # Text within parentheses is city/province
        else:
            string = string.split('(')[0].strip() # Text within parentheses is not helpful

    comma_count = string.count(',')
    no_school = string.split('/')[0].strip()
    if comma_count > 0:
        no_school_list = no_school.split(',')
        city = no_school_list[0].strip()
        province = no_school_list[1].strip()
        province_stripped = re.sub(r'[^a-zA-Z]+', '', province.lower()) # Ex. ", Sask." --> "sask"
        if province_stripped in hometown_conversion_dict.keys():
            province = hometown_conversion_dict[province_stripped] # Convert province abbreviations to full name
        elif (province[:3].lower() == 'can') | (province == ''):
            if city.strip().lower() in hometown_conversion_dict.keys():
                city = hometown_conversion_dict[city.strip().lower()] # In case province accidentally labeled as city
            return city # No province provided... just return city
        if city == city.upper(): # All caps... Set to proper case
            city = ' '.join([name_part[0].upper() + name_part[1:].lower() for name_part in city.split()])
        string = city + ', ' + province
    else:
        string = no_school
    return string


def format_df(dict_list):
    cols = ['name', 'position', 'b', 't', 'class', 'school', 'league', 'division', 'state', 'hometown']
    new_dict_list = list()
    for dictionary in dict_list:
        new_dict = dict()

        for col in cols:
            if col != 'state':
                new_dict['__' + col] = ''
        new_dict['_first_name'] = ''
        new_dict['_last_name'] = ''
        hometown_orig = ''

        for key, value in dictionary.items():
            key_str = str(key).lower()
            value_str = str(value)
            value_str = value_str.split(':')[-1].strip()
            if (len(value_str) != 0) & (value_str.lower() != 'nan'):
                # Set __class column
                if (new_dict['__class'] == '') & (key_str.startswith('cl') | key_str.startswith('y') | key_str.startswith('e') |
                                                  key_str.startswith('ci.') | ('year' in key_str) | (key_str in ['athletic', 'academic'])):
                    new_dict['__class'] = format_player_class(value_str)

                # Set __name columns
                elif ('first' in key_str) & ('last' not in key_str):
                    new_dict['_first_name'] = value_str
                elif (key_str == 'last') | (('last' in key_str) & ('nam' in key_str)):
                    new_dict['_last_name'] = value_str
                elif ('name' in key_str) | (key_str == 'player') | (key_str == 'student athlete'):
                    new_dict['__name'] = format_player_name(value_str) # Format as "First Last"

                # Set __position column
                elif key_str.startswith('po'):
                    new_dict['__position'] = format_player_position(value_str.upper())

                # Set __b and __t column
                elif (key_str.startswith('b')) & (not key_str.startswith('bi')):
                    new_dict['__b'] = value_str[0].upper()
                    if 'T' in key:
                        new_dict['__t'] = value_str[-1].upper()
                elif (key_str == 't') | (key_str.startswith('throw')) | (key_str.startswith('t/')):
                    new_dict['__t'] = value_str[0].upper()
                    if 'B' in key:
                        new_dict['__b'] = value_str[-1].upper()

                # Inlcude __ keys
                elif key_str.startswith('__'):
                    if key == '__hometown':
                        hometown_orig = value_str
                        new_dict[key_str] = format_player_hometown(value_str)
                    else:
                        new_dict[key_str] = value_str

        # Specify RHP/LHP for pitcher
        if ('P' in new_dict['__position']) & ('HP' not in new_dict['__position']) & (new_dict['__t'] != ''):
            new_dict['__position'] = new_dict['__position'].replace('P', new_dict['__t'] + 'HP')
        # Combine fist and last name if necessary
        if (new_dict['__name'] == '') & (new_dict['_first_name'] != '') & (new_dict['_last_name'] != ''):
            new_dict['__name'] = new_dict['_first_name'] + ' ' + new_dict['_last_name']
        elif ('Name' in dictionary.keys()) & ('Name.1' in dictionary.keys()):
            new_dict['__name'] = dictionary['Name'] + ' ' + dictionary['Name.1']
        if (new_dict['__name'] != '') & (new_dict['__school'] != hometown_orig) & (new_dict['__name'] != hometown_orig):
            new_dict['__name'] = re.sub(r'\s+', ' ', new_dict['__name']) # Remove unnecessary spaces in names
            new_dict_list.append(new_dict)

    canadians_df = pd.DataFrame(new_dict_list)
    canadians_df = canadians_df.loc[:, canadians_df.columns.str.startswith('__')]
    canadians_df.columns = canadians_df.columns.str.lstrip('__')
    return canadians_df[cols]


def update_gsheet(df, last_run):
    blank_row = [['', '', '', '', '']]

    # define the scope
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']

    # add credentials to the account
    keyfile_dict = json.loads(os.environ.get('KEYFILE'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)

    # authorize the clientsheet 
    client = gspread.authorize(creds)

    # get the instance of the Spreadsheet
    sheet = client.open(os.environ.get('SHEET_NAME'))

    # get the sheets of the Spreadsheet
    year = os.environ.get('YEAR')
    players_sheet = sheet.worksheet(str(year))
    players_sheet_id = players_sheet._properties['sheetId']

    # clear values in both sheets
    clear_sheets(sheet, [players_sheet_id])

    # initialize summary data
    summary_data = [['Canadian Baseball Network', '', '', '', last_run], ['Pete Berryman', '', '', '', '']] + blank_row
    summary_data += ([['Total', '{} players'.format(str(len(df.index))), '', '', '']] + blank_row)

    # Add title row
    col_headers = [[col[0].upper() + col[1:] for col in df.drop(['division', 'class'], axis=1).columns.values.tolist()]]
    player_data = list()
    coach_data = [['Coaches', '', '', '', '']] + blank_row
    coaches = pd.read_csv('coaches.csv', dtype=str).fillna('')

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
        df_split_div = df[(df['league'] == league) & (df['division'] == division)].drop(['division'], axis=1)
        if len(df_split_div.index) > 0:
            # Row/Division Header
            player_data += [[label, '', '', '', '']]

        for class_year in class_list:
            df_split_class = pd.DataFrame()
            if class_year == 'Freshman':
                df_split_class = df_split_div[(df_split_div['class'] == class_year) | (df_split_div['class'] == '')].drop(['class'], axis=1)
                class_year = 'Freshmen'
            else:
                df_split_class = df_split_div[df_split_div['class'] == class_year].drop(['class'], axis=1)
                if len(df_split_class.index) > 0:
                    player_data += blank_row
                class_year += 's'
            if len(df_split_class.index) > 0:
                player_data += ([[class_year, '', '', '', '']] + col_headers + df_split_class.values.tolist())

        # Compile data rows
        player_data += blank_row
        if len(df_split_div.index) > 0:
            summary_data.append([label + ' ', '{} players'.format(str(len(df_split_div.index))), '', '', ''])

        coaches_split_div = coaches[(coaches['league'] == league) & (coaches['division'] == division)].drop(['division'], axis=1)
        if len(coaches_split_div.index) > 0:
            coach_data += ([[label, '', '', '', '']] + [[col[0].upper() + col[1:] for col in coaches_split_div.columns.values.tolist()]] + coaches_split_div.values.tolist() + blank_row)

    # Add data to sheets
    data = summary_data + blank_row + player_data + coach_data
    players_sheet.insert_rows(data, row=1)

    # Format division/class headers
    division_list.append('Coaches')
    format_headers(sheet, players_sheet_id, players_sheet.findall(re.compile(r'^(' + '|'.join(division_list) + r')$')), True, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    format_headers(sheet, players_sheet_id, players_sheet.findall(re.compile(r'^(' + '|'.join(['Freshmen', 'Sophomores', 'Juniors', 'Seniors']) + r')$')), False, len(blank_row[0]))
    time.sleep(120) # break up the requests to avoid error
    players_sheet.format('A1:A{}'.format(len(summary_data)), {'textFormat': {'bold': True}}) # bold Summary text
    players_sheet.format('E1:E1', {'backgroundColor': {'red': 1, 'green': 0.95, 'blue': 0.8}}) # light yellow background color
    players_sheet.format('A4:B4', {'backgroundColor': {'red': 0.92, 'green': 0.92, 'blue': 0.92}}) # light grey background color
    players_sheet.format('A{}:E{}'.format(len(summary_data) + 1, len(data)), {'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE'}) # center all cells
    players_sheet.format('E1:E1', {'horizontalAlignment': 'CENTER'}) # center some other cells

    # Resize columns and re-size sheets
    players_sheet.resize(rows=len(data))
    resize_columns(sheet, players_sheet_id, {'Name': 160, 'Position': 81, 'School': 295, 'State': 40, 'Hometown': 340})
    players_sheet.format('B:B', {'wrapStrategy': 'WRAP'})

    logger.info('Google sheet updated with {} players...'.format(str(len(df.index))))


def clear_sheets(spreadsheet, sheet_ids):
    body = dict()
    requests = list()
    for sheet_id in sheet_ids:
        request = dict()
        update_cells_dict = dict()
        range_dict = dict()
        range_dict['sheetId'] = sheet_id
        update_cells_dict['range'] = range_dict
        update_cells_dict['fields'] = '*'
        request['updateCells'] = update_cells_dict
        requests.append(request)
    body['requests'] = requests
    spreadsheet.batch_update(body)


def resize_columns(spreadsheet, sheet_id, col_widths_dict):
    col = 0
    for width in col_widths_dict.values():
        body = {
            'requests': [
                {
                    'update_dimension_properties' : {
                        'range': {
                            'sheetId': sheet_id,
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


def format_headers(spreadsheet, sheet_id, occurrences, division_header, number_of_cols):
    color = 0.8
    font_size = 20
    if division_header == False:
        color = 0.92
        font_size = 14

    range = {
        'sheetId': sheet_id,
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


def csv_to_dict_list(csv_file):
    with open(csv_file) as f:
        return [{k: v for k, v in row.items()} for row in csv.DictReader(f, skipinitialspace=True)]


# Run main function
if __name__ == "__main__":
    main()