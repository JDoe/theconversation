import settings
import tornado.web
import tornado.auth
import tornado.httpserver
import os
from lib.sanitize import html_sanitize, linkify
from lib.hackpad import HackpadAPI
from base import BaseHandler
import mongoengine
from models import User, Tag, Content, Post

from urlparse import urlparse
from BeautifulSoup import BeautifulSoup

class PostHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(PostHandler, self).__init__(*args, **kwargs)

    def detail(self, id):
        post = Post.objects(id=id).first()
        if not post:
            raise tornado.web.HTTPError(404)
        if post.deleted:
            self.write("Deleted.")
            return
        self.vars.update({'post': post})
        self.render('posts/get.html', **self.vars)

    @tornado.web.asynchronous
    def new(self, model=Post(), errors={}):
        hackpad_api = HackpadAPI(settings.hackpad['oauth_client_id'],
                                            settings.hackpad['oauth_secret'],
                                            domain=settings.hackpad['domain'])
        def hpad_created(hpad_json):
            model.hackpad_url = 'https://%s.hackpad.com/%s'\
                                            % (settings.hackpad['domain'], hpad_json['padId'])
            # Link creation page
            self.vars.update({
                'model': model,
                'errors': errors,
                'edit_mode': False,
            })
            self.render('posts/new.html', **self.vars)

        hackpad_api.create(hpad_created)

    def create(self):
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

        # Content
        body_raw = attributes.get('body_raw', '')
        body_html = html_sanitize(body_raw)

        # Handle Hackpad
        if attributes.get('has_hackpad'):
            attributes['has_hackpad'] = True

        attributes.update({
            'user': User(**self.get_current_user()),
            'body_html': body_html,
            'featured': True if attributes.get('featured') else False,
            'tags': tag_names,
        })
        post = Post(**attributes)
        try:
            post.save()
        except mongoengine.ValidationError, e:
            self.new(model=post, errors=e.errors)
            return

        self.redirect('/posts/%s' % post.id)

    def update(self, id):
        post = Post.objects(id=id).first()
        if not post:
            raise tornado.web.HTTPError(404)

        if not self.get_current_user()['username'] == post.user['username']:
            raise tornado.web.HTTPError(401)

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

        # Content
        body_raw = attributes.get('body_raw', '')
        body_html = html_sanitize(body_raw)

        # Handle Hackpad
        if attributes.get('has_hackpad'):
            attributes['has_hackpad'] = True

        attributes.update({
            'user': User(**self.get_current_user()),
            'body_html': body_html,
            'featured': True if attributes.get('featured') else False,
            'tags': tag_names,
        })

        if attributes['_xsrf']:
            del attributes['_xsrf']

        attributes = {('set__%s' % k): v for k, v in attributes.iteritems()}
        post.update(**attributes)
        try:
            post.save()
        except mongoengine.ValidationError, e:
            self.edit(post.id, errors=e.errors)
            return

        self.redirect('/posts/%s' % post.id)

    def edit(self, id, errors={}):
        post = Post.objects(id=id).first()
        if not post:
            raise tornado.web.HTTPError(404)

        if not self.get_current_user()['username'] == post.user['username']:
            raise tornado.web.HTTPError(401)

        # Modification page
        self.vars.update({
            'model': post,
            'errors': errors,
            'edit_mode': True,
        })
        self.render('posts/new.html', **self.vars)


    @tornado.web.authenticated
    def get(self, id='', action=''):
        if action == 'upvote' and id:
            self.upvote(id)
        else:
            super(PostHandler, self).get(id, action)

    def upvote(self, id):
        username = self.get_current_user()['username']
        user_q = {'$elemMatch': {'username': username}}
        link = Link.objects(id=id).fields(voted_users=user_q).first()
        if not link:
            raise tornado.web.HTTPError(404)
        detail = self.get_argument('detail', '')
        if link.voted_users:
            self.redirect(('/posts/%s?error' % link.id) if detail else '/?error')
            return


        link.update(inc__votes=1)
        link.update(push__voted_users=User(**self.get_current_user()))

        self.redirect(('/posts/%s' % link.id) if detail else '/')
