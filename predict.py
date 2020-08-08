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

    def _set_back_to_back(self, df):       
        today = (datetime.datetime.now()-datetime.timedelta(days = 1)).strftime('%Y%m%d')
        content = requests.get(f'https://www.espn.com/nba/schedule/_/date/{today}').content
        soup = BeautifulSoup(content,'html.parser')
        html = soup.find_all(name='table', attrs={'class':'schedule'})
        game_result = pd.read_html(str(html))[0]
        teams_played_today = []
        for two_team in game_result['result'].tolist():
            teams_played_today.append(two_team.split(' ')[0])
            teams_played_today.append(two_team.split(' ')[2])
        df['b2b'] = df['team'].apply(lambda x : True if x in teams_played_today else False)
        non_b2b_teams = df[df['b2b'] == False]
        return non_b2b_teams

    def _append_cost(self, df, players_status):
        cost_dict = {}
        for idx in range(len(players_status)):
            cost_dict[players_status[idx]['firstName']+' '+players_status[idx]['lastName']] = int(players_status[idx]['rating'])
        df['cost'] = df['Player'].apply(lambda player_name:self._is_same_player(cost_dict, player_name))
        df = df[df['cost'].notnull()]
        return df

    def _get_healthy_players(self, df):
        content = requests.get('https://www.cbssports.com/nba/injuries/').content
        soup = BeautifulSoup(content,'html.parser')
        table = soup.find(name= 'div' ,attrs= {'class':'Page-colMain'})
        injury_players = pd.read_html(str(table))
        players_full_name = soup.find_all(name='span',attrs={'class':'CellPlayerName--long'})
        injury_players = []
        for html in players_full_name:
            injury_players.append(html.find('a').text)
        df['injury'] = df['Player'].apply(lambda x: self._is_injury(x, injury_players))
        df = df[df['injury'] == False]
        return df
    
    def _is_injury(self, player, injury_players):
        for injury_player in injury_players:
            if fuzz.ratio(player, injury_player) >= 80:
                return True
        return False
    
    def _set_away_home(self, df):
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
        home = self._arena_filter(df, team_home, 'home')
        away = self._arena_filter(df, team_away, 'away')
        df = pd.concat([home,away])
        return df

    def _arena_filter(self, df, team_arena, home_away):
        arena_filter_df = pd.DataFrame()
        for team in team_arena:
            for_concat = df[(df['team'] == team)&(df['arena'] == home_away)]
            arena_filter_df = pd.concat([arena_filter_df,for_concat])
        return arena_filter_df

    def _avg_filter(self, df):
        df = df[df['AVG']>(df['AVG'].mean())*1.25]
        df = df[df['cost']>=75]
        df.reset_index(inplace=True)
        return df

    def _position_classfy(self, df):
        guards = df[(df['position'] == 'G') | (df['position'] == 'F-G')]
        forwards = df[(df['position'] == 'F') | (df['position'] == 'F-G')| (df['position'] == 'C-F')]
        centers = df[(df['position'] == 'C') | (df['position'] == 'C-F')]
        return guards, forwards, centers

    def _get_suggestion(self, df, guards, forwards, centers):
        team = []
        for player1 in range(len(guards)-1):
            for player2 in range(player1+1,len(guards)):
                for player3 in range(len(forwards)-1):
                    for player4 in range(player3+1,len(forwards)):
                        for player5 in range(len(centers)):
                            if (guards['cost'].values[player1]+guards['cost'].values[player2]\
                                +forwards['cost'].values[player3]+forwards['cost'].values[player4]\
                                +centers['cost'].values[player5]<=430)\
                                and(guards['cost'].values[player1]+guards['cost'].values[player2]\
                                    +forwards['cost'].values[player3]+forwards['cost'].values[player4]\
                                    +centers['cost'].values[player5]>=420):
                                team.append([guards['Player'].values[player1],
                                            guards['Player'].values[player2],
                                            forwards['Player'].values[player3],
                                            forwards['Player'].values[player4],
                                            centers['Player'].values[player5]])
        players_score={}
        for idx in range(len(team)):
            score = guards[guards['Player'] == team[idx][0]]['AVG'].values[0]\
                +guards[guards['Player'] == team[idx][1]]['AVG'].values[0]\
                +forwards[forwards['Player'] == team[idx][2]]['AVG'].values[0]\
                +forwards[forwards['Player'] == team[idx][3]]['AVG'].values[0]\
                +centers[centers['Player'] == team[idx][4]]['AVG'].values[0]  
            players_score[(team[idx][0], team[idx][1], team[idx][2], team[idx][3], team[idx][4])] = score
        return players_score

    def _get_top3_players(self, players_score):
        rank_players_score = sorted(players_score.items(), key=lambda d: d[1], reverse=True)
        prediction = []
        repeat_team_check = []
        for players in rank_players_score:
            players_set = set(players[0])
            if players_set not in repeat_team_check:
                prediction.append(players[0])
                repeat_team_check.append(players_set)
                if len(prediction) == 3:
                    break
        return prediction

    def _get_prediction_with_team(self, prediction, df):
        df = df.loc[:,['Player', 'team']]
        prediction_with_team = pd.DataFrame()
        n = 1
        for players in prediction:
            prediction_with_team = pd.concat([prediction_with_team, pd.DataFrame({'Player': n, 'team':'Team'}, index=[0])])
            n += 1
            for player in players:
                for_concat = df[df['Player'] == player]
                prediction_with_team = pd.concat([prediction_with_team,for_concat])
        prediction_with_team = prediction_with_team.set_index('team')
        return prediction_with_team

    def sent_ifttt(self, data):
        data = str(data)
        url = (f'https://maker.ifttt.com/trigger/{self.line_group}/with/key/{self.ifttt_key}?value1={data}')
        result = requests.get(url) 
        return result

    def predict(self):
        players_status = self._get_player_status()
        player_table = self._concat_daily_stat()
        player_table_with_position_team = self._append_position_team(player_table, players_status)
        team_tmr = self._team_play_tomorrow(player_table_with_position_team)
        non_b2b_team = self._set_back_to_back(team_tmr)
        team_with_cost = self._append_cost(non_b2b_team, players_status)
        players_without_injury = self._get_healthy_players(team_with_cost)
        team__with_arena = self._set_away_home(players_without_injury)
        team_with_avg_filter = self._avg_filter(team__with_arena)
        guards, forwards, centers = self._position_classfy(team_with_avg_filter)
        players_score = self._get_suggestion(team_with_avg_filter, guards, forwards, centers)
        prediction = self._get_top3_players(players_score)
        prediction_with_team = self._get_prediction_with_team(prediction, team_with_avg_filter)
        result = self.sent_ifttt(prediction_with_team)
        return str(result)

if __name__ == '__main__':
    predictor = NBAPredict('aa469413927@yahoo.com.tw','a358302916', 'nba_fantasy', 'btssJUCF_1qKOVluaYsMC1')
    print(predictor.predict())