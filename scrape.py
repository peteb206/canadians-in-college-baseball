import google_sheets
import cbn_utils
from model import School, Player, StatsPage, SchedulePage, BoxScore
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import re
import json

pd.set_option('display.max_columns', None) # show all cols
pd.set_option('display.max_colwidth', None) # show full width of showing cols
pd.set_option('display.expand_frame_repr', False) # print cols side by side as it's supposed to be

today_str = datetime.now().strftime("%Y-%m-%d")

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
        return compare_and_join(df.sort_values(by = ['division', 'name'], ignore_index = True))

    def get_other_schools(league: str, division: int = 0) -> pd.DataFrame:
        domain = ''
        if league == 'NAIA':
            domain = cbn_utils.NAIA_DOMAIN
        elif league == 'JUCO':
            domain = cbn_utils.JUCO_DOMAIN
        elif league == 'CCCAA':
            domain = cbn_utils.CCCAA_DOMAIN
        elif league == 'NWAC':
            domain = cbn_utils.NWAC_DOMAIN
        elif league == 'USCAA':
            domain = cbn_utils.USCAA_DOMAIN
        else:
            return pd.DataFrame()
        url = f'https://{domain}/sports/bsb/{google_sheets.config["ACADEMIC_YEAR"]}/div{division}/teams'
        if division not in [1, 2, 3]:
            url = f'https://{domain}/sports/bsb/{google_sheets.config["ACADEMIC_YEAR"]}/teams'
            if league == 'NAIA':
                url = f'{url}?dec=printer-decorator'
        html = cbn_utils.get(url).text
        soup = BeautifulSoup(html, 'html.parser')
        schools = list()
        schools_table = soup.find('table')
        if schools_table == None:
            return pd.DataFrame()
        for i, tr in enumerate(schools_table.find_all('tr')):
            if i > 0: # skip header row
                td = tr.find_all('td')[1]
                a = td.find('a')
                name = (td.text if a == None else a.text).strip()
                url_split = [] if a == None else a['href'].split('/')
                schools.append({
                    'id': name.lower().replace(' ', '') if len(url_split) == 0 else url_split[-1],
                    'name': name,
                    'league': league,
                    'division': str(division) if division in [1, 2, 3] else ''
                })
        return compare_and_join(pd.DataFrame(schools))

    def get_naia_schools() -> pd.DataFrame:
        return get_other_schools('NAIA')

    def get_juco_schools() -> pd.DataFrame:
        schools_df = pd.concat(
            [
                get_other_schools('JUCO', division = 1),
                get_other_schools('JUCO', division = 2),
                get_other_schools('JUCO', division = 3)
            ],
            ignore_index = True
        )
        return schools_df

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
    compare_df = pd.merge(existing_df, schools_df, how = 'outer', indicator = 'source')

    # Drop rows not found in new data
    rows_to_delete_df = compare_df[compare_df['source'] == 'left_only'][schools_df.columns].reset_index(drop = True)
    cbn_utils.log('')
    cbn_utils.log(f'{len(rows_to_delete_df.index)} Schools to Delete:')
    if len(rows_to_delete_df.index) > 0:
        cbn_utils.log(rows_to_delete_df.to_string())

    # Add rows not found in existing data
    rows_to_add_df = compare_df[compare_df['source'] == 'right_only'][schools_df.columns].reset_index(drop = True)
    cbn_utils.log('')
    cbn_utils.log(f'{len(rows_to_add_df.index)} Schools to Add:')
    if len(rows_to_add_df.index) > 0:
        cbn_utils.log(rows_to_add_df.to_string())
    cbn_utils.log('')

