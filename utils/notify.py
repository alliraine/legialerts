import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from atproto import Client as BSKYClient

from utils.bsky_helper import send_skeet
from utils.config import SOCIAL_ENABLED, EMAIL_ENABLED

curr_path = os.path.dirname(__file__)
logger = logging.getLogger(__name__)

sender = "hello@legialerts.com"
password = os.environ.get('GOOGLE_TOKEN')

def notify_social(msg):
    if not SOCIAL_ENABLED:
        logger.info("Social notifications disabled via SOCIAL_ENABLED")
        return
    bsky = BSKYClient()
    bsky.login(os.environ.get('bsky_user'), os.environ.get('bsky_pass'))
    try:
        send_skeet(msg, bsky)
    except Exception as e:
        logger.exception("Unable to send social notifications: %s", e)

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
    if not EMAIL_ENABLED:
        logger.info("Email notifications disabled via EMAIL_ENABLED")
        return
    msg = MIMEMultipart('alternative')

    # Record the MIME types of both parts - text/plain and text/html.
    part1 = MIMEText(content, 'plain')
    part2 = MIMEText(content, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(part1)
    msg.attach(part2)

    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(to)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, to, msg.as_string())
    logger.info("Email sent to %s", to)

def send_history_report(report):
    html = open(f"{curr_path}/email.html", "r")
    email = html.read()
    email = email.replace("{subject}", "New status for bills")
    email = email.replace("{preview}", "New History on bills!")
    email = email.replace("{pre-text}", "Hey there! <br><br> Here is the latest updates as of the last bot run.")
    email = email.replace("{data-table}", report)
    notify_legi_team("New status for bills", email)
    html.close()

def send_new_report(report):
    html = open(f"{curr_path}/email.html", "r")
    email = html.read()
    email = email.replace("{subject}", "New bills added to tracker")
    email = email.replace("{preview}", "New bills added to the tracker!")
    email = email.replace("{pre-text}",
                          "Hey there! <br><br> Here are the new bills that have been added to the tracker as of the latest bot run:")
    email = email.replace("{data-table}", report)
    notify_world("New bills added to tracker!", email)
    html.close()
