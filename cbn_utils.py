import re
import requests
import os
import pandas as pd
from datetime import datetime
import time
import smtplib
from email.mime.text import MIMEText
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
urllib3 = requests.packages.urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Environment
def env(key: str):
    if os.path.isfile('.env'):
        with open('.env') as f:
            for line in f.read().split('\n'):
                key_value_tuple = tuple(line.split('='))
                if key_value_tuple[0] == key:
                    return key_value_tuple[1]

RUNNING_LOCALLY = env('LOCAL') == '1'
now = datetime.now()

# Requests
session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}

def get(url: str, headers: dict[str, str] = headers, timeout: int = 60, verify: bool = True, attempt: int = 0):
    def print_req_result(req: requests.Response):
        if not isinstance(req, requests.Response):
            print(f' - timed out after {timeout}s')
        else:
            print(f' ({req.status_code}) {round(req.elapsed.total_seconds(), 2)}s')

    if not verify:
        log(f'WARNING: sending unverified request to {url}')

    print(log_prefix(), 'GET', url, end = '')
    req = None
    try:
        req = session.get(url, headers = headers, timeout = timeout, verify = verify)
        print_req_result(req)
    except requests.exceptions.SSLError:
        print_req_result(req)
        if verify:
            return get(url, headers = headers, timeout = timeout, verify = False)
    except (
        requests.exceptions.ReadTimeout,
        requests.exceptions.ConnectTimeout
    ): # 1 retry on timeout
        print_req_result(req)
        if attempt == 0:
            return get(url, headers = headers, timeout = timeout * 2, verify = verify, attempt = 1)
    except requests.exceptions.ConnectionError:
        print_req_result(req)
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
def pause(_):
    time.sleep(0.7)

def log(message: str):
    print(log_prefix(), message) if RUNNING_LOCALLY else print(message)

def log_prefix() -> str:
    return f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-4]} -'

def check_arg_type(name = '', value = None, value_type = None):
    assert type(value) == value_type, f'"{name}" argument must be of type {value_type.__name__}, NOT {type(value).__name__}'

def check_string_arg(name = '', value = '', allowed_values = [], disallowed_values = []):
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

def replace(string: str, dictionary: dict[str, str]) -> str:
    for old, new in dictionary.items():
        string = string.replace(old, new)
    return string

def strikethrough(x) -> str:
    return ''.join([character + '\u0336' for character in str(x)])

# Email
def player_scrape_results_email_html(added_df: pd.DataFrame) -> str:
    diff_cols = ['last_name', 'first_name', 'positions', 'year', 'city', 'province', 'school', 'league', 'division', 'state']
    new_line = '<div><br></div>'

    html = f'<div dir="ltr">Hey Bob,{new_line}'
    if len(added_df.index) > 0:
        if len(added_df.index) > 0:
            added_df['division'] = added_df['division'].apply(lambda x: x if x in ['1', '2', '3'] else '') # don't print NAIA conferences
            table = added_df.to_html(index = False, columns = diff_cols, justify = 'left')
            html += f'<div>Here are the {len(added_df.index)} new players who have been added to the list this week:</div><div>{table}</div>{new_line * 2}'
        html = html.replace('<table ', '<table style="border-collapsed: collapsed;" ') # TODO: get table border to look better... this doesn't seem to work
    else:
        html += f'<div>No new players were found by the scraper this week.</div>{new_line}'
    html += f'<div>Thanks,</div><div>Pete</div></div>'
    return html

def send_email(subject: str, html: str):
    # Ensure password is found
    if os.environ.get('GMAIL_PASSWORD') == None:
        os.environ['GMAIL_PASSWORD'] = env('GMAIL_PASSWORD')
    if os.environ.get('GMAIL_PASSWORD') == None:
        log('No Gmail password found')
        return

    # Send
    msg = MIMEText(html, 'html')
    msg['Subject'] = subject
    my_gmail = 'peteb206@gmail.com'
    msg['From'] = f'CBN Scrape Results <{my_gmail}>'
    msg['To'] = my_gmail
    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(my_gmail, os.environ.get('GMAIL_PASSWORD'))
    smtp_server.sendmail(my_gmail, my_gmail, msg.as_string())
    smtp_server.quit()

# Canada logic
city_strings = {
    'Quebec': ['montreal', 'saint-hilaire'],
    'Manitoba': ['winnipeg']
}

province_strings = {
    'Alberta': ['alberta', ', alta.', ', ab', 'a.b.'],
    'British Columbia': ['british columbia', 'b.c', ' bc', ',bc'],
    'Manitoba': ['manitoba', ', mb', ', man.'],
    'New Brunswick': ['new brunswick', ', nb', 'n.b.'],
    'Newfoundland & Labrador': ['newfoundland', 'nfld', ', nl'],
    'Nova Scotia': ['nova scotia', ', ns', 'n.s.' ],
    'Ontario': [', ontario', ', on', ',on', '(ont)', ', o.n.'],
    'Prince Edward Island': ['prince edward island', 'p.e.i.'],
    'Quebec': ['quebec', 'q.c.', ', qu', ', que.', ', qb', ', qc'],
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
    'bc high',
    'new brunswick,',
    'bca',
    'seoul, sk',
    'alkmaar, nl',
    'bc post grad'
]

def is_canadian(string: str) -> bool:
    return bool(any(canada_string.lower() in string.lower() for canada_string in canada_strings)) & (not any(ignore_string in string.lower() for ignore_string in ignore_strings))