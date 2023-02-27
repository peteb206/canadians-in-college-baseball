import cbn_utils
from google_sheets import config
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3 = requests.packages.urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}
timeout = 20

class Page:
    '''
    # Test code:
    from model import Page
    page = Page(url = 'https://goairforcefalcons.com/sports/baseball/roster/2023')
    page.get_table()
    '''

    def __init__(self, url = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'url', value = url, value_type = str)

        # Check values
        cbn_utils.check_string_arg(name = 'url', value = url, disallowed_values = [''])

        self.url = url
        self.redirect = False
        self.status = u'\u2717'
        self.__html = ''
        self.dfs = list()
        self.df = pd.DataFrame()

    def __repr__(self):
        return self.url

    def __fetch_roster_page__(self):
        if self.url:
            try: # send verified request
                return session.get(self.url, headers = headers, timeout = timeout, verify = True)
            except requests.exceptions.SSLError: # send unverified request
                print(f'WARNING: sending unverified request to {self.url}')
                return session.get(self.url, headers = headers, timeout = timeout, verify = False)

    def html(self, new_request = False):
        if (self.url != '') & (new_request | (self.__html == '')):
            # Re-request if URL is not blank and either re-request manually ordered or html string is blank
            self.__html = ''
            response = self.__fetch_roster_page__()
            self.redirect = (len(response.history) > 0) & (response.url != self.url)
            self.status = f'--> {response.url} ' if self.redirect else ''
            self.status += u'\u2713' if response.status_code == 200 else u'\u2717'
            self.__html = response.text
        return self.__html

    def __parse_sidearm_cards__(self, soup):
        rows = list()
        for person_div in soup.find_all('div', {'class': 's-person-card'}):
            row = {
                'name': '',
                'position': '',
                'class': '',
                'height': '',
                'weight': '',
                'hometown': ''
            }
            # Name
            name_div = person_div.find('div', {'class': 's-person-details__personal'})
            if name_div:
                a = name_div.find('a')
                if a:
                    row['name'] = a.text
            details_div = person_div.find('div', {'class': 's-person-details__bio-stats'})
            if details_div:
                for i, span in enumerate(details_div.find_all('span', {'class': 's-person-details__bio-stats-item'})):
                    # Position
                    if i == 0:
                        row['position'] = span.text
                    # Class
                    elif i == 1:
                        row['class'] = span.text
                    # Height
                    elif i == 2:
                        row['height'] = span.text
                    # Weight
                    elif i == 3:
                        row['weight'] = span.text
            hometown_div = person_div.find('div', {'class': 's-person-card__content__location'})
            if hometown_div:
                for span in hometown_div.find_all('span', {'class': 's-person-card__content__person__location-item'}):
                    if span.find('svg', {'class': 's-icon-location'}):
                        row['hometown'] = span.text
                        break
            rows.append(row)
        return pd.DataFrame(rows)

    def get_table(self):
        self.html()
        soup = BeautifulSoup(self.__html, 'html.parser')
        if soup.find('table'):
            self.dfs = pd.read_html(self.__html)
            for df in self.dfs:
                if len(df.index) > max(len(self.df.index), 8): # Assuming a baseball roster should have 9+ players
                    self.df = df
        elif soup.find('div', {'class': 's-person-card'}):
            self.df = self.__parse_sidearm_cards__(soup)
        if len(self.df.columns) > 0:
            if [str(col) for col in self.df.columns] == [str(i) for i in range(len(self.df.columns))]:
                new_header = self.df.iloc[0] # grab the first row for the header
                self.df = self.df[1:] # take the data less the header row
                self.df.columns = new_header # set the header row as the df header
            # Standardize columns / properly align column names, if applicable
            cols = [str(col).lower() for col in self.df.columns]
            if cols[-1] == f'unnamed: {len(cols) - 1}':
                cols = ['ignore'] + cols[:-1]
            self.df.columns = cols
        return self.df.dropna(axis = 0, how = 'all') # remove rows with all NaN


