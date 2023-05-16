import google_sheets
import cbn_utils
from model import School, Player, StatsPage
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

pd.set_option('display.max_columns', None) # show all cols
pd.set_option('display.max_colwidth', None) # show full width of showing cols
pd.set_option('display.expand_frame_repr', False) # print cols side by side as it's supposed to be

def schools():
    # Fetch existing schools to dataframe
    schools_worksheet = google_sheets.hub_spreadsheet.worksheet('Schools')
    school_cols = ['id', 'name', 'league', 'division', 'state']
    old_schools_df = google_sheets.df(schools_worksheet)[school_cols]

    def compare_and_join(df: pd.DataFrame) -> pd.DataFrame:
        df['name'] = df['name'].apply(lambda x: x.split('(')[0].strip())
        df = df.merge(
            old_schools_df,
            how = 'left',
            on = ['league', 'id'],
            suffixes = ['', '_old']
        )
        return df[school_cols].fillna('')

    def get_ncaa_schools() -> pd.DataFrame:
        df = pd.read_json(cbn_utils.get('https://web3.ncaa.org/directory/api/directory/memberList?type=12&sportCode=MBA').text)
        df = df[['orgId', 'nameOfficial', 'division', 'athleticWebUrl', 'memberOrgAddress']]
        df['name'] = df['nameOfficial']
        df['league'] = 'NCAA'
        df['id'] = df['orgId'].astype(str)
        df['division'] = df['division'].astype(str)
        df['state'] = df['memberOrgAddress'].apply(lambda x: x['state'])
        df['site_domain'] = df['athleticWebUrl'].apply(lambda x: x.replace('www.', ''))
        return compare_and_join(df.sort_values(by = ['division', 'name'], ignore_index = True))

    def get_other_schools(league: str) -> pd.DataFrame:
        domain = ''
        if league == 'NAIA':
            domain = cbn_utils.NAIA_DOMAIN
        elif league == 'CCCAA':
            domain = cbn_utils.CCCAA_DOMAIN
        elif league == 'NWAC':
            domain = cbn_utils.NWAC_DOMAIN
        elif league == 'USCAA':
            domain = cbn_utils.USCAA_DOMAIN
        else:
            return pd.DataFrame()
        html = cbn_utils.get(f'https://{domain}/sports/bsb/{google_sheets.config["ACADEMIC_YEAR"]}/teams').text
        soup = BeautifulSoup(html, 'html.parser')
        schools = list()
        for i, tr in enumerate(soup.find('table').find_all('tr')):
            if i > 0: # skip header row
                td = tr.find_all('td')[1]
                a = td.find('a')
                name = (td.text if a == None else a.text).strip()
                url_split = [] if a == None else a['href'].split('/')
                schools.append({
                    'id': name.lower().replace(' ', '') if len(url_split) == 0 else url_split[-1],
                    'name': name,
                    'league': league,
                    'division': url_split[-3] if league == 'NAIA' else ''
                })
        return compare_and_join(pd.DataFrame(schools))

    def get_naia_schools() -> pd.DataFrame:
        return get_other_schools('NAIA')

    def get_juco_schools() -> pd.DataFrame:
        domain = cbn_utils.JUCO_DOMAIN
        html = cbn_utils.get(f'https://{domain}/sports/bsb/teams').text
        soup = BeautifulSoup(html, 'html.parser')
        schools, league, division = list(), 'JUCO', 0
        for div in soup.find_all('div', {'class': 'content-col'}):
            division += 1
            for a in div.find_all('a', {'class': 'college-name'}):
                school_id = a['href'].split('/')[-1]
                schools.append({
                    'id': school_id,
                    'name': a.text,
                    'league': league,
                    'division': str(division)
                })
        return compare_and_join(pd.DataFrame(schools))

    def get_cccaa_schools() -> pd.DataFrame:
        return get_other_schools('CCCAA')

    def get_nwac_schools() -> pd.DataFrame:
        return get_other_schools('NWAC')

    def get_uscaa_schools() -> pd.DataFrame:
        return get_other_schools('USCAA')

    def get_schools() -> pd.DataFrame:
        # Fetch new schools to dataframe
        schools_df = pd.concat(
            [
                get_ncaa_schools(),
                get_naia_schools(),
                get_juco_schools(),
                get_cccaa_schools(),
                get_nwac_schools(),
                get_uscaa_schools()
            ],
            ignore_index = True
        )
        return schools_df

    schools_df = get_schools()

    # Compare existing and new data
    existing_df = google_sheets.df(schools_worksheet)[schools_df.columns]
    existing_df['row_number'] = existing_df.index.to_series() + 2
    compare_df = pd.merge(existing_df, schools_df, how = 'outer', indicator = 'source')

    # Drop rows not found in new data
    rows_to_delete_df = compare_df[compare_df['source'] == 'left_only'].reset_index(drop = True)
    number_of_rows_to_delete = len(rows_to_delete_df.index)
    if number_of_rows_to_delete > 0:
        schools_worksheet.freeze(rows = 0, cols = 0) # Un-freeze header and columns
        cbn_utils.log(f'Deleting the following {number_of_rows_to_delete} rows:')
        rows_to_delete_df = rows_to_delete_df.astype({'row_number': int}).drop('source', axis = 1).sort_values(by = 'row_number', ascending = False)
        print(rows_to_delete_df)
        time.sleep(len(rows_to_delete_df.index))
        rows_to_delete_df['row_number'].apply(lambda row_number: schools_worksheet.delete_rows(row_number))

    # Add rows not found in existing data
    rows_to_add_df = compare_df[compare_df['source'] == 'right_only'][schools_df.columns].reset_index(drop = True)
    number_of_rows_to_add = len(rows_to_add_df.index)
    if number_of_rows_to_add > 0:
        cbn_utils.log(f'Adding the following {number_of_rows_to_add} rows:')
        print(rows_to_add_df)
        time.sleep(1)
        schools_worksheet.append_rows(rows_to_add_df[schools_df.columns].values.tolist())
    google_sheets.set_sheet_header(schools_worksheet, sort_by = ['roster_url', 'id'])

    # Email results to self
    html = '<div>No changes to the schools list</div>'
    if len(rows_to_add_df.index) > 0:
        table = rows_to_add_df.to_html(index = False, justify = 'left')
        html = f'<div>New schools ({len(rows_to_add_df.index)})</div><div>{table}</div>{"<div><br></div>" * 2}'
    if len(rows_to_delete_df.index) > 0:
        table = rows_to_delete_df.to_html(columns = schools_df.columns, index = False, justify = 'left')
        html += f'<div>Dropped schools ({len(rows_to_delete_df.index)})</div><div>{table}</div>{"<div><br></div>" * 2}'
    cbn_utils.send_email(f'New Schools (Week of {datetime.now().strftime("%B %d, %Y")})', html)

