import imaplib
import smtplib
import socket, ssl
import email
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from email.header import decode_header

non_bmp_map = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)

MY_EMAIL = 'yakov_yooy@aol.com'


def get_name():
    return "I want to formard something"


def get_native_header(header):
    result = ""
    for part in decode_header(header):
        byt, chars = part
        # print(chars, type(byt))
        if type(byt)==bytes:
            result = result + byt.decode(chars if chars else 'utf-8')
        else:
            result = result + byt
    return result


def create_forward_email(params):
    sResult = None
    ret_subjects = ""

    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_default_certs()
    
    imap = imaplib.IMAP4_SSL(host='imap.aol.com', port=993, ssl_context=context)
    try:
        imap.login(MY_EMAIL, 'ojyfdxgiqnomexop')

#        resp, exist_data = imap.select(mailbox='2Vera', readonly=False)
        resp, exist_data = imap.select(mailbox=params['mailfolder'], readonly=False)
        try:
            sSearch=u'UNSEEN'
            resp, exist_data = imap.uid('SEARCH', None, 'UNSEEN')
            if resp == 'OK' and len(exist_data[0]) > 0:
                
                email_uid = exist_data[0].split()[0]
                resp, data = imap.uid('FETCH', email_uid, '(RFC822)')
                msg_src = email.message_from_bytes(data[0][1])
                
                msg = MIMEMultipart()
                msg["From"] = MY_EMAIL
                msg["To"] = params['receiver']
                msg["Date"] = formatdate(localtime=True)
                subject = get_native_header(msg_src.get("Subject"))
                msg["Subject"] = 'Fwd: ' + subject
                try:
                    ret_subjects += "<p>" + subject + "</p>"
                except UnicodeError:
                    ret_subjects += "<p>" + subject.translate(non_bmp_map) + "</p>"
        
                h_From = get_native_header(msg_src.get("From"))
                h_To = get_native_header(msg_src.get("To"))
        
                body_text = '\r\n'.join([
                    '-----Original Message-----',
                    'From: '+h_From,
                    'To: '+h_To,
                    'Sent: '+msg_src.get("Date"),
                    ""
                    ]).encode('UTF-8')
                msg.attach(MIMEText(body_text, 'plain', 'UTF-8'))
        
                for part in msg_src.walk():
                    if part.is_multipart() or not msg_src.is_multipart():
                        msg.attach(part)
                        
                sResult = msg.as_string()
                
            else:
                sResult = 'No messages ' + resp
        
        except Exception as err:
            sResult = "Error-" + str(err)
        finally:
            imap.close()
    except Exception as err:
        sResult = "Error-" + str(err)
    finally:
        imap.logout()
    
    return [sResult, ret_subjects]


def send_email(str_msg):
    
    sResult = "Ok"

    msg = email.message_from_string(str_msg)

    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_default_certs()
    
    smtp = smtplib.SMTP_SSL(host='smtp.aol.com', port=465, context=context)
    try:
        smtp.ehlo()
        smtp.login(MY_EMAIL, "ojyfdxgiqnomexop")
        
        smtp.send_message(msg)
    except Exception as err:
        sResult = "Error - " + str(err)
    finally:
        smtp.quit()
     
    return sResult

    
def get_plain_email(recipient, subj, body_text):
    msg = MIMEText(body_text, 'plain', 'UTF-8')
    msg["From"] = MY_EMAIL
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subj
    
    return msg.as_string()
    
    


    

def main():
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_default_certs()
    
    ret_subjects = ""

    imap = imaplib.IMAP4_SSL(host='imap.aol.com', port=993, ssl_context=context)
    try:
        imap.login('yakov_yooy@aol.com', 'ojyfdxgiqnomexop')

        resp, exist_data = imap.select(mailbox='2Vera', readonly=False)
        sSearch=u'UNSEEN'
        resp, exist_data = imap.uid('SEARCH', None, 'UNSEEN')
        if resp != 'OK' or len(exist_data[0])==0:
#            print('No messages', resp)
            return 'No messages ' + resp
        
        smtp = smtplib.SMTP_SSL(host='smtp.aol.com', port=465, context=context)
        try:
            smtp.ehlo()
            smtp.login("yakov_yooy@aol.com", "ojyfdxgiqnomexop")

            for email_uid in exist_data[0].split():
                resp, data = imap.uid('FETCH', email_uid, '(RFC822)')

                msg_src = email.message_from_bytes(data[0][1])

                msg = MIMEMultipart()
                msg["From"] = 'yakov_yooy@aol.com'
                msg["To"] = 'veralmnva@gmail.com'
                msg["Date"] = formatdate(localtime=True)
                subject = get_native_header(msg_src.get("Subject"))
                msg["Subject"] = 'Fwd: ' + subject
                try:
                    ret_subjects += "<p>" + subject + "</p>"
                except UnicodeError:
                    ret_subjects += "<p>" + subject.translate(non_bmp_map) + "</p>"

                h_From = get_native_header(msg_src.get("From"))
                h_To = get_native_header(msg_src.get("To"))

                body_text = '\r\n'.join([
                    '-----Original Message-----',
                    'From: '+h_From,
                    'To: '+h_To,
                    'Sent: '+msg_src.get("Date"),
                    ""
                    ]).encode('UTF-8')
                msg.attach(MIMEText(body_text, 'plain', 'UTF-8'))

                for part in msg_src.walk():
                    if part.is_multipart() or not msg_src.is_multipart():
                        msg.attach(part)
                
                smtp.send_message(msg, from_addr='yakov_yooy@aol.com', to_addrs='veralmnva@gmail.com')
#                smtp.send_message(msg, from_addr='yakov_yooy@aol.com', to_addrs='yakov.yooy@yandex.ru')

        finally:
            smtp.quit()
    except Exception as err:
        ret_subjects += "<p>" + "Error - "+str(err) + "</p>"
    finally:
        imap.close()
        imap.logout()
    
    return ret_subjects




if __name__ == '__NOmain__':
    result = create_forward_email({"mailfolder": "2Vera"})
    with open(r"d:\Temp\task.txt", "wb") as tfile:
        tfile.write(result[0].encode())
    print(result[1])



if __name__ == '__main__':
    with open(r"d:\Temp\task.txt", "r") as tfile:
        str_msg = tfile.read()
    print(send_email(str_msg))
    

