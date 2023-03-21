import re
import requests
import os
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

# Requests
session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}

def get(url: str, headers: dict[str, str] = headers, timeout: int = 60, verify: bool = True, attempt: int = 0):
    print(log_prefix(), 'GET', url, end = '')
    try:
        req = session.get(url, headers = headers, timeout = timeout, verify = verify)
    except requests.exceptions.ReadTimeout: # 1 retry on timeout
        if attempt == 0:
            print(f' ({req.status_code}) {round(req.elapsed.total_seconds(), 2)}s')
            get(url, headers = headers, timeout = timeout * 2, verify = verify, attempt = 1)
    print(f' ({req.status_code}) {round(req.elapsed.total_seconds(), 2)}s')
    return req

# Labels
NCAA_DOMAIN = 'stats.ncaa.org'
NAIA_DOMAIN = 'naiastats.prestosports.com'
JUCO_DOMAIN = 'www.njcaa.org'
CCCAA_DOMAIN = 'www.cccaasports.org'
NWAC_DOMAIN = 'nwacsports.com'
USCAA_DOMAIN = 'uscaa.prestosports.com'

leagues = [
    {'league': 'NCAA', 'division': str(division), 'label': f'NCAA: Division {division}'} for division in range(1, 4)
] + [
    {'league': 'NAIA', 'division': '', 'label': 'NAIA'}
] + [
    {'league': 'JUCO', 'division': str(division), 'label': f'JUCO: Division {division}'} for division in range(1, 4)
] + [
    {'league': 'CCCAA', 'division': '', 'label': 'California CC'},
    {'league': 'NWAC', 'division': '', 'label': 'NW Athletic Conference'},
    {'league': 'USCAA', 'division': '', 'label': 'USCAA'}
]

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

# Functions
def log(message: str):
    print(log_prefix(), message)

def log_prefix() -> str:
    return f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-4]} -'

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

# Email
def send_results_email(diff_df: pd.DataFrame):
    os.environ['EMAIL_SENDER'] = 'peteb206@gmail.com'
    os.environ['EMAIL_RECIPIENT'] = 'peteb206@gmail.com'
    os.environ['EMAIL_SENDER_PASSWORD'] = 'uvuklzplnvnypgbu'
    now = datetime.now()
    new_line = '<div><br></div>'
    added_df = diff_df[diff_df['diff'] == 'added']
    dropped_df = diff_df[diff_df['diff'] == 'dropped']

    html = f'<div dir="ltr">Hey Bob,{new_line}'
    if len(added_df.index) + len(dropped_df.index) > 0:
        if len(added_df.index) > 0:
            html += f'<div>Here are the new players who have been added to the list this week:<br></div><div>{added_df.drop("diff", axis = 1).to_html()}</div>{new_line * 2}'
        if len(dropped_df.index) > 0:
            html += f'<div>These guys were dropped from the list because they were on the schools\' {now.year - 1} rosters but NOT on the updated {now.year} roster:</div><div>{dropped_df.drop("diff", axis = 1).to_html()}</div>{new_line * 2}'
    else:
        html += f'<div>No new players were found by the scraper this week.</div>{new_line}'
    html += f'<div>Thanks,</div><div>Pete</div></div>'

    msg = MIMEText(html, 'html')
    msg['Subject'] = f'New Players (Week of {now.strftime("%B %d, %Y")})'
    msg['From'] = os.environ.get('EMAIL_SENDER')
    msg['To'] = os.environ.get('EMAIL_RECIPIENT')
    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(os.environ.get('EMAIL_SENDER'), os.environ.get('EMAIL_SENDER_PASSWORD'))
    smtp_server.sendmail(os.environ.get('EMAIL_SENDER'), os.environ.get('EMAIL_RECIPIENT'), msg.as_string())
    smtp_server.quit()

# Canada logic
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