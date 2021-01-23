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


def save_body_datastore(kind, body):
    from google.cloud import datastore
    import uuid

    result = str(uuid.uuid4())
    dcli = datastore.Client(project=PROJECT_ID)
    task_key = dcli.key(kind, result)
    task = datastore.Entity(key=task_key, exclude_from_indexes=['body'])
    task['body'] = body
    dcli.put(task)
    result = kind + ':' + result

    dcli = None

    logr.log_text("save into datastore: {}".format(result))

    return result


def get_body_datastore(key):
    from google.cloud import datastore

    result = None
    kind, name = key.rpartition(':')[::2]
    dcli = datastore.Client(project=PROJECT_ID)
    task_key = dcli.key(kind, name)
    task = dcli.get(task_key)
    if task:
        result = task.get('body')
        # dcli.delete(task_key)

    if result:
        logr.log_text("get from datastore: {}, length {}".format(kind + ':' + name, len(result)))
    else:
        logr.log_text("get from datastore: {}, length {}".format(kind + ':' + name, 'None'))

    dcli = None

    return result


def save_body(body, qtype):
    if len(body) < 99000:
        return body

    return save_body_datastore('#q:' + qtype, body)


def get_body(req):
    result = req.get_data(as_text=True)

    if result.startswith("#q:"):
        return get_body_datastore(result)

    return result


def is_tasks_exist(except_of) -> bool:
    from google.cloud import tasks_v2

    client = tasks_v2.CloudTasksClient()

    qname = client.queue_path(PROJECT_ID, PROJECT_LOCATION, CURRENT_QUEUE)
    tlist = client.list_tasks(parent=qname)
    res: bool = False
    for task in tlist:
        if isinstance(task, tasks_v2.types.task.Task) and task.app_engine_http_request.relative_uri != except_of:
            res = True
            break

    tlist = None
    client = None

    return res


def add_task(body, uri, in_seconds=None):
    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2

    #    log_str = "create_task: " + uri
    #    log_str = log_str + ", sec="
    #    log_str = log_str + (str(in_seconds) if in_seconds else "None")
    #    log_str = log_str + ", body: " + (body[:30] if body else "None") + "... "
    logr.log_text("add_task: {}, sec={}, body: {}".format(uri, in_seconds, (body[:30] if body else "None")))

    client = tasks_v2.CloudTasksClient()

    parent = client.queue_path(PROJECT_ID, PROJECT_LOCATION, CURRENT_QUEUE)

    #    logr.log_text("add_task: parent = {} is {}".format(parent, type(parent).__name__))

    task = {'app_engine_http_request': {
        'http_method': tasks_v2.HttpMethod.POST,
        'relative_uri': uri
    }
    }

    if body:
        task['app_engine_http_request']['body'] = body.encode()

    if in_seconds:
        d = datetime.datetime.utcnow() + datetime.timedelta(seconds=in_seconds)

        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(d)

        task['schedule_time'] = timestamp

    # logr.log_text("add_task: parent is {}".format(str(parent)))
    # logr.log_text("add_task: task is {}".format(type(task).__name__))
    # logr.log_text("add_task: task = <{}>".format(str(task)))
    # logr.log_text("add_task: client is {}".format(type(client).__name__))

    response = client.create_task(parent=parent, task=task)
    #    logr.log_text("add_task: response is {}".format(type(response).__name__))
    logr.log_text("add_task: response={}...".format(str(response)[:50]))

    return response


def add_task_dbg(body, uri, in_seconds=None):
    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2

    log_str = "add_task: " + uri
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

    with open(r"d:\Temp\task_" + uri.split('/')[-1] + ".txt", "ab") as fl:
        fl.write(task['app_engine_http_request']['body'])

    logr.log_text("add_task: response=" + type(task['app_engine_http_request'].get('body')).__name__ + ", ")

    return "add_task - Ok"


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
        add_task(body=str(result[0]), uri=flask.url_for('gqueue.view_bee_service'), in_seconds=2)

    if result[1] and len(result[1]) > 0:
        json_result = json.dumps(result[1])
        add_task(body=json_result, uri=flask.url_for('gqueue.bee_services_read'))

    logr.log_text(
        "view_bee_service: next setup id - {}, current setup - {}".format(result[0], result[1].get('title', 'none')))

    return "Ok"


@app.route('/bee_services_read', methods=['POST'])
def bee_services_read():
    import bee_conn_srvcs_analize as bee

    setup_json = flask.request.get_data(as_text=True)
    logr.log_text(
        "bee_services_read: {}... [{}]".format((setup_json[:30] if setup_json else "None"), type(setup_json).__name__))

    setup = json.loads(setup_json)
    services = bee.read_page(setup)

    error = services.get('error')
    if error:
        logr.log_text("read_page error: {}".format(error))
        sResult = "Error"
    else:
        add_task(body=json.dumps(services), uri=flask.url_for('gqueue.bee_analize_page'))
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
                    logr.log_text(
                        "bee_analize_page error: {}, Id={}, type={}, data: {}".format(result[1], Id, serv_type,
                                                                                      str(data)))
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
        add_task(body=save_body(result[0], "emlfwd"), uri=flask.url_for('gqueue.send_email_handler'))
        add_task(body=mails_check_json, uri=flask.url_for('gqueue.forward_next_email'), in_seconds=5)
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
