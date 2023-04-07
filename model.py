import cbn_utils
import requests
from bs4 import BeautifulSoup, element
import pandas as pd
import json
import re
urllib3 = requests.packages.urllib3

class WebPage:
    # Class variables
    __SUCCESS_ICON__ = u'\u2705'
    __ERROR_ICON__ = u'\u274C'
    __REDIRECT_ICON__ = u'\u27A1'

    def __init__(self, url = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'url', value = url, value_type = str)

        # Check values
        cbn_utils.check_string_arg(name = 'url', value = url, disallowed_values = [''])

        # Instance variables
        self.__url__ = url
        self.__redirect__ = False
        self.__response__: requests.Response = None
        self.__html__ = ''

    def __repr__(self):
        return self.__url__ + self.status()

    def status(self):
        status = ''
        if self.redirected() == True:
            # Redirected
            status += f' {self.__REDIRECT_ICON__} {self.__response__.url}'
        if self.__response__ == None:
            status += f' {self.__ERROR_ICON__} - not fetched yet'
        elif self.success():
            status += f' {self.__SUCCESS_ICON__}'
        else:
            status += f' {self.__ERROR_ICON__}'
        return status

    def url(self) -> str:
        return self.__url__

    def success(self) -> bool:
        if self.__response__ != None:
            return self.__response__.status_code == 200

    def redirected(self) -> bool:
        if self.__response__ != None:
            return (len(self.__response__.history) > 0) & (self.__response__.url != self.__url__)

    def html(self) -> str:
        if self.__html__ != '':
            # page has already been fetched
            return self.__html__
        url_split = self.__url__.split('#')
        self.__response__ = cbn_utils.get(url_split[0])
        if self.__response__ != None:
            # if 'content-type' in self.__response__.headers.keys():
            #     if 'application/json' in self.__response__.headers['content-type']:
            #         json_to_dict: dict = json.loads(self.__response__.text)
            #         if 'players' in json_to_dict.keys():
            #             self.__html__ = pd.DataFrame(json_to_dict['players']).to_html()
            #             return self.__html__
            self.__html__ = self.__response__.text
        return self.__html__

