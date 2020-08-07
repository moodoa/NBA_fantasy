import re
import ast
import time
import datetime
import requests
import pandas as pd

from fuzzywuzzy import fuzz
from bs4 import BeautifulSoup
from selenium import webdriver

class NBAPredict:
    def __init__(self, account, password, line_group, ifttt_key):
        option = webdriver.ChromeOptions()
        option.add_argument("headless")
        driver = webdriver.Chrome(chrome_options=option,executable_path='./chromedriver.exe')
        self.webdriver = driver
        self.account = account
        self.password = password
        self.line_group = line_group
        self.ifttt_key = ifttt_key

    def _get_player_status(self):
        driver = self.webdriver
        driver.get("http://www.facebook.com/dialog/oauth?client_id=1945821345437674&redirect_uri=https%3A%2F%2Fnba.udn.com%2Ffantasy%2Ffb_check.jsp&auth_type=rerequest&state=&scope=email") 
        time.sleep(2)
        email_input = driver.find_element_by_name('email')
        email_input.send_keys(self.account)
        pass_input = driver.find_element_by_name('pass')
        pass_input.send_keys(self.password)
        start_login = driver.find_element_by_name('login')
        time.sleep(2)
        start_login.click()
        time.sleep(5)
        start_web = driver.find_element_by_class_name('btn-play')
        start_web.click()
        time.sleep(3)
        htmltext = driver.page_source
        time.sleep(3)
        driver.close()
        htmltext = htmltext.split('_NBA_STATE=')[1]
        htmltext = htmltext.split(';\nvar historyObject')[0]
        players_status = ast.literal_eval(htmltext)
        return players_status

    def _get_players_statistics_by_day(self, mon, day, year):
        year, mon, day = str(year), str(mon), str(day)
        content = requests.get(f'https://www.basketball-reference.com/friv/dailyleaders.fcgi?month={mon}&day={day}&year={year}').content
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find(name = 'table', attrs = {'id':'stats'})
        try:
            players_statistics = pd.read_html(str(table))[0]
            players_statistics_daily = self._set_arena_score_column(players_statistics)
        except:
            players_statistics_daily = pd.DataFrame()
        return players_statistics_daily

    def _set_arena_score_column(self, players_statistics):
        players_statistics = players_statistics[players_statistics['Player'] != 'Player']
        players_statistics['arena'] = players_statistics['Unnamed: 3'].apply(lambda x : 'home' if x != '@' else 'away')
        players_statistics = players_statistics.loc[:,['Player','PTS','TRB','AST','STL','BLK','TOV','arena']]
        columns = players_statistics.columns
        for column in columns:
            if column == 'Player' or column == 'arena':
                pass
            else:
                players_statistics[column] = players_statistics[column].astype(int)
        players_statistics['score'] = players_statistics['PTS']*1 + players_statistics['TRB']*1.2 + players_statistics['AST']*1.5 + players_statistics['STL']*3 + players_statistics['BLK']*3 - players_statistics['TOV']*1
        players_statistics = players_statistics.sort_values('score',ascending = False)
        return players_statistics
        
    def _concat_daily_stat(self):
        today = datetime.datetime.now()
        players_table = pd.DataFrame()
        for days_ago in range(1,8):
            date_ago = today - datetime.timedelta(days = days_ago)
            mon, day, year = date_ago.month, date_ago.day, date_ago.year
            try:
                for_concat = self._get_players_statistics_by_day(mon, day, year)
                players_table = pd.concat([players_table,for_concat])
            except:
                pass
        home_table = self._set_arena_averge_score(players_table, 'home')
        away_table = self._set_arena_averge_score(players_table, 'away')
        table_with_average_score = pd.concat([home_table,away_table])
        table_with_average_score = table_with_average_score.drop_duplicates()
        return table_with_average_score
    
    def _set_arena_averge_score(self, players_table, team):
        players_table = players_table[players_table['arena'] == team]
        players_table['AVG'] = players_table['Player'].apply(lambda x : players_table[players_table['Player'] == x]['score'].mean())
        players_table = players_table.loc[:,['Player','AVG','arena']]
        return players_table

    def _append_position_team(self, players_table, players_status):
        position_dict, team_dict = self._get_position_team_status(players_status)
        players_table['position'] = players_table['Player'].apply(lambda player_name:self._is_same_player(position_dict, player_name))
        players_table['team'] = players_table['Player'].apply(lambda player_name:self._is_same_player(team_dict, player_name))
        return players_table

    def _get_position_team_status(self, players_status):
        position_trans={str(['F', 'G']):'F-G',str(['G', 'F']):'F-G',str(['F', 'C']):'C-F',str(['C', 'F']):'C-F'
      ,str(['G']):'G',str(['F']):'F',str(['C']):'C',str(['F', 'F']):'F',str(['G', 'G']):'G'
       ,str(['C', 'C']):'C'}
        position_dict = {}
        team_dict = {}
        for idx in range(len(players_status)):
            position_dict[players_status[idx]['firstName']+' '+players_status[idx]['lastName']] = position_trans[str(players_status[idx]['position'])]
            team_dict[players_status[idx]['firstName']+' '+players_status[idx]['lastName']] = players_status[idx]['team']  
        return position_dict, team_dict

    def _is_same_player(self, dic, player_name):
        for key in dic.keys():
            if fuzz.ratio(key,player_name) >= 80:
                return dic[key]
        return ''

    def _team_play_tomorrow(self, players_table):
        players_table = players_table[players_table['team'] != '']
        return players_table

    def _set_back_to_back(self, team_tmr):       
        today = (datetime.datetime.now()-datetime.timedelta(days = 1)).strftime('%Y%m%d')
        content = requests.get(f'https://www.espn.com/nba/schedule/_/date/{today}').content
        soup = BeautifulSoup(content,'html.parser')
        html = soup.find_all(name='table', attrs={'class':'schedule'})
        game_result = pd.read_html(str(html))[0]
        teams_played_today = []
        for two_team in game_result['result'].tolist():
            teams_played_today.append(two_team.split(' ')[0])
            teams_played_today.append(two_team.split(' ')[2])
        team_tmr['b2b'] = team_tmr['team'].apply(lambda x : True if x in teams_played_today else False)
        no_b2b_teams = team_tmr[team_tmr['b2b'] == False]
        return no_b2b_teams

    def _append_cost(self, team_tmr, players_status):
        cost_dict = {}
        for idx in range(len(players_status)):
            cost_dict[players_status[idx]['firstName']+' '+players_status[idx]['lastName']] = int(players_status[idx]['rating'])
        team_tmr['cost'] = team_tmr['Player'].apply(lambda player_name:self._is_same_player(cost_dict, player_name))
        team_tmr = team_tmr[team_tmr['cost'].notnull()]
        return team_tmr

    def _set_injury_players(self, team_tmr):
        content = requests.get('https://www.cbssports.com/nba/injuries/').content
        soup = BeautifulSoup(content,'html.parser')
        table = soup.find(name= 'div' ,attrs= {'class':'Page-colMain'})
        injury_players = pd.read_html(str(table))
        players_full_name = soup.find_all(name='span',attrs={'class':'CellPlayerName--long'})
        injury_players = []
        for html in players_full_name:
            injury_players.append(html.find('a').text)
        team_tmr['injury'] = team_tmr['Player'].apply(lambda x: self._is_injury(x, injury_players))
        return team_tmr
    
    def _is_injury(self, player, injury_players):
        for injury_player in injury_players:
            if fuzz.ratio(player, injury_player) >= 80:
                return True
        return False
    
    def _set_away_home(self, team_tmr):
        today = datetime.datetime.now()
        m, d, y = today.strftime('%m'), today.strftime('%d'), today.strftime('%Y')
        content = requests.get(f'https://stats.nba.com/scores/{m}/{d}/{y}').content
        soup = BeautifulSoup(content,'html.parser')
        web_string = str(soup)
        away_home_teams = re.findall(r'\d+\\/(\D{6})',web_string)
        team_home = []
        team_away = []
        for team in away_home_teams:
            team_away.append(team[0:3])
            team_home.append(team[3::])
        home = self._arena_filter(team_tmr, team_home, 'home')
        away = self._arena_filter(team_tmr, team_away, 'away')
        team_tmr = pd.concat([home,away])
        return team_tmr

    def _arena_filter(self, team_tmr, team_arena, home_away):
        df = pd.DataFrame()
        for team in team_arena:
            for_concat = team_tmr[(team_tmr['team'] == team)&(team_tmr['arena'] == home_away)]
            df = pd.concat([df,for_concat])
        return df

    def predict(self):
        players_status = self._get_player_status()
        player_table = self._concat_daily_stat()
        player_table_with_position_team = self._append_position_team(player_table, players_status)
        team_tmr = self._team_play_tomorrow(player_table_with_position_team)
        team_tmr = self._set_back_to_back(team_tmr)
        team_tmr = self._append_cost(team_tmr, players_status)
        team_tmr = self._set_injury_players(team_tmr)
        team_tmr = self._set_away_home(team_tmr)
        return team_tmr

