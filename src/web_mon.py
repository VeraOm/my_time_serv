# from lxml.etree import tostring
import json
import re
import flask
import os
from google.cloud import logging as glog

app = flask.Blueprint('web_mon', __name__)

# import logging  ###

Q_KEY_TYPE = "wmon"
Q_SEND_MAIL = "wmmail"
# Q_KEY_PAGE = "wmonpage"
KIND_WM_RESULT = "wm:result"

CURRENT_LOG = os.environ.get("UP_LOG_NAME", default=False)
PROJECT_ID = os.environ.get("FN_PROJECT_ID", default=False)

# logging.basicConfig(handlers=[logging.FileHandler(u'd:\Temp\mylog.log', 'w', 'utf-8')],
#                     format=u'%(levelname)-8s [%(asctime)s] %(message)s',
#                     level=logging.DEBUG)  ###

logr = glog.Client().logger(CURRENT_LOG)


def log_line(line):
    logr.log_text(line)

    return


def read_setup():
    # with open(r'c:\tools\Python\src\html_grab\wb\flw_config.json', 'rb') as suf:
    #     json_setup = suf.read().decode('utf-8')

    from google.cloud import storage
    BUCKET_RESOURCE = os.environ.get("FN_BUCKET_RESOURCE", default=False)
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(BUCKET_RESOURCE)
    blob = bucket.get_blob("flw_config.json")

    str_config = blob.download_as_string().decode()

    setup = json.loads(str_config)

    return setup


@app.route('/send_email_result', methods=['POST'])
def send_email_result():
    """
    {
    "keys": [{"kind": "str", "name": "str"}, ...],
    "send_to": "<recipient email address>"
    "body": "<email body>"
    }
    """
    import gqueue
    from google.cloud import datastore
    import email_forward as ef

    dmsg_json = get_body()
    dmsg = dict(json.loads(dmsg_json))
    dcli = datastore.Client(project=gqueue.PROJECT_ID)

    log_line("send_email_result: to {}, keys - {}".format(dmsg["send_to"], len(dmsg["keys"])))

    with dcli.transaction() as transact:
        for k in dmsg["keys"]:
            task_key = dcli.key(k["kind"], k["name"])
            transact.delete(task_key)
        mail_str = ef.get_plain_email(dmsg["send_to"], "Web monitoring results", dmsg["body"])
        str_res = ef.send_email(mail_str)

    log_line("send_email_result: " + str_res)

    return str_res


@app.route('/send_results', methods=['POST'])
def send_results():
    from google.cloud import datastore
    import gqueue

    dcli = datastore.Client(project=gqueue.PROJECT_ID)
    query = dcli.query(kind=KIND_WM_RESULT, order=["send_to"])
    send_to = '##'
    body = None
    msg = {}
    keys = []

    log_line("send_results: query {}".format(str(query)))

    for ent in query.fetch():
        recipient = ent.get("send_to").lower()
        if recipient != send_to:
            if body and msg:
                msg["body"] = body
                msg["keys"] = keys
                gqueue.add_task(body=gqueue.save_body(json.dumps(msg), Q_SEND_MAIL),
                                uri=flask.url_for('web_mon.send_email_result'))
            body = ""
            msg = {"send_to": recipient}
            keys.clear()

        send_to = recipient
        body += ent.get("body")
        keys.append({"kind": ent.key.kind, "name": ent.key.name})

    if body and msg:
        msg["body"] = body
        msg["keys"] = keys
        gqueue.add_task(body=gqueue.save_body(json.dumps(msg), Q_SEND_MAIL),
                        uri=flask.url_for('web_mon.send_email_result'))

    query = None
    dcli = None

    return "Ok"


# GLOBAL_BODY = ""  ###


def get_body():
    import gqueue
    # if GLOBAL_BODY.startswith("#q:"):
    #     return gqueue.get_body_datastore(GLOBAL_BODY)
    # return GLOBAL_BODY
    return gqueue.get_body(flask.request)


def read_page(data_part, source):
    import gqueue
    import requests

    log_line("read_page: " + source)
    headers = data_part["headers"]
    with requests.Session() as ss:
        ss.headers.update(headers)
        with ss.get(source) as resp:
            content_type = resp.headers.get('content-type')
            chset = 'utf-8'
            if content_type:
                match_chset = re.search(r'(charset\W+)([^\;]+)', content_type, flags=re.IGNORECASE)
                if match_chset and len(match_chset.groups()) > 1:
                    chset = match_chset[2]
                else:
                    log_line("read_page: content_type is {}".format(content_type))
            # chset = resp.encoding

            page = resp.content.decode(chset)

            result = dict(data_part)
            result["page"] = page

            log_line("read_page: page length is {}, chrset is {}".format(len(page), chset))

            gqueue.add_task(body=gqueue.save_body(json.dumps(result), Q_KEY_TYPE),
                            uri=flask.url_for('web_mon.run_data_part'))

    return str(len(result))


