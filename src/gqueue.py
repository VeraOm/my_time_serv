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


def save_body_redis(key, value):
    import redis
    import uuid
        
    REDISHOST = os.environ.get("REDISHOST", default=False)
    REDISPORT = os.environ.get("REDISPORT", default=False)
    
    result = key + ':' + str(uuid.uuid4())
    with redis.StrictRedis(host=REDISHOST, port=REDISPORT) as rcash:
        rcash.set(result, value, ex=3600)
    
    logr.log_text("save into redis: {}".format(result))

    return result


def get_body_redis(key):
    import redis
        
    REDISHOST = os.environ.get("REDISHOST", default=False)
    REDISPORT = os.environ.get("REDISPORT", default=False)
    
    result = None
    with redis.StrictRedis(host=REDISHOST, port=REDISPORT) as rcash:
        result = rcash.get(key)

    logr.log_text("get from redis: {}, length {}".format(key, len(result)))
    
    return result


def save_body(body, qtype):
    if len(body) < 99000:
        return body
        
    return save_body_redis('#q:' + qtype, body)


def get_body(req):
    result = req.get_data(as_text=True)
    
    if result.startswith("#q:"):
        return get_body_redis(result).decode()
        
    return result

    

def create_task(body, uri, in_seconds=None):

    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2

#    log_str = "create_task: " + uri
#    log_str = log_str + ", sec="
#    log_str = log_str + (str(in_seconds) if in_seconds else "None")
#    log_str = log_str + ", body: " + (body[:30] if body else "None") + "... "
    logr.log_text("create_task: {}, sec={}, body: {}".format(uri, in_seconds, (body[:30] if body else "None")))

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
    logr.log_text("create_task: response={}...".format(str(response)[:50]))

    return response
    

def create_task_dbg(body, uri, in_seconds=None):

    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2

    log_str = "create_task: " + uri
    log_str = log_str + ", sec="
    log_str = log_str + (str(in_seconds) if in_seconds else "None")
    log_str = log_str + ", body: " + (body[:30] if body else "None") + "... "
    logr.log_text(log_str)


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

    with open(r"d:\Temp\task_" + uri.split('/')[-1] + ".txt", "wb") as fl:
        fl.write(task['app_engine_http_request']['body'])
        
    logr.log_text("create_task: response=" + type(task['app_engine_http_request'].get('body')).__name__ + ", ")

    return "create_task - Ok"
    

@app.route('/bee_services_check', methods=['POST'])
def view_bee_service():
    import bee_conn_srvcs_analize as bee
    
    setup_id_str = flask.request.get_data(as_text=True)
    logr.log_text("view_bee_service: {}".format(setup_id_str))
    
    try:
        setup_id = int(setup_id_str)
        result = bee.get_setup_config(setup_id)
    except Exception as err:
        result = bee.get_setup_config()
        
    if result[2]:
        logr.log_text("get_setup_config error: {}".format(result[2]))
        
    if result[0]:
        create_task(body=str(result[0]), uri=flask.url_for('gqueue.view_bee_service'), in_seconds=2)
        
    if result[1] and len(result[1]) > 0:
        json_result = json.dumps(result[1])
        create_task(body=json_result, uri=flask.url_for('gqueue.bee_services_read'))
        
    logr.log_text("view_bee_service: next setup id - {}, current setup - {}".format(result[0], result[1].get('title', 'none')))
    
    return "Ok"
    

@app.route('/bee_services_read', methods=['POST'])
def bee_services_read():
    
    import bee_conn_srvcs_analize as bee
    
    setup_json = flask.request.get_data(as_text=True)
    logr.log_text("bee_services_read: {}... [{}]".format((setup_json[:30] if setup_json else "None"), type(setup_json).__name__))

    setup = json.loads(setup_json)
    services = bee.read_page(setup)
    
    error = services.get('error')
    if error:
        logr.log_text("read_page error: {}".format(error))
        sResult = "Error"
    else:
        create_task(body=json.dumps(services), uri=flask.url_for('gqueue.bee_analize_page'))
        sResult = str(services.get("Id"))
    
    logr.log_text("bee_services_read: {}".format(sResult))
    
    return "Ok"
  
  
@app.route('/bee_analize_page', methods=['POST'])
def bee_analize_page():  

    import bee_conn_srvcs_analize as bee
    import email_forward as ef

    page_json = flask.request.get_data(as_text=True)
    logr.log_text("bee_analize_page: {}...".format((page_json[:30] if page_json else "None")))

    service_page = dict(json.loads(page_json))

    title = service_page.get("title")
    Id = service_page.get("Id")
    sResult = title + " - Ok."
    sError = ""
    for s in service_page.get("body", []):
        serv_type = s.get("type")
        error = s.get("error")
        if error:
            logr.log_text("read page {} error: {}".format(serv_type, error))
            sError = "Error exist."
        else:
          data = s.get("result")
          if serv_type == "services":
              result = bee.services_parse(title, Id, service_page.get("exclude_urls", []), data)
          elif serv_type == "subscriptions":
              result = bee.subscriptions_parse(title, Id, data)
          
          if result:
              if result[1]:
                  logr.log_text("bee_analize_page error: {}, Id={}, type={}, data: {}".format(result[1], Id, serv_type, str(data)))
                  sError = "Error exist."

              if result[0]:
                  logr.log_text("bee_analize_page - payable services exist: {}".format(result[0]))
                  mail_str = ef.get_plain_email("alexanderlmnv@gmail.com", "Beeline needs money", result[0])
                  ef.send_email(mail_str)
                  sResult = "Info exist."
    
    logr.log_text("bee_analize_page: {} {}".format(sResult, sError))
        
    return sResult + sError

    
@app.route('/forward_next_email', methods=['POST'])
def forward_next_email():
    import email_forward as ef
    
    mails_check_json = flask.request.get_data(as_text=True)
    logr.log_text("forward_next_email: " + mails_check_json)
    mails_check = dict(json.loads(mails_check_json))
    
    result = ef.create_forward_email(mails_check)
    if result[0] and not result[0].startswith("No messages") and not result[0].startswith("Error"):
        create_task(body=save_body(result[0], "emlfwd"), uri=flask.url_for('gqueue.send_email_handler'))
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
    
#    str_msg = flask.request.get_data(as_text=True)
    str_msg = get_body(flask.request)
    logr.log_text("send_email_handler: " + str_msg[:50] + "... " + str_msg[-15:])
     
    sResult = ef.send_email(str_msg)

    logr.log_text("send_email_handler: " + sResult)
    
    return sResult


    