class RosterPage(WebPage):
    def __init__(self, url = ''):
        WebPage.__init__(self, url)
        self.__result__ = ''
        self.__players__: list[Player] = None
        if url != '':
            self.__fetch_players__()

    def __repr__(self):
        self.str()

    def str(self):
        return super().str() + self.__result__

    def result(self):
        return super().status() + self.__result__

    def to_df(self):
        players = self.players()
        if players == None:
            return pd.DataFrame()
        return pd.DataFrame([player.to_dict() for player in players])

    def players(self):
        return self.__players__

    def __fetch_players__(self):
        if self.__players__ != None:
            # roster has already been fetched
            return self.__players__
        html = super().html()
        roster_json_match = re.search('roster: (\{.*\}),.*\n', html)
        if roster_json_match != None:
            # Parse roster JSON
            self.__parse_sidearm_json__(roster_json_match[1])
        else:
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.find_all('div', {'class': 's-person-card'})
            if len(cards) > 0:
                # Parse sidearm cards
                self.__parse_s_person_cards__(cards)
            else:
                cards = soup.find_all('div', {'class': 'sidearm-roster-player-container'})
                if len(cards) > 0:
                    self.__parse_sidearm_cards__(cards)
                elif soup.find('table'):
                    # Parse HTML table
                    self.__parse_table__(html)

    def __parse_sidearm_json__(self, json_string: str):
        self.__result__ += ' Parsed sidearm (roster JSON)'
        roster_json = json.loads(json_string)
        players_list = roster_json['players']
        self.__players__ = []
        for player_dict in players_list:
            is_canadian = cbn_utils.is_canadian(player_dict['hometown'])
            city, province = '', ''
            if is_canadian:
                city, province = self.format_player_hometown(player_dict['hometown'])
            player = Player(
                last_name = player_dict['last_name'],
                first_name = player_dict['first_name'],
                positions = self.format_player_position(player_dict['position_short']),
                year = self.format_player_class(player_dict['academic_year_short'].lower()),
                city = city,
                province = province,
                canadian = is_canadian
            )
            self.__players__.append(player)

    def __parse_s_person_cards__(self, cards: element.ResultSet):
        self.__result__ += ' Parsed sidearm (s-person-card)'
        self.__players__ = []
        for person_div in cards:
            last_name = ''
            first_name = ''
            positions = set()
            year = ''
            city = ''
            province = ''
            is_canadian = False
            # Name
            name_div = person_div.find('div', {'class': 's-person-details__personal'})
            if name_div:
                a = name_div.find('a')
                if a:
                    first_name, last_name = self.format_player_name(a.text)
            details_div = person_div.find('div', {'class': 's-person-details__bio-stats'})
            if details_div:
                for i, span in enumerate(details_div.find_all('span', {'class': 's-person-details__bio-stats-item'})):
                    # Position
                    if i == 0:
                        positions = self.format_player_position(span.text)
                    # Class
                    elif i == 1:
                        year = self.format_player_class(span.text.lower())
            hometown_div = person_div.find('div', {'class': 's-person-card__content__location'})
            if hometown_div:
                for span in hometown_div.find_all('span', {'class': 's-person-card__content__person__location-item'}):
                    if span.find('svg', {'class': 's-icon-location'}):
                        is_canadian = cbn_utils.is_canadian(span.text)
                        if is_canadian:
                            city, province = self.format_player_hometown(span.text)
                        break
            player = Player(
                last_name = last_name,
                first_name = first_name,
                positions = positions,
                year = year,
                city = city,
                province = province,
                canadian = is_canadian
            )
            self.__players__.append(player)

    def __parse_sidearm_cards__(self, cards: element.ResultSet):
        self.__result__ += ' Parsed sidearm (sidearm-roster-player-container)'
        self.__players__ = []
        for person_div in cards:
            last_name = ''
            first_name = ''
            positions = set()
            year = ''
            city = ''
            province = ''
            is_canadian = False
            # Name
            name_h3 = person_div.find('h3')
            if name_h3:
                a = name_h3.find('a')
                if a:
                    first_name, last_name = self.format_player_name(a.text)
                else:
                    span = name_h3.find('span')
                    if span:
                        first_name, last_name = self.format_player_name(span.text)
            # Position
            position_div = person_div.find('div', {'class': 'sidearm-roster-player-position'})
            if position_div:
                position_span = position_div.find('span')
                if position_span:
                    positions = self.format_player_position(position_span.text)
            # Year
            year_span = person_div.find('span', {'class': 'sidearm-roster-player-academic-year'})
            if year_span:
                year = self.format_player_class(year_span.text.lower())
            # Hometown
            hometown_span = person_div.find('span', {'class': 'sidearm-roster-player-hometown'})
            if hometown_span:
                is_canadian = cbn_utils.is_canadian(hometown_span.text)
                if is_canadian:
                    city, province = self.format_player_hometown(hometown_span.text)
            player = Player(
                last_name = last_name,
                first_name = first_name,
                positions = positions,
                year = year,
                city = city,
                province = province,
                canadian = is_canadian
            )
            self.__players__.append(player)

    def __parse_table__(self, html: str):
        self.__players__ = []
        dfs = None
        try:
            dfs = pd.read_html(html)
        except:
            return
        df = pd.DataFrame()
        url_split = super().url().split('#')
        if len(url_split) > 1:
            index_str = url_split[-1]
            if index_str.isdigit():
                df = dfs[int(index_str)]
            else:
                return # page doesn't have a parseable roster
        else:
            for df_ in dfs:
                if len(df_.index) > max(len(df.index), 8): # Assuming a baseball roster should have 9+ players
                    df = df_
        if len(df.columns) == 0:
            return
        # Format columns
        if [str(col) for col in df.columns] == [str(i) for i in range(len(df.columns))]:
            new_header = df.iloc[0] # grab the first row for the header
            df = df[1:].copy() # take the data less the header row
            df.columns = new_header # set the header row as the df header
        # Standardize columns / properly align column names, if applicable
        cols = [str(col).lower() for col in df.columns]
        if cols[-1] == f'unnamed: {len(cols) - 1}':
            cols = ['ignore'] + cols[:-1]
        df.columns = cols
        while df.columns.count('nan') > 1:
            new_header = [str(col).lower() for col in df.iloc[0]] # grab the first row for the header
            df = df[1:].copy() # take the data less the header row
            df.columns = new_header # set the header row as the df header
        self.__result__ += f' Parsed table: | {" | ".join(df.columns)} |'
        df.dropna(axis = 0, how = 'all', inplace = True) # remove rows with all NaN
        cols = ['last_name', 'first_name', 'positions', 'bats', 'throws', 'year', 'city', 'province', 'canadian']
        for dictionary in df.to_dict(orient = 'records'):
            last_name = ''
            first_name = ''
            positions = set()
            year = ''
            throws = ''
            city = ''
            province = ''
            is_canadian = False
            for key, value in dictionary.items():
                value_str = str(value).split(':')[-1].strip()
                if value_str.lower() not in ['', 'nan']:
                    # Set year column
                    if (year == '') & ((key.startswith('cl') | key.startswith('y') | key.startswith('e') | key.startswith('ci.') | 
                        ('year' in key) | (key in ['athletic', 'academic']))):
                        year = self.format_player_class(value_str.lower())

                    # Set first_name and last_name columns
                    elif ('first' in key) & ('last' not in key):
                        first_name = value_str
                    elif (key == 'last') | (('last' in key) & ('nam' in key) & ('first' not in key)):
                        last_name = value_str
                    elif ('name' in key) | ('full' in key) | (key == 'player') | (key == 'student athlete'):
                        if ((key == 'name') & ('name.1' in dictionary.keys())) | ((key == 'name.1') & ('name' in dictionary.keys())):
                            first_name, last_name = dictionary['name'], dictionary['name.1']
                        else:
                            first_name, last_name = self.format_player_name(value_str)

                    # Set positions column
                    elif key.startswith('po'):
                        positions = self.format_player_position(value_str.upper())

                    # Set bats and throws column
                    elif (key.startswith('b')) & (not key.startswith('bi')) & ('t' in key):
                        throws = self.format_player_handedness(value_str[-1])
                    elif (key == 't') | key.startswith('throw') | key.startswith('t/'):
                        throws = self.format_player_handedness(value_str[0])

                    # Set hometown column
                    elif (key == 'province') & ('hometown/high school' in dictionary.keys()):
                        value_str = dictionary['hometown/high school'].replace(' /', f', {value_str}').split(':')[-1]
                        is_canadian = cbn_utils.is_canadian(value_str)
                        if is_canadian:
                            city, province = self.format_player_hometown(value_str)
                    elif not is_canadian: # elif ('home' in key) | ('province' in key):
                        is_canadian = cbn_utils.is_canadian(value_str)
                        if is_canadian:
                            city, province = self.format_player_hometown(value_str)
            player = Player(
                last_name = last_name,
                first_name = first_name,
                positions = positions,
                year = year,
                throws = throws,
                city = city,
                province = province,
                canadian = is_canadian
            )
            self.__players__.append(player)

    @staticmethod
    def format_player_class(string: str):
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

    @staticmethod
    def format_player_name(name_string: str):
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

    @staticmethod
    def format_player_position(string: str):
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
        return position_set

    @staticmethod
    def format_player_handedness(character: str):
        out = ''
        if character.upper() == 'R':
            out = 'R'
        elif character.upper() == 'L':
            out = 'L'
        elif character.upper() in ['B', 'S']:
            out = 'B'
        return out

    @staticmethod
    def format_player_hometown(string: str):
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
                if province_abbreviation.lower() in string2.lower():
                    # Ex. ', on' in "burlington, on / nelson hs" or "nelson hs / burlington, on"
                    city = re.split(province_abbreviation, string2, flags=re.IGNORECASE)[0].split('/')[-1]
                    province = province_name
                    formatted = True
        if not formatted: # Province likely not listed, just get city
            city = string2.split(',')[0]
        city = re.sub(r'[^\w\-\s\.]', '', city).strip() # remove unwanted characters from city

        cbn_utils.log(f'"{string}" converted to ---> City: "{city}" | Province: "{province}"')
        return city, province 

