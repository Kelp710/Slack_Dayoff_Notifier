import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import openai
import time
import json
import os
import uuid
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
import notice
import flask
from azure.cosmosdb.table.tableservice import TableService

import dotenv
dotenv.load_dotenv()

api = App(token=os.environ.get("SLACK_BOT_TOKEN"))

openai.api_type = "azure"
openai.api_base = os.environ.get("OPENAI_API_BASE")
openai.api_version = "2023-03-15-preview"
openai.api_key = os.environ.get("OPENAI_API_KEY")

table_service = TableService(
    account_name=os.environ.get("STORAGE_NAME"), 
    account_key=os.environ.get("STORAGE_KEY")
    )

app = flask.Flask(__name__)

today = time.strftime("%Y/%m/%d")
weekday = datetime.today().weekday()

@api.event("message")
def get_user_name(user_id):
    user_name = api.client.users_info(user=user_id)
    return user_name["user"]["real_name"]

# works when the bot mentioned
# メンションされたら動作
@api.event("app_mention")
def chatgpt_reply(event, say):
    input_message = event["text"]
    thread_ts = event.get("thread_ts") or None
    channel = event["channel"]
    # メッセージからIDを削除
    input_message = input_message.replace("<@A05JN779K36>", "")
    user_name = get_user_name(event["user"])
    # check if the message is a request for a day off or a declaration of a day off, if so return json format, or False
    # メッセージが休みを報告しているかどうかをGPTで判断
    # 午前休、午後休は何時なのかをはっきりさせる。
    # 16~fullになるので変更する。
    response_to_day_off = openai.ChatCompletion.create(
        engine="gpt-35-turbo",
        temperature=0.0,
        messages=[
            {'role': 'system', 'content':'You must only respond with JSON formats with day-off information or the string "False" only but anything else。 Your role is to distinguish if users declare/request/tell taking day-offs in the message only day off that a company would recognize。 For example、with messages such as「時間休を8月22日の14時から18時にください」、「明日と明後日休みます」、「6月23日から25日まで休暇申請しています」you need to extract information from the message、the information you need to collect is: who takes day offs("WorkerName": string)、the days ("Date": string) and time("Time": string) if there is no information about each topic you should not make a json for the date/user. You need to make json format for each day and make a list containing the jsons. The current day will be provided with a message、if the current day is behind the requested day of day offs that means they request day-offs for next year 、you can not use the days already past the current day if they ask the day off at specific time put that information and if they not put full instead. For instance、with messages like「全休を金曜日に、時間休を6月22日に11時から14時で、6月25日に12時から16時にいただきます。本日の日付は2023/06/21でWednesdayです、nameは桝口です」、you need to response with a list of JSON formats:[{"WorkerName": "枡口", "Date": "2024/06/23", "Time": "full"},{"WorkerName": "枡口", "Date": "2023/06/22", "Time": "11:00~14:00"},{"WorkerName": "枡口", "Date": "2023/06/25", "Time": "12:00~16:00"}], When user specified a day with weekday you need to figure it out step by step, For example, If today is Wednesday 5/10, Friday will be in two days therefore 5/12 is correct, When you response you can only response with mere JSON format data。 On the other hand、messages such as「明日はご飯をみんなで食べに行こう」、「疲れたー,休みたい」、「生きてますか？」、「6月23日から25日まで忙しいです」do not contain any declaration or request for day offs、No explanation or additional context must be provided. Only reply with "False"' },
            {'role': 'user', 'content': input_message+f'本日の日付は{today}で{weekday}です。nameは{user_name}です'},
            ]
    )
    day_off_content = response_to_day_off["choices"][0]["message"]["content"]
    try:
        day_off_content = json.loads(day_off_content)
    except json.JSONDecodeError:
        day_off_content = "False"
    if thread_ts is not None:
        parent_thread_ts = event["thread_ts"]
        say(
            text="thread_ts is not None",
            thread_ts=parent_thread_ts,
            channel=channel
            )
    # determine the therad to reply
    response = api.client.conversations_replies(channel=channel, ts=event["ts"])
    thread_ts = response["messages"][0]["ts"]
    
    # When the message is a request for a day off store 
    # メッセージが休みを報告していた場合、json形式で記入
    if type(day_off_content) == list:
        for one_day in day_off_content:
            one_day["PartitionKey"] = "dayoff"
            one_day["RowKey"] = str(datetime.utcnow()) + str(uuid.uuid4())
            try:
                table_service.insert_or_replace_entity('slackdayoffworkers', one_day)
            except:
                say(text="休みを申請できませんでした。")
                return
        say(text="お疲れ様です、ゆっくり休んでくださいね！", 
            thread_ts=thread_ts, 
            channel=channel) 
            
    # メッセージが休みを報告していなかった場合、雑談対話
    else:
        original_response = openai.ChatCompletion.create(
            engine="gpt-35-turbo",
            temperature=1.0,
            messages=[
                {"role": "system", "content": "You're called Baleen bot your job is assisting the user with polite attitude"+ f"user name is {user_name} and use thier name like you are talking to them."},
                {"role": "user", "content": input_message},
                ]
    )
        text = original_response["choices"][0]["message"]["content"]
        say(
            text=text, 
            thread_ts=thread_ts, 
            channel=channel
            ) 
        
@app.route('/')
def main(): 
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: notice.notice_absence(api, today),
        'cron',
        hour=18, 
        minute=30,
        day_of_week='mon-fri', 
        timezone=timezone('Asia/Tokyo')
                      )
    scheduler.start()
    handler = SocketModeHandler(api, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
    return "Bolt is running, such a hard working bot!"

if __name__ == '__main__':
    app.run()