import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import csv

def last_year():
    return '2021-22'

def year_convert(url):
    conversion_dict = {
        '2021-2022': '2022-2023',
        '2022': '2023',
        last_year(): '2022-23',
        '2021': '2023'
    }
    for old, new in conversion_dict.items():
        url = url.replace(old, new)
    return url

def headers():
    return {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36',
      'X-Requested-With': 'XMLHttpRequest'
    }

def get_college_baseball_hub_schools(division='D1', auth=''):
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
        'appId': '6f20d739-3700-4bcb-820a-c52f632ed312'
    }
    headers_ = headers()
    # Get this header from visiting https://www.collegebaseballhub.com/d1
    # Search Dev Tools for first "query" call
    headers_['authorization'] = auth
    req = requests.post('https://www.collegebaseballhub.com/_api/cloud-data/v1/wix-data/collections/query', json=body, headers=headers_)
    schools = list()
    for school in json.loads(req.text)['items']:
        school_dict = {k: school[k] for k in ['title', 'state', 'division', 'link'] if k in school}
        school_dict['school'] = school_dict.pop('title')
        if division == 'NAIA':
            school_dict['league'], school_dict['division'] = division, ''
        else:
            school_dict['league'], school_dict['division'] = 'NCAA', school_dict['division'][-1]
        schools.append(school_dict)
    return schools

def get_ncaa_schools(division='', auth=''):
    return get_college_baseball_hub_schools(division=division, auth=auth)

def get_naia_schools(auth=''):
    return get_college_baseball_hub_schools(division='NAIA', auth=auth)

def get_juco_schools():
    req = requests.get('https://www.njcaa.org/sports/bsb/teams', headers=headers())
    soup = BeautifulSoup(req.text, 'html.parser')
    schools, division = list(), 0
    for div in soup.find_all('div', {'class': 'content-col'}):
        division += 1
        for ul in div.find_all('ul'):
            for li in ul.find_all('li'):
                school = li.find('a', {'class': 'college-name'})
                if school != None:
                    schools.append({'school': school.text, 'state': '', 'league': 'JUCO', 'division': division, 'link': ''})
    return schools

def get_cccaa_schools():
    req = requests.get(f'https://www.cccaasports.org/sports/bsb/{last_year()}/teams', headers=headers())
    schools_df = pd.read_html(req.text)[0]
    schools_df['school'] = schools_df['Name']
    schools_df['state'] = 'CA'
    schools_df['league'] = 'CCCAA'
    schools_df['division'] = ''
    schools_df['link'] = ''
    schools_df = schools_df[['school', 'league', 'division', 'state', 'link']]
    return schools_df.to_dict(orient='records')

def get_nwac_schools():
    req = requests.get(f'https://nwacsports.com/sports/bsb/{last_year()}/teams', headers=headers())
    schools_df = pd.read_html(req.text)[0]
    schools_df['school'] = schools_df['Name']
    schools_df['state'] = ''
    schools_df['league'] = 'NWAC'
    schools_df['division'] = ''
    schools_df['link'] = ''
    schools_df = schools_df[['school', 'league', 'division', 'state', 'link']]
    return schools_df.to_dict(orient='records')

def get_uscaa_schools():
    req = requests.get(f'https://uscaa.prestosports.com/sports/bsb/{last_year()}/teams', headers=headers())
    schools_df = pd.read_html(req.text)[0]
    schools_df['school'] = schools_df['Name']
    schools_df['state'] = ''
    schools_df['league'] = 'USCAA'
    schools_df['division'] = ''
    schools_df['link'] = ''
    schools_df = schools_df[['school', 'league', 'division', 'state', 'link']]
    return schools_df.to_dict(orient='records')

# wixcode-pub.b7afbf0aa46fa32979947ad548a542cd972d3ea4.eyJpbnN0YW5jZUlkIjoiZjFiMGI3NjUtMzM1OC00Mjc1LThkODItY2NmZWJiNTAyMGIwIiwiaHRtbFNpdGVJZCI6IjFkNmQxYzg5LTRlNTAtNGNiMy1hM2M3LTJkNzFmYjg0MDU5NCIsInVpZCI6bnVsbCwicGVybWlzc2lvbnMiOm51bGwsImlzVGVtcGxhdGUiOmZhbHNlLCJzaWduRGF0ZSI6MTY2OTY1NzM2MzI3MywiYWlkIjoiZjFhY2QzOWItY2YwYS00MTlhLWI3NTAtMDJjZmViYzYwYmIzIiwiYXBwRGVmSWQiOiJDbG91ZFNpdGVFeHRlbnNpb24iLCJpc0FkbWluIjpmYWxzZSwibWV0YVNpdGVJZCI6IjA3NzA4OGEwLWU2ODAtNDg4Ni1hMWY4LThmMjYxMGZjMDQwZiIsImNhY2hlIjpudWxsLCJleHBpcmF0aW9uRGF0ZSI6bnVsbCwicHJlbWl1bUFzc2V0cyI6IlNob3dXaXhXaGlsZUxvYWRpbmcsSGFzRG9tYWluLEFkc0ZyZWUiLCJ0ZW5hbnQiOm51bGwsInNpdGVPd25lcklkIjoiNzM4M2FkYmUtMTc4ZS00OGE1LWFhMWItNjI3YmYxMDUxYmZiIiwiaW5zdGFuY2VUeXBlIjoicHViIiwic2l0ZU1lbWJlcklkIjpudWxsLCJwZXJtaXNzaW9uU2NvcGUiOm51bGx9
auth = input('Authorization token:')
schools = get_ncaa_schools(division='D1', auth=auth) + get_ncaa_schools(division='D2', auth=auth) + get_ncaa_schools(division='D3', auth=auth) + get_naia_schools(auth=auth) + get_juco_schools() + get_cccaa_schools() + get_nwac_schools() + get_uscaa_schools()

cols = ['school', 'league', 'division', 'state', 'link']
schools_df = pd.DataFrame(schools)[cols]
cols.append('roster_link')
old_schools_df = pd.read_csv('archive/roster_pages_2022.csv')[['title', 'state', 'roster_link']]
display(schools_df[schools_df.duplicated(subset='school', keep=False)].sort_values(by='school'))

merged_df = pd.merge(schools_df, old_schools_df.rename({'title': 'school'}, axis=1), how='left', on='school', suffixes=['', '_old']).fillna('')
merged_df['state'] = merged_df.apply(lambda row: row['state'] if row['state'] != '' else row['state_old'], axis=1)
merged_df['roster_link'] = merged_df['roster_link'].apply(lambda x: year_convert(x))
merged_df.drop_duplicates(inplace=True)
merged_df.to_csv('roster_pages_2023.csv', index=False, columns=cols, quoting=csv.QUOTE_NONNUMERIC)
merged_df