def players():
    schools_worksheet = google_sheets.hub_spreadsheet.worksheet('Schools')
    schools_df = google_sheets.df(schools_worksheet)
    players_worksheet = google_sheets.hub_spreadsheet.worksheet('Players')
    cols = ['school_roster_url', 'last_name', 'first_name', 'positions', 'throws', 'year', 'city', 'province']

    # Manual corrections
    corrections_df = google_sheets.df(google_sheets.hub_spreadsheet.worksheet('Corrections'))
    corrections = dict(zip(corrections_df['From'], corrections_df['To']))

    # Iterate schools' roster pages
    roster_url = ''
    for i, school_series in schools_df.iterrows():
        school_last_roster_check = school_series['last_roster_check']
        days_since_last_check = (datetime.today() - datetime.strptime(school_last_roster_check, "%Y-%m-%d")).days if school_last_roster_check != '' else 99
        # if i not in [55, 56]: # test a specific school (i should be 2 less than the row number in the google sheet)
        if (school_series['roster_url'] in ['']) | school_series['roster_url'].endswith('#') | (days_since_last_check < 1):
            continue # Skip schools that have no parseable roster site or have already been scraped recently

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
            school_last_roster_check = today_str

            # Get existing values
            players_df = google_sheets.df(players_worksheet)
            existing_school_canadians_df: pd.DataFrame = players_df[players_df['school_roster_url'] == school_series['roster_url']].copy()
            existing_school_canadians_df['row'] = existing_school_canadians_df.index.to_series() + 2
            existing_school_canadians_df['positions'] = existing_school_canadians_df['positions'].str.upper() # INF is converted to inf

            # Re-use existing_players_df to update new_players_df with manually updated info...
            # use last_name, first_name, school to get id, throws, city, province
            scraped_school_canadians_df = pd.DataFrame([canadian.to_dict() for canadian in canadians], columns = cols)
            scraped_school_canadians_df['school_roster_url'] = roster_url
            scraped_school_canadians_df['positions'] = scraped_school_canadians_df['positions'].apply(lambda x: '/'.join(x)) # Convert list to "/" delimited string
            school_canadians_df = scraped_school_canadians_df.merge(
                existing_school_canadians_df[['school_roster_url', 'last_name', 'first_name', 'positions', 'year', 'throws', 'city', 'province']],
                how = 'left',
                on = ['school_roster_url', 'last_name', 'first_name'],
                suffixes = ['_fetched', '']
            )
            school_canadians_df.fillna('', inplace = True)
            for attribute in ['positions', 'year', 'throws', 'city', 'province']:
                # Use saved attribute, if not blank (allows for manual fixes in Google Sheets)
                school_canadians_df[attribute] = school_canadians_df.apply(lambda row: row[attribute] if row[attribute] != '' else row[f'{attribute}_fetched'], axis = 1).astype(object)

            # Compare and add/delete rows as needed
            compare_df = existing_school_canadians_df.merge(school_canadians_df, how = 'outer', indicator = 'source')
            rows_to_add_df = compare_df[compare_df['source'] == 'right_only'][cols]
            rows_to_add_df['added'] = today_str
            rows_to_add_df['last_confirmed_on_roster'] = today_str
            if len(rows_to_add_df.index):
                cbn_utils.pause(players_worksheet.append_rows(rows_to_add_df.values.tolist()))
            confirmed_rows_indices = compare_df[compare_df['source'] == 'both']['row'].to_list()
            for confirmed_row_index in confirmed_rows_indices:
                cbn_utils.pause(players_worksheet.update(f'J{int(confirmed_row_index)}', today_str))

        # Update Schools sheet row
        cbn_utils.pause(schools_worksheet.update(f'I{i + 2}:L{i + 2}', [[school_last_roster_check, len(players), len(canadians), school.roster_page.result()]]))

    google_sheets.set_sheet_header(players_worksheet, sort_by = ['school_roster_url', 'last_name', 'first_name'])

