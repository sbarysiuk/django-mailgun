# -*- coding: utf-8 -*-

import requests

from email.MIMEBase import MIMEBase
from webob.multidict import MultiDict

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class MailgunAPIError(Exception):
    pass

class MailgunBackend(BaseEmailBackend):
    """A Django Email backend that uses mailgun.
    """

    def __init__(self, fail_silently=False, *args, **kwargs):
        access_key, server_name = (kwargs.pop('access_key', None),
                                   kwargs.pop('server_name', None))

        super(MailgunBackend, self).__init__(
                        fail_silently=fail_silently,
                        *args, **kwargs)

        try:
            self._access_key = access_key or getattr(settings, 'MAILGUN_ACCESS_KEY')
            self._server_name = server_name or getattr(settings, 'MAILGUN_SERVER_NAME')
        except AttributeError:
            if fail_silently:
                self._access_key, self._server_name = None
            else:
                raise

        self._api_url = "https://api.mailgun.net/v2/%s/" % self._server_name

    def open(self):
        """Stub for open connection, all sends are done over HTTP POSTs
        """
        pass

    def close(self):
        """Close any open HTTP connections to the API server.
        """
        pass

    def _send(self, email_message):
        """A helper method that does the actual sending."""

        if not email_message.to:
            return False

        from_email = sanitize_address(email_message.from_email, email_message.encoding)

        # \n can be added by python core email address encoder if address contains unicode symbols from
        # different charsets. see https://github.com/python/cpython/blame/2.7/Lib/email/header.py#L339
        to = [ sanitize_address(addr, email_message.encoding).replace('\n', '')
               for addr in email_message.to ]

        data = {
            "to": ', '.join(to),
            "from": from_email,
        }

        if email_message.cc:
            data['cc'] = ', '.join([ sanitize_address(addr, email_message.encoding)
                           for addr in email_message.cc ])

        if email_message.bcc:
            data['bcc'] = ', '.join([ sanitize_address(addr, email_message.encoding)
                            for addr in email_message.bcc ])

        if hasattr(email_message, 'alternatives') and email_message.alternatives:
            for alt in email_message.alternatives:
                if alt[1] == 'text/html':
                    data['html'] = alt[0]
                    break

        extra_headers = email_message.extra_headers

        if 'X-Mailgun-Dkim' in extra_headers:
            data['o:dkim'] = extra_headers.pop('X-Mailgun-Dkim')

        if len(extra_headers) > 0:
            headers = {}

            for k, v in extra_headers.iteritems():
                headers['h:{0}'.format(k)] = v

            data.update(headers)

        data['subject'] = email_message.subject
        data['text'] = email_message.body

        files = MultiDict()

        if email_message.attachments:
            for attachment in email_message.attachments:
                if isinstance(attachment, MIMEBase):
                    files.add('attachment', (attachment.get_filename(), attachment.get_payload()))
                else:
                    files.add('attachment', (attachment[0], attachment[1]))

        try:
            r = requests.\
                post(self._api_url + "messages",
                     auth=("api", self._access_key),
                     data=data,
                     files=files)
        except:
            if not self.fail_silently:
                raise
            return False

        if r.status_code != 200:
            if not self.fail_silently:
                raise MailgunAPIError(r)

            return False

        return True

    def send_messages(self, email_messages):
        """Sends one or more EmailMessage objects and returns the number of
        email messages sent.
        """
        if not email_messages:
            return

        num_sent = 0
        for message in email_messages:
            if self._send(message):
                num_sent += 1

        return num_sent