def save_mon_result(body, recipient: str):
    from google.cloud import datastore
    import uuid
    import gqueue

    result = str(uuid.uuid4())
    dcli = datastore.Client(project=gqueue.PROJECT_ID)
    task_key = dcli.key(KIND_WM_RESULT, result)
    task = datastore.Entity(key=task_key, exclude_from_indexes=tuple(['body']))
    task['send_to'] = recipient
    task['body'] = body
    dcli.put(task)
    result = KIND_WM_RESULT + ':' + result

    dcli = None

    log_line("save into datastore: {}".format(result))

    return result


def get_float(pval):
    # log_line('get_float from ' + pval)  ###

    match = re.search(r'\s*[\d\,\s]*\.?[\d\,\s]*\d', pval, flags=re.IGNORECASE)
    if match:
        sval = re.sub(r"\s", "", match[0])
        pnts = len(sval.split('.')) - 1

        # log_line('get_float. sval = ' + sval + ', pnts = ' + str(pnts))  ###

        try:
            if pnts == 1:
                return float(re.sub(r',', "", sval))
            elif pnts == 0:
                if len(sval.split(',')) == 2:
                    return float(re.sub(r',', ".", sval))
                else:
                    return float(re.sub(r',', "", sval))
        except ValueError as err:
            print(str(err))

    return None


def get_wgram(pval):
    # log_line('get_wgram from ' + pval)  ###

    match = re.search(r"([\d\s\,]*\.?[\d\s\,]+)\s*[\(\{\[]?(г[р\s\.]?|кг[\.\s]?)", pval, flags=re.IGNORECASE)
    if match and len(match.groups()) == 2:
        wght = get_float(match[1])
        unit = re.sub(r"\s", "", match[2]).lower()

        # log_line('get_wgram. wght = ' + str(wght) + ', unit = ' + unit)  ###

        if unit.startswith("кг"):
            wght *= 1000

        return wght

    return None


def xsearch(page, data_source):
    res_body = None
    res_links = None
    res_err = []

    if page:
        from lxml import html
        xtree = html.fromstring(page)

        path = data_source.get("xpath")
        list_val = []
        if path:
            list_val += [val.strip() for val in xtree.xpath(path)]

        # log_line('list_val count is ' + str(len(list_val)))  ###

        vals = data_source.get("xvals")
        dict_val = {}
        if vals:
            for k, v in vals.items():
                xres = " ".join([str(val) for val in xtree.xpath(v["xpath"])])
                # log_line(str(k) + " = " + str(xres))  ###
                if xres:
                    way_clean = v.get("wclean")
                    if way_clean:
                        if way_clean == "get_float":
                            dict_val[k] = get_float(str(xres))
                        elif way_clean == "get_wgram":
                            dict_val[k] = get_wgram(str(xres))
                    elif k == "price":
                        dict_val[k] = get_float(str(xres))
                    else:
                        dict_val[k] = str(xres).strip()
                else:
                    dict_val[k] = ""

                # log_line(str(k) + " Is " + str(dict_val[k]))  ###

        link_format = data_source.get("source_template")
        res_links = []
        body_format = data_source.get("print_format")
        res_body = ""
        pass_clause_templ = data_source.get("true_clause")

        result_proc = data_source.get("result_proc")
        if result_proc:
            d_proc = result_proc.split('#')
            if d_proc[0] == "join":
                list_val = [d_proc[1].join(list_val)]

        for val in list_val if list_val else [None]:
            if pass_clause_templ:
                pass_clause = pass_clause_templ.format(val, **dict_val)

                # log_line(pass_clause)  ###

                try:
                    if not eval(pass_clause):
                        continue
                except Exception as err:
                    res_err.append(pass_clause + " - error: " + str(err))
                    return res_body, res_links, res_err

            if link_format:
                res_links.append(link_format.format(val, **dict_val, **data_source))
            if body_format:
                res_body += body_format.format(val, **dict_val, **data_source)

        # log_line("next_sources count Is " + str(len(res_links)))  ###

    return res_body, res_links, res_err


def plain_json(page, data_source):
    res_body = None
    res_links = None
    res_err = None
    if page:
        import jsonpath
        src = json.loads(page)

        positions = jsonpath.jsonpath(src, data_source["jpath"])
        res_body = ""
        body_format = data_source.get("print_format")
        res_links = []
        link_format = data_source.get("source_template")

        if positions:
            result_proc = data_source.get("result_proc")
            if result_proc:
                d_proc = result_proc.split('#')
                if d_proc[0] == "join":
                    positions = [d_proc[1].join(positions)]

            for position in positions:
                if body_format:
                    res_body += body_format.format(**position, **data_source)
                if link_format:
                    res_links.append(link_format.format(**position, **data_source))

    return res_body, res_links, res_err


