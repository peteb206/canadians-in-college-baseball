import cbn_utils
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3 = requests.packages.urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        self.status = u'\u274C'
        self.__html = ''
        self.dfs = list()
        self.df = pd.DataFrame()

    def __repr__(self):
        return self.url

    def __fetch_page__(self):
        if self.url:
            try: # send verified request
                return cbn_utils.get(self.url)
            except requests.exceptions.SSLError: # send unverified request
                cbn_utils.log(f'WARNING: sending unverified request to {self.url}')
                return cbn_utils.get(self.url, verify = False)

    def html(self, new_request = False) -> str:
        if (self.url != '') & (new_request | (self.__html == '')):
            # Re-request if URL is not blank and either re-request manually ordered or html string is blank
            self.__html = ''
            response = self.__fetch_page__()
            self.redirect = (len(response.history) > 0) & (response.url != self.url)
            self.status = '{} {} '.format(u'\u27A1', response.url) if self.redirect else ''
            self.status += u'\u2705' if response.status_code == 200 else u'\u274C'
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
    def __init__(self, id = '', name = '', league = '', division = '', state = '', roster_page: Page = None, stats_page: Page = None):
        # Check types
        cbn_utils.check_arg_type(name = 'id', value = id, value_type = str)
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)
        cbn_utils.check_arg_type(name = 'league', value = league, value_type = str)
        cbn_utils.check_arg_type(name = 'division', value = division, value_type = str)
        cbn_utils.check_arg_type(name = 'state', value = state, value_type = str)
        cbn_utils.check_arg_type(name = 'roster_page', value = roster_page, value_type = Page)
        cbn_utils.check_arg_type(name = 'stats_page', value = stats_page, value_type = Page)

        # Check values
        cbn_utils.check_string_arg(name = 'id', value = id, disallowed_values = [''])
        cbn_utils.check_string_arg(name = 'name', value = name, disallowed_values = [''])
        cbn_utils.check_string_arg(name = 'league', value = league, allowed_values = ['NCAA', 'NAIA', 'JUCO', 'CCCAA', 'NWAC', 'USCAA'])
        cbn_utils.check_string_arg(name = 'state', value = state, allowed_values = ['AL', 'AK', 'AR', 'AZ', 'BC', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT', 'WA', 'WI', 'WV'])

        self.id = id
        self.name = name
        self.league = league
        self.division = division
        self.state = state
        self.roster_page = roster_page
        self.stats_page = stats_page
        self.__players = list()
        self.stats_df = None

    def __repr__(self):
        return str({
            'name': self.name,
            'league': self.league,
            'division': self.division,
            'state': self.state
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

    def __format_player_hometown__(self, string: str, debug = False):
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

    def players(self, debug = False):
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
                player = Player(**new_dict)
                self.__players.append(player)
        return self.__players

    def get_stats_df(self) -> pd.DataFrame:
        if self.stats_df != None:
            return self.stats_df
        html = self.stats_page.html()
        soup = BeautifulSoup(html, 'html.parser')
        if self.league == 'NCAA':
            hitting_table = soup.find('table', {'id': 'stat_grid'})
            hitting_df = pd.read_html(str(hitting_table))[0]
            hitting_df = hitting_df[hitting_df['GP'] != '-']
            hitting_df['id'] = hitting_df['Player'].apply(lambda x: hitting_table.find('a', text = x)['href'].split('stats_player_seq=')[-1])
            url_parts = urllib3.util.parse_url(self.stats_page.url)
            self.stats_page = Page(url = f'{url_parts.scheme}://{url_parts.netloc}{soup.find("a", text = "Pitching")["href"]}')
            html = self.stats_page.html()
            soup = BeautifulSoup(html, 'html.parser')
            pitching_table = soup.find('table', {'id': 'stat_grid'})
            pitching_df = pd.read_html(str(pitching_table))[0]
            pitching_df = pitching_df[pitching_df['GP'] != '-']
            pitching_df['id'] = pitching_df['Player'].apply(lambda x: pitching_table.find('a', text = x)['href'].split('stats_player_seq=')[-1])
            df = pd.merge(
                hitting_df[['id', 'Player', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'BA', 'OBPct', 'SlgPct']],
                pitching_df[['id', 'App', 'GS.1', 'IP', 'W', 'L', 'ER', 'H', 'BB', 'ERA', 'SV', 'SO']],
                how = 'outer',
                on = 'id',
                suffixes = ['', 'A']
            )
            df['last_name'] = df['Player'].apply(lambda x: x.split(', ')[0])
            df['first_name'] = df['Player'].apply(lambda x: x.split(', ')[1])
            self.stats_df = df.drop('Player', axis = 1).rename({'BA': 'AVG', 'OBPct': 'OBP', 'SlgPct': 'SLG', 'App': 'APP', 'GS.1': 'GS', 'SO': 'K'}, axis = 1)
        else:
            hitting_df, pitching_df = None, None
            for table in soup.find_all('table'):
                df = pd.read_html(str(table))[0]
                if 'ab' in df.columns:
                    # Hitting
                    ids_dict = {a.text.replace('  ', ' ').strip(): a['href'].split('/')[-1] for a in table.find_all('a') if '/players/' in a['href']}
                    ids_dict_keys = list(ids_dict.keys())
                    hitting_df = df.rename({col: col.upper() for col in df.columns}, axis = 1)
                    hitting_df = hitting_df[~hitting_df['NAME'].isin(['Totals', 'Opponent'])]
                    hitting_df['id'] = hitting_df['NAME'].apply(lambda x: ids_dict[x] if x in ids_dict_keys else '')
                elif 'ip' in df.columns:
                    # Pitching
                    ids_dict = {a.text.replace('  ', ' ').strip(): a['href'].split('/')[-1] for a in table.find_all('a') if '/players/' in a['href']}
                    ids_dict_keys = list(ids_dict.keys())
                    pitching_df = df.rename({col: col.upper() for col in df.columns}, axis = 1)
                    pitching_df = pitching_df[~pitching_df['NAME'].isin(['Totals', 'Opponent'])]
                    pitching_df['id'] = pitching_df['NAME'].apply(lambda x: ids_dict[x] if x in ids_dict_keys else '')
                    break
            df = pd.merge(
                hitting_df[['id', 'NAME', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG']],
                pitching_df[['id', 'NAME', 'APP', 'GS', 'IP', 'W', 'L', 'ER', 'H', 'BB', 'ERA', 'SV', 'K']],
                how = 'outer',
                on = ['id', 'NAME'],
                suffixes = ['', 'A']
            )
            df['last_name'] = df['NAME'].apply(lambda x: ' '.join(x.split(' ')[-1:]))
            df['first_name'] = df['NAME'].apply(lambda x: ' '.join(x.split(' ')[:-1]))
            self.stats_df = df.drop('NAME', axis = 1)
        self.stats_df['OPS'] = self.stats_df.apply(lambda row: row['OBP'] + row['SLG'], axis = 1)
        return self.stats_df

class Player:
    def __init__(self, id = '', last_name = '', first_name = '', positions = [], bats = '', throws = '', year = '', city = '', province = '', canadian: bool = False):
        # Check types
        cbn_utils.check_arg_type(name = 'id', value = id, value_type = str)
        cbn_utils.check_arg_type(name = 'last_name', value = last_name, value_type = str)
        cbn_utils.check_arg_type(name = 'first_name', value = first_name, value_type = str)
        cbn_utils.check_arg_type(name = 'positions', value = positions, value_type = list)
        cbn_utils.check_arg_type(name = 'bats', value = bats, value_type = str)
        cbn_utils.check_arg_type(name = 'throws', value = throws, value_type = str)
        cbn_utils.check_arg_type(name = 'year', value = year, value_type = str)
        cbn_utils.check_arg_type(name = 'city', value = city, value_type = str)
        cbn_utils.check_arg_type(name = 'province', value = province, value_type = str)
        cbn_utils.check_arg_type(name = 'canadian', value = canadian, value_type = bool)

        # Check values
        cbn_utils.check_string_arg(name = 'last_name', value = last_name, disallowed_values = [''])
        cbn_utils.check_string_arg(name = 'first_name', value = first_name, disallowed_values = [''])
        cbn_utils.check_list_arg(name = 'positions', values = positions, allowed_values = ['', 'P', 'C', '1B', '2B', '3B', 'SS', 'INF', 'LF', 'CF', 'RF', 'OF', 'DH', 'UTIL'])
        cbn_utils.check_string_arg(name = 'bats', value = bats, allowed_values = ['', 'R', 'L', 'B'])
        cbn_utils.check_string_arg(name = 'throws', value = throws, allowed_values = ['', 'R', 'L', 'B'])
        cbn_utils.check_string_arg(name = 'year', value = year, allowed_values = ['', 'Redshirt', 'Freshman', 'Sophomore', 'Junior', 'Senior'])
        cbn_utils.check_string_arg(name = 'province', value = province, allowed_values = ['', 'Alberta', 'British Columbia', 'Manitoba', 'New Brunswick', 'Newfoundland & Labrador', 'Nova Scotia', 'Ontario', 'Prince Edward Island', 'Quebec', 'Saskatchewan'])

        self.id = id
        self.last_name = last_name
        self.first_name = first_name
        self.positions = positions
        self.bats = bats
        self.throws = throws
        self.year = year
        self.school: School = None
        self.city = city
        self.province = province
        self.canadian = canadian
        self.G = 0
        self.AB = 0
        self.R = 0
        self.H = 0
        self._2B = 0
        self._3B = 0
        self.HR = 0
        self.RBI = 0
        self.SB = 0
        self.AVG = '.000'
        self.OBP = '.000'
        self.SLG = '.000'
        self.OPS = '.000'
        self.APP = 0
        self.GS = 0
        self.IP = '0.0'
        self.W = 0
        self.L = 0
        self.ER = 0
        self.HA = 0
        self.BB = 0
        self.ERA = '0.00'
        self.SV = 0
        self.K = 0

    def __repr__(self):
        return f'{self.first_name} {self.last_name}'

    def to_dict(self):
        return {
            'id': self.id,
            'last_name': self.last_name,
            'first_name': self.first_name,
            'positions': self.positions,
            'bats': self.bats,
            'throws': self.throws,
            'year': self.year,
            'city': self.city,
            'province': self.province,
            'school': self.school.stats_page.url if self.school != None else '',
            'league': self.school.league if self.school != None else '',
            'division': self.school.division if self.school != None else '',
            'state': self.school.state if self.school != None else '',
            'canadian': self.canadian,
            'G': self.G,
            'AB': self.AB,
            'R': self.R,
            'H': self.H,
            '2B': self._2B,
            '3B': self._3B,
            'HR': self.HR,
            'RBI': self.RBI,
            'SB': self.SB,
            'AVG': self.AVG,
            'OBP': self.OBP,
            'SLG': self.SLG,
            'OPS': self.OPS,
            'APP': self.APP,
            'GS': self.GS,
            'IP': self.IP,
            'W': self.W,
            'L': self.L,
            'ER': self.ER,
            'HA': self.HA,
            'BB': self.BB,
            'ERA': self.ERA,
            'SV': self.SV,
            'K': self.K
        }

    def get_stats(self) -> dict:
        if (self.id == '') & (self.school != None):
            if not isinstance(self.school.stats_df, pd.DataFrame):
                self.school.get_stats_df()
            stat_df_row = self.school.stats_df[
                (self.school.stats_df['last_name'] == self.last_name) & (self.school.stats_df['first_name'] == self.first_name)
            ]
            if len(stat_df_row.index) > 0:
                stat_dict = stat_df_row.fillna(0.0).to_dict(orient = 'records')[0]
                self.id = str(stat_dict['id'])
                self.G = int(stat_dict['G'])
                self.AB = int(stat_dict['AB'])
                self.R = int(stat_dict['R'])
                self.H = int(stat_dict['H'])
                self._2B = int(stat_dict['2B'])
                self._3B = int(stat_dict['3B'])
                self.HR = int(stat_dict['HR'])
                self.RBI = int(stat_dict['RBI'])
                self.SB = int(stat_dict['SB'])
                self.AVG = '{0:.3f}'.format(stat_dict['AVG'])
                self.AVG = self.AVG[1:] if self.AVG.startswith('0') else self.AVG
                self.OBP = '{0:.3f}'.format(stat_dict['OBP'])
                self.OBP = self.OBP[1:] if self.OBP.startswith('0') else self.OBP
                self.SLG = '{0:.3f}'.format(stat_dict['SLG'])
                self.SLG = self.SLG[1:] if self.SLG.startswith('0') else self.SLG
                self.OPS = '{0:.3f}'.format(stat_dict['OPS'])
                self.OPS = self.OPS[1:] if self.OPS.startswith('0') else self.OPS
                self.APP = int(stat_dict['APP'])
                self.GS = int(stat_dict['GS'])
                self.IP = '{0:.1f}'.format(stat_dict['IP'])
                self.W = int(stat_dict['W'])
                self.L = int(stat_dict['L'])
                self.ER = int(stat_dict['ER'])
                self.HA = int(stat_dict['HA'])
                self.BB = int(stat_dict['BB'])
                self.ERA = '{0:.2f}'.format(stat_dict['ERA'], 2)
                self.SV = int(stat_dict['SV'])
                self.K = int(stat_dict['K'])
        return {
            'G': self.G,
            'AB': self.AB,
            'R': self.R,
            'H': self.H,
            '2B': self._2B,
            '3B': self._3B,
            'HR': self.HR,
            'RBI': self.RBI,
            'SB': self.SB,
            'AVG': self.AVG,
            'OBP': self.OBP,
            'SLG': self.SLG,
            'OPS': self.OPS,
            'APP': self.APP,
            'GS': self.GS,
            'IP': self.IP,
            'W': self.W,
            'L': self.L,
            'ER': self.ER,
            'HA': self.HA,
            'BB': self.BB,
            'ERA': self.ERA,
            'SV': self.SV,
            'K': self.K
        }