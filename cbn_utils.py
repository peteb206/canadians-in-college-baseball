import re

def check_arg_type(name='', value=None, value_type=None) -> bool:
    assert type(value) == value_type, f'"{name}" argument must be of type {value_type.__name__}, NOT {type(value).__name__}'

def check_string_arg(name='', value='', allowed_values=[], disallowed_values=[]) -> bool:
    passes, message = True, ''
    if len(allowed_values):
        if value not in allowed_values:
            passes = False
            message = f'"{name}" argument must be a str from the following list: {allowed_values}. "{value}" was provided. '
    if len(disallowed_values):
        if value in disallowed_values:
            passes = False
            message += f'"{name}" argument must be a str NOT from the following list: {disallowed_values}. "{value}" was provided. '
    assert passes, message

def check_list_arg(name='', values=[], allowed_values=[], disallowed_values=[]) -> bool:
    passes, message = True, ''
    for value in values:
        if len(allowed_values):
            if value not in allowed_values:
                passes = False
                message += f'"{name}" argument must be from the following list: {allowed_values}. "{value}" was provided. '
        if len(disallowed_values):
            if value in disallowed_values:
                passes = False
                message += f'"{name}" argument must NOT be from the following list: {disallowed_values}. "{value}" was provided. '
    assert passes, message

def strikethrough(x) -> str:
    return ''.join([character + '\u0336' for character in str(x)])

stats_labels = {
    'batting': {
        'G': 'Games Played',
        'AB': 'At Bats',
        'R': 'Runs Scored',
        'H': 'Hits',
        '2B': 'Doubles',
        '3B': 'Triples',
        'HR': 'Home Runs',
        'RBI': 'Runs Batted In',
        'SB': 'Stolen Bases',
        'AVG': 'Batting Average',
        'OBP': 'On-Base Percentage',
        'SLG': 'Slugging Percentage',
        'OPS': 'On-Base plus Slugging'
    },
    'pitching': {
        'APP': 'Appearances',
        'GS': 'Games Started',
        'IP': 'Innings Pitched',
        'W': 'Wins',
        'L': 'Losses',
        'ER': 'Earned Runs',
        'HA': 'Hits Allowed',
        'BB': 'Walks Allowed',
        'ERA': 'Earned Run Average',
        'SV': 'Saves',
        'K': 'Strikeouts'
    }
}

city_strings = {
    'Quebec': ['montreal', 'saint-hilaire']
}

province_strings = {
    'Alberta': ['alberta', ', alta.', ', ab', 'a.b.'],
    'British Columbia': ['british columbia', 'b.c', ' bc'],
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
    ', queens',
    'bc high'
]