if __name__ == '__main__':
    predictor = NBAPredict('acc','pass', 'a', 'b')
    print(predictor.predict())



# # make a filter and weight the AVG 

# tmr_set = tmr_set[tmr_set['AVG']>(tmr_set['AVG'].mean())*1.25]
# tmr_set = tmr_set[tmr_set['cost']>=75]

# tmr_set.reset_index(inplace=True)
# # classfy players by position

# guards = tmr_set[(tmr_set['position'] == 'G') | (tmr_set['position'] == 'F-G')]
# forwards = tmr_set[(tmr_set['position'] == 'F') | (tmr_set['position'] == 'F-G')| (tmr_set['position'] == 'C-F')]
# centers = tmr_set[(tmr_set['position'] == 'C') | (tmr_set['position'] == 'C-F')]



# # suggestion
# team = []

# for player1 in range(len(guards)-1):
#     for player2 in range(player1+1,len(guards)):
#         for player3 in range(len(forwards)-1):
#             for player4 in range(player3+1,len(forwards)):
#                 for player5 in range(len(centers)):
#                     if (guards['cost'].values[player1]+guards['cost'].values[player2]\
#                         +forwards['cost'].values[player3]+forwards['cost'].values[player4]\
#                         +centers['cost'].values[player5]<=430)\
#                         and(guards['cost'].values[player1]+guards['cost'].values[player2]\
#                             +forwards['cost'].values[player3]+forwards['cost'].values[player4]\
#                             +centers['cost'].values[player5]>=420):
#                         team.append([guards['Player'].values[player1],
#                                     guards['Player'].values[player2],
#                                     forwards['Player'].values[player3],
#                                     forwards['Player'].values[player4],
#                                     centers['Player'].values[player5]])