def email_additions(to: str):
    # Email results to self
    schools_worksheet = google_sheets.hub_spreadsheet.worksheet('Schools')
    schools_df = google_sheets.df(schools_worksheet)
    schools_df.rename({'name': 'school'}, axis = 1, inplace = True)

    added_players_df = pd.DataFrame()
    for sheet_name in ['Players (Manual)', 'Players']:
        players_worksheet = google_sheets.hub_spreadsheet.worksheet(sheet_name)
        players_df = google_sheets.df(players_worksheet)
        players_df = players_df[players_df['added'].apply(lambda x: (datetime.today() - datetime.strptime(x, "%Y-%m-%d")).days) < 4] # Players added this week
        added_players_df = pd.concat([added_players_df, players_df], ignore_index = True)
    added_players_df = added_players_df.rename({'school_roster_url': 'roster_url'}, axis = 1).merge(schools_df, how = 'left', on = 'roster_url').sort_values(by = ['last_name', 'first_name', 'roster_url'])
    added_players_df.drop_duplicates(subset = ['roster_url', 'last_name', 'first_name'], inplace = True) # keep first (highest league for a school)
    email_html = cbn_utils.player_scrape_results_email_html(added_players_df)
    cbn_utils.send_email(to, f'New Players (Week of {datetime.now().strftime("%B %d, %Y")})', email_html, google_sheets.config)

def find_player_stat_ids():
    # Manual corrections
    corrections_df = google_sheets.df(google_sheets.hub_spreadsheet.worksheet('Corrections'))
    corrections = dict(zip(corrections_df['From'], corrections_df['To']))

    schools_worksheet = google_sheets.hub_spreadsheet.worksheet('Schools')
    schools_df = google_sheets.df(schools_worksheet)

    for sheet_name in ['Players (Manual)', 'Players']:
        players_worksheet = google_sheets.hub_spreadsheet.worksheet(sheet_name)
        players_df = google_sheets.df(players_worksheet)
        players_df = players_df[players_df['stats_url'] == '']
        players_df['row'] = players_df.index.to_series() + 2

        players_df = pd.merge(
            players_df,
            schools_df,
            how = 'inner',
            left_on = 'school_roster_url',
            right_on = 'roster_url',
            suffixes = ['', '_school']
        )

        for school_stats_url in players_df['stats_url_school'].unique():
            stats_page = StatsPage(school_stats_url, corrections = corrections)
            if len(stats_page.to_df().index) == 0:
                continue
            search_players_df = players_df[players_df['stats_url_school'] == school_stats_url].drop('stats_url', axis = 1)
            print('Looking for a stats url for the following player(s):')
            print(search_players_df[['last_name', 'first_name']].to_string())
            print('\nFound the following stats url(s):')
            print(stats_page.to_df().to_string())
            print()
            stats_urls_to_add = pd.merge(search_players_df, stats_page.to_df(), how = 'inner', on = ['last_name', 'first_name'])
            for _, player_row in stats_urls_to_add.iterrows():
                cbn_utils.pause(players_worksheet.update(f'L{int(player_row["row"])}', player_row['stats_url']))

        google_sheets.set_sheet_header(players_worksheet, sort_by = ['school_roster_url', 'last_name', 'first_name'])

def stats():
    for sheet_name in ['Players (Manual)', 'Players']:
        players_worksheet = google_sheets.hub_spreadsheet.worksheet(sheet_name)
        players_df = google_sheets.df(players_worksheet)

        for i, player_row in players_df.iterrows():
            player_last_stats_update = player_row['last_stats_update']
            days_since_last_check = (datetime.today() - datetime.strptime(player_last_stats_update, "%Y-%m-%d")).days if player_last_stats_update != '' else 99
            if (days_since_last_check <= 1) | (player_row['stats_url'] == ''):
                continue
            player = Player(
                last_name = player_row['last_name'],
                first_name = player_row['first_name'],
                stats_url = player_row['stats_url']
            )
            try:
                success = player.add_stats(google_sheets.config['ACADEMIC_YEAR'])
                if success == False:
                    continue
                stat_values = list(player.to_dict().values())[13:]
                cbn_utils.pause(players_worksheet.update(f'K{i + 2}:AJ{i + 2}', [[today_str, player_row['stats_url']] + stat_values]))
            except Exception as e:
                cbn_utils.log(f'ERROR: Player.add_stats - {player_row["stats_url"]} - {str(e)}')
    cbn_utils.driver.close()

