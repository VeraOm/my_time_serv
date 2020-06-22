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

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = flask.Flask(__name__)

import json
import google.oauth2.credentials
import googleapiclient.discovery

import gauth
app.secret_key = "wsxcvb"
app.register_blueprint(gauth.app, url_prefix="/gauth")

def check_auth(func):
    @functools.wraps(func)
    def check_auth_impl(*args, **kwargs):
        if gauth.is_logged_in():
            return flask.make_response(func(*args, **kwargs))
        return "Everything Will Be Ok"
    return check_auth_impl   # functools.update_wrapper(check_auth_impl, func)
        

@app.route('/')
def hello():
    
    logging_client = logging.Client()
    log_name = 'my-test-log'
    logger = logging_client.logger(log_name)
#    text = 'Test hello log'
#    logger.log_text(text)
    if gauth.is_logged_in():
        return 'I can help you.'

    return 'Hello! Can I help you?'


@app.route('/africa/')
@check_auth
def do_email_forward():
    return ef.main()
    

@app.route('/gauth/username')
@check_auth
def login():
#    if gauth.is_logged_in():
    user_info = json.dumps(flask.session[gauth.AUTH_PARAMS_KEY], indent=4)
    return '<div>You are currently logged in as </div><pre>' + user_info + "</pre>"

#    return 'You are not currently logged in.'


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=9998, debug=True)
# [END gae_python37_app]
