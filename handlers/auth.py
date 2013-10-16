import settings
import tornado.escape
import tornado.web
import tornado.auth
import tornado.httpserver
from models.user_info import UserInfo, User, AccessToken
from base import BaseHandler
import urlparse
import time

class TwitterLoginHandler(BaseHandler, tornado.auth.TwitterMixin):
    def get_next(self):
        next = self.get_argument('next', '/')
        if next == self.request.path:
            next = '/'
        next = urlparse.urljoin(settings.base_url, next)
        return next

    @tornado.web.asynchronous
    def get(self):
        email_required = self.get_argument('email_required', '')
        close_popup = self.get_argument('close_popup', '')

        # The user is logged in but an email address is required.
        print self.get_current_user_id_str()
        if self.get_current_user_id_str()\
                and not self.get_secure_cookie('email_address')\
                and email_required:
            email_uri = '/auth/email/'
            email_uri += '?next=%s' % tornado.escape.url_escape(self.get_next())
            email_uri += '&close_popup=1' if close_popup else ''
            self.redirect(email_uri)
            return

        callback_uri = urlparse.urljoin(settings.base_url, '/auth/twitter/')
        callback_uri += '?next=%s' % tornado.escape.url_escape(self.get_next())
        callback_uri += '&email_required=1' if email_required else ''
        callback_uri += '&close_popup=1' if close_popup else ''


        if self.get_argument("oauth_token", None):
            self.get_authenticated_user(callback=self.async_callback(self._on_login))
            return
        self.authorize_redirect(callback_uri=callback_uri)

    def _on_login(self, user_obj):
        if not user_obj:
            #raise tornado.web.HTTPError(500, "Twitter authentication failed.")
            self.redirect('/auth-failed')

        #allowed_users = settings.allowed_users

        #if not user_obj['username'].lower() in settings.allowed_users:
        #if not user_obj['username'].lower() in allowed_users:
            #raise tornado.web.HTTPError(401, "Not authorized.")
        #    self.redirect('/not-authorized')

        user = {
                'auth_type': 'twitter',
                'id_str': user_obj['id_str'],
                'username': user_obj['username'],
                'fullname': user_obj['name'],
                'screen_name': user_obj['screen_name'],
                'profile_image_url': user_obj['profile_image_url'],
                'profile_image_url_https': user_obj['profile_image_url_https'],
        }
        self.set_secure_cookie("user_id_str", user_obj['id_str'])
        self.set_secure_cookie("username", user_obj['username'])
        # the one below is for wordpress
        self.set_cookie("usv_username", user_obj['username'])
        self.set_cookie("debug_username", user_obj['username'])
        access_token = user_obj['access_token']
        u = UserInfo.objects(user__id_str=user['id_str']).first()
        if u:
            u.user = User(**user)
            u.access_token = AccessToken(**access_token)
        else:
            u = UserInfo(user=User(**user), access_token=AccessToken(**access_token))
        u.save()
        if u.email_address:
            self.set_secure_cookie('email_address', u.email_address)
            if self.get_argument('close_popup', ''):
                self.redirect('/auth/close_popup/')
                return
        if not u.email_address and self.get_argument('email_required', ''):
            email_uri = '/auth/email/'
            email_uri += '?next=%s' % tornado.escape.url_escape(self.get_next())
            self.redirect(email_uri)
        self.redirect(self.get_next())


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_all_cookies()
        next = self.get_argument('next', '/')
        self.redirect(next)


class CloseHandler(BaseHandler):
    def get(self):
        self.render('auth/close_popup.html')