def reset_roster_scrape_results():
    schools_worksheet = google_sheets.hub_spreadsheet.worksheet('Schools')
    schools_df = google_sheets.df(schools_worksheet)
    schools_count = len(schools_df.index)
    schools_worksheet.update(f'H2:J{schools_count + 1}', [['' for _ in range(3)] for _ in range(schools_count)])

def players():
    schools_worksheet = google_sheets.hub_spreadsheet.worksheet('Schools')
    schools_df = google_sheets.df(schools_worksheet)
    players_worksheet = google_sheets.hub_spreadsheet.worksheet('Players')
    cols = ['school', 'last_name', 'first_name', 'positions', 'bats', 'throws', 'year', 'city', 'province', 'school_roster_url']

    # Manual corrections
    corrections_df = google_sheets.df(google_sheets.hub_spreadsheet.worksheet('Corrections'))
    corrections = dict(zip(corrections_df['From'], corrections_df['To']))

    added_rows_df = pd.DataFrame(columns = cols)
    deleted_rows_df = added_rows_df.copy()

    # Iterate schools' roster pages
    roster_url = ''
    for i, school_series in schools_df.iterrows():
        if (school_series['roster_url'] in ['']) | school_series['roster_url'].endswith('#') | (school_series['notes'] != ''):
            continue # Skip schools that have no parseable roster site or have already been scraped

        school, roster_url = None, school_series['roster_url']
        try:
            school = School(
                id = school_series['id'],
                name = school_series['name'],
                league = school_series['league'],
                division = school_series['division'],
                state = school_series['state'],
                roster_url = roster_url,
                # stats_url = school_series['stats_url'],
                corrections = corrections
            )
        except Exception as e:
            cbn_utils.log(f'ERROR: School instance __init__ - {school_series["name"]} - {school_series["roster_url"]} - {str(e)}')
            continue # Skip iteration

        # Fetch players from school's roster page
        players = school.players()

        # Extract Canadians from roster and handle scrape success
        canadians = [player for player in players if player.canadian]
        if (school.roster_page.redirected() == False) & (len(players) > 0):
            # Successful
            # Get existing values
            players_df = google_sheets.df(players_worksheet)[cols]
            existing_school_canadians_df: pd.DataFrame = players_df[players_df['school'] == school_series['stats_url']].copy()
            existing_school_canadians_df['row'] = existing_school_canadians_df.index.to_series() + 2
            existing_school_canadians_df['positions'] = existing_school_canadians_df['positions'].str.upper() # INF is converted to inf

            # Re-use existing_players_df to update new_players_df with manually updated info...
            # use last_name, first_name, school to get id, throws, city, province
            scraped_school_canadians_df = pd.DataFrame([canadian.to_dict() for canadian in canadians], columns = cols)
            scraped_school_canadians_df['school'] = school_series['stats_url']
            scraped_school_canadians_df['school_roster_url'] = roster_url
            scraped_school_canadians_df['positions'] = scraped_school_canadians_df['positions'].apply(lambda x: '/'.join(x)) # Convert list to "/" delimited string
            school_canadians_df = scraped_school_canadians_df.merge(
                existing_school_canadians_df[['school', 'last_name', 'first_name', 'positions', 'year', 'throws', 'city', 'province']],
                how = 'left',
                on = ['school', 'last_name', 'first_name'],
                suffixes = ['_fetched', '']
            )
            school_canadians_df.fillna('', inplace = True)
            for attribute in ['positions', 'year', 'throws', 'city', 'province']:
                # Use saved attribute, if not blank (allows for manual fixes in Google Sheets)
                try:
                    school_canadians_df[attribute] = school_canadians_df.apply(lambda row: row[attribute] if row[attribute] != '' else row[f'{attribute}_fetched'], axis = 1).astype(object)
                except ValueError as e:
                    cbn_utils.log(f'ERROR: issue with attribute "{attribute}"... dataframe columns: {", ".join([col for col in school_canadians_df.columns])}')

            # Compare and add/delete rows as needed
            compare_df = existing_school_canadians_df.merge(school_canadians_df, how = 'outer', indicator = 'source')
            rows_to_delete_df = compare_df[compare_df['source'] == 'left_only'].copy()
            time.sleep(len(rows_to_delete_df.index))
            rows_to_delete_df['row'].apply(lambda x: players_worksheet.delete_rows(int(x)))
            deleted_rows_df = pd.concat([deleted_rows_df, rows_to_delete_df[cols]], ignore_index = True)
            rows_to_add_df = compare_df[compare_df['source'] == 'right_only'][cols]
            if len(rows_to_add_df.index):
                players_worksheet.append_rows(rows_to_add_df.values.tolist())
            added_rows_df = pd.concat([added_rows_df, rows_to_add_df], ignore_index = True)

        # Update Schools sheet row
        schools_worksheet.update(f'H{i + 2}:J{i + 2}', [[len(players), len(canadians), school.roster_page.result()]])

    google_sheets.set_sheet_header(players_worksheet, sort_by = ['school_roster_url', 'last_name', 'first_name'])

    # Email results to self
    schools_df.rename({'name': 'school'}, axis = 1, inplace = True)
    added_rows_df = added_rows_df.rename({'school': 'stats_url'}, axis = 1).merge(schools_df, how = 'left', on = 'stats_url')
    deleted_rows_df = deleted_rows_df.rename({'school': 'stats_url'}, axis = 1).merge(schools_df, how = 'left', on = 'stats_url')
    email_html = cbn_utils.player_scrape_results_email_html(added_rows_df, deleted_rows_df)
    cbn_utils.send_email(f'New Players (Week of {datetime.now().strftime("%B %d, %Y")})', email_html)

