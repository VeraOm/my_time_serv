import os
import json
import requests

from google.cloud import storage

BUCKET_RESOURCE = os.environ.get("FN_BUCKET_RESOURCE", default=False)


def get_setup_config(config_id=None):
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(BUCKET_RESOURCE)
    blob = bucket.get_blob("bee_serv_read.json")

    str_config = blob.download_as_string().decode()
    json_config = json.loads(str_config)
    
    blob = None
    bucket = None
    storage_client = None
    
    dId = [cust.get("Id") for cust in json_config]
    dId.sort()
    
    result = [None, {}, None]      # [<Next Id to process>, <Setup for current Id (config_id or 0)>, <Error message>]
    curr_index = None
    if len(dId) == 0:
        return result
    elif config_id:
        try:
            curr_index = dId.index(config_id)
        except Exception as err:
            result[2] = "Error: " + str(err)
            return result
    else:
        curr_index = 0

    if (curr_index + 1) < len(dId):
        result[0] = dId[curr_index + 1]

    result[1] = [setup for setup in json_config if setup.get("Id") == dId[curr_index]][0]
       
    return result



def read_page(setup):
    
    result = {}       # {title: <Setup title>, Id: <Setup Id>, exclude_urls: [<exclude position>], error: <error text>, body: [{type: <part type>, result: {<received data>}, error: <error text>}]}
    result['title'] = setup.get('title')
    result['Id'] = setup.get('Id')
    
    exclude_urls = setup.get('exclude_urls')
    if exclude_urls:
        result['exclude_urls'] = exclude_urls
    
    body = []
    session = requests.Session()
    try:
        for pg in setup['pages']:
            res_resp = {}
            addr = pg.get('page')
            res_resp['type'] = pg.get('outfile')
            try:
                session.headers.update(pg['headers'])
                resp = session.get(addr)
    #            res_text = resp.content.decode('utf-8')
                res_text = resp.content.decode()
                res_resp['result'] = dict(json.loads(res_text))
            except Exception as err:
                res_resp['error'] = "Error: " + str(err)
            body.append(res_resp)
            
    except Exception as err:
        result['error'] = "Error: " + str(err)
    finally:
        session.close()

    result['body'] = body
    
    return result


def services_parse(title, Id, exclude_urls, data):
  
    result = [None, None]        # [<Payable service description (None - is Ok)>, <Error in received data (None - is Ok)>]

    b_header = True
    services = data.get('connectedServices', {}).get('data')
    payable = ""
    if services:
        for srv in list(services):
            if not srv.get('url', '???') in exclude_urls:
                price = srv.get('rcRate', 0.0)
                if price > 0:
                    if b_header:
                        payable = payable + '================== Услуги:\n'
                        payable = payable + '{0} [{1}]\n'.format(title, Id)
                        b_header=False
                    payable = payable + '{0} - {1}\n'.format(srv.get('title', '?'), price)
            
    else:
        result[1] = "Could not parse data: \n" + str(data)

    if len(payable) > 0:
        result[0] = payable
        
    return result     
    

def subscriptions_parse(title, Id, data):
    
    result = [None, None]        # [<Payable subscription description (None - is Ok)>, <Error in received data (None - is Ok)>]

    services = data.get('subscriptions', {}).get('data')
    payable = ""
    if services:
        payable = payable + '================== Сервисы:\n'
        payable = payable + '{0} [{1}]\n'.format(title, Id)
        result[0] = payable + str(services)
    
    return result
    
    
if __name__ == '__main__':
    
    services = read_page(get_setup_config(1)[1])
    for s in services.get("body", []):
        s_type = s.get("type")
        if s_type == "services":
            print(services_parse(services.get("title"), services.get("Id"), services.get("exclude_urls", []), s.get("result")))
        elif s_type == "subscriptions":
            print(subscriptions_parse(services.get("title"), services.get("Id"), s.get("result")))
    
    print()
    