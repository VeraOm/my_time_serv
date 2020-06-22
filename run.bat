set GOOGLE_APPLICATION_CREDENTIALS=d:\projs\pyt\my_time_serv\res\Quickstart-b7174fb00908.json
rem set FN_BASE_URI=http://localhost:9998/gauth/username
rem set FN_AUTH_REDIRECT_URI=http://localhost:9998/gauth/auth
set FN_BUCKET_RESOURCE=time_services_resources
set FN_WEB_CONFIG_FILE=cs.json
set FN_PROJECT_ID=quickstart-1574153168977
set FN_USER_ROLE_PT=projects\/.*\/?roles\/MyServicesAccess

python src\main.py
