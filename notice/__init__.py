import logging
import azure.functions as func
import datetime
from slack_bolt import App
import os
from azure.cosmosdb.table.tableservice import TableService

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
today = datetime.date.today().strftime("%Y/%m/%d")

table_service = TableService(account_name=os.environ.get("STORAGE_NAME") , account_key=os.environ.get("STORAGE_KEY"))

# notice if someone is absent today
def main(mytimer: func.TimerRequest):
    logging.info('notice_absence job started')
    filter_string = "Date eq '{}'".format(today)
    try:
        now = datetime.datetime.now()
        app.client.chat_postMessage(channel="#general", text=f"今は{now}です。")
        entries = table_service.query_entities("slackdayoffworkers", filter=filter_string)
        for entry in entries:
                if entry["Time"] == "full":
                    app.client.chat_postMessage(channel="#general", text=f"{entry['WorkerName']}さんは今日お休みです。")
                else:
                    app.client.chat_postMessage(channel="#general", text=f"{entry['WorkerName']}さんは今日{entry['Time']}の間お休みです。")

        logging.info('notice_absence job finished')
    except Exception as e:
        logging.error('Failed to execute notice_absence', exc_info=True)
