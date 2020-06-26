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
import json
import google.oauth2.credentials
import googleapiclient.discovery

try:
  import googleclouddebugger
  googleclouddebugger.enable()
except ImportError:
  pass

import gauth

app.secret_key = "wsxcvb"
app.register_blueprint(gauth.app, url_prefix="/gauth")

CURRENT_LOG = os.environ.get("UP_LOG_NAME", default=False)

def check_auth(func):
    @functools.wraps(func)
    def check_auth_impl(*args, **kwargs):
        if gauth.is_logged_in():
            return flask.make_response(func(*args, **kwargs))
        return "Everything Will Be Ok"
    return check_auth_impl
        

@app.route('/')
def hello():
    
    logging_client = logging.Client()
    log_name = CURRENT_LOG
    logger = logging_client.logger(log_name)
    if gauth.is_logged_in():
        return 'I can help you.'

    return 'Hello! Can I help you?'


@app.route('/africa/')
def do_email_forward():
    return ef.main()
    

@app.route('/params/')
def show_info():
    sResult = str(flask.request.headers)
    return sResult


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=9998, debug=True)
# [END gae_python37_app]
