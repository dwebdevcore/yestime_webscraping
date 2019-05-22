import os
import sys
import smtplib

from dha_poc.start import flask_app
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class MailSender:
    def __init__(self, to_addr, from_addr=flask_app.config['GMAIL_USER_ADDRESS']):
        self.to_addr = to_addr
        self.from_addr = from_addr
        self.subject = 'yestime-poc email'

    def send_email(self):
        raise NotImplementedError('You should use a subclass')

    def prepare_email(self, html):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.subject
        msg['From'] = self.from_addr
        msg['To'] = self.to_addr
        html_msg = html
        msg.attach(MIMEText(html_msg, 'html'))
        return msg


class GmailMailer(MailSender):
    def send_email(self, html):
        msg = self.prepare_email(html)
        with smtplib.SMTP(flask_app.config['GMAIL_SMTP_ADDRESS'],
                          flask_app.config['GMAIL_SMTP_PORT']) as smtpserver:
            smtpserver.ehlo()
            smtpserver.starttls()
            smtpserver.ehlo()
            smtpserver.login(flask_app.config['GMAIL_USER_ADDRESS'], flask_app.config['GMAIL_USER_PASSWORD'])
            smtpserver.send_message(msg, self.from_addr, self.to_addr)
            print('Email sent to: {0}, with address: {1}'.format(self.to_addr, self.from_addr))
        return msg.as_string()


class TextMailer(MailSender):
    def send_email(self):
        email = self.prepare_email().as_string()
        with open('output.txt', 'w') as f:
            f.write(email)
        return email


class TestMailer(MailSender):
    def send_email(self):
        return self.prepare_email().as_string()
