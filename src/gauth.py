import sys
import json
import os
import re
import functools

import time

import flask

import google_auth_oauthlib.flow
import google.oauth2.credentials
import googleapiclient.discovery
from google.cloud import storage
from google.cloud import logging

# logr = logging.Client().logger(os.environ.get("UP_LOG_NAME", default=False))

import google.auth

ACCESS_TOKEN_URI = 'https://www.googleapis.com/oauth2/v4/token'
AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&prompt=consent'

#AUTHORIZATION_SCOPE ='openid email profile'
AUTHORIZATION_SCOPE = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

BUCKET_RESOURCE = os.environ.get("FN_BUCKET_RESOURCE", default=False)
WEB_CONFIG_FILE = os.environ.get("FN_WEB_CONFIG_FILE", default=False)
PROJECT_ID = os.environ.get("FN_PROJECT_ID", default=False)
USER_ROLE_PT = os.environ.get("FN_USER_ROLE_PT", default="projects\/.*\/?roles\/MyServicesAccess")


AUTH_STATE_KEY = 'auth_state'
AUTH_CONFIG_KEY = 'auth_config'
AUTH_PARAMS_KEY = 'auth_params'
AUTH_USERS_KEY = 'auth_users'

app = flask.Blueprint('gauth', __name__)



def is_logged_in():
    return True if AUTH_PARAMS_KEY in flask.session else False


def is_cron_request():
    hdrs = flask.request.headers
    if (flask.request.remote_addr == '127.0.0.1' and
            hdrs.get("X-Appengine-Cron", default='false').lower() == 'true' and
            hdrs.get("X-Appengine-User-Ip", default='9') == '0.1.0.1' and
            (hdrs.get("X-Forwarded-For", default='9').startswith("0.1.0.1") or
            hdrs.get("Forwarded", default='9').find("0.1.0.1") > -1)):
        return True
    
    return False


def get_client_config(file_name):
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(BUCKET_RESOURCE)
    blob = bucket.get_blob(file_name)

    json_config = json.loads(blob.download_as_string())
    
    blob = None
    bucket = None
    storage_client = None
       
    return json_config
    

def check_user_access(username):
    if AUTH_USERS_KEY in flask.session:
        return username.lower() in list(flask.session[AUTH_USERS_KEY])
        
    return False


def init_user_access():
    flask.session.pop(AUTH_USERS_KEY, None)
    credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    service = googleapiclient.discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
    policy = service.projects().getIamPolicy(resource=PROJECT_ID).execute()
    bindings = policy.get("bindings")
    if bindings:
        prog = re.compile(USER_ROLE_PT)
        auth_users = [usr.split(':')[-1].lower() for members in [bind["members"] for bind in bindings if prog.search(bind["role"])] for usr in members]
        flask.session[AUTH_USERS_KEY] = auth_users
    
    service = None
    
    return "AUTH_USERS_KEY - " + str(len(list(flask.session[AUTH_USERS_KEY])))


def init_auth_config():
    client_config = get_client_config(WEB_CONFIG_FILE)
    flask.session[AUTH_CONFIG_KEY] = client_config
    
    return "AUTH_CONFIG_KEY - " + flask.session[AUTH_CONFIG_KEY]["web"]["project_id"]


def no_cache(view):
    @functools.wraps(view)
    def no_cache_impl(*args, **kwargs):
        response = flask.make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return no_cache_impl   


@app.route('/init1')
@no_cache
def init_user_access_page():
    return init_user_access()
    

@app.route('/init2')
@no_cache
def init_auth_config_page():
    return init_auth_config()


@app.route('/init')
@no_cache
def init_auth():
    sResult = init_user_access()
    sResult2 = init_auth_config()
    
    return sResult + "<br/>" + sResult2

    
@app.route('/login')
@no_cache
def auth_request():
    if AUTH_CONFIG_KEY in flask.session:
        client_config = flask.session[AUTH_CONFIG_KEY]
    else:
        return flask.make_response('Invalid config', 401)
        
    auth_redirect_uri = flask.url_for('gauth.auth_receive', _external=True)
    flw = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes=AUTHORIZATION_SCOPE, redirect_uri=auth_redirect_uri)
    sResult = "Create flow " + str(flw) + "<br/> redirect = " + str(flw.redirect_uri);
    sResult = sResult + "<br/>" + client_config["web"]["project_id"] + "<br/>"

    uri, state = flw.authorization_url(access_type='offline', prompt='consent', include_granted_scopes='true')
    
    flw = None
    
    flask.session[AUTH_STATE_KEY] = state
    flask.session.permanent = False

    return flask.redirect(uri, code=302)


@app.route('/auth')
@no_cache
def auth_receive():

    flask.session.pop(AUTH_PARAMS_KEY, None)

    req_state = flask.request.args.get('state', default=None, type=None)

    if not req_state or req_state != flask.session[AUTH_STATE_KEY]:
        response = flask.make_response('Invalid state parameter', 401)
        return response

    client_config = flask.session[AUTH_CONFIG_KEY]

    auth_redirect_uri = flask.url_for('gauth.auth_receive', _external=True)

    flw = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes = AUTHORIZATION_SCOPE,  # flask.request.args.get("scope"), 
                redirect_uri = auth_redirect_uri,
                state = req_state)
    flw.fetch_token(code=flask.request.args.get('code'))
    credentials = flw.credentials

    flw = None
    flask.session.pop(AUTH_STATE_KEY, None)
    service = googleapiclient.discovery.build('oauth2', 'v2', credentials=credentials)
    
    auth_params = service.userinfo().get().execute()
    username = auth_params["email"].lower()
    service = None

    sResult = username + " - Fail"
    
    if check_user_access(username):
        flask.session[AUTH_PARAMS_KEY] = auth_params
        sResult = username + " - Success"
    
    flask.session.pop(AUTH_CONFIG_KEY, None)
    flask.session.pop(AUTH_USERS_KEY, None)
    
    return sResult



# https://developers.google.com/oauthplayground/
# https://developers.google.com/discovery/v1/reference
# https://developers.google.com/identity/protocols/oauth2/web-server#python_3
# https://cloud.google.com/iam/docs/granting-changing-revoking-access