def page_desc(data_part, page):
    src = data_part.get("sources")
    src_type = src[0].get("type")
    body = None
    links = None
    errs = None

    log_line("page_desc: Type is {}".format(src_type))

    if src_type == 'jsp':
        body, links, errs = plain_json(page, src[0])
    elif src_type == 'xsearch_xp':
        import html as py_html
        py_html.entities.html5["nbsp"]=' '
        py_html.entities.html5["nbsp;"]=' '
        body, links, errs = xsearch(py_html.unescape(page), src[0])

    if body:
        save_mon_result(body, data_part.get("send_to"))

    if errs:
        for e in errs:
            log_line("page_desc error - {}".format(e))
        return

    log_line("page_desc: body - {}, links - {}, err - {}".format(body if body is None else len(body),
                                                                 links if links is None else len(links),
                                                                 errs if errs is None else len(errs)))

    result = {}

    import gqueue

    has_last = data_part.get("last")
    if len(src) > 1:
        result["headers"] = data_part["headers"]
        result["send_to"] = data_part["send_to"]

        if links:
            first_source = src[1].get("source")
            has_source = first_source and not first_source.startswith('#')
            if has_last:
                first_lnk = -1
                last_lnk = -1
            else:
                first_lnk = None
                last_lnk = len(links)

            for lnk in links[:first_lnk]:
                if not has_source:
                    src[1]["source"] = lnk
                result["sources"] = src[1:]
                gqueue.add_task(body=gqueue.save_body(json.dumps(result), Q_KEY_TYPE),
                                uri=flask.url_for('web_mon.run_data_part'))

            for lnk in links[last_lnk:None]:
                if not has_source:
                    src[1]["source"] = lnk
                result["sources"] = src[1:]
                result["last"] = True
                gqueue.add_task(body=gqueue.save_body(json.dumps(result), Q_KEY_TYPE),
                                uri=flask.url_for('web_mon.run_data_part'))
        else:
            result["sources"] = src[1:]
            if has_last:
                result["last"] = True
            gqueue.add_task(body=gqueue.save_body(json.dumps(result), Q_KEY_TYPE),
                            uri=flask.url_for('web_mon.run_data_part'))
    elif has_last:
        result["go"] = True
        gqueue.add_task(body=gqueue.save_body(json.dumps(result), Q_KEY_TYPE),
                        uri=flask.url_for('web_mon.send_results'))

    return str(len(result))


@app.route('/run_data_part', methods=['POST'])
def run_data_part():
    """
    {"page": "<file to process>",
#     "chset": "<page char set>",
#     "links": [<links to get pages>],
     "sources": {<from setup>, "last": <last sources list member>},
     "send_to": {<from setup>},
     "headers": {<from setup>}
    }
    """
    part_json = get_body()
    #    log_line(part_json)
    data_part = json.loads(part_json)
    log_line("run_part: to {}, sources - {}".format(data_part.get("send_to"), len(data_part["sources"])))

    src = data_part.get("sources")
    result = ""
    if src:
        """
                links = data_part.pop("links", None)
                if links:
                    import gqueue
                    source = src[0].get("source")
                    has_source = source and not source.startswith('#')
                    for lnk in links:
                        if not has_source:
                            src[0]["source"]=lnk
                        gqueue.add_task(gqueue.save_body(json.dumps(data_part), Q_KEY_TYPE), '/run_data_part')
                else:
        """
        page = data_part.pop("page", None)
        if page:
            # chset = data_part.pop("chset", 'utf-8')
            result = page_desc(data_part, page)
        else:
            lnk = src[0].get("source")
            if lnk and not lnk.startswith('#'):
                result = read_page(data_part, lnk)

    return "Ok, " + result


@app.route('/run', methods=['POST'])
def run_mon():
    import gqueue
    mon_setup = read_setup()
    for fs in mon_setup[:-1]:
        for da in fs["data"]:
            data_part = dict(da)
            data_part["headers"] = fs["headers"]
            gqueue.add_task(body=gqueue.save_body(json.dumps(data_part), Q_KEY_TYPE),
                            uri=flask.url_for('web_mon.run_data_part'))
    for ls in mon_setup[-1:]:
        for da in ls["data"][:-1]:
            data_part = dict(da)
            data_part["headers"] = ls["headers"]
            gqueue.add_task(body=gqueue.save_body(json.dumps(data_part), Q_KEY_TYPE),
                            uri=flask.url_for('web_mon.run_data_part'))
        for da in ls["data"][-1:]:
            data_part = dict(da)
            data_part["headers"] = ls["headers"]
            data_part["last"] = True
            gqueue.add_task(body=gqueue.save_body(json.dumps(data_part), Q_KEY_TYPE),
                            uri=flask.url_for('web_mon.run_data_part'))

    return "Ok - " + str(len(mon_setup))

# if __name__ == '__main__':
#     read_setup()
# log_line("===============================================================")  ###

# run_mon()
# GLOBAL_BODY = None
# with open(r"d:\Temp\t3181.txt", "rb") as fl:
#     GLOBAL_BODY = fl.read().decode()
# if GLOBAL_BODY:
#     run_data_part()

# send_results()

# logging.shutdown()