def positions():
    # Manual corrections
    corrections_df = google_sheets.df(google_sheets.hub_spreadsheet.worksheet('Corrections'))
    corrections = dict(zip(corrections_df['From'], corrections_df['To']))

    positions_df = pd.DataFrame(columns = ['url', 'player', 'positions'])
    for sheet_name in ['Players (Manual)', 'Players']:
        players_worksheet = google_sheets.hub_spreadsheet.worksheet(sheet_name)
        players_df = google_sheets.df(players_worksheet)
        # Don't search for positions if not going to be on ballot anyway or if already fetched their positions count
        players_df = players_df[(players_df['G.C'] == '') & (players_df['AB'].replace('', 0).astype(int) > 0)]

        for stats_url in players_df['school'].unique():
            schedule_url = re.sub(
                r'^(.*)/team/(.*)/stats/(.*)$',
                r'\1/player/game_by_game?game_sport_year_ctl_id=\3&org_id=\2&stats_player_seq=-100',
                stats_url.replace('?view=lineup', '?view=gamelog')
            )
            schedule_page = SchedulePage(schedule_url)
            for box_score_url in schedule_page.box_score_links:
                if box_score_url not in positions_df['url']:
                    box_score_page = BoxScore(url = box_score_url, corrections = corrections)
                    box_score_page.positions_df['positions'].replace({'LF': 'OF', 'CF': 'OF', 'RF': 'OF'}, inplace = True)
                    positions_df = pd.concat([positions_df, box_score_page.positions_df]) \
                        .drop_duplicates(subset = ['player', 'url', 'positions'], ignore_index = True)
                    time.sleep(1)

            positions_df2 = positions_df[positions_df['url'].isin(schedule_page.box_score_links)].groupby(['player', 'positions']).count().reset_index()
            player_games_by_position_df = positions_df2.pivot(index = 'player', columns = 'positions', values = 'url').fillna(0).astype(int)
            for i, player_row in players_df[players_df['school'] == stats_url].iterrows():
                if f'{player_row["first_name"]} {player_row["last_name"]}' in player_games_by_position_df.index:
                    cbn_utils.pause(
                        players_worksheet.update(
                            f'AI{i + 2}:AO{i + 2}',
                            [player_games_by_position_df.loc[f'{player_row["first_name"]} {player_row["last_name"]}', ['C', '1B', '2B', '3B', 'SS', 'OF', 'DH']].values.tolist()]
                        )
                    )

