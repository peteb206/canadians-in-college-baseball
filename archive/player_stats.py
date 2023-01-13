import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
from roster_scrape import format_player_name

def base_urls():
    return {
        'ncaa': 'http://stats.ncaa.org',
        'naia': f'https://naiastats.prestosports.com',
        'juco': f'https://www.njcaa.org',
        'cccaa': f'https://www.cccaasports.org',
        'uscaa': f'https://www.theuscaa.com',
        'nwac': f'https://nwacstats.org'
    }

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36'
    }

def get_all_team_urls(year):
    session = requests.Session()

    url, sport = '', 'bsb'
    season = f'{str(year - 1)}-{str(year)[2:]}'

    ncaa_ext_url = f'{base_urls()["ncaa"]}/rankings'
    naia_ext_url = f'{base_urls()["naia"]}/sports/{sport}/{season}/teams'
    juco_ext_url = f'{base_urls()["juco"]}/sports/{sport}/{season}'
    cccaa_ext_url = f'{base_urls()["cccaa"]}/sports/{sport}/{season}'
    uscaa_ext_url = f'{base_urls()["uscaa"]}/sports/{sport}/{season}'
    nwac_ext_url = f'{base_urls()["nwac"]}/sports/{sport}/{season}'

    setup_dict = {
        # 'ncaa': {
        #     '1': {
        #         'url': f'{ncaa_ext_url}/national_ranking',
        #         'parameters': {
        #             'academic_year': year,
        #             'division': 1,
        #             'sport_code': 'MBA',
        #             'stat_seq': 210,
        #             'ranking_period': 73
        #         },
        #         'referer': f'{ncaa_ext_url}/change_sport_year_div'
        #     },
        #     '2': {
        #         'url': f'{ncaa_ext_url}/national_ranking',
        #         'parameters': {
        #             'academic_year': year,
        #             'division': 2,
        #             'sport_code': 'MBA',
        #             'stat_seq': 210,
        #             'ranking_period': 73
        #         },
        #         'referer': f'{ncaa_ext_url}/change_sport_year_div'
        #     },
        #     '3': {
        #         'url': f'{ncaa_ext_url}/national_ranking',
        #         'parameters': {
        #             'academic_year': year,
        #             'division': 3,
        #             'sport_code': 'MBA',
        #             'stat_seq': 210,
        #             'ranking_period': 73
        #         },
        #         'referer': f'{ncaa_ext_url}/change_sport_year_div'
        #     }
        # },
        'naia': {
            'url': naia_ext_url,
            'parameters': {
                'sort': 'gp',
                'r': 0,
                'pos': 'h'
            },
            'referer': 'https://www.naia.org'
        },
        'juco': {
            '1': {
                'url': f'{juco_ext_url}/div1/teams',
                'parameters': {
                    'sort': 'gp',
                    'r': 0,
                    'pos': 'h'
                },
                'referer': f'{juco_ext_url}/div1/leaders'
            },
            '2': {
                'url': f'{juco_ext_url}/div2/teams',
                'parameters': {
                    'sort': 'gp',
                    'r': 0,
                    'pos': 'h'
                },
                'referer': f'{juco_ext_url}/div2/leaders'
            },
            '3': {
                'url': f'{juco_ext_url}/div3/teams',
                'parameters': {
                    'sort': 'gp',
                    'r': 0,
                    'pos': 'h'
                },
                'referer': f'{juco_ext_url}/div3/leaders'
            }
        },
        'cccaa': {
            'url': f'{cccaa_ext_url}/teams',
            'parameters': {
                'sort': 'gp',
                'r': 0,
                'pos': 'h'
            },
            'referer': f'{cccaa_ext_url}/leaders'
        },
        'nwac': {
            'url': f'{nwac_ext_url}/teams',
            'parameters': {
                'sort': 'gp',
                'r': 0,
                'pos': 'h'
            },
            'referer': f'{nwac_ext_url}/leaders'
        },
        'uscaa': {
            'url': f'{uscaa_ext_url}/teams',
            'parameters': {
                'sort': 'gp',
                'r': 0,
                'pos': 'h'
            },
            'referer': f'{uscaa_ext_url}/leaders'
        }
    }

    urls = list()
    for league, league_details in setup_dict.items():
        league_has_divisions = True if '1' in league_details.keys() else False
        if league_has_divisions:
            for division, division_details in league_details.items():
                urls += get_league_stats(session, division_details['url'], division_details['parameters'], division_details['referer'])
        else:
            urls += get_league_stats(session, league_details['url'], league_details['parameters'], league_details['referer'])
    return urls