class School:
    '''
    from model import School, Page
    school = School(name = 'U.S. Air Force Academy', league = 'NCAA', division = '1', state = 'CO', roster_page = Page(url = 'https://goairforcefalcons.com/sports/baseball/roster/2023'))
    school.players()
    '''
    def __init__(self, name = '', league = '', division = '', state = '', roster_page: Page = None):
        # Check types
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)
        cbn_utils.check_arg_type(name = 'league', value = league, value_type = str)
        cbn_utils.check_arg_type(name = 'division', value = division, value_type = str)
        cbn_utils.check_arg_type(name = 'state', value = state, value_type = str)
        cbn_utils.check_arg_type(name = 'roster_page', value = roster_page, value_type = Page)

        # Check values
        cbn_utils.check_string_arg(name = 'name', value = name, disallowed_values = [''])
        cbn_utils.check_string_arg(name = 'league', value = league, allowed_values = ['NCAA', 'NAIA', 'JUCO', 'CCCAA', 'NWAC', 'USCAA'])
        cbn_utils.check_string_arg(name = 'division', value = division, allowed_values = ['', '1', '2', '3'])
        cbn_utils.check_string_arg(name = 'state', value = state, allowed_values = ['AL', 'AK', 'AR', 'AZ', 'BC', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT', 'WA', 'WI', 'WV'])

        self.name = name
        self.league = league
        self.division = division
        self.state = state
        self.roster_page = roster_page
        self.__players = list()

    def __repr__(self):
        return str({
            'name': self.name,
            'league': self.league,
            'division': self.division,
            'state': self.state,
            'roster_page': self.roster_page,
            'players': [f'{player.first_name} {player.last_name}' for player in self.__players]
        })

    def __format_player_class__(self, string: str):
        # Output Freshman, Sophomore, Junior or Senior
        grad_year_map = {"'23": "Senior", "'24": "Junior", "'25": "Sophomore", "'26": "Freshman"}
        if string in grad_year_map.keys():
            return grad_year_map[string]

        if ('j' in string) | ('3' in string):
            return 'Junior'
        elif ('so' in string) | (string == 's') | ('2' in string):
            return 'Sophomore'
        elif ('sen' in string) | ('sr' in string) | ('gr' in string) | ('4' in string) | ('5' in string) | ('6' in string):
            return 'Senior'
        elif ('f' in string) | ('1' in string) | ('hs' in string) | (string == 'rs.') | (string == 'rs'):
            return 'Freshman'
        return ''

    def __format_player_name__(self, name_string: str):
        if name_string == name_string.upper(): # All caps... Set to proper case
            name_string = ' '.join([name_part[0].upper() + name_part[1:].lower() for name_part in name_string.split()])
        full_name_string =  ' '.join(name_string.split(',')[::-1]).strip() # Format as "First Last"
        full_name_string = re.sub(r'\s*\d+', '', full_name_string) # Remove digits, e.g. First Last 0
        full_name_string_split = full_name_string.split(None, 1)
        if len(full_name_string_split) == 2:
            first_name, last_name = full_name_string_split
        else:
            first_name, last_name = ' ', full_name_string
        return first_name, last_name

    def __format_player_position__(self, string: str):
        position_set = set()
        # Pitcher
        if ('P' in string) & ('STOP' not in string) & ('PLAY' not in string):
            position_set.add('P')
        # Catcher
        if ('C' in string) & ('CF' not in string) & ('CI' not in string) & ('PITCHER' not in string):
            position_set.add('C')
        # Infield
        if ('IN' in string) | ('IF' in string):
            position_set.add('INF')
        else: # 1B, 2B, 3B
            for base in range(1, 4):
                if str(base) in string:
                    position_set.add(f'{base}B')
            if 'FIRST' in string:
                position_set.add('1B')
            if 'SECOND' in string:
                position_set.add('2B')
            if 'THIRD' in string:
                position_set.add('3B')
            if ('SS' in string) | ('SHORT' in string):
                position_set.add('SS')
        # Outfield
        if ('OF' in string) | ('OUT' in string):
            position_set.add('OF')
        else:
            for outfield in ['LF', 'CF', 'RF']:
                if outfield in string:
                    position_set.add(outfield)
        # Designated Hitter & Utility
        if ('DH' in string) | ('DES' in string):
            position_set.add('DH')
        if ('UT' in string) & ('OUT' not in string):
            position_set.add('UTIL')
        return list(position_set)

    def __format_player_handedness__(self, character: str):
        out = ''
        if character.upper() == 'R':
            out = 'R'
        elif character.upper() == 'L':
            out = 'L'
        elif character.upper() in ['B', 'S']:
            out = 'B'
        return out

    def __format_player_hometown__(self, string: str, debug=False):
        city, province = '', ''
        string2 = re.sub(r'\s*\(*(?:Canada|CANADA|Can.|CN|CAN|CA)\)*\.*', '', string) # Remove references to Canada

        parentheses_search = re.search(r'\(([^)]+)', string2) # Search for text within parentheses
        if parentheses_search != None:
            if parentheses_search.group(1).count(',') == 1:
                string2 = parentheses_search.group(1) # Text within parentheses is city/province
            else:
                string2 = string2.split('(')[0].strip() # Text within parentheses is not helpful

        formatted = False
        for province_name, province_abbreviations in cbn_utils.province_strings.items():
            for province_abbreviation in [province_name] + province_abbreviations:
                if province_abbreviation.lower() in string2.lower(): # Ex. ', on' in burlington, on / nelson high school
                    city = re.split(province_abbreviation, string2, flags=re.IGNORECASE)[0]
                    province = province_name
                    formatted = True
        if not formatted: # Province likely not listed, just get city
            city = string2.split(',')[0]

        if debug:
            print(f'"{string}" converted to ---> City: "{city}" | Province: "{province}"')
        return re.sub(r'[^\w\-\s\.]', '', city).strip(), province # remove unwanted characters from city

    def players(self, debug=False):
        if len(self.__players) == 0:
            df = self.roster_page.get_table()
            cols = ['last_name', 'first_name', 'positions', 'bats', 'throws', 'year', 'city', 'province', 'canadian']
            for dictionary in df.to_dict(orient = 'records'):
                new_dict = {f'{col}': '' for col in cols if col not in ['positions', 'school', 'canadian']}
                new_dict['positions'] = list()
                for key, value in dictionary.items():
                    value_str = str(value).split(':')[-1].strip()
                    if value_str.lower() not in ['', 'nan']:
                        # Set year column
                        if (new_dict['year'] == '') & ((key.startswith('cl') | key.startswith('y') | key.startswith('e') | key.startswith('ci.') | 
                           ('year' in key) | (key in ['athletic', 'academic']))):
                            new_dict['year'] = self.__format_player_class__(value_str.lower())

                        # Set first_name and last_name columns
                        elif ('first' in key) & ('last' not in key):
                            new_dict['first_name'] = value_str
                        elif (key == 'last') | (('last' in key) & ('nam' in key) & ('first' not in key)):
                            new_dict['last_name'] = value_str
                        elif ('name' in key) | ('full' in key) | (key == 'player') | (key == 'student athlete'):
                            if ((key == 'name') & ('name.1' in dictionary.keys())) | ((key == 'name.1') & ('name' in dictionary.keys())):
                                new_dict['first_name'], new_dict['last_name'] = dictionary['name'], dictionary['name.1']
                            else:
                                new_dict['first_name'], new_dict['last_name'] = self.__format_player_name__(value_str)

                        # Set positions column
                        elif key.startswith('po'):
                            new_dict['positions'] = self.__format_player_position__(value_str.upper())

                        # Set bats and throws column
                        elif (key.startswith('b')) & (not key.startswith('bi')):
                            new_dict['bats'] = self.__format_player_handedness__(value_str[0])
                            if 't' in key:
                                new_dict['throws'] = self.__format_player_handedness__(value_str[-1])
                        elif (key == 't') | key.startswith('throw') | key.startswith('t/'):
                            new_dict['throws'] = self.__format_player_handedness__(value_str[0])
                            if 'b' in key:
                                new_dict['bats'] = self.__format_player_handedness__(value_str[-1])

                        # Set hometown column
                        else: # elif ('home' in key) | ('province' in key):
                            if (any(canada_string.lower() in value_str.lower() for canada_string in cbn_utils.canada_strings)) & (~any(ignore_string in value_str.lower() for ignore_string in cbn_utils.ignore_strings)):
                                new_dict['city'], new_dict['province'] = self.__format_player_hometown__(value_str, debug=debug)
                                new_dict['canadian'] = True
                new_dict['school'] = self
                player = Player(**new_dict)
                self.__players.append(player)
        return self.__players

class Player:
    def __init__(self, last_name = '', first_name = '', positions = [], bats = '', throws = '', year = '', school: School = None, city = '', province = '', canadian: bool = False, stats_id = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'last_name', value = last_name, value_type = str)
        cbn_utils.check_arg_type(name = 'first_name', value = first_name, value_type = str)
        cbn_utils.check_arg_type(name = 'positions', value = positions, value_type = list)
        cbn_utils.check_arg_type(name = 'bats', value = bats, value_type = str)
        cbn_utils.check_arg_type(name = 'throws', value = throws, value_type = str)
        cbn_utils.check_arg_type(name = 'year', value = year, value_type = str)
        cbn_utils.check_arg_type(name = 'school', value = school, value_type = School)
        cbn_utils.check_arg_type(name = 'city', value = city, value_type = str)
        cbn_utils.check_arg_type(name = 'province', value = province, value_type = str)
        cbn_utils.check_arg_type(name = 'canadian', value = canadian, value_type = bool)
        cbn_utils.check_arg_type(name = 'stats_id', value = stats_id, value_type = str)

        # Check values
        cbn_utils.check_string_arg(name = 'last_name', value = last_name, disallowed_values = [''])
        cbn_utils.check_string_arg(name = 'first_name', value = first_name, disallowed_values = [''])
        cbn_utils.check_list_arg(name = 'positions', values = positions, allowed_values = ['', 'P', 'C', '1B', '2B', '3B', 'SS', 'INF', 'LF', 'CF', 'RF', 'OF', 'DH', 'UTIL'])
        cbn_utils.check_string_arg(name = 'bats', value = bats, allowed_values = ['', 'R', 'L', 'B'])
        cbn_utils.check_string_arg(name = 'throws', value = throws, allowed_values = ['', 'R', 'L', 'B'])
        cbn_utils.check_string_arg(name = 'year', value = year, allowed_values = ['', 'Redshirt', 'Freshman', 'Sophomore', 'Junior', 'Senior'])
        # cbn_utils.check_string_arg(name = 'school', value = school, disallowed_values = [None])
        cbn_utils.check_string_arg(name = 'province', value = province, allowed_values = ['', 'Alberta', 'British Columbia', 'Manitoba', 'New Brunswick', 'Newfoundland & Labrador', 'Nova Scotia', 'Ontario', 'Prince Edward Island', 'Quebec', 'Saskatchewan'])

        self.last_name = last_name
        self.first_name = first_name
        self.positions = positions
        self.bats = bats
        self.throws = throws
        self.year = year
        self.school = school
        self.city = city
        self.province = province
        self.canadian = canadian
        self.stats_id = stats_id
        self.__stats_url = ''
        self.__batting_stats = list(cbn_utils.stats_labels['batting'].keys())
        self.__pitching_stats = list(cbn_utils.stats_labels['pitching'].keys())
        self.__stats = {stat: 0 for stat in self.__batting_stats + self.__pitching_stats}

    def __repr__(self):
        return str(self.to_dict())

    def to_dict(self):
        return {
            'last_name': self.last_name,
            'first_name': self.first_name,
            'positions': self.positions,
            'bats': self.bats,
            'throws': self.throws,
            'year': self.year,
            'city': self.city,
            'province': self.province,
            'school': self.school.name if self.school != None else '',
            'league': self.school.league if self.school != None else '',
            'division': self.school.division if self.school != None else '',
            'state': self.school.state if self.school != None else '',
            'canadian': self.canadian,
            'stats_id': self.stats_id
        }

    def stats(self):
        if self.stats_id != '':
            stat_dict = self.__stats
            if self.school.league == 'NCAA':
                ncaa_base_url = f'https://stats.ncaa.org/player/index?id={config["NCAA_STAT_YEAR"]}&stats_player_seq='
                for i, stat_category_id in enumerate([config['NCAA_BATTING_STAT_ID'], config['NCAA_PITCHING_STAT_ID']]):
                    self.__stats_url = f'{ncaa_base_url}{self.stats_id}&year_stat_category_id={stat_category_id}'
                    html = session.get(self.__stats_url, headers = headers, timeout = timeout).text
                    df = pd.read_html(html)[2]
                    new_header = df.iloc[1] # grab the first row for the header
                    df = df[2:] # take the data less the header row
                    df.columns = new_header # set the header row as the df header
                    df = df[df['Year'] == config['ACADEMIC_YEAR']]
                    if len(df.index) == 1:
                        if i == 0:
                            df.rename({'BA': 'AVG', 'OBPct': 'OBP', 'SlgPct': 'SLG'}, axis = 1, inplace = True)
                            df['OPS'] = 0.0
                            df = df[self.__batting_stats]
                        else:
                            df.rename({'App': 'APP', 'H': 'HA', 'SO': 'K'}, axis = 1, inplace = True)
                            df = df[self.__pitching_stats]
                        stat_dict = stat_dict | df.fillna(0).to_dict(orient = 'records')[0]
            else:
                if self.school.league == 'NAIA':
                    self.__stats_url = f'https://naiastats.prestosports.com/sports/bsb/{config["ACADEMIC_YEAR"]}/players/{self.stats_id}?view=profile'
                elif self.school.league == 'JUCO':
                    self.__stats_url = f'https://www.njcaa.org/sports/bsb/{config["ACADEMIC_YEAR"]}/div{self.school.division}/players/{self.stats_id}?view=profile'
                elif self.school.league == 'CCCAA':
                    self.__stats_url = f'https://www.cccaasports.org/sports/bsb/{config["ACADEMIC_YEAR"]}/players/{self.stats_id}?view=profile'
                elif self.school.league == 'NWAC':
                    self.__stats_url = f'https://nwacsports.com/sports/bsb/{config["ACADEMIC_YEAR"]}/players/{self.stats_id}?view=profile'
                elif self.school.league == 'USCAA':
                    self.__stats_url = f'https://uscaa.prestosports.com/sports/bsb/{config["ACADEMIC_YEAR"]}/players/{self.stats_id}?view=profile'
                req = session.get(self.__stats_url, headers = headers, timeout = timeout)
                for df in pd.read_html(req.text):
                    if 'Statistics category' in df.columns:
                        pitching_stat_index = df[df['Statistics category'] == 'Appearances'].index.to_list()[0]
                        batting_df = df.head(pitching_stat_index).set_index('Statistics category')
                        batting_df.rename({'Games': 'G', 'At Bats': 'AB', 'Runs': 'R', 'Hits': 'H', 'Doubles': '2B', 'Triples': '3B', 'Home Runs': 'HR', 'Runs Batted In': 'RBI', 'Stolen Bases': 'SB', 'Batting Average': 'AVG', 'On Base Percentage': 'OBP', 'Slugging Percentage': 'SLG'}, inplace = True)
                        batting_stat_dict = batting_df.filter(items = self.__batting_stats, axis = 0)['Overall'].replace('-', '0').to_dict()

                        pitching_df = df.tail(len(df.index) - pitching_stat_index).set_index('Statistics category')
                        pitching_df.rename({'Appearances': 'APP', 'Games Started': 'GS', 'Innings Pitched': 'IP', 'Wins': 'W', 'Losses': 'L', 'Earned Runs': 'ER', 'Hits': 'HA', 'Walks': 'BB', 'Earned Run Average': 'ERA', 'Saves': 'SV', 'Strikeouts': 'K'}, inplace = True)
                        pitching_stat_dict = pitching_df.filter(items = self.__pitching_stats, axis = 0)['Overall'].replace('-', '0').to_dict()

                        stat_dict = stat_dict | batting_stat_dict | pitching_stat_dict
                        break
            # Format to integers and rounded decimals
            for key, value in stat_dict.items():
                if key in ['AVG', 'OBP', 'SLG', 'IP', 'ERA']:
                    stat_dict[key] = float(value)
                else:
                    stat_dict[key] = int(value)
            stat_dict['OPS'] = stat_dict['OBP'] + stat_dict['SLG']
            self.__stats = stat_dict
        return self.__stats

    def stats_url(self):
        return self.__stats_url