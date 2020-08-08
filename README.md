# NBA_fantasy
a predictor for nba fantasy game

![alt text](https://miro.medium.com/max/540/1*TshXyGsehhGvZXQ9cGNzNQ.jpeg)

# NBAPredict
#### __init__
* 初始傳值分別為 `FB 帳號`、`FB 密碼`、`接收通知的 LINE 群組`、`ifttt 金鑰`。
#### _get_player_status
* 以 selenium 進入 FANTASY GAME 首頁，並且獲得明日比賽資訊(球員名稱、隊伍、球員Cost ,etc.)。
#### _concat_daily_stat
* 至 basketball-reference 爬取今日之前 `7` 天的比賽數據。
* 將球員分出`主客場`，並分別算出該球員在主客場的`平均 Fantasy points`。
#### _append_position_team
* 將 Dataframe 加上球員所屬`球隊`，以及該球員的`位置`。
#### _team_play_tomorrow
* 從 Dataframe 中篩選出`明日有比賽`的球隊。
#### _set_back_to_back
* 從 Dataframe 中篩選出`非 b2b`的球隊。
#### _get_healthy_players
* 從 `https://www.cbssports.com/nba/injuries/` 取得球員傷病資訊，並且篩選出`健康的球員`。
#### _set_away_home
* 依照明天比賽隊伍的主客場決定球員使用哪一個`Fantasy points`。
#### _avg_filter
* 將`Fantasy points`以及`cost`太低的球員剃除。
* 篩選標準為：`Fantasy points > 平均值的 1.25 倍`、`cost >= 75`。
#### _position_classfy
* 將 Dataframe 的球員依照各自的位置分開，回傳值為`guards`,`forwards`,`centers`。
#### _get_suggestion
* 遍歷球員的各種組合，並加上`Fantasy points`總分。
* 篩選規則為：`後衛*2` + `前鋒*2` + `中鋒*1`。
#### _get_top3_players
* 從`_get_suggestion`取前三高分的組合。
#### _get_prediction_with_team
* 將`_get_top3_players`取出的球員組合加上各自的所屬隊伍，並回傳最後結果。
#### sent_ifttt
* 將最後推薦結果透過`ifttt`傳至`LINE群組`。

## Requirements
python 3

## Usage

```
if __name__ == '__main__':
    predictor = NBAPredict('fb_account','fb_password', 'LINE_group', 'ifttt_key')
    predictor.predict()

```

## Installation
`pip install -r requriements.txt`