# allteam = len(team)
# score_dict={}

# for i in range(allteam):
#     score = guards[tmr_set['Player'] == team[i][0]]['AVG'].values[0]\
#         +guards[tmr_set['Player'] == team[i][1]]['AVG'].values[0]\
#         +forwards[tmr_set['Player'] == team[i][2]]['AVG'].values[0]\
#         +forwards[tmr_set['Player'] == team[i][3]]['AVG'].values[0]\
#         +centers[tmr_set['Player'] == team[i][4]]['AVG'].values[0]  
#     score_dict[i] = score


# # get the predict score and index
# rank = sorted(score_dict.items(), key=lambda d: d[1],reverse=True)
# teamcheck = []
# team_number = 0
# medal = 0
# predict = pd.DataFrame()
# for i in range(len(rank)):
#     player_dict={'team':str(medal+1)}
#     teamlist=[]
#     for player in team[rank[i][0]]:
#         if player in teamlist:
#             break
#         else:
#             teamlist.append(player)
#     sort_team = sorted(teamlist)
#     if len(teamlist) == 5 and sort_team not in teamcheck:
#         teamcheck.append(sort_team)
#         medal+=1
#         for j in range(len(teamlist)):
#             player_dict[teamlist[j]]=tmr_set[tmr_set['Player']==teamlist[j]]['Team'].values[0]
#         for_concat = pd.DataFrame(list(player_dict.items()))
#         predict = pd.concat([predict,for_concat])
        
#     if medal == 3 :
#         break
# predict.columns=['Player','Team']

# predict = predict.set_index('Team')


# # send the result to line
# def send_ifttt(data):   
# #     send the report to line
#     url = (f'https://maker.ifttt.com/trigger/{self.line_group}/with/key/{self.ifttt_key}' +
#           '?value1='+str(data))
# #     action!!
#     r = requests.get(url) 
# result = send_ifttt(predict)
