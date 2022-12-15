from cbn_utils import check_arg_type, check_string_arg, check_list_arg
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials


class GoogleSpreadsheet:
    def __init__(self, keyfile = ''):
        # Check types
        check_arg_type(name = 'keyfile', value = keyfile, value_type = str)

        # Check values
        check_string_arg(name = 'keyfile', value = keyfile, disallowed_values = [''])

        # authorize the clientsheet 
        self.client = gspread.authorize(
            ServiceAccountCredentials.from_json_keyfile_dict(
                json.loads(keyfile),
                [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
        )

    def spreadsheet(self, name = ''):
        return self.client.open(name)


class Page:
    '''
    # Test code:
    from model import Page
    page = Page(url = 'https://goairforcefalcons.com/sports/baseball/roster/2023')
    page.get_table()
    '''

    def __init__(self, url = '', session = None):
        # Check types
        check_arg_type(name = 'url', value = url, value_type = str)
        if session != None:
            check_arg_type(name = 'session', value = session, value_type = requests.Session)

        # Check values
        check_string_arg(name = 'url', value = url, disallowed_values = [''])

        self.url = url
        self.session = requests.Session() if session == None else session
        self.__html = ''
        self.dfs = list()
        self.df = pd.DataFrame()

    def __repr__(self):
        return self.url

    def __fetch_roster_page__(self):
        if self.url:
            return self.session.get(
                self.url,
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                allow_redirects = False,
                timeout = 10
            )

    def html(self, new_request = False):
        if (self.url != '') & (new_request | (self.__html == '')):
            # Re-request if URL is not blank and either re-request manually ordered or html string is blank
            self.__html = ''
            response = self.__fetch_roster_page__()
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
                if len(self.df.index) < len(df.index):
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
    def __init__(self, name = '', league = '', division = '', state = '', roster_page: Page = None):
        # Check types
        check_arg_type(name = 'name', value = name, value_type = str)
        check_arg_type(name = 'league', value = league, value_type = str)
        check_arg_type(name = 'division', value = division, value_type = str)
        check_arg_type(name = 'state', value = state, value_type = str)
        check_arg_type(name = 'roster_page', value = roster_page, value_type = Page)

        # Check values
        check_string_arg(name = 'name', value = name, disallowed_values = [''])
        check_string_arg(name = 'league', value = league, allowed_values = ['NCAA', 'NAIA', 'JUCO', 'CCCAA', 'NWAC', 'USCAA'])
        check_string_arg(name = 'division', value = division, allowed_values = ['', '1', '2', '3'])
        check_string_arg(name = 'state', value = state, allowed_values = ['AL', 'AK', 'AR', 'AZ', 'BC', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'HI',
                                                                          'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO',
                                                                          'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR',
                                                                          'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT', 'WA', 'WI', 'WV'])

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
        if 'P' in string:
            position_set.add('P')
        # Catcher
        if ('C' in string) & ('CF' not in string) & ('CI' not in string):
            position_set.add('C')
        # Infield
        if ('IN' in string) | ('IF' in string):
            position_set.add('INF')
        elif ('SS' in string):
            position_set.add('SS')
        else: # 1B, 2B, 3B
            for base in range(1, 4):
                if str(base) in string:
                    position_set.add(f'{base}B')
        # Outfield
        if 'OF' in string:
            position_set.add('OF')
        else:
            for outfield in ['LF', 'CF', 'RF']:
                if outfield in string:
                    position_set.add(outfield)
        # Designated Hitter & Utility
        if 'D' in string:
            position_set.add('DH')
        if 'U' in string:
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
        for province_name, province_abbreviations in province_strings.items():
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
                            if (any(canada_string.lower() in value_str.lower() for canada_string in canada_strings)) & (~any(ignore_string in value_str.lower() for ignore_string in ignore_strings)):
                                new_dict['city'], new_dict['province'] = self.__format_player_hometown__(value_str, debug=debug)
                                new_dict['canadian'] = True
                new_dict['school'] = self
                player = Player(**new_dict)
                self.__players.append(player)
        return self.__players

class Player:
    def __init__(self, last_name = '', first_name = '', positions = [], bats = '', throws = '', year = '', school: School = None, city = '',
                 province = '', canadian: bool = False, stats_link = ''):
        # Check types
        check_arg_type(name = 'last_name', value = last_name, value_type = str)
        check_arg_type(name = 'first_name', value = first_name, value_type = str)
        check_arg_type(name = 'positions', value = positions, value_type = list)
        check_arg_type(name = 'bats', value = bats, value_type = str)
        check_arg_type(name = 'throws', value = throws, value_type = str)
        check_arg_type(name = 'year', value = year, value_type = str)
        check_arg_type(name = 'school', value = school, value_type = School)
        check_arg_type(name = 'city', value = city, value_type = str)
        check_arg_type(name = 'province', value = province, value_type = str)
        check_arg_type(name = 'canadian', value = canadian, value_type = bool)
        check_arg_type(name = 'stats_link', value = stats_link, value_type = str)

        # Check values
        check_string_arg(name = 'last_name', value = last_name, disallowed_values = [''])
        check_string_arg(name = 'first_name', value = first_name, disallowed_values = [''])
        check_list_arg(name = 'positions', values = positions, allowed_values = ['', 'P', 'C', '1B', '2B', '3B', 'SS', 'INF', 'LF', 'CF', 'RF', 'OF',
                                                                                'DH', 'UTIL'])
        check_string_arg(name = 'bats', value = bats, allowed_values = ['', 'R', 'L', 'B'])
        check_string_arg(name = 'throws', value = throws, allowed_values = ['', 'R', 'L', 'B'])
        check_string_arg(name = 'year', value = year, allowed_values = ['', 'Redshirt', 'Freshman', 'Sophomore', 'Junior', 'Senior'])
        # check_string_arg(name = 'school', value = school, disallowed_values = [None])
        check_string_arg(name = 'province', value = province, allowed_values = ['', 'Alberta', 'British Columbia', 'Manitoba', 'New Brunswick',
                                                                                'Newfoundland & Labrador', 'Nova Scotia', 'Ontario',
                                                                                'Prince Edward Island', 'Quebec', 'Saskatchewan'])

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
        self.stats_link = stats_link

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
            'stats_link': self.stats_link
        }

# global variables
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