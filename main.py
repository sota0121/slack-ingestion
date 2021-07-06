import datetime
import io
import json
import logging
import os
import pytz
import shutil
import sys
import tempfile
from flask import Request
from pathlib import Path
from slack_bolt import App
from slack_sdk import errors
from typing import List


logfilename = 'ingest_log_at_{}.log'.format(datetime.datetime.now().isoformat())
logging.basicConfig(
    filename=logfilename,
    format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %I:%M:%S %p',
    level=logging.INFO)
SCRIPT_DIR = str(Path(__file__).resolve().parent)


def download_conversations_list(client, page_limit: int) -> List[dict]:
    """download Slack Web API conversations.list response.
        Returns:
            [{"id":xx, "name":yy}, {}, ...]
    """
    channels = []
    next_obj_exists = True
    next_cursor = None
    while next_obj_exists is True:
        slack_response = client.conversations_list(
                            cursor = next_cursor,
                            limit = page_limit,
                            types = 'public_channel,private_channel')

        channels.extend(slack_response.get('channels'))
        next_cursor = slack_response.get('response_metadata').get('next_cursor')
        if next_cursor == "":
            next_obj_exists = False

    return channels


def download_users_list(client, page_limit: int) -> List[dict]:
    """download Slack Web API users.list response.
        Returns:
            [{"id":xx, "name":yy}, {}, ...]
    """
    users = []
    next_obj_exists = True
    next_cursor = None
    while next_obj_exists is True:
        slack_response = client.users_list(
                            cursor = next_cursor,
                            limit = page_limit)

        users.extend(slack_response.get('members'))
        next_cursor = slack_response.get('response_metadata').get('next_cursor')
        if next_cursor == "":
            next_obj_exists = False

    return users


def download_conversations_history(
    client, channel: str, page_limit: int,
    latest_unix_time: float, oldest_unix_time: float) -> List[dict]:
    """download Slack Web API conversations.list response.
        Returns:
            List of dict{"channel":ccc, "message":{ ... }}
    """
    conversations_by_channel = []
    next_obj_exists = True
    next_cursor = None
    while next_obj_exists is True:
        try:
            slack_response = client.conversations_history(
                                channel = channel,
                                cursor = next_cursor,
                                limit = page_limit,
                                latest = latest_unix_time,
                                oldest = oldest_unix_time)
            cnv_by_ch = slack_response.get('messages')
            for item in cnv_by_ch:
                item.update( {"channel": channel})
            conversations_by_channel.extend(cnv_by_ch)
            if slack_response.get('has_more') is False:
                next_cursor = ""
            else:
                next_cursor = slack_response.get('response_metadata').get('next_cursor')
        except errors.SlackApiError as e:
            logging.info(e)
            break
        if next_cursor == "":
            next_obj_exists = False

    return conversations_by_channel


def target_channel_id_name_list(
    conversations_list: list=None, including_archived: bool=False):
    """extract targeted channels id list from conversations_list response.
        Returns:
            id_list, name_list
    """
    id_list = []
    name_list = []
    for ch in conversations_list:
        if including_archived is False:
            if ch['is_archived'] is True:
                continue
        id_list.append(ch['id'])
        name_list.append(ch['name'])
    return id_list, name_list


def exporting_dir(oldest_ut: float=None) -> str:
    oldest_dt = datetime.datetime.fromtimestamp(oldest_ut)
    oldest_dt_str = datetime.datetime.strftime(oldest_dt, format='%Y-%m-%d')
    dir_name = "slack_lake/daily-ingest_target-date_{}".format(oldest_dt_str)
    dir_path = f"{SCRIPT_DIR}/{dir_name}"
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    return dir_path


# ==  BEGIN - Main Cloud Function  ==
def ingest_slack_data(request, **kwargs):
    """ingest slack data + publish topic
        Arguments:
            - request (flask.Request): The request object.
            - **kwargs for locally test
            latest_ut: float=None, oldest_ut: float=None, bucket_name: str=None
            - **kwargs[latest_ut]: float
            - **kwargs[oldest_ut]: float
            - **kwargs[bucket_name]: str
        * Request Body
            latest_ut(float): データ取得対象の最新タイムスタンプ（UNIXタイム）
            oldest_ut: データ取得対象の最古タイムスタンプ（UNIXタイム）
            bucket_name: 保存先のバケット名
    """
    # ボットトークンと署名シークレットを使ってアプリを初期化します
    app = App(
        # process_before_response must be True when running on FaaS
        process_before_response=True,
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
    )

    # Settings
    _conditions = {}
    if request is None: # locally test
        _conditions = kwargs
    else : # production environment
        req_data = request.get_json()
        _conditions = {} if req_data is None else req_data
    print('■ request json data\n', _conditions)
    latest_unix_time = _conditions['latest_ut'] if ('latest_ut' in _conditions.keys()) else None
    oldest_unix_time = _conditions['oldest_ut'] if ('oldest_ut' in _conditions.keys()) else None
    bucket_name = _conditions['bucket_name'] if ('bucket_name' in _conditions.keys()) else None

    # 時刻が明示されていない場合は、通常のデイリー実行を前提として
    # データ取得期間を定義する
    if latest_unix_time is None or oldest_unix_time is None:
        tz = pytz.timezone('Asia/Tokyo')
        start_of_today = datetime.datetime.now(tz).replace(hour=0,minute=0,second=0,microsecond=0)
        latest_unix_time = start_of_today.timestamp()
        start_of_yesterday = start_of_today - datetime.timedelta(days=1)
        oldest_unix_time = start_of_yesterday.timestamp()
    out_dir = exporting_dir(oldest_ut=oldest_unix_time)
    logging.info('out_dir : {}'.format(out_dir))
    logging.info('oldest_ut : {}'.format(oldest_unix_time) + ' | latest_ut : {}'.format(latest_unix_time))

    client = app.client

    # ingest channles list
    channels = download_conversations_list(client=client, page_limit=100)
    save_as_json(channels, out_dir + '/' + 'conversations_list.json')

    # ingest users list
    users = download_users_list(client=client, page_limit=100)
    save_as_json(users, out_dir + '/' + 'users_list.json')

    # ingest conversations history
    channel_id_list, channel_name_list = target_channel_id_name_list(channels, including_archived=False)
    conversations = []
    for channel_id, channel_name in zip(channel_id_list, channel_name_list):
        logging.info('download conversations (ch_id: {0}, ch_name: {1})'.format(
            channel_id, channel_name))
        conversations_by_ch = download_conversations_history(
            client=client, channel=channel_id, page_limit=100, latest_unix_time=latest_unix_time, oldest_unix_time=oldest_unix_time
        )
        if len(conversations_by_ch) > 0:
            conversations.extend(conversations_by_ch)
    save_as_json(conversations, out_dir + '/' + 'conversations_history.json')

    # # save completing log
    # tz = pytz.timezone('Asia/Tokyo')
    # now = datetime.datetime.now(tz)
    # ingest_log = {'ingested_at_ts': now.timestamp(), 'ingested_at': now.strftime('%Y-%m-%d %H:%M:%S')}
    # save_into_bucket(ingest_log, bucket, out_dir + '/' + 'ingest_log.json')

    # == only local env ==
    # copy log to export dir
    from_log_path = Path(logfilename)
    to_log_path = Path(out_dir)
    shutil.copy2(from_log_path, to_log_path)
    # == only local env ==

    return f"Successfully ingested slack data."
# ==  END - Main Cloud Function  ==


# ==  BEGIN - Sub Cloud Function for Test  ==
def save_as_json(data: List[dict], fname: str=None):
    """save response data as json
    """
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info('save {}'.format(fname))
# ==  END - Sub Cloud Function for Test  ==


# run app
if __name__ == "__main__":
    # parse args
    args = sys.argv
    latest_ut = 0
    oldest_ut = 0
    if len(args) > 2:
        latest_ut = float(args[1])
        oldest_ut = float(args[2])
    # main proc
    return_str = ingest_slack_data(None, latest_ut=latest_ut, oldest_ut=oldest_ut)
    logging.info(return_str)