class StatsPage(WebPage):
    def __init__(self, url = ''):
        WebPage.__init__(self, url)
        self.__df__: pd.DataFrame = None
        if url != '':
            self.__fetch_stats__()

    def to_df(self):
        return self.__df__

    def __fetch_stats__(self):
        if self.__df__ != None:
            return self.df
        url, html = self.url(), self.html()
        if self.success() == False:
            return cbn_utils.log(f'ERROR: request to {url} was unsuccessful')
        soup = BeautifulSoup(html, 'html.parser')
        if cbn_utils.NCAA_DOMAIN in url:
            hitting_table = soup.find('table', {'id': 'stat_grid'})
            hitting_df = pd.read_html(str(hitting_table))[0].replace('-', 0)
            hitting_df = hitting_df[hitting_df['GP'].astype(int) > 0]
            def get_ncaa_id(x):
                try: return hitting_table.find('a', text = x)['href'].split('stats_player_seq=')[-1]
                except: return ''
            hitting_df['id'] = hitting_df['Player'].apply(lambda x: get_ncaa_id(x))
            url_parts = urllib3.util.parse_url(url)
            pitching_stats_page = WebPage(url = f'{url_parts.scheme}://{url_parts.netloc}{soup.find("a", text = "Pitching")["href"]}')
            html = pitching_stats_page.html()
            soup = BeautifulSoup(html, 'html.parser')
            pitching_table = soup.find('table', {'id': 'stat_grid'})
            pitching_df = pd.read_html(str(pitching_table))[0].replace('-', 0)
            pitching_df = pitching_df[pitching_df['GP'].astype(int) > 0]
            pitching_df['id'] = pitching_df['Player'].apply(lambda x: get_ncaa_id(x))
            df = pd.merge(
                hitting_df[['id', 'Player', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'BA', 'OBPct', 'SlgPct']],
                pitching_df[['id', 'App', 'GS.1', 'IP', 'W', 'L', 'ER', 'H', 'BB', 'ERA', 'SV', 'SO']],
                how = 'outer',
                on = 'id',
                suffixes = ['', 'A']
            )
            df['last_name'] = df['Player'].apply(lambda x: x.split(', ')[0])
            df['first_name'] = df['Player'].apply(lambda x: x.split(', ')[1])
            self.__df__ = df.drop('Player', axis = 1).fillna(0).rename({'BA': 'AVG', 'OBPct': 'OBP', 'SlgPct': 'SLG', 'App': 'APP', 'GS.1': 'GS', 'SO': 'K'}, axis = 1)
        else:
            hitting_df, pitching_df = None, None
            for table in soup.find_all('table'):
                df = pd.read_html(str(table))[0].replace('-', 0)
                if 'ab' in df.columns:
                    # Hitting
                    ids_dict = {re.sub(' +', ' ', a.text.replace('\n', '').replace('\r', '').strip()): a['href'].split('/')[-1] for a in table.find_all('a') if '/players/' in a['href']}
                    ids_dict_keys = list(ids_dict.keys())
                    hitting_df = df.rename({col: col.upper() for col in df.columns}, axis = 1)
                    hitting_df = hitting_df[~hitting_df['NAME'].isin(['Totals', 'Opponent'])]
                    hitting_df['NAME'] = hitting_df['NAME'].apply(lambda x: re.sub(' +', ' ', x))
                    hitting_df['id'] = hitting_df['NAME'].apply(lambda x: ids_dict[x] if x in ids_dict_keys else '')
                elif 'ip' in df.columns:
                    # Pitching
                    ids_dict = {re.sub(' +', ' ', a.text.replace('\n', '').replace('\r', '').strip()): a['href'].split('/')[-1] for a in table.find_all('a') if '/players/' in a['href']}
                    ids_dict_keys = list(ids_dict.keys())
                    pitching_df = df.rename({col: col.upper() for col in df.columns}, axis = 1)
                    pitching_df = pitching_df[~pitching_df['NAME'].isin(['Totals', 'Opponent'])]
                    pitching_df['NAME'] = pitching_df['NAME'].apply(lambda x: re.sub(' +', ' ', x))
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
            self.__df__ = df.drop('NAME', axis = 1).fillna(0)
        self.__df__['OPS'] = self.__df__.apply(lambda row: float(row['OBP']) + float(row['SLG']), axis = 1)
        return self.__df__

