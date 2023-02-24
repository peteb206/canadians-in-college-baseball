from config import hub_spreadsheet, config_values
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urlparse

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}

# Year format
this_year = int(config_values['YEAR'])
last_year = this_year - 1

# Fetch existing schools to dataframe
school_cols = ['id', 'name', 'league', 'division', 'state', 'roster_url']
schools_worksheet = hub_spreadsheet.worksheet('Schools_')
old_schools_df = pd.DataFrame(schools_worksheet.get_all_records(), dtype = str)
old_schools_df['site_domain'] = old_schools_df['roster_url'].apply(lambda x: urlparse(x).netloc.replace('www.', ''))
old_schools_df = old_schools_df[old_schools_df['name'] != ''].reset_index(drop = True)
old_schools_df = old_schools_df[school_cols + ['site_domain']]

def compare_and_join(df: pd.DataFrame):
    df['name'] = df['name'].apply(lambda x: x.split('(')[0].strip())
    df = df.merge(
        old_schools_df,
        how = 'left',
        on = ['id', 'league'],
        suffixes = ['', '_old']
    )
    return df[school_cols].fillna('')

def get_ncaa_schools() -> pd.DataFrame:
    df = pd.read_json('https://web3.ncaa.org/directory/api/directory/memberList?type=12&sportCode=MBA')
    df = df[['orgId', 'nameOfficial', 'division', 'athleticWebUrl', 'memberOrgAddress']]
    df['id'] = df['orgId'].astype(str)
    df['name'] = df['nameOfficial']
    df['league'] = 'NCAA'
    df['division'] = df['division'].astype(str)
    df['state'] = df['memberOrgAddress'].apply(lambda x: x['state'])
    df['site_domain'] = df['athleticWebUrl'].apply(lambda x: x.replace('www.', ''))
    return compare_and_join(df.sort_values(by = ['division', 'name'], ignore_index = True))

def get_other_schools(league: str) -> pd.DataFrame:
    url = ''
    if league == 'NAIA':
        url = f'https://naiastats.prestosports.com/sports/bsb/{str(this_year - 1)}-{str(this_year)[-2:]}/teams'
    elif league == 'CCCAA':
        url = f'https://www.cccaasports.org/sports/bsb/{str(this_year - 1)}-{str(this_year)[-2:]}/teams'
    elif league == 'NWAC':
        url = f'https://nwacsports.com/sports/bsb/{str(this_year - 1)}-{str(this_year)[-2:]}/teams'
    elif league == 'USCAA':
        url = f'https://uscaa.prestosports.com/sports/bsb/{str(this_year - 1)}-{str(this_year)[-2:]}/teams'
    else:
        return pd.DataFrame()
    req = session.get(url, headers = headers)
    soup = BeautifulSoup(req.text, 'html.parser')
    schools = list()
    for i, tr in enumerate(soup.find('table').find_all('tr')):
        if i > 0: # skip header row
            td = tr.find_all('td')[1]
            a = td.find('a')
            if a:
                schools.append({'id': a['href'].split('/')[-1], 'name': a.text, 'league': league})
            else:
                name = td.text.strip()
                schools.append({'id': name.lower().remove(' ', ''), 'name': name, 'league': league})
    return compare_and_join(pd.DataFrame(schools))

def get_naia_schools() -> pd.DataFrame:
    return get_other_schools('NAIA')

def get_juco_schools() -> pd.DataFrame:
    req = session.get('https://www.njcaa.org/sports/bsb/teams', headers = headers)
    soup = BeautifulSoup(req.text, 'html.parser')
    schools, division = list(), 0
    for div in soup.find_all('div', {'class': 'content-col'}):
        division += 1
        for ul in div.find_all('ul'):
            for li in ul.find_all('li'):
                school = li.find('a', {'class': 'college-name'})
                if school != None:
                    schools.append({'id': school['href'].split('/')[-1], 'name': school.text, 'league': 'JUCO', 'division': str(division)})
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
    print('The following schools were not found in the current Google Sheet:')
    print(schools_df[schools_df['state'] == ''])
    print()
    print('The following schools may be duplicated in the updated Google Sheet:')
    print(schools_df[schools_df.duplicated(subset = ['name', 'state'], keep = False)].sort_values(by = 'name', ignore_index = True))
    print()
    print('The following schools have the same roster url:')
    print(schools_df[schools_df.duplicated(subset = 'roster_url', keep = False)].sort_values(by = 'roster_url', ignore_index = True))

    # Output to Canadians in College Hub Google Sheet
    # TODO: Add the following columns to Schools sheet:
    #   school, league, division, state, rosterurl (rename to roster), status (check mark/X/redirect with conditional formatting), players, canadians
    schools_df.drop_duplicates(subset = ['name', 'league', 'state'], ignore_index = True, inplace = True)
    return schools_df

if __name__ == '__main__':
    schools_df = get_schools()
    schools_list = schools_df.values.tolist()
    
    schools_worksheet.resize(2) # Delete existing data
    schools_worksheet.resize(3)
    schools_worksheet.insert_rows(schools_list, row = 3) # Add updated data