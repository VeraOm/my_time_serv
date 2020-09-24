# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python37_app]
import flask
import email_forward as ef
from google.cloud import logging
import functools

app = flask.Flask(__name__)

import os
# import json
# import google.oauth2.credentials
# import googleapiclient.discovery

import gauth
import gqueue
import web_mon

app.secret_key = "wsxcvb"
app.register_blueprint(gauth.app, url_prefix="/gauth")
app.register_blueprint(gqueue.app, url_prefix="/q")
app.register_blueprint(web_mon.app, url_prefix="/wm")

CURRENT_LOG = os.environ.get("UP_LOG_NAME", default=False)
logr = logging.Client().logger(CURRENT_LOG)

def check_auth(func):
    @functools.wraps(func)
    
    def check_auth_impl(*args, **kwargs):
        if gauth.is_logged_in():
            sResult = func(*args, **kwargs)
        elif gauth.is_cron_request():
            logr.log_text(func(*args, **kwargs))
            sResult = "Everything Ok"
        else:
            logr.log_text("[" + flask.request.remote_addr + " / " 
                + flask.request.headers.get("X-Appengine-Cron", default='###').lower() 
                + "] HEADER -> " + str(flask.request.headers)
                + " Env -> " + str(flask.request.environ))
            sResult = "Everything Will Be Ok"

        return flask.make_response(sResult)
    
    return check_auth_impl
        

@app.route('/')
def hello():
    
    if gauth.is_logged_in():
        return 'I can help you.'

    return 'Hello! Can I help you?'


@app.route('/africa/')
@check_auth
def do_email_forward():
    return ef.main()
    

@app.route('/afgo/')
@check_auth
def task_email_forward():
    
    res = gqueue.add_task(body='{"mailfolder": "2Vera", "receiver": "veralmnva@gmail.com"}', uri=flask.url_for('gqueue.forward_next_email'))
#    res = gqueue.add_task(body='{"mailfolder": "2Vera", "receiver": "yakov.yooy@yandex.ru"}', uri=flask.url_for('gqueue.forward_next_email'))
    
#    return res
    return res.name


@app.route('/beel/')
@check_auth
def bee_serv_check():
    
    res = gqueue.add_task(body=None, uri=flask.url_for('gqueue.view_bee_service'))
    
    return res.name


@app.route('/wmon/')
@check_auth
def run_web_mon():

    res = gqueue.add_task(body=None, uri=flask.url_for('web_mon.run_mon'))

    return res.name



def show_info():
    sResult = str(flask.request.headers)
    return sResult


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=9998, debug=True)
# [END gae_python37_app]
