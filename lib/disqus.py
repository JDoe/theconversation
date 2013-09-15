import base64
import urllib
import functools
import logging
from tornado import httpclient, escape
import hashlib
import hmac
import json
import time
import settings


class Disqus(object):
    """Base Disqus object"""

    _BASE_URL = "https://disqus.com/api/3.0/"

    def __init__(self, public, secret, forum, sentry_client):
        self._public = public
        self._secret = secret
        self._forum = forum
        self._sentry_client = sentry_client

    def subscribe(self, callback, user_info, thread_id):
        info = {
            'api_secret': self._secret,
            'remote_auth': self.get_sso(False, user_info),
            'thread': thread_id,
        }
        api_url = "%s%s" % (self._BASE_URL, 'threads/subscribe.json')
        post_body = urllib.urlencode(info)
        http = httpclient.HTTPClient()
        request = httpclient.HTTPRequest(api_url, method='POST', body=post_body)
        http.fetch(request, callback=functools.partial(self._on_subscribe, callback))

    def _on_subscribe(self, callback, result):
        result = escape.json_decode(result.body)
        if int(result.get('code')):
            # Sentry error
            self._sentry_client.captureMessage('[Disqus API] "subscribe" error: %s' %
                                                        str(result.get('code')),
                                                        disqus_response=result.get('response', ''))
            callback(None)
            return
        callback(result['response'])


    def create_thread(self, callback, user_info, thread_info):
        thread_info.update({
            'forum': self._forum,
            'api_secret': self._secret,
            'remote_auth': self.get_sso(False, user_info),
        })
        api_url = "%s%s" % (self._BASE_URL, 'threads/create.json')
        post_body = urllib.urlencode(thread_info)
        http = httpclient.HTTPClient()
        request = httpclient.HTTPRequest(api_url, method='POST', body=post_body)
        http.fetch(request, callback=functools.partial(self._on_create, callback))

    def _on_create(self, callback, result):
        result = escape.json_decode(result.body)
        if int(result.get('code')):
            # Sentry error
            self._sentry_client.captureMessage('[Disqus API] "create" Error: %s' %
                                                        str(result.get('code')),
                                                        disqus_response=result.get('response', ''))
            callback(None)
            return
        callback(result['response'])


    def get_sso(self, format_html, user_info):
        # create a JSON packet of our data attributes
        data = json.dumps(user_info)
        # encode the data to base64
        message = base64.b64encode(data)
        # generate a timestamp for signing the message
        timestamp = int(time.time())
        # generate our hmac signature
        sig = hmac.HMAC(self._secret, '%s %s' % (message, timestamp), hashlib.sha1).hexdigest()

        if format_html:
            # return a script tag to insert the sso message
            return """
    <script type="text/javascript">
        var disqus_config = function() {
            this.page.remote_auth_s3 = "%(message)s %(sig)s %(timestamp)s";
            this.page.api_key = "%(pub_key)s";
        }
    </script>""" % dict(
            message=message,
            timestamp=timestamp,
            sig=sig,
            pub_key=self._public,
            )
        else:
            return "%(message)s %(sig)s %(timestamp)s" % dict(
                    message=message,
                    timestamp=timestamp,
                    sig=sig,
            )
