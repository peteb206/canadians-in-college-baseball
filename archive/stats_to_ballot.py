import pandas as pd
import numpy as np

pd.set_option('display.max_rows', 500)
stats_df = pd.read_csv('stats.csv')

# Split multi-position players into multiple rows
stats_df['Position'] = stats_df['Position'].str.replace(',', '/', regex=False)
stats_df['Positions'] = stats_df['Position'].str.split('/')
positions = stats_df['Positions'].apply(pd.Series).reset_index().melt(id_vars='index').dropna()[['index', 'value']].set_index('index')
stats_df = pd.merge(stats_df, positions, how = 'left', left_index = True, right_index = True).drop(['Position', 'Positions'], axis=1).rename({'value': 'Position'}, axis=1)
stats_df

# Separate relief pitchers
stats_df['Position'] = np.where((stats_df['Position'].isin(['RHP', 'LHP', 'P'])) & (stats_df['Appearances (G)'] > stats_df['Games Started (GS)'] * 2), 'RP', stats_df['Position'])

# Rename positions
position_label_to_value = {
    'Right-handers': ['RHP'],
    'Left-handers': ['LHP'],
    'Relievers': ['RP'],
    'Catchers': ['C'],
    'First basemen': ['1B', 'IB'],
    'Second basemen': ['2B'],
    'Third basemen': ['3B'],
    'Shortstops': ['SS'],
    'Third basemen': ['3B'],
    'Outfielders': ['OF', 'CF'],
    'Designated hitters': ['DH'],
    'Misc. Pitchers': ['P'],
    'Misc. Infielders': ['IF', 'INF', 'IN', 'CIF', 'MIF'],
    'Utility players': ['UT', 'UTL', 'UTIL']
}

position_value_to_label = dict()
for label, values in position_label_to_value.items():
    for value in values:
        position_value_to_label[value] = label

stats_df['Position'] = stats_df['Position'].apply(lambda x: position_value_to_label[x] if x in position_value_to_label.keys() else '')

base_stats = ['Name', 'School']
hitter_stats = ['Games Played (G)', 'At Bats (AB)', 'Runs Scored (R)', 'Hits (H)', 'Doubles (2B)', 'Triples (3B)', 'Home Runs (HR)', 'Runs Batted In (RBI)', 'Batting Average (AVG)', 'On-Base plus Slugging (OPS)', 'Stolen Bases (SB)']
pitcher_stats = ['Appearances (G)', 'Games Started (GS)', 'Innings Pitched (IP)', 'Wins (W)', 'Losses (L)', 'Saves (SV)', 'Hits Allowed (H)', 'Walks Allowed (BB)', 'Earned Runs (ER)', 'Earned Run Average (ERA)', 'Strikeouts (K)']

for position in position_label_to_value.keys():
    print(f'\n{position}:')

    stats = hitter_stats
    mask = ((stats_df['Position'] == position) & (stats_df['Games Played (G)'] > 0))

    if position in ['Right-handers', 'Left-handers', 'Relievers', 'Misc. Pitchers']: # Pitchers
        stats = pitcher_stats
        mask = ((stats_df['Position'] == position) & (stats_df['Appearances (G)'] > 0))

    df = stats_df[mask][base_stats + stats]

    columns = list()
    for col in df.columns:
        if ('(' in col) & (')' in col):
            col = col.split('(')[1].split(')')[0]
        columns.append(col)
    df.columns = columns

    df['last'] = df['Name'].apply(lambda x: x.split(' ')[1])
    df = df.sort_values(by='last', ignore_index=True)
    df.drop('last', axis=1, inplace=True)
    display(df)