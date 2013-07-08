import settings
import tornado.web
import tornado.auth
import tornado.httpserver
import os
from lib.sanitize import html_sanitize, linkify
from base import BaseHandler
import mongoengine
from models import Link, User, Tag, Content

from urlparse import urlparse
from BeautifulSoup import BeautifulSoup
from lib.recaptcha import RecaptchaMixin

class LinkHandler(BaseHandler, RecaptchaMixin):
    def __init__(self, *args, **kwargs):
        super(LinkHandler, self).__init__(*args, **kwargs)
        self.vars.update({
            'recaptcha_render': self.recaptcha_render
        })

    def detail(self, id):
        link = Link.objects(id=id).first()
        if not link:
            raise tornado.web.HTTPError(404)
        if link.deleted:
            self.write("Deleted.")
            return
        if link.url:
            link.url_domain = urlparse(link.url).netloc
        self.vars.update({'link': link})
        self.render('links/get.html', **self.vars)

    @tornado.web.asynchronous
    def new(self, model=Link(), errors={}, recaptcha_error=False):
        # Link creation page
        self.vars.update({
            'model': model,
            'errors': errors,
            'edit_mode': False,
            'recaptcha_error': recaptcha_error,
        })
        self.render('links/new.html', **self.vars)

    @tornado.web.asynchronous
    def create(self):
        self.recaptcha_validate(self._on_validate)

    def _on_validate(self, recaptcha_response):
        attributes = {k: v[0] for k, v in self.request.arguments.iteritems()}

        # Handle tags
        tag_names = attributes.get('tags', '').split(',')
        tag_names = [t.strip().lower() for t in tag_names]
        tag_names = [t for t in tag_names if t]
        exising_names = [t.name for t in Tag.objects(name__in=tag_names)]
        for name in tag_names:
            if name in exising_names:
                continue
            tag = Tag(name=name)
            tag.save()

        protected_attributes = ['_xsrf', 'user', 'votes', 'voted_users']
        for attribute in protected_attributes:
            if attributes.get(attribute):
                del attributes[attribute]

        attributes.update({
            'user': User(**self.get_current_user()),
            'featured': False,
            'tags': tag_names,
        })

        link = Link(**attributes)
        if not recaptcha_response:
            self.new(model=link, recaptcha_error=True)
            return

        try:
            link.save()
        except mongoengine.ValidationError, e:
            self.new(model=link, errors=e.errors)
            return

        self.redirect('/links/%s' % link.id)

    def update(self, id):
        link = Link.objects(id=id).first()
        if not link:
            raise tornado.web.HTTPError(404)

        id_str = self.get_current_user()['id_str']
        if not (id_str == link.user['id_str'] or self.is_admin()):
            raise tornado.web.HTTPError(403)

        attributes = {k: v[0] for k, v in self.request.arguments.iteritems()}
        # Handle tags
        tag_names = attributes.get('tags', '').split(',')
        tag_names = [t.strip().lower() for t in tag_names]
        tag_names = [t for t in tag_names if t]
        exising_names = [t.name for t in Tag.objects(name__in=tag_names)]
        for name in tag_names:
            if name in exising_names:
                continue
            tag = Tag(name=name)
            tag.save()

        protected_attributes = ['_xsrf', 'user', 'votes', 'voted_users']
        for attribute in protected_attributes:
            if attributes.get(attribute):
                del attributes[attribute]

        attributes.update({
            'user': User(**self.get_current_user()),
            'featured': False,
            'deleted': True if attributes.get('deleted') else False,
            'tags': tag_names,
        })
        link.set_fields(**attributes)
        try:
            link.save()
        except mongoengine.ValidationError, e:
            self.edit(link.id, errors=e.errors)
            return

        self.redirect('/links/%s' % link.id)

    def edit(self, id, errors={}):
        link = Link.objects(id=id).first()
        if not link:
            raise tornado.web.HTTPError(404)

        id_str = self.get_current_user()['id_str']
        if not (self.is_admin() or id_str == link.user['id_str']):
            raise tornado.web.HTTPError(403)

        # Link modification page
        self.vars.update({
            'model': link,
            'errors': errors,
            'edit_mode': True,
        })
        self.render('links/new.html', **self.vars)

    @tornado.web.authenticated
    def get(self, id='', action=''):
        if action == 'upvote' and id:
            self.upvote(id)
        else:
            super(LinkHandler, self).get(id, action)

    def upvote(self, id):
        id_str = self.get_current_user()['id_str']
        user_q = {'$elemMatch': {'id_str': id_str}}
        link = Link.objects(id=id).fields(voted_users=user_q).first()
        if not link:
            raise tornado.web.HTTPError(404)
        detail = self.get_argument('detail', '')
        if link.voted_users and not self.is_admin():
            self.redirect(('/links/%s?error' % link.id) if detail else '/?error')
            return

        link.update(inc__votes=1)
        if not link.voted_users:
            link.update(push__voted_users=User(**self.get_current_user()))

        self.redirect(('/links/%s' % link.id) if detail else '/')