def minors():
    players_worksheet = google_sheets.hub_spreadsheet.worksheet('Players (Minors)')
    players_df = google_sheets.df(players_worksheet)

    def province(abbreviation):
        return {
            'AB': 'Alberta',
            'BC': 'British Columbia',
            'MB': 'Manitoba',
            'NF': 'Newfoundland & Labrador',
            'NS': 'Nova Scotia',
            'ON': 'Ontario',
            'QC': 'Quebec',
            'SK': 'Saskatchewan'
        }[abbreviation]

    teams_req = cbn_utils.get('https://statsapi.mlb.com/api/v1/teams')
    teams_json = json.loads(teams_req.text)
    teams_df = pd.DataFrame(teams_json['teams'])[['id', 'name', 'parentOrgName']]
    teams_df['parentOrgName'].replace('Office of the Commissioner', pd.NA, inplace = True)
    teams_df['org'] = teams_df['parentOrgName'].combine_first(teams_df['name'])
    teams_dict = dict(zip(teams_df['id'], teams_df['org']))

    scraped_players_df = pd.DataFrame()
    levels_req = cbn_utils.get('https://statsapi.mlb.com/api/v1/sports')
    levels_json = json.loads(levels_req.text)
    for level in levels_json['sports']:
        if level['code'] in ['win', 'nlb', 'int', 'nae', 'nas', 'ame', 'bbc', 'hsb']:
            continue
        players_req = cbn_utils.get(f'https://statsapi.mlb.com/api/v1/sports/{level["id"]}/players')
        players_json = json.loads(players_req.text)
        for player in players_json['people']:
            if 'birthCountry' not in player.keys():
                continue
            if player['birthCountry'] != 'Canada':
                continue
            scraped_player = pd.DataFrame([
                {
                    'mlbam_id': player['id'],
                    'last_name': player['lastName'],
                    'first_name': player['useName'],
                    'position': player['primaryPosition']['abbreviation'],
                    'city': player['birthCity'],
                    'province': province(player['birthStateProvince']),
                    'level': level['abbreviation'],
                    'org': teams_dict[player['currentTeam']['id']],

                }
            ])
            scraped_players_df = pd.concat([scraped_players_df, scraped_player], ignore_index = True).drop_duplicates(subset = 'mlbam_id', ignore_index = True)
        time.sleep(1)

    updated_players_df = pd.concat([players_df, scraped_players_df], ignore_index = True)
    updated_players_df['mlbam_id'] = updated_players_df['mlbam_id'].astype('int')
    updated_players_df = updated_players_df.groupby('mlbam_id').agg({
        'last_name': 'last',
        'first_name': 'last',
        'position': 'last',
        'city': 'last',
        'province': 'last',
        'added': 'first',
        'last_confirmed': 'last',
        'last_stats_update': 'first',
        'bbref': 'first',
        'org': 'last'
    }).reset_index()
    updated_players_df['added'] = updated_players_df['added'].fillna(today_str)
    updated_players_df['last_confirmed'] = today_str
    updated_players_df.sort_values(['last_name', 'first_name'], ascending = [True, True], ignore_index = True, inplace = True)
    updated_players_df.fillna('', inplace = True)
    if len(players_df.index) > 0:
        cbn_utils.pause(players_worksheet.delete_rows(2, len(players_df.index) + 1))
    cbn_utils.pause(players_worksheet.append_rows(updated_players_df.values.tolist()))

    # Season Stats
    pages_to_look_up = len(updated_players_df[(updated_players_df['bbref'] == '') | (updated_players_df['bbref'] == None)].index)
    cbn_utils.log(f'Take {pages_to_look_up / 2} minutes to look up any missing baseball reference links')
    time.sleep(30 * pages_to_look_up)
    updated_players_df = google_sheets.df(players_worksheet).iloc[:, :11]
    stats_df = pd.DataFrame()
    for i, player_series in updated_players_df.iterrows():
        if (player_series['bbref'] == '') | (player_series['bbref'] == None): continue
        bbref_player_req = cbn_utils.get(player_series['bbref'])
        if bbref_player_req == None: continue
        if '<table' not in bbref_player_req.text: continue
        dfs = pd.read_html(bbref_player_req.text)
        for df in dfs:
            if 'Year' not in df.columns: continue
            year_df = df[(df['Year'].str.contains(str(google_sheets.config['YEAR'])) == True) & (df['Lev'].isin(['Maj']) == False) & (df['Tm'].str.contains('Teams') == False)]
            if len(year_df.index) == 0: continue
            year_batting_df = pd.DataFrame(columns = ['Tm', 'Lev', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG', 'OPS'])
            year_pitching_df = pd.DataFrame(columns = ['Tm', 'Lev', 'APP', 'GS', 'IP', 'W', 'L', 'ER', 'HA', 'BB', 'ERA', 'SV', 'K'])
            if 'OPS' in year_df.columns:
                year_batting_df = pd.concat([year_batting_df, year_df.rename({'BA': 'AVG'}, axis = 1)], ignore_index = True)[year_batting_df.columns]
            elif 'SV' in year_df.columns:
                year_pitching_df = pd.concat([year_pitching_df, year_df.rename({'G': 'APP', 'H': 'HA', 'SO': 'K'}, axis = 1)], ignore_index = True)[year_pitching_df.columns]
            year_combined_df = pd.merge(year_batting_df, year_pitching_df, 'outer', on = ['Tm', 'Lev'])
            year_combined_df = year_combined_df[year_batting_df.columns.tolist() + [col for col in year_pitching_df.columns if col not in ['Tm', 'Lev']]]
            year_combined_df.fillna(0, inplace = True)
            for col in ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'APP', 'GS', 'W', 'L', 'ER', 'HA', 'BB', 'SV', 'K']:
                year_combined_df[col] = year_combined_df[col].astype('int')
            for col in ['AVG', 'OBP', 'SLG', 'OPS']:
                year_combined_df[col] = year_combined_df[col].astype('float').round(3)
            year_combined_df['ERA'] = year_combined_df['ERA'].astype('float').round(2)
            year_combined_df['IP'] = year_combined_df['IP'].astype('float').round(1)
            year_combined_df['mlbam_id'] = player_series['mlbam_id']
            stats_df = pd.concat([stats_df, year_combined_df], ignore_index = True)
            updated_players_df.loc[i, 'last_stats_update'] = today_str
        time.sleep(4)

    updated_players_df = pd.merge(updated_players_df, stats_df, 'left', on = 'mlbam_id')
    updated_players_df.rename({'Tm': 'team', 'Lev': 'level'}, axis = 1, inplace = True)
    updated_players_df.sort_values(['last_name', 'first_name', 'level', 'G', 'APP'], ascending = [True, True, False, False, False], ignore_index = True, inplace = True)
    updated_players_df.fillna('', inplace = True)
    if len(players_df.index) > 0:
        cbn_utils.pause(players_worksheet.delete_rows(2, len(players_df.index) + 1))
    cbn_utils.pause(players_worksheet.append_rows(updated_players_df.values.tolist()))

    google_sheets.update_minors_sheet()

    # Last week stats
    end_date = datetime.now() - timedelta(days = 1)
    start_date = (end_date - timedelta(days = 5)).strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")
    week_hitting_df = pd.DataFrame()
    week_pitching_df = pd.DataFrame()
    players_df = google_sheets.df(players_worksheet).iloc[:, :11].drop_duplicates(ignore_index = True)
    for i, player_series in players_df.iterrows():
        if (player_series['bbref'] == '') | (player_series['bbref'] == None): continue
        for splits_page in ['bgl', 'pgl']:
            if (player_series['position'] == 'P') & (splits_page == 'bgl'): continue
            if (player_series['position'] != 'P') & (splits_page == 'pgl'): continue
            bbref_player_req = cbn_utils.get(f'{player_series["bbref"]}&type={splits_page}&year={google_sheets.config["YEAR"]}')
            time.sleep(4)
            if bbref_player_req == None: continue
            soup = BeautifulSoup(bbref_player_req.text, 'html.parser')
            if soup.find('table') == None: continue
            dfs = pd.read_html(bbref_player_req.text)
            for df in dfs:
                if 'Tm' not in df.columns: continue
                games_df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)].copy()
                if len(games_df.index) == 0: continue
                if splits_page == 'bgl':
                    week_df = pd.DataFrame([{
                        'Player': f'{player_series["first_name"]} {player_series["last_name"]}',
                        'Position': player_series['position'],
                        'Current Organization': player_series['org'],
                        'Team(s)': '\n'.join(set(games_df.apply(lambda row: f'{row["Tm"]} ({row["Lev"].split("-")[0]})', axis = 1).tolist())),
                        'PA': sum(games_df['PA'].astype('int')),
                        'R': sum(games_df['R'].astype('int')),
                        'H': sum(games_df['H'].astype('int')),
                        '2B': sum(games_df['2B'].astype('int')),
                        '3B': sum(games_df['3B'].astype('int')),
                        'HR': sum(games_df['HR'].astype('int')),
                        'RBI': sum(games_df['RBI'].astype('int')),
                        'SB': sum(games_df['SB'].astype('int')),
                        'AVG': (sum(games_df['H'].astype('int')) / sum(games_df['AB'].astype('int'))) if sum(games_df['AB'].astype('int')) > 0 else 0,
                        'OBP': ((sum(games_df['H'].astype('int')) + sum(games_df['BB'].astype('int'))) / sum(games_df['PA'].astype('int'))) if sum(games_df['PA'].astype('int')) > 0 else 0,
                        'SLG': (sum(games_df['H'].astype('int') + games_df['2B'].astype('int') + 2 * games_df['3B'].astype('int') + 3 * games_df['HR'].astype('int')) / sum(games_df['AB'].astype('int'))) if sum(games_df['AB'].astype('int')) > 0 else 0
                    }])
                    week_df['OPS'] = (week_df['OBP'] + week_df['SLG']).round(3)
                    week_df['OBP'] = week_df['OBP'].round(3)
                    week_df['SLG'] = week_df['SLG'].round(3)
                    week_hitting_df = pd.concat([week_hitting_df, week_df], ignore_index = True)
                else:
                    games_df['IP'] = games_df['IP'].astype('float').apply(lambda x: x if x == round(x) else round(x) + 1/3 if (x - 0.1) == round(x) else round(x) + 2/3)
                    week_df = pd.DataFrame([{
                        'Player': f'{player_series["first_name"]} {player_series["last_name"]}',
                        'Position': player_series['position'],
                        'Current Organization': player_series['org'],
                        'Team(s)': '\n'.join(set(games_df.apply(lambda row: f'{row["Tm"]} ({row["Lev"].split("-")[0]})', axis = 1).tolist())),
                        'APP': len(games_df.index),
                        'IP': sum(games_df['IP']),
                        'W': sum(games_df['Dec'].astype('str').str.contains('W')),
                        'L': sum(games_df['Dec'].astype('str').str.contains('L')),
                        'ER': sum(games_df['ER'].astype('int')),
                        'HA': sum(games_df['H'].astype('int')),
                        'BB': sum(games_df['BB'].astype('int')),
                        'ERA': (round(9 * sum(games_df['ER'].astype('int')) / sum(games_df['IP']), 2)) if sum(games_df['IP']) > 0 else 99,
                        'WHIP': (round((sum(games_df['H'].astype('int')) + sum(games_df['BB'].astype('int'))) / sum(games_df['IP']), 2)) if sum(games_df['IP']) > 0 else 99,
                        'SV': sum(games_df['Dec'].astype('str').str.contains('S')),
                        'K': sum(games_df['SO'].astype('int'))
                    }])
                    week_df['IP'] = week_df['IP'].round(1).apply(lambda x: int(x) if x == round(x) else round(x) + 0.1 if '.3' in str(x) else x - 0.5)
                    week_pitching_df = pd.concat([week_pitching_df, week_df], ignore_index = True)

    week_worksheet = google_sheets.hub_spreadsheet.worksheet('Minors Players of the Week')
    cbn_utils.pause(week_worksheet.delete_rows(2, len(google_sheets.df(week_worksheet).index) + 1))
    cbn_utils.pause(week_worksheet.append_rows(
        [['Hitting']] + [week_hitting_df.columns.tolist()] + week_hitting_df.values.tolist() + [['']] + \
        [['Pitching']] + [week_pitching_df.columns.tolist()] + week_pitching_df.values.tolist()
    ))


# if __name__ == '__main__':
#     schools()
#     players()
#     stats()
#     minors()
#     transition_ncaa_ids()
#     find_player_stat_ids()
