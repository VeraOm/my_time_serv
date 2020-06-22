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

import google.auth

ACCESS_TOKEN_URI = 'https://www.googleapis.com/oauth2/v4/token'
AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&prompt=consent'

AUTHORIZATION_SCOPE ='openid email profile'

BUCKET_RESOURCE = os.environ.get("FN_BUCKET_RESOURCE", default=False)
WEB_CONFIG_FILE = os.environ.get("FN_WEB_CONFIG_FILE", default=False)
PROJECT_ID = os.environ.get("FN_PROJECT_ID", default=False)
USER_ROLE_PT = os.environ.get("FN_USER_ROLE_PT", default="projects\/.*\/?roles\/MyServicesAccess")


# AUTH_CREDENTIALS_KEY = 'credentials'
AUTH_STATE_KEY = 'auth_state'
AUTH_CONFIG_KEY = 'auth_config'
AUTH_PARAMS_KEY = 'auth_params'
AUTH_USERS_KEY = 'auth_users'

app = flask.Blueprint('gauth', __name__)

# AUTH_REDIRECT_URI = os.environ.get("FN_AUTH_REDIRECT_URI", default=False)
# BASE_URI = os.environ.get("FN_BASE_URI", default=False)


def is_logged_in():
    return True if AUTH_PARAMS_KEY in flask.session else False


def get_client_secrets():
#    with open(r'd:\Temp\cs.json', 'r') as config:
#        json_config = json.load(config)
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(BUCKET_RESOURCE)
    blob = bucket.get_blob(WEB_CONFIG_FILE)

    json_config = json.loads(blob.download_as_string())
       
    return json_config


@app.route('/params')
def out_params():
    credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    service = googleapiclient.discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
    
    policy = service.projects().getIamPolicy(resource=PROJECT_ID).execute()
    
    sResult = "<pre>" + str(policy) + "</pre>"
    sResult = sResult + flask.url_for('gauth.auth', _external=True) + "<br/>"
    return sResult

def check_user_access(username):
    credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    service = googleapiclient.discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
    
    policy = service.projects().getIamPolicy(resource=PROJECT_ID).execute()
    
    bindings = policy.get("bindings")
    if not bindings:
      return False
      
#        auth_users = list(chain(*[bind["members"] for bind in bindings if bind["role"] == "roles/owner"]))
    prog = re.compile(USER_ROLE_PT)
    auth_users = [usr.split(':')[-1].lower() for members in [bind["members"] for bind in bindings if prog.search(bind["role"])] for usr in members]
#    return str(auth_users)
    
    return username.lower() in auth_users

def no_cache(view):
    @functools.wraps(view)
    def no_cache_impl(*args, **kwargs):
        response = flask.make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return no_cache_impl   # functools.update_wrapper(no_cache_impl, view)
    

@app.route('/login')
@no_cache
def login():
#    flw = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
#                r'd:\Temp\cs.json', 
    client_config = get_client_secrets()
    flask.session[AUTH_CONFIG_KEY] = client_config
    auth_redirect_uri = flask.url_for('gauth.auth', _external=True)
    flw = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes=AUTHORIZATION_SCOPE, redirect_uri=auth_redirect_uri)

    uri, state = flw.authorization_url(access_type='offline', include_granted_scopes='true')

    flask.session[AUTH_STATE_KEY] = state
    flask.session.permanent = True

    return flask.redirect(uri, code=302)

@app.route('/auth')
@no_cache
def auth():
    
    flask.session.pop(AUTH_PARAMS_KEY, None)
    
    sRes = ""
    for arg in flask.request.args.items():
        sRes = sRes + arg[0] + " = " + arg[1] + "<br/>"
    
    req_state = flask.request.args.get('state', default=None, type=None)

    if req_state != flask.session[AUTH_STATE_KEY]:
        response = flask.make_response('Invalid state parameter', 401)
        return response


#    flw = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
#                r'd:\Temp\cs.json', 
    client_config = flask.session[AUTH_CONFIG_KEY]
    
    auth_redirect_uri = flask.url_for('gauth.auth', _external=True)
    flw = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes = flask.request.args.get("scopes"), 
                redirect_uri = auth_redirect_uri,
                state = req_state)
                
    flw.fetch_token(code=flask.request.args.get('code'))
    credentials = flw.credentials
    
    flask.session.pop(AUTH_STATE_KEY, None)
    flask.session.pop(AUTH_CONFIG_KEY, None)
    
    """
    flask.session[AUTH_CREDENTIALS_KEY] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret}
        
    sRes = sRes + 'token = ' + str(credentials.token) + "<br/>"
    sRes = sRes + 'refresh_token = ' + str(credentials.refresh_token) + "<br/>"
    sRes = sRes + 'token_uri = ' + str(credentials.token_uri) + "<br/>"
    sRes = sRes + 'client_id = ' + str(credentials.client_id) + "<br/>"
    sRes = sRes + 'client_secret = ' + str(credentials.client_secret) + "<br/>"
    
    creds = google.oauth2.credentials.Credentials(**flask.session[AUTH_CREDENTIALS_KEY])
    """ 
   
    auth_params = googleapiclient.discovery.build('oauth2', 'v2', credentials=credentials).userinfo().get().execute()
    
    base_uri = flask.url_for('hello')
    
    if check_user_access(auth_params["email"]):
        # return flask.make_response('Who are you?', 401)
        flask.session[AUTH_PARAMS_KEY] = auth_params

#    sRes = sRes + "<pre>" + flask.session[AUTH_PARAMS_KEY] + "</pre>"
    
    return flask.redirect(base_uri, code=302)

# https://developers.google.com/oauthplayground/
# https://developers.google.com/discovery/v1/reference
# https://developers.google.com/identity/protocols/oauth2/web-server#python_3
# https://cloud.google.com/iam/docs/granting-changing-revoking-access
# /oauthplayground/?state=TOm7CmagTjdN7X3dytlVpPGUSQDraU&code=4%2F1AGrfoLFK25xSpj4KLay3AqxJeNQkMQptaouqFyVMP6Qor1MnByBL_qBDxP9hQ-8D4RVJKvvd2u0Mx62a_GjI54&scope=email+profile+openid+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile&authuser=0&prompt=consent HTTP/1.1
def login2():
    flow = InstalledAppFlow.from_client_secrets_file(
                r'd:\Temp\cs.json', 
                scopes=AUTHORIZATION_SCOPE, redirect_uri='https://developers.google.com/oauthplayground')
    flow.run_local_server()
    uri = flow.authorization_url()
    return flask.redirect(uri, code=302)

