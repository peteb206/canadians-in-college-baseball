from google_sheets import hub_spreadsheet, config
import cbn_utils
from model import School, Page, Player
from bs4 import BeautifulSoup
import pandas as pd
import time

pd.set_option('display.max_columns', None) # show all cols
pd.set_option('display.max_colwidth', None) # show full width of showing cols
pd.set_option('display.expand_frame_repr', False) # print cols side by side as it's supposed to be

def schools():
    # Fetch existing schools to dataframe
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    school_cols = ['id', 'name', 'league', 'division', 'state']
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
        html = cbn_utils.get(f'https://{domain}/sports/bsb/{str(int(config["YEAR"]) - 1)}-{config["YEAR"][-2:]}/teams').text
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
    schools_worksheet.update_data(schools_df, sort_by = ['name'])

def reset_roster_scrape_results():
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    schools_count = schools_worksheet.row_count() - 1
    schools_worksheet.update_cells(f'H2:J{schools_count + 1}', [['', '', ''] for _ in range(schools_count)])

def players():
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    schools_df = schools_worksheet.to_df()
    schools_df['success'] = False
    # reset_roster_scrape_results() # Reset school roster scrape results | DO THIS MANUALLY

    all_canadians: list[Player] = list()
    # Iterate schools' roster pages
    for i, school_series in schools_df.iterrows():
        if (school_series['roster_url'] == '') | (school_series['notes'] != ''):
            continue # Skip schools that have no roster site or have already been scraped

        school = School(
            id = school_series['id'],
            name = school_series['name'],
            league = school_series['league'],
            division = school_series['division'],
            state = school_series['state'],
            roster_page = Page(url = school_series['roster_url']),
            stats_page = Page(url = school_series['stats_url'])
        )

        # Try to fetch players from school's roster page
        players: list[Player] = list()
        try:
            players = school.players()
        except Exception as e:
            cbn_utils.log(f'ERROR: {school.name} - {school.roster_page.url} - {str(e)}')

        # Extract Canadians from roster and handle scrape success
        canadians = [player for player in players if player.canadian]
        players_count, canadians_count = str(len(players)), str(len(canadians))
        if school.roster_page.redirect:
            players_count, canadians_count = cbn_utils.strikethrough(players_count), cbn_utils.strikethrough(canadians_count)
        else: # correct url in Google Sheet
            for j, canadian in enumerate(canadians):
                if j == 0:
                    try:
                        school.get_stats_df()
                    except:
                        pass
                canadian.school = school
                try:
                    canadian.get_stats()
                except:
                    pass
                all_canadians.append(canadian)
            schools_df.at[i, 'success'] = len(players) > 0

        # Update Schools sheet row
        schools_worksheet.update_cells(f'H{i + 2}:J{i + 2}', [[players_count, canadians_count, school.roster_page.status]])

    new_players_df = pd.DataFrame([canadian.to_dict() for canadian in all_canadians]).drop('canadian', axis=1)
    new_players_df['positions'] = new_players_df['positions'].apply(lambda x: '/'.join(x)) # Convert list to "/" delimited string

    # Get existing values
    player_cols = ['school', 'id', 'last_name', 'first_name', 'positions', 'bats', 'throws', 'year', 'city', 'province', 'school_roster_url', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG', 'OPS', 'APP', 'GS', 'IP', 'W', 'L', 'ER', 'HA', 'BB', 'ERA', 'SV', 'K']
    players_worksheet = hub_spreadsheet.sheet('Players')
    existing_players_df = players_worksheet.to_df()[player_cols]
    existing_players_df['positions'] = existing_players_df['positions'].str.upper() # INF is converted to inf

    # Combine existing and new values based on success of scrape...
    # TODO: re-use existing DF for ID, pos, b/t, etc. to avoid overwriting correct info...
    #       use last_name, first_name, school
    existing_players_df = pd.merge(existing_players_df, schools_df.rename({'stats_url': 'school'}, axis = 1), how = 'left', on = 'school')
    combined_players_df = pd.concat([existing_players_df[~existing_players_df['success'].fillna(False)], new_players_df], ignore_index = True)

    # Output to Canadians in College Hub Google Sheet
    players_worksheet.update_data(combined_players_df, sort_by = ['last_name', 'first_name'])

    # Last Run
    diff_df = pd.merge(existing_players_df, combined_players_df, on = ['last_name', 'first_name', 'school'], how = 'outer', suffixes = ['_', ''], indicator = 'diff')
    diff_df = diff_df[diff_df['diff'] != 'both']
    diff_df['diff'] = diff_df['diff'].apply(lambda x: 'dropped' if x == 'left_only' else 'added')
    diff_df = diff_df.rename({'school': 'stats_url'}, axis = 1).merge(schools_df.rename({'name': 'school'}, axis = 1), how = 'left', on = 'stats_url')
    diff_df = diff_df[['id', 'last_name', 'first_name', 'school', 'league', 'division', 'positions', 'bats', 'throws', 'year', 'city', 'province']]

    # Email results to self
    cbn_utils.send_results_email(diff_df)

def stats():
    players_worksheet = hub_spreadsheet.worksheet('Players')
    players_df = pd.DataFrame(players_worksheet.get_all_records(), dtype=str)
    players_df = players_df[players_df['stats_id'] != ''].reset_index(drop=True)
    players_df['success'] = False

    stats = list()

    for i, player_series in players_df.iterrows():
        player = Player(
            last_name = player_series['last_name'],
            first_name = player_series['first_name'],
            school = School(
                name = player_series['school'],
                league = player_series['league'],
                division = str(player_series['division']),
                state = player_series['state'],
                roster_page = Page(url = 'dummy')
            ),
            stats_id = player_series['stats_id']
        )

        player_stats = dict()
        try:
            player_stats = player.stats()
        except Exception as e:
            cbn_utils.log(f'ERROR: {player.first_name} {player.last_name} - {player.stats_url()} - {str(e)}')

        player_stats['stats_id'] = player.stats_id
        stats.append(player_stats)
        players_df.at[i, 'success'] = True

    new_stats_df = pd.DataFrame(stats)

    # Get existing values
    stats_worksheet = hub_spreadsheet.worksheet('Stats')
    stats_worksheet_values = stats_worksheet.get_all_values()
    stats_worksheet_columns = stats_worksheet_values[0]
    existing_stats_df = pd.DataFrame(stats_worksheet_values[1:], columns = stats_worksheet_columns) # Read existing values
    existing_stats_df = existing_stats_df[existing_stats_df['stats_id'] != ''] # Ignore blank row
    existing_stats_df = existing_stats_df.astype({col: str if col == 'stats_id' else float if col in ['AVG', 'OBP', 'SLG', 'OPS', 'IP', 'ERA'] else int for col in existing_stats_df.columns})

    # Combine existing and new values based on success of scrape
    existing_stats_df = pd.merge(existing_stats_df, players_df, how = 'left', on = 'stats_id')
    combined_stats_df = pd.concat([existing_stats_df[~existing_stats_df['success'].fillna(False)], new_stats_df], ignore_index = True)
    combined_stats_df[['AVG', 'OBP', 'SLG', 'OPS']] = combined_stats_df[['AVG', 'OBP', 'SLG', 'OPS']].round(3)
    combined_stats_df['ERA'] = combined_stats_df.apply(lambda row: 99.99 if row['ERA'] > 100 else row['ERA'], axis = 1).round(2)
    combined_stats_df['IP'] = combined_stats_df['IP'].round(1)
    combined_stats_df.sort_values(by = 'stats_id', inplace = True)

    # Output to Canadians in College Hub Google Sheet
    stats_worksheet.resize(2) # Delete existing data
    stats_worksheet.resize(3)
    stats_worksheet.insert_rows(combined_stats_df[stats_worksheet_columns].values.tolist(), row = 3) # Add updated data

if __name__ == '__main__':
    schools()
    players()
    # stats()