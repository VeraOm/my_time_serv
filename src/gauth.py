import sys
import json
import os
import re
import functools

import flask

import google_auth_oauthlib.flow
import google.oauth2.credentials
import googleapiclient.discovery
from google.cloud import storage
from google.cloud import logging

logr = logging.Client().logger(os.environ.get("UP_LOG_NAME", default=False))

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


def get_client_secrets():
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(BUCKET_RESOURCE)
    blob = bucket.get_blob(WEB_CONFIG_FILE)

    json_config = json.loads(blob.download_as_string())
       
    return json_config


def check_user_access(username):
    logr.log_text("DO check_user_access (1)")

    credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])

    logr.log_text("project_id: " + str(project_id))
    logr.log_text("credentials: " + str(credentials))

    service = googleapiclient.discovery.build('cloudresourcemanager', 'v1', credentials=credentials)

    logr.log_text("service: " + str(service))
    logr.log_text("PROJECT_ID: " + PROJECT_ID)
    
    policy = service.projects().getIamPolicy(resource=PROJECT_ID).execute()

    logr.log_text("service: " + str(policy))
    
    bindings = policy.get("bindings")

    logr.log_text("bindings: " + str(bindings))

    if not bindings:
      return False
      
    logr.log_text("USER_ROLE_PT: " + USER_ROLE_PT)

    prog = re.compile(USER_ROLE_PT)

    logr.log_text("prog: " + str(prog))

    auth_users = [usr.split(':')[-1].lower() for members in [bind["members"] for bind in bindings if prog.search(bind["role"])] for usr in members]

    logr.log_text("auth_users: " + str(auth_users))
    
    return username.lower() in auth_users


def no_cache(view):
    @functools.wraps(view)
    def no_cache_impl(*args, **kwargs):
        response = flask.make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return no_cache_impl   
    

@app.route('/login')
# @no_cache
def login():
    client_config = get_client_secrets()
    flask.session[AUTH_CONFIG_KEY] = client_config
    auth_redirect_uri = flask.url_for('gauth.auth', _external=True)
    flw = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes=AUTHORIZATION_SCOPE, redirect_uri=auth_redirect_uri)

    uri, state = flw.authorization_url(access_type='offline', include_granted_scopes='true')

    flask.session[AUTH_STATE_KEY] = state
    flask.session.permanent = True

    logr.log_text("URI: " + uri + ", state: " + state)
    
    return flask.redirect(uri, code=302)

@app.route('/auth')
# @no_cache
def auth():
    
    logr.log_text("DO AUTH (1)")

    flask.session.pop(AUTH_PARAMS_KEY, None)

    logr.log_text("DO AUTH (2)")
    
    req_state = flask.request.args.get('state', default=None, type=None)

    logr.log_text("req_state: " + str(req_state))

    if not req_state or req_state != flask.session[AUTH_STATE_KEY]:
        response = flask.make_response('Invalid state parameter', 401)
        return response

    logr.log_text("DO AUTH (3)")

    client_config = flask.session[AUTH_CONFIG_KEY]

    logr.log_text("client_config: " + str(client_config))
    
    auth_redirect_uri = flask.url_for('gauth.auth', _external=True)

    logr.log_text("auth_redirect_uri: " + auth_redirect_uri)
    logr.log_text("args: " + str(flask.request.args))

    flw = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes = AUTHORIZATION_SCOPE,  # flask.request.args.get("scope"), 
                redirect_uri = auth_redirect_uri,
                state = req_state)
                
    logr.log_text("flw: " + str(flw))

    flw.fetch_token(code=flask.request.args.get('code'))
    credentials = flw.credentials

    logr.log_text("credentials: " + str(credentials))
    
    flask.session.pop(AUTH_STATE_KEY, None)

    logr.log_text("DO AUTH (4)")

    flask.session.pop(AUTH_CONFIG_KEY, None)
    
    logr.log_text("DO AUTH (5)")
   
    auth_params = googleapiclient.discovery.build('oauth2', 'v2', credentials=credentials).userinfo().get().execute()

    logr.log_text("auth_params: " + str(auth_params))
    
    base_uri = flask.url_for('hello')

    logr.log_text("base_uri: " + base_uri)
    
    if check_user_access(auth_params["email"]):
        flask.session[AUTH_PARAMS_KEY] = auth_params

    
    return flask.redirect(base_uri, code=302)

# https://developers.google.com/oauthplayground/
# https://developers.google.com/discovery/v1/reference
# https://developers.google.com/identity/protocols/oauth2/web-server#python_3
# https://cloud.google.com/iam/docs/granting-changing-revoking-access
