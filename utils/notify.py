import os
import smtplib
from email.mime.text import MIMEText

sender = "hello@legialerts.com"
password = os.environ.get('GOOGLE_TOKEN')

def notify_legi_team(subject, content):
    to = ["hello@legialerts.com", "allichapman22@gmail.com"]
    send_email(to, subject, content)

def notify_dev_team(subject, content):
    to = ["hello@legialerts.com", "allichapman22@gmail.com"]
    send_email(to, subject, content)

def notify_world(subject, content):
    to = ["hello@legialerts.com", "allichapman22@gmail.com"]
    send_email(to, subject, content)

def send_email(to, subject, content):
    msg = MIMEText("html", content)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, to, msg.as_string())
    print("Message sent!")
