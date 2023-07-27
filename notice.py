import logging
import os
from azure.cosmosdb.table.tableservice import TableService

import dotenv
dotenv.load_dotenv()

table_service = TableService(account_name=os.environ.get("STORAGE_NAME") , account_key=os.environ.get("STORAGE_KEY"))

# notice if someone is absent today
def notice_absence(api,today):
    logging.info('notice_absence job started')
    filter_string = "Date eq '{}'".format(today)
    try:
        entries = table_service.query_entities("slackdayoffworkers", filter=filter_string)
        for entry in entries:
                if entry["Time"] == "full":
                    api.client.chat_postMessage(
                        channel="#notice_勤務連絡", 
                        text=f"{entry['WorkerName']}さんは今日お休みです。"
                    )
                else:
                    api.client.chat_postMessage(
                        channel="#notice_勤務連絡", 
                        text=f"{entry['WorkerName']}さんは今日{entry['Time']}の間お休みです。"
                    )
                try:
                    table_service.delete_entity(
                            table_name='slackdayoffworkers',
                            partition_key='dayoff',
                            row_key=entry['RowKey']
                            )
                except:
                    logging.error('Failed to delete entity', exc_info=True)

        logging.info('notice_absence job finished')
    except Exception as e:
        logging.error('Failed to execute notice_absence', exc_info=True)
