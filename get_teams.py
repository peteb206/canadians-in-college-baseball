from google_sheets import hub_spreadsheet, config
from bs4 import BeautifulSoup
import pandas as pd
import requests

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}

# Year format
this_year = int(config['YEAR'])
last_year = this_year - 1

# Fetch existing schools to dataframe
school_cols = ['id', 'name', 'league', 'division', 'state', 'roster_url']
schools_worksheet = hub_spreadsheet.sheet('Schools')
old_schools_df = schools_worksheet.to_df()
old_schools_df = old_schools_df[school_cols]
# old_schools_df['site_domain'] = old_schools_df['roster_url'].apply(lambda x: urlparse(x).netloc.replace('www.', ''))

def compare_and_join(df: pd.DataFrame):
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
    df['id'] = df.apply(lambda row: '-'.join([row['league'], str(row['orgId'])]), axis = 1)
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
                schools.append({'id': '-'.join([league, a['href'].split('/')[-1]]), 'name': a.text, 'league': league})
            else:
                name = td.text.strip()
                schools.append({'id': '-'.join([league, name.lower().remove(' ', '')]), 'name': name, 'league': league})
    return compare_and_join(pd.DataFrame(schools))

def get_naia_schools() -> pd.DataFrame:
    return get_other_schools('NAIA')

def get_juco_schools() -> pd.DataFrame:
    req = session.get('https://www.njcaa.org/sports/bsb/teams', headers = headers)
    soup = BeautifulSoup(req.text, 'html.parser')
    schools, league, division = list(), 'JUCO', 0
    for div in soup.find_all('div', {'class': 'content-col'}):
        division += 1
        for ul in div.find_all('ul'):
            for li in ul.find_all('li'):
                school = li.find('a', {'class': 'college-name'})
                if school != None:
                    schools.append({'id': '-'.join([league, school['href'].split('/')[-1]]), 'name': school.text, 'league': league, 'division': str(division)})
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

    schools_no_dup_df = schools_df.drop_duplicates(subset = ['name', 'league', 'state'], ignore_index = True)

    # Analyze
    diff_df = pd.merge(old_schools_df[school_cols], schools_df[school_cols], how = 'outer', on = school_cols, indicator = 'indicator')
    diff_df = diff_df[diff_df['indicator'] != 'both']
    print('The following differences were found:')
    if len(diff_df.index):
        diff_df['indicator'] = diff_df['indicator'].apply(lambda x: 'Previous' if x == 'left_only' else 'New')
        print(diff_df.sort_values(by = 'indicator', ascending = False))
    print()

    duplicate_schools_df = schools_df[schools_df.duplicated(subset = ['name', 'state'], keep = False)].sort_values(by = 'name', ignore_index = True)
    print('The following schools may be duplicated in the updated Google Sheet:')
    if len(duplicate_schools_df.index):
        print(duplicate_schools_df)
    print()

    duplicate_roster_df = schools_df[schools_df.duplicated(subset = 'roster_url', keep = False)].sort_values(by = 'roster_url', ignore_index = True)
    print('The following schools have the same roster url:')
    if len(duplicate_schools_df.index):
        print(duplicate_roster_df)

    return schools_no_dup_df

if __name__ == '__main__':
    schools_df = get_schools()
    schools_worksheet.update_data(schools_df, sort_by = ['league', 'division', 'name'], freeze_cols = 2)