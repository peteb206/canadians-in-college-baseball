from google_sheets import hub_spreadsheet, config
import cbn_utils
from model import School, Player
from bs4 import BeautifulSoup
import pandas as pd

pd.set_option('display.max_columns', None) # show all cols
pd.set_option('display.max_colwidth', None) # show full width of showing cols
pd.set_option('display.expand_frame_repr', False) # print cols side by side as it's supposed to be

def schools():
    # Fetch existing schools to dataframe
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    school_cols = schools_worksheet.columns()[:5]
    old_schools_df = schools_worksheet.to_df()
    old_schools_df = old_schools_df[school_cols]

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
        html = cbn_utils.get(f'https://{domain}/sports/bsb/{config["ACADEMIC_YEAR"]}/teams').text
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
    dropped_df, added_df = schools_worksheet.update_data(schools_df, sort_by = ['roster_url', 'id'])
    # This sorting will help with not duplicating players for schools in multiple leagues (NCAA takes precedence)

    # Email results to self
    html = '<div>No changes to the schools list</div>'
    if len(added_df.index) > 0:
        table = added_df.to_html(index = False, justify = 'left')
        html = f'<div>New schools ({len(added_df.index)})</div><div>{table}</div>{"<div><br></div>" * 2}'
    if len(dropped_df.index) > 0:
        table = dropped_df.to_html(index = False, justify = 'left')
        html = f'<div>Dropped schools ({len(dropped_df.index)})</div><div>{table}</div>{"<div><br></div>" * 2}'
    cbn_utils.send_email(html)

def reset_roster_scrape_results():
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    schools_count = schools_worksheet.row_count() - 1
    schools_worksheet.update_cells(f'H2:J{schools_count + 1}', [['', '', ''] for _ in range(schools_count)])

def players():
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    schools_df = schools_worksheet.to_df()
    schools_df['success'] = False

    all_canadians: list[Player] = list()
    # Iterate schools' roster pages
    for i, school_series in schools_df.iterrows():
        if (school_series['roster_url'] == '') | (school_series['notes'] != ''):
            continue # Skip schools that have no roster site or have already been scraped

        school = None
        try:
            school = School(
                id = school_series['id'],
                name = school_series['name'],
                league = school_series['league'],
                division = school_series['division'],
                state = school_series['state'],
                roster_url = school_series['roster_url'],
                stats_url = school_series['stats_url']
            )
        except Exception as e:
            cbn_utils.log(f'ERROR: School instance __init__ - {school_series["name"]} - {school_series["roster_url"]} - {str(e)}')
            continue # Skip iteration

        # Try to fetch players from school's roster page
        players: list[Player] = list()
        try:
            players = school.players()
        except Exception as e:
            cbn_utils.log(f'ERROR: school.players() - {school.name} - {school.roster_page.url()} - {str(e)}')

        # Extract Canadians from roster and handle scrape success
        canadians = [player for player in players if player.canadian]
        players_count, canadians_count = len(players), len(canadians)
        if school.roster_page.redirected() == False:
            # correct url in Google Sheet
            for canadian in canadians:
                canadian.school = school
                all_canadians.append(canadian)
            schools_df.at[i, 'success'] = len(players) > 0

        # Update Schools sheet row
        schools_worksheet.update_cells(f'H{i + 2}:J{i + 2}', [[players_count, canadians_count, school.roster_page.result()]])

    # Output
    new_players_df = pd.DataFrame([canadian.to_dict() for canadian in all_canadians]).drop('canadian', axis=1)
    new_players_df['positions'] = new_players_df['positions'].apply(lambda x: '/'.join(x)) # Convert list to "/" delimited string

    # Get existing values
    players_worksheet = hub_spreadsheet.sheet('Players')
    existing_players_df = players_worksheet.to_df()
    existing_players_df['positions'] = existing_players_df['positions'].str.upper() # INF is converted to inf
    existing_players_df = pd.merge(existing_players_df, schools_df.rename({'stats_url': 'school', 'id': 'school_id'}, axis = 1), how = 'left', on = 'school')

    # re-use existing_players_df to update new_players_df with manually updated info... use last_name, first_name, school to get id, throws, city, province
    new_players_df = new_players_df.merge(
        existing_players_df[['school', 'id', 'last_name', 'first_name', 'throws', 'city', 'province']],
        how = 'left',
        on = ['school', 'last_name', 'first_name'],
        suffixes = ['_fetched', '']
    ).fillna('')
    new_players_df['id'] = new_players_df.apply(lambda row: row['id_fetched'] if row['id_fetched'] != '' else row['id'], axis = 1) # Use saved id if fetched id not found
    new_players_df['throws'] = new_players_df.apply(lambda row: row['throws'] if row['throws'] != '' else row['throws_fetched'], axis = 1) # Use saved throws, if possible
    new_players_df['city'] = new_players_df.apply(lambda row: row['city'] if row['city'] != '' else row['city_fetched'], axis = 1) # Use saved city, if possible
    new_players_df['province'] = new_players_df.apply(lambda row: row['province'] if row['province'] != '' else row['province_fetched'], axis = 1) # Use saved province, if possible

    # Combine existing and new values based on success of scrape
    combined_players_df = pd.concat([existing_players_df[~existing_players_df['success'].fillna(False)], new_players_df], ignore_index = True)

    # Output players to Canadians in College Hub Google Sheet
    biographical_cols = ['school', 'id', 'last_name', 'first_name', 'positions', 'bats', 'throws', 'year', 'city', 'province', 'school_roster_url']
    deleted_rows_df, added_rows_df = players_worksheet.update_data(combined_players_df[biographical_cols], sort_by = ['last_name', 'first_name'])

    # Update stats in Canadians in College Hub Google Sheet
    stats_df = pd.merge(
        players_worksheet.to_df()[['school', 'id', 'last_name', 'first_name']],
        combined_players_df[players_worksheet.columns()],
        how = 'left'
    ).drop(biographical_cols, axis = 1)
    if len(stats_df.index) > 0:
        players_worksheet.update_cells(f'L2:AI{len(stats_df.index) + 1}', stats_df.values.astype(float).tolist())

    # Email results to self
    schools_df.rename({'name': 'school'}, axis = 1, inplace = True)
    added_rows_df = added_rows_df.rename({'school': 'stats_url'}, axis = 1).merge(schools_df, how = 'left', on = 'stats_url')
    deleted_rows_df = deleted_rows_df.rename({'school': 'stats_url'}, axis = 1).merge(schools_df, how = 'left', on = 'stats_url')
    email_html = cbn_utils.player_scrape_results_email_html(added_rows_df, deleted_rows_df)
    cbn_utils.send_email(email_html)

if __name__ == '__main__':
    schools()
    options = ['y', 'n']
    selection = ''
    while selection not in options:
        selection = input(f'Reset player scrape results for each school? {"/".join(options)} ')
    if selection == options[0]:
        reset_roster_scrape_results()
    players()