def get_league_stats(session, url, parameters, referer):
    headers = get_headers()
    headers['Referer'] = referer
    response, urls = session.get(url, params=parameters, headers=headers), list()
    content_type = response.headers['Content-Type'].lower() if 'Content-Type' in response.headers.keys() else None
    html = response.text[33:-3] if content_type == 'text/javascript; charset=utf-8' else response.text
    if html:
        soup, ncaa = BeautifulSoup(html, 'html.parser'), False
        table = soup.find('table', {'id': 'rankings_table'})
        if table:
            ncaa = True
        else:
            table = soup.find('table')
        if table:
            for anchor in table.find_all('a'):
                if ncaa:
                    team_link_split = anchor['href'].split('/')
                    team_id = team_link_split[-2].split('.')[0]
                    period_id = int(team_link_split[-1])
                    href = f'{base_urls()["ncaa"]}/team/{team_id}/stats'
                    year_stat_category_ids = {
                        'batting': 14840, # TO DO: update for 2022
                        'pitching': 14841 # TO DO: update for 2022
                    }
                    for year_stat_category, year_stat_category_id in year_stat_category_ids.items():
                        urls.append({
                            'type': year_stat_category,
                            'href': href,
                            'parameters': {
                                'id': period_id,
                                'year_stat_category_id': year_stat_category_id
                            }
                        })
                elif not anchor['href'].endswith('pos=h'):
                    href = f'{url}/{anchor["href"].split("/")[-1]}'
                    urls.append({
                        'school': anchor.text,
                        'href': href,
                        'parameters': {
                            'view': 'lineup'
                        }
                    })
    time.sleep(0.5)
    return urls[:1]

def get_team_stats(year):
    urls = get_all_team_urls(year)
    session = requests.Session()
    batting_dfs, pitching_dfs = list(), list()
    for url in urls:
        ncaa = 'type' in url.keys()
        response = session.get(url['href'], params=url['parameters'], headers=get_headers())
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        if not soup.find('table'):
            print(url)
        dfs = pd.read_html(html)
        if ncaa:
            stat_type = url['type']
            df = dfs[-1]
            df = df[~df['Player'].isin(['Totals', 'Opponent Totals'])].copy()
            if len(df.index) > 0:
                school_url_link = soup.find('a', {'target': 'ATHLETICS_URL'})
                school_url = school_url_link['href'] if school_url_link else None
                # if school_url:
                #     school_row = schools_df[schools_df['roster_link'].str.contains(school_url)]
                #     df['School'] = school_row.iloc[0, :]['title'] if len(school_row.index) else ''
                # else:
                #     df['School'] = ''
                # df['Name'] = df['Player'].apply(lambda x: format_player_name(x))
                if stat_type == 'batting':
                    batting_dfs.append(df)
                elif stat_type == 'pitching':
                    pitching_dfs.append(df)
        else:
            for stat_type in ['batting', 'pitching']:
                df, df_found = None, False
                for temp_df in dfs:
                    if len(temp_df.index) > 1:
                        if ((stat_type == 'batting') & ('slg' in temp_df.columns)) | ((stat_type == 'pitching') & ('era' in temp_df.columns)):
                            df, df_found = temp_df, True
                            break
                if df_found:
                    df = df[~df['Name'].isin(['Totals', 'Opponent', 'No players meet the minimum'])].copy()
                    if len(df.index) > 0:
                        df['Name'] = df['Name'].apply(lambda x: format_player_name(x))
                        df['School'] = url['school']
                        if stat_type == 'batting':
                            batting_dfs.append(df)
                        else:
                            pitching_dfs.append(df)
        time.sleep(0.5)
    return {
        'batting': batting_dfs,
        'pitching': pitching_dfs
    }

if __name__ == '__main__':
    year = 2022
    schools_df = pd.read_csv(f'roster_pages_{year}.csv')
    team_stats = get_team_stats(year)
    batting_stats_df = pd.merge(pd.concat(team_stats['batting'], ignore_index=True), schools_df, how='left', left_on='School', right_on='title')
    pitching_stats_df = pd.concat(team_stats['pitching'], ignore_index=True)
    display(batting_stats_df)
    display(pitching_stats_df)
    batting_stats_df.to_csv(f'batting_{year}.csv', index=False)
    pitching_stats_df.to_csv(f'pitching_{year}.csv', index=False)