def stats():
    # Manual corrections
    corrections_df = google_sheets.df(google_sheets.hub_spreadsheet.worksheet('Corrections'))
    corrections = dict(zip(corrections_df['From'], corrections_df['To']))

    for sheet_name in ['Players (Manual)', 'Players']:
        players_worksheet = google_sheets.hub_spreadsheet.worksheet(sheet_name)
        players_df = google_sheets.df(players_worksheet)

        for stats_url in players_df['school'].unique():
            try:
                stats_page = StatsPage(stats_url, corrections = corrections)
                for i, player_row in players_df[players_df['school'] == stats_url].iterrows():
                    player = Player(
                        last_name = player_row['last_name'],
                        first_name = player_row['first_name']
                    )
                    player.add_stats(stats_page)
                    if player.id != '':
                        # Update player stats
                        stat_values = list(player.to_dict().values())[15:]
                        players_worksheet.update(f'K{i + 2}:AI{i + 2}', [[player.id] + stat_values])
            except Exception as e:
                cbn_utils.log(f'ERROR: Player.add_stats - {stats_url} - {str(e)}')

if __name__ == '__main__':
    # schools()

    options = ['y', 'n']
    # selection = ''
    # while selection not in options:
    #     selection = input(f'Reset player scrape results for each school? {"/".join(options)} ')
    # if selection == options[0]:
    #     reset_roster_scrape_results()
    # players()

    # stats()