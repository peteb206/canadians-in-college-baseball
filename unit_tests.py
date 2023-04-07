from model import RosterPage, School

###################################################################################################
# RosterPage
###################################################################################################

# Sidearm JSON
roster_page = RosterPage('https://hokiesports.com/sports/baseball/roster/2023')
players = roster_page.players()
assert players[0].last_name == 'Arguelles'

# Sidearm Cards (s-person-card)
roster_page = RosterPage('https://gobulldogs.com/sports/baseball/roster/2023')
players = roster_page.players()
assert players[1].last_name == 'Takayoshi'

# Sidearm Cards (sidearm-roster-player-container)
roster_page = RosterPage('https://ecupirates.com/sports/baseball/roster/2023')
players = roster_page.players()
assert players[2].last_name == 'Chrismon'

# Table
roster_page = RosterPage('https://www.fullertontitans.com/sports/m-basebl/2022-23/roster')
players = roster_page.players()
assert players[0].last_name == 'Lew'

###################################################################################################
# School
###################################################################################################

# NCAA: Division 1
school = School(id = '248', name = 'George Mason University', league = 'NCAA', division = '1', state = 'VA', roster_url = 'https://gomason.com/sports/baseball/roster/2023', stats_url = 'https://stats.ncaa.org/team/248/stats/16340')
players = school.players()
assert (players[3].id == '2658233') & (players[3].last_name == 'Dykstra')

# NCAA: Division 2
school = School(id = '1071', name = 'Emporia State University', league = 'NCAA', division = '2', state = 'KS', roster_url = 'https://esuhornets.com/sports/baseball/roster/2023', stats_url = 'https://stats.ncaa.org/team/1071/stats/16340')
players = school.players()
assert (players[18].id == '2812025') & (players[18].last_name == 'Bucovetsky')

# NCAA: Division 3
school = School(id = '59', name = 'Bethany College', league = 'NCAA', division = '3', state = 'WV', roster_url = 'https://www.bethanybison.com/sports/bsb/2022-23/roster', stats_url = 'https://stats.ncaa.org/team/59/stats/16340')
players = school.players()
assert (players[28].id == '2337388') & (players[28].last_name == "D'Angela")

# NAIA
school = School(id = 'britishcolumbiabc', name = 'British Columbia', league = 'NAIA', division = 'cascade', state = 'BC', roster_url = 'https://gothunderbirds.ca/sports/baseball/roster/2022-23', stats_url = 'https://naiastats.prestosports.com/sports/bsb/2022-23/conf/cascade/teams/britishcolumbiabc?view=lineup')
players = school.players()
assert (players[0].id == 'hiloyamamoto4wu6') & (players[0].last_name == 'Yamamoto')

# JUCO: Division 1
school = School(id = 'bossierparishcommunitycollege', name = 'Bossier Parish', league = 'JUCO', division = '1', state = 'LA', roster_url = 'https://bpcc.prestosports.com/sports/bsb/2022-23/roster', stats_url = 'https://www.njcaa.org/sports/bsb/2022-23/div1/teams/bossierparishcommunitycollege?view=lineup')
players = school.players()
assert (players[0].id == 'dreamaral1zlf') & (players[0].last_name == 'Amaral')

# JUCO: Division 2
school = School(id = 'prairiestatecollege', name = 'Prairie State', league = 'JUCO', division = '2', state = 'IL', roster_url = 'https://prairiestateathletics.com/sports/baseball/roster/2023', stats_url = 'https://www.njcaa.org/sports/bsb/2022-23/div2/teams/prairiestatecollege?view=lineup')
players = school.players()
assert (players[2].id == 'fabianromero1op0') & (players[2].last_name == 'Romero')

# JUCO: Division 3
school = School(id = 'niagaracountycommunitycollege', name = 'Niagara County', league = 'JUCO', division = '3', state = 'NY', roster_url = 'https://www.ncccathletics.com/sports/bsb/2022-23/roster', stats_url = 'https://www.njcaa.org/sports/bsb/2022-23/div3/teams/niagaracountycommunitycollege?view=lineup')
players = school.players()
assert (players[0].id == 'alexminnehanbjv1') & (players[0].last_name == 'Minnehan')

# CCCAA
school = School(id = 'antelopevalley', name = 'Antelope Valley', league = 'CCCAA', division = '', state = 'CA', roster_url = 'https://gomarauders.avc.edu/sports/bsb/2022-23/roster', stats_url = 'https://www.cccaasports.org/sports/bsb/2022-23/teams/antelopevalley?view=lineup')
players = school.players()
assert (players[0].id == 'jasonzhang7wgu') & (players[0].last_name == 'Zhang')

# NWAC
school = School(id = 'bigbend', name = 'Big Bend', league = 'NWAC', division = '', state = 'WA', roster_url = 'https://bigbend.prestosports.com/sports/bsb/2022-23/roster', stats_url = 'https://nwacsports.com/sports/bsb/2022-23/teams/bigbend?view=lineup')
players = school.players()
assert (players[1].id == 'brockrindlisbacher1s1s') & (players[1].last_name == 'Rindlisbacher')

# USCAA
school = School(id = 'dyouville', name = "D'Youville", league = 'USCAA', division = '', state = 'NY', roster_url = 'https://athletics.dyc.edu/sports/bsb/2022-23/roster', stats_url = 'https://uscaa.prestosports.com/sports/bsb/2022-23/teams/dyouville?view=lineup')
players = school.players()
assert (players[1].id == 'dilloncrookskm1') & (players[1].last_name == 'Crook')