class School:
    '''
    from model import School, Page
    school = School(name = 'U.S. Air Force Academy', league = 'NCAA', division = '1', state = 'CO', roster_page = Page(url = 'https://goairforcefalcons.com/sports/baseball/roster/2023'))
    school.players()
    '''
    def __init__(self, id = '', name = '', league = '', division = '', state = '', roster_url = '', stats_url = ''):
        # Check types
        cbn_utils.check_arg_type(name = 'id', value = id, value_type = str)
        cbn_utils.check_arg_type(name = 'name', value = name, value_type = str)
        cbn_utils.check_arg_type(name = 'league', value = league, value_type = str)
        cbn_utils.check_arg_type(name = 'division', value = division, value_type = str)
        cbn_utils.check_arg_type(name = 'state', value = state, value_type = str)
        cbn_utils.check_arg_type(name = 'roster_url', value = roster_url, value_type = str)
        cbn_utils.check_arg_type(name = 'stats_url', value = stats_url, value_type = str)

        # Check values
        cbn_utils.check_string_arg(name = 'id', value = id, disallowed_values = [''])
        cbn_utils.check_string_arg(name = 'name', value = name, disallowed_values = [''])
        cbn_utils.check_string_arg(name = 'league', value = league, allowed_values = [l['league'] for l in cbn_utils.leagues])
        cbn_utils.check_string_arg(name = 'state', value = state, allowed_values = ['AL', 'AK', 'AR', 'AZ', 'BC', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT', 'WA', 'WI', 'WV'])

        self.id = id
        self.name = name
        self.league = league
        self.division = division
        self.state = state
        self.roster_page = RosterPage(roster_url)
        # Only fetch stats if 1+ Canadians on roster
        self.stats_page = None
        if self.roster_page.players() != None:
            if any(player.canadian for player in self.roster_page.players()):
                self.stats_page = StatsPage(stats_url)

    def __repr__(self):
        return str({
            'name': self.name,
            'league': self.league,
            'division': self.division,
            'state': self.state
        })

    def players(self) -> list:
        players: list[Player] = list()
        if self.roster_page.players() == None:
            return players
        for player in self.roster_page.players():
            if (player.id == '') & (self.stats_page != None):
                player.add_stats(self.stats_page)
            players.append(player)
        return players

class Player:
    def __init__(self, last_name = '', first_name = '', positions: list[str] = [], bats = '', throws = '', year = '', city = '', province = '', canadian: bool = False):
        # Check types
        cbn_utils.check_arg_type(name = 'last_name', value = last_name, value_type = str)
        cbn_utils.check_arg_type(name = 'first_name', value = first_name, value_type = str)
        cbn_utils.check_arg_type(name = 'positions', value = positions, value_type = set)
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
        self.id = ''
        self.G = 0
        self.AB = 0
        self.R = 0
        self.H = 0
        self._2B = 0
        self._3B = 0
        self.HR = 0
        self.RBI = 0
        self.SB = 0
        self.AVG = 0.0
        self.OBP = 0.0
        self.SLG = 0.0
        self.OPS = 0.0
        self.APP = 0
        self.GS = 0
        self.IP = 0.0
        self.W = 0
        self.L = 0
        self.ER = 0
        self.HA = 0
        self.BB = 0
        self.ERA = 0.0
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
            'school': self.school.stats_page.url() if self.school != None else '',
            'school_roster_url': self.school.roster_page.url() if self.school != None else '',
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

    def add_stats(self, stats_page: StatsPage):
        stats_df = stats_page.to_df()
        stat_dict_list = stats_df[(stats_df['last_name'].str.lower() == self.last_name.lower()) & (stats_df['first_name'].str.lower() == self.first_name.lower())].to_dict(orient = 'records')
        if len(stat_dict_list) == 0:
            return
        stat_dict = stat_dict_list[0]
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
        self.AVG = round(float(stat_dict['AVG']), 3)
        self.OBP = round(float(stat_dict['OBP']), 3)
        self.SLG = round(float(stat_dict['SLG']), 3)
        self.OPS = round(float(stat_dict['OPS']), 3)
        self.APP = int(stat_dict['APP'])
        self.GS = int(stat_dict['GS'])
        self.IP = round(float(stat_dict['IP']), 1)
        self.W = int(stat_dict['W'])
        self.L = int(stat_dict['L'])
        self.ER = int(stat_dict['ER'])
        self.HA = int(stat_dict['HA'])
        self.BB = int(stat_dict['BB'])
        self.ERA = round(float(stat_dict['ERA']), 2) if float(stat_dict['ERA']) < 100 else 99.99
        self.SV = int(stat_dict['SV'])
        self.K = int(stat_dict['K'])