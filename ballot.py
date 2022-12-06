import pandas as pd
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)

index = ['Name', 'School']
canadians_df = pd.read_csv('canadians_2022.csv').rename({'name': 'Name', 'school': 'School'}, axis=1).set_index(index)[['t', 'stats_link']]
stats_df = pd.read_csv('stats_2022.csv')
stats_df['last'] = stats_df['Name'].apply(lambda x: x.split(' ')[-1])

pitching_df = stats_df.copy()
pitching_df = pitching_df.set_index(index).sort_values(by='last')
pitching_df = pitching_df[['Position', 'Appearances (G)', 'Games Started (GS)', 'Innings Pitched (IP)', 'Wins (W)', 'Losses (L)', 'Earned Runs (ER)', 'Hits Allowed (H)', 'Walks Allowed (BB)', 'Earned Run Average (ERA)', 'Saves (SV)', 'Strikeouts (K)']]
pitching_df.rename({col: col.split('(')[-1].replace(')', '') for col in pitching_df.columns}, axis=1, inplace=True)
pitching_df = pitching_df[(pitching_df['IP'] > 10) & (pitching_df['ERA'] < 9)]
pitching_df = pd.merge(pitching_df, canadians_df, how='left', left_index=True, right_index=True)
pitching_df['Position'].fillna('', inplace=True)
pitching_df['Position'] = pitching_df.apply(lambda row: 'RHP' if (row['t'] == 'R') | ('RHP' in row['Position']) else 'LHP' if (row['t'] == 'L') | ('LHP' in row['Position']) else '', axis=True)
pitching_df = pitching_df[['Position', 'G', 'GS', 'IP', 'W', 'L', 'SV', 'H', 'BB', 'ER', 'ERA', 'K']]
right_handers_df = pitching_df[(pitching_df['Position'] == 'RHP') & (pitching_df['GS'] / pitching_df['G'] >= 0.5)].drop('Position', axis=1)
left_handers_df = pitching_df[(pitching_df['Position'] == 'LHP') & (pitching_df['GS'] / pitching_df['G'] >= 0.5)].drop('Position', axis=1)
relievers_df = pitching_df[pitching_df['GS'] / pitching_df['G'] < 0.5].drop('Position', axis=1)
unknown_pitcher_df = pitching_df[(pitching_df['Position'] == '') & (pitching_df['GS'] / pitching_df['G'] >= 0.5)].drop('Position', axis=1)

hitting_df = stats_df.set_index(index).sort_values(by='last')
hitting_df = hitting_df[['Position', 'Games Played (G)', 'At Bats (AB)', 'Runs Scored (R)', 'Hits (H)', 'Doubles (2B)', 'Triples (3B)', 'Home Runs (HR)', 'Runs Batted In (RBI)', 'Stolen Bases (SB)', 'Batting Average (AVG)', 'On-Base Percentage (OBP)', 'Slugging Percentage (SLG)', 'On-Base plus Slugging (OPS)']]
hitting_df.rename({col: col.split('(')[-1].replace(')', '') for col in hitting_df.columns}, axis=1, inplace=True)
htting_df = hitting_df[['Position', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'AVG', 'OPS', 'SB']]
hitting_df = hitting_df[hitting_df['AB'] > 20]
hitting_df['Position'].fillna('', inplace=True)
catchers_df = hitting_df[hitting_df['Position'].apply(lambda x: ('C' in x) & ('CF' not in x))].drop('Position', axis=1)
first_base_df = hitting_df[hitting_df['Position'].apply(lambda x: '1B' in x)].drop('Position', axis=1)
second_base_df = hitting_df[hitting_df['Position'].apply(lambda x: '2B' in x)].drop('Position', axis=1)
third_base_df = hitting_df[hitting_df['Position'].apply(lambda x: '3B' in x)].drop('Position', axis=1)
shortstops_df = hitting_df[hitting_df['Position'].apply(lambda x: 'SS' in x)].drop('Position', axis=1)
outfielders_df = hitting_df[hitting_df['Position'].apply(lambda x: 'OF' in x)].drop('Position', axis=1)
misc_hitter_df = hitting_df[hitting_df['Position'].apply(lambda x: ('IF' in x) | ('IN' in x) | ('U' in x) | ('DH' in x) | ('M' in x) | (x == ''))]
misc_hitter_df = pd.merge(misc_hitter_df, canadians_df[['stats_link']], how='left', left_index=True, right_index=True)

display(hitting_df['Position'].value_counts())
# display(right_handers_df)
# display(left_handers_df)
# display(relievers_df)
# display(unknown_pitcher_df)
# display(catchers_df)
# display(first_base_df)
# display(second_base_df)
# display(third_base_df)
# display(shortstops_df)
# display(outfielders_df)
display(misc_hitter_df)