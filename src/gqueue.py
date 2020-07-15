import os
import flask
import json
import datetime
from google.cloud import logging


CURRENT_LOG = os.environ.get("UP_LOG_NAME", default=False)
CURRENT_QUEUE = os.environ.get("UP_QUEUE_NAME", default=False)
PROJECT_ID = os.environ.get("FN_PROJECT_ID", default=False)
PROJECT_LOCATION = os.environ.get("FN_PROJECT_LOC", default=False)

logr = logging.Client().logger(CURRENT_LOG)

app = flask.Blueprint('gqueue', __name__)

def is_task_request():
    hdrs = flask.request.headers
    if (flask.request.remote_addr == '127.0.0.1' and
            hdrs.get("X-Appengine-Queuename", default='false') == CURRENT_QUEUE and
            hdrs.get("X-Appengine-User-Ip", default='9') == '0.1.0.2' and
            (hdrs.get("X-Forwarded-For", default='9').startswith("0.1.0.2") or
            hdrs.get("Forwarded", default='9').find("0.1.0.2") > -1)):
        return True
    
    return False


def create_task(body, uri, in_seconds=None):

    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2

    log_str = "create_task: " + uri
    log_str = log_str + ", sec="
    log_str = log_str + (str(in_seconds) if in_seconds else "None")
    log_str = log_str + body[:25] + "... "
    logr.log_text(log_str)

    client = tasks_v2.CloudTasksClient()
    
    parent = client.queue_path(PROJECT_ID, PROJECT_LOCATION, CURRENT_QUEUE)

    task = {'app_engine_http_request': {  
                'http_method': 'POST',
                'relative_uri': uri
            }
    }
    
    if body:
        task['app_engine_http_request']['body'] = body.encode()

    if in_seconds is not None:
        d = datetime.datetime.utcnow() + datetime.timedelta(seconds=in_seconds)

        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(d)

        task['schedule_time'] = timestamp

    response = client.create_task(parent, task)
    logr.log_text("create_task: response=" + str(response))

    return response
    

@app.route('/forward_next_email', methods=['POST'])
def forward_next_email():
    import email_forward as ef
    
    mails_check_json = flask.request.get_data(as_text=True)
    logr.log_text("forward_next_email: " + mails_check_json)
    mails_check = dict(json.loads(mails_check_json))
    
    result = ef.create_forward_email(mails_check)
    if result[0] and not result[0].startswith("No messages") and not result[0].startswith("Error"):
        create_task(body=result[0], uri=flask.url_for('gqueue.send_email_handler') + "7")
        create_task(body=mails_check_json, uri=flask.url_for('gqueue.forward_next_email'), in_seconds=5)
        sResult = "Ok. Do next"
    else:
        sResult = "Ok. " + result[0]

    logr.log_text("forward_next_email: " + sResult)
    if result[1]:
        logr.log_text("forward_next_email: " + result[1])

    return result[1] if result[1] else sResult


@app.route('/send_email', methods=['POST'])
def send_email_handler():
    import email_forward as ef
    
    str_msg = flask.request.get_data(as_text=True)
    logr.log_text("send_email_handler: " + str_msg[:50] + "... " + str_msg[-15:])
     
    sResult = ef.send_email(str_msg)

    logr.log_text("send_email_handler: " + sResult)
    
    return sResult

