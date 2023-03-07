from google_sheets import hub_spreadsheet, config
import cbn_utils
from model import School, Page, Player
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

pd.set_option('display.max_columns', None) # show all cols
pd.set_option('display.max_colwidth', None) # show full width of showing cols
pd.set_option('display.expand_frame_repr', False) # print cols side by side as it's supposed to be

def schools():
    # Fetch existing schools to dataframe
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    school_cols = ['id', 'name', 'league', 'division', 'state', 'roster_url']
    old_schools_df = schools_worksheet.to_df()
    old_schools_df = old_schools_df[school_cols]

    def compare_and_join(df: pd.DataFrame) -> pd.DataFrame:
        df['name'] = df['name'].apply(lambda x: x.split('(')[0].strip())
        df = df.merge(
            old_schools_df,
            how = 'left',
            on = 'id',
            suffixes = ['', '_old']
        )
        return df[school_cols].fillna('')

    def get_ncaa_schools() -> pd.DataFrame:
        df = pd.read_json('https://web3.ncaa.org/directory/api/directory/memberList?type=12&sportCode=MBA')
        df = df[['orgId', 'nameOfficial', 'division', 'athleticWebUrl', 'memberOrgAddress']]
        df['name'] = df['nameOfficial']
        df['league'] = 'NCAA'
        df['id'] = df.apply(lambda row: f'=HYPERLINK(CONCAT("https://stats.ncaa.org/team/{row["orgId"]}/roster/", Configuration!B9), "{row["league"]}-{row["orgId"]}")' , axis = 1)
        df['division'] = df['division'].apply(lambda x: f'="{x}"')
        df['state'] = df['memberOrgAddress'].apply(lambda x: x['state'])
        df['site_domain'] = df['athleticWebUrl'].apply(lambda x: x.replace('www.', ''))
        return compare_and_join(df.sort_values(by = ['division', 'name'], ignore_index = True))

    def get_other_schools(league: str) -> pd.DataFrame:
        domain = ''
        if league == 'NAIA':
            domain = 'https://naiastats.prestosports.com'
        elif league == 'CCCAA':
            domain = f'https://www.cccaasports.org'
        elif league == 'NWAC':
            domain = f'https://nwacsports.com'
        elif league == 'USCAA':
            domain = f'https://uscaa.prestosports.com'
        else:
            return pd.DataFrame()
        html = cbn_utils.get(f'{domain}/sports/bsb/{str(int(config["YEAR"]) - 1)}-{config["YEAR"][-2:]}/teams').text
        soup = BeautifulSoup(html, 'html.parser')
        schools = list()
        for i, tr in enumerate(soup.find('table').find_all('tr')):
            if i > 0: # skip header row
                td = tr.find_all('td')[1]
                a = td.find('a')
                name = (td.text if a == None else a.text).strip()
                school_id = name.lower().replace(' ', '') if a == None else a['href'].split('/')[-1]
                schools.append({
                    'id': f'=HYPERLINK(CONCAT(CONCAT("{domain}/sports/bsb/", Configuration!B6), "/teams/{school_id}?view=lineup"), "{league}-{school_id}")',
                    'name': name,
                    'league': league
                })
        return compare_and_join(pd.DataFrame(schools))

    def get_naia_schools() -> pd.DataFrame:
        return get_other_schools('NAIA')

    def get_juco_schools() -> pd.DataFrame:
        domain = 'https://www.njcaa.org'
        html = cbn_utils.get(f'{domain}/sports/bsb/teams').text
        soup = BeautifulSoup(html, 'html.parser')
        schools, league, division = list(), 'JUCO', 0
        for div in soup.find_all('div', {'class': 'content-col'}):
            division += 1
            for a in div.find_all('a', {'class': 'college-name'}):
                school_id = a['href'].split('/')[-1]
                schools.append({
                    'id': f'=HYPERLINK(CONCAT(CONCAT("{domain}/sports/bsb/", Configuration!B6), "/div{division}/teams/{school_id}?view=roster"), "{league}-{school_id}")',
                    'name': a.text,
                    'league': league,
                    'division': f'="{division}"'
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

        # Analyze
        duplicate_schools_df = schools_df[schools_df.duplicated(subset = ['name', 'state'], keep = False)].sort_values(by = 'name', ignore_index = True)
        print('The following schools may be duplicated in the updated Google Sheet:')
        if len(duplicate_schools_df.index):
            print(duplicate_schools_df)
        print()

        duplicate_roster_df = schools_df[schools_df.duplicated(subset = 'roster_url', keep = False)].sort_values(by = 'roster_url', ignore_index = True)
        print('The following schools have the same roster url:')
        if len(duplicate_schools_df.index):
            print(duplicate_roster_df)

        return schools_df

    schools_df = get_schools()
    schools_worksheet.update_data(schools_df, sort_by = ['name'], freeze_cols = 2)

def reset_roster_scrape_results():
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    row_count = schools_worksheet.row_count()
    schools_worksheet.update_cells(f'G2:I{row_count}', [['', '', ''] for _ in range(row_count)])

def players():
    schools_worksheet = hub_spreadsheet.sheet('Schools')
    schools_df = schools_worksheet.to_df()
    schools_df['success'] = False
    reset_roster_scrape_results() # Reset school roster scrape results

    all_canadians = list()
    # Iterate schools' roster pages
    for i, school_series in schools_df.iterrows():
        roster_url = cbn_utils.replace_year_placeholder(school_series['roster_url'], config)
        if roster_url == '':
            break

        school = School(
            id = school_series['id'],
            name = school_series['name'],
            league = school_series['league'],
            division = school_series['division'],
            state = school_series['state'],
            roster_page = Page(url = roster_url)
        )

        # Try to fetch players from school's roster page
        players: list[Player] = list()
        try:
            players = school.players()
        except Exception as e:
            print(f'ERROR: {school.name} - {school.roster_page.url} - {str(e)}')

        # Extract Canadians from roster and handle scrape success
        canadians = [player for player in players if player.canadian]
        players_count, canadians_count = str(len(players)), str(len(canadians))
        if school.roster_page.redirect:
            players_count, canadians_count = cbn_utils.strikethrough(players_count), cbn_utils.strikethrough(canadians_count)
        else: # correct url in Google Sheet
            if len(canadians) > 0:
                school.player_stat_ids(config)
            for canadian in canadians:
                canadian.school = school
                canadian.get_id(config)
                all_canadians.append(canadian)
            schools_df.at[i, 'success'] = len(players) > 0

        # Update Schools sheet row
        schools_worksheet.update_cells(f'G{i + 2}:I{i + 2}', [[players_count, canadians_count, school.roster_page.status]])
        time.sleep(1)

    new_players_df = pd.DataFrame([canadian.to_dict() for canadian in all_canadians]).drop('canadian', axis=1)
    new_players_df['positions'] = new_players_df['positions'].apply(lambda x: '/'.join(x)) # Convert list to "/" delimited string

    # Get existing values
    players_worksheet = hub_spreadsheet.sheet('Players')
    players_worksheet_columns = players_worksheet.columns()
    existing_players_df = players_worksheet.to_df()
    existing_players_df['positions'] = existing_players_df['positions'].str.upper() # INF is converted to inf

    # Combine existing and new values based on success of scrape
    existing_players_df = pd.merge(existing_players_df, schools_df.rename({'id': 'school'}, axis = 1), how = 'left', on = 'school')
    combined_players_df = pd.concat([existing_players_df[~existing_players_df['success'].fillna(False)], new_players_df], ignore_index = True).drop(['roster_url', 'success'], axis = 1)

    # Output to Canadians in College Hub Google Sheet
    players_worksheet.update_data(
        combined_players_df[players_worksheet_columns],
        sort_by = ['last_name', 'first_name'],
        freeze_cols = 4
    )

    # Last Run
    diff_df = pd.merge(existing_players_df, combined_players_df, on = ['last_name', 'first_name', 'school'], how = 'outer', suffixes = ['_', ''], indicator = 'diff')
    diff_df = diff_df[diff_df['diff'] != 'both']
    diff_df['diff'] = diff_df['diff'].apply(lambda x: 'dropped' if x == 'left_only' else 'added')

    # Email results to self
    # cbn_utils.send_results_email(diff_df)

def stats():
    players_worksheet = hub_spreadsheet.worksheet('Players')
    players_df = pd.DataFrame(players_worksheet.get_all_records(), dtype=str)
    players_df = players_df[players_df['stats_id'] != ''].reset_index(drop=True)
    players_df['success'] = False

    # Set up logging
    index_col_length, stat_url_col_length, stat_col_length = len(str(len(players_df.index))), 97, 5
    batting_stats, pitching_stats = list(cbn_utils.stats_labels["batting"].keys()), list(cbn_utils.stats_labels["pitching"].keys())
    print()
    print('Checking the stats of {} players...'.format(str(len(players_df.index))))
    print()
    border_row = f'|{"-" * (index_col_length + 2)}|{"-" * (stat_url_col_length + 2)}|{"|".join(["-" * (stat_col_length + 2) for _ in range(len(batting_stats) + len(pitching_stats))])}|'
    print(border_row)
    print(f'| {"#".ljust(index_col_length)} | {"Stats URL".ljust(stat_url_col_length)} | {" | ".join([stat.ljust(stat_col_length) for stat in batting_stats + pitching_stats])} |')
    print(border_row)

    stats = list()

    # Start timer
    start_time = time.time()

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

        try:
            player_stats = player.stats()
            print(f'| {str(i + 1).ljust(index_col_length)} | {player.stats_url().ljust(stat_url_col_length)} | {" | ".join([str(stat).ljust(stat_col_length) for stat in player_stats.values()])} |')
            player_stats['stats_id'] = player.stats_id
            stats.append(player_stats)
            players_df.at[i, 'success'] = True
        except Exception as e:
            print(f'ERROR: {player.first_name} {player.last_name} - {player.stats_url()} - {str(e)}')
        time.sleep(1)

    print(border_row)

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

    # Print results
    print()
    print(f'--- Total time: {round((time.time() - start_time) / 60, 1)} minutes ---')

if __name__ == '__main__':
    schools()
    players()
    # stats()