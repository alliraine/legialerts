from mailersend import emails

def notify_legi_team(subject, content):
    to = [{"email": "hello@legialerts.com"}]
    send_email(to, subject, content)

def notify_dev_team(subject, content):
    to = [{"email": "hello@legialerts.com"}]
    send_email(to, subject, content)

def notify_world(subject, content):
    to = [{"email": "hello@legialerts.com"}]
    send_email(to, subject, content)

def send_email(to, subject, content):
    # assigning NewEmail() without params defaults to MAILERSEND_API_KEY env var
    mailer = emails.NewEmail()

    # define an empty dict to populate with mail values
    mail_body = {}

    mail_from = {
        "name": "LegiAlerts",
        "email": "alerts@legialerts.com",
    }

    recipients = to

    reply_to = {
        "name": "LegiAlerts",
        "email": "hello@legialerts.com",
    }

    mailer.set_mail_from(mail_from, mail_body)
    mailer.set_mail_to(recipients, mail_body)
    mailer.set_subject(subject, mail_body)
    mailer.set_html_content(content, mail_body)
    mailer.set_plaintext_content(content, mail_body)
    mailer.set_reply_to(reply_to, mail_body)

    # using print() will also return status code and data
    print(mailer.send(mail_body))