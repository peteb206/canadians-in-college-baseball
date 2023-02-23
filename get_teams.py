from config import hub_spreadsheet, config_values
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from urllib.parse import urlparse

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}

# Year format
this_year = int(config_values['YEAR'])
last_year = this_year - 1
two_years_ago = last_year - 1
year_conversion_dict = {
    f'{str(last_year)[-2:]}': f'{str(this_year)[-2:]}',
    f'{str(two_years_ago)[-2:]}': f'{str(last_year)[-2:]}'
}

# Fetch existing schools to dataframe
school_cols = ['id', 'name', 'league', 'division', 'state', 'roster_url']
schools_worksheet = hub_spreadsheet.worksheet('Schools_')
old_schools_df = pd.DataFrame(schools_worksheet.get_all_records(), dtype = str)
old_schools_df['site_domain'] = old_schools_df['roster_url'].apply(lambda x: urlparse(x).netloc.replace('www.', ''))
old_schools_df = old_schools_df[old_schools_df['name'] != ''].reset_index(drop = True)
old_schools_df = old_schools_df[school_cols + ['site_domain']]

def year_convert(url: str) -> str:
    for old, new in year_conversion_dict.items():
        url = url.replace(old, new)
    return url

def get_college_baseball_hub_auth_token() -> tuple:
    req = session.get('https://www.collegebaseballhub.com/d1')
    soup = BeautifulSoup(req.text, 'html.parser')
    wix_javascript = soup.find('script', {'id': 'wix-viewer-model'})
    if wix_javascript != None:
        wix_dict = json.loads(wix_javascript.text)
        app_id = wix_dict['siteFeaturesConfigs']['dynamicPages']['prefixToRouterFetchData']['school']['urlData']['appDefinitionId']
        req = session.get('https://www.collegebaseballhub.com/_api/v2/dynamicmodel')
        return wix_dict['siteFeaturesConfigs']['dataWixCodeSdk']['gridAppId'], json.loads(req.text)['apps'][app_id]['instance']

app_id, auth_token = get_college_baseball_hub_auth_token()

def get_college_baseball_hub_schools(division: str = 'D1') -> pd.DataFrame:
    body = {
        'collectionName': 'Division1',
        'dataQuery': {
            'filter': {
                '$and': [
                    {
                        'orderId': {
                            '$gt': 0
                        }
                    }, {
                        'division': {
                            '$eq': division
                        }
                    }, {
                        'show': {
                            '$eq': True
                        }
                    }, {
                        '$and': []
                    }, {
                        '$and': []
                    }, {
                        '$and': []
                    }, {
                        '$and': []
                    }
                ]
            },
            'sort': [
                {
                    'fieldName': 'orderId',
                    'order': 'ASC'
                }
            ],
            'paging': {
                'offset': 0,
                'limit': 500
            }
        },
        'options': {},
        'includeReferencedItems': [],
        'segment': 'LIVE',
        'appId': app_id
    }
    req = session.post('https://www.collegebaseballhub.com/_api/cloud-data/v1/wix-data/collections/query', json = body, headers = headers | {'authorization': auth_token})
    schools = list()
    for school in json.loads(req.text)['items']:
        school_dict = {k: school[k] for k in ['shortname', 'state', 'division', 'link'] if k in school}
        school_dict['name'] = school_dict.pop('shortname')
        # school_dict['site_domain'] = site_domain(school_dict.pop('link'))
        if division == 'NAIA':
            school_dict['league'], school_dict['division'] = division, ''
        else:
            school_dict['league'], school_dict['division'] = 'NCAA', school_dict['division'][-1]
        schools.append(school_dict)
    df = pd.merge(
        pd.DataFrame(schools),
        old_schools_df,
        how = 'left',
        on = ['name', 'league', 'state'], # 'site_domain',
        suffixes = ['', '_old']
    )
    return df[school_cols].fillna('')

def get_ncaa_schools(division: str = '1') -> pd.DataFrame:
    return get_college_baseball_hub_schools(division = f'D{division}')

def get_naia_schools() -> pd.DataFrame:
    return get_college_baseball_hub_schools(division = 'NAIA')

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
    df = pd.merge(
        pd.DataFrame(schools),
        old_schools_df,
        how = 'left',
        on = ['name', 'league'],
        suffixes = ['', '_old']
    )
    return df[school_cols].fillna('')

def get_other_schools(league: str) -> pd.DataFrame:
    url = ''
    if league == 'CCCAA':
        url = f'https://www.cccaasports.org/sports/bsb/{str(last_year)}-{str(this_year)[-2:]}/teams'
    elif league == 'NWAC':
        url = f'https://nwacsports.com/sports/bsb/{str(last_year)}-{str(this_year)[-2:]}/teams'
    elif league == 'USCAA':
        url = f'https://uscaa.prestosports.com/sports/bsb/{str(last_year)}-{str(this_year)[-2:]}/teams'
    if url == '':
        return pd.DataFrame()
    req = session.get(url, headers = headers)
    soup = BeautifulSoup(req.text, 'html.parser')
    schools = list()
    for i, tr in enumerate(soup.find('table').find_all('tr')):
        if i > 0:
            school = tr.find_all('td')[1].find('a')
            schools.append({'id': school['href'].split('/')[-1], 'name': school.text, 'league': league})
    df = pd.merge(
        pd.DataFrame(schools),
        old_schools_df,
        how = 'left',
        on = ['name', 'league'],
        suffixes = ['', '_old']
    )
    return df[school_cols].fillna('')

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
            get_ncaa_schools('1'),
            get_ncaa_schools('2'),
            get_ncaa_schools('3'),
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