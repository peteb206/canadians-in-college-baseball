import requests
from bs4 import BeautifulSoup
import pandas as pd
import re


def get_canadian_players(year):
    assert type(year) == int

    page = requests.get('https://www.canadianbaseballnetwork.com/canadians-in-college/{}-canadians-in-college'.format(str(year)))
    soup = BeautifulSoup(page.text, 'html.parser')

    player_dict_list = list()
    for p in soup.find_all("p"):
        text = p.getText().strip()
        if re.match(r".*\(.{2}\)$", text):
            temp_list = text.split(')')
            for player in temp_list:
                if len(player) > 0:
                    player_re = re.compile(re.escape(', Jr.'), re.IGNORECASE)
                    player = player_re.sub(' Jr.', player) # Ensure ", Jr." is roped in with name
                    player_dict = dict()
                    temp_list2 = player.split(',')
                    temp_list3 = temp_list2[0].split(' ')
                    player_dict['position'] = temp_list3[0] if len(temp_list3) > 2 else ''
                    player_dict['name'] = temp_list2[0].replace(temp_list3[0], '', 1).strip()
                    temp_list4 = temp_list2[-1].split('(')
                    player_dict['school'] = temp_list4[0]
                    player_dict['state'] = temp_list4[1]
                    player_dict['hometown'] = ''
                    iter = 0
                    for item in temp_list2:
                        if (iter != 0) & (iter != len(temp_list2) - 1):
                            player_dict['hometown'] += item
                        iter += 1
                    player_dict_list.append(player_dict)
    return pd.DataFrame(player_dict_list)


def compare(df_cbn, df_scrape_list, out_excel):
    # Ex. cbn.compare(cbn.get_canadian_players(2021), pd.read_html('canadians.html'), 'diff.xlsx')
    df_scrape = pd.concat(df_scrape_list, ignore_index=True)
    df_cbn['name'] = df_cbn['name'].str.lower()
    df_scrape['name'] = df_scrape['name'].str.lower()
    df_combined = pd.merge(df_scrape, df_cbn, how='outer', on='name', suffixes=('_pete', '_cbn')).sort_values(by='name')
    df_diff = df_combined[(df_combined['school_pete'].isna()) | (df_combined['school_cbn'].isna())][['name','school_cbn','school_pete']]
    df_diff.sort_values(by=['school_cbn','school_pete','name'], inplace=True)
    df_diff.to_excel(out_excel, index=False)
    print('Exported {} rows to {}'.format(str(len(df_diff.index)), out_excel))
    return df_diff


def main():
    in_html_file = input('Input HTML file: ')
    out_file = input('Output Excel file: ')
    return compare(pd.read_html(in_html_file)[0], get_canadian_players(2021), out_file)


# Run main function
if __name__ == "__main__":
    main()