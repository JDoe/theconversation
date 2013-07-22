import settings
import tornado.web
import tornado.auth
import tornado.httpserver
import os
from lib.sanitize import html_sanitize, linkify
from base import BaseHandler
import mongoengine
from models import User, Tag, Post

from urlparse import urlparse
from BeautifulSoup import BeautifulSoup
from datetime import datetime
from lib.recaptcha import RecaptchaMixin
from lib.score import calculate_score
import datetime as dt

class PostHandler(BaseHandler, RecaptchaMixin):
    def __init__(self, *args, **kwargs):
        super(PostHandler, self).__init__(*args, **kwargs)
        self.vars.update({
            'recaptcha_render': self.recaptcha_render,
        })

    def index(self):
        # list posts
        query = {}
        tag = self.get_argument('tag', '').lower()
        if tag:
            query.update({
                'tags': tag,
            })
        ordering = {
            'hot': ('-score', '-date_created'),
            'new': ('-date_created', '-score')
        }
        per_page = 50
        sort_by = self.get_argument('sort_by', 'hot')
        page = abs(int(self.get_argument('page', '1')))
        posts = Post.objects(featured=False, deleted=False, **query).order_by(*ordering[sort_by])
        posts = posts[(page - 1) * per_page:(page - 1) * per_page + (per_page -1)]
        post_count = Post.objects(featured=False, deleted=False, **query).count()
        featured_posts = list(Post.objects(featured=True, deleted=False, **query).order_by('-date_featured'))

        for post in featured_posts:
            soup = BeautifulSoup(post['body_html'])
            post['body_html'] = soup.prettify()
            #try:
            #    post['body_html'] = truncate(post['body_html'], 500, ellipsis='...')
            #except:
            #    pass
            #post['body_html'] = html_sanitize_preview(post['body_html'])

        tags = Tag.objects()
        self.vars.update({
            'sort_by': sort_by,
            'posts': posts,
            'post_count': post_count,
            'page': page,
            'per_page': per_page,
            'featured_posts': featured_posts,
            'tags': tags,
            'current_tag': tag,
            'urlparse': urlparse,
        })
        self.render('post/index.html', **self.vars)

    def detail(self, id):
        post = Post.objects(id=id).first()
        if not post:
            raise tornado.web.HTTPError(404)
        if post.deleted:
            self.write("Deleted.")
            return
        self.vars.update({'post': post})
        self.render('post/get.html', **self.vars)

    @tornado.web.asynchronous
    def new(self, model=Post(), errors={}, recaptcha_error=False):
        # Link creation page
        self.vars.update({
            'model': model,
            'errors': errors,
            'edit_mode': False,
            'recaptcha_error': recaptcha_error,
        })
        self.render('post/new.html', **self.vars)

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

        # Content
        body_raw = attributes.get('body_raw', '')
        body_html = html_sanitize(body_raw)

        protected_attributes = ['date_created', '_xsrf', 'user', 'votes', 'voted_users']
        for attribute in protected_attributes:
            if attributes.get(attribute):
                del attributes[attribute]

        featured = False
        date_featured = None
        if self.is_admin() and attributes.get('featured'):
            featured = True
            date_featured = datetime.now()

        date_created = dt.datetime.now()
        attributes.update({
            'user': User(**self.get_current_user()),
            'body_html': body_html,
            'featured': featured,
            'date_featured': date_featured,
            'tags': tag_names,
            'date_created': date_created,
            'score': calculate_score(1, date_created),
            'votes': 1,
            'voted_users': [User(**self.get_current_user())]
        })

        post = Post(**attributes)
        if not recaptcha_response:
            self.new(model=post, recaptcha_error=True)
            return

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

        id_str = self.get_current_user()['id_str']
        if not (self.is_admin() or id_str == post.user['id_str']):
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

        # Content
        body_raw = attributes.get('body_raw', '')
        body_html = html_sanitize(body_raw)

        protected_attributes = ['date_created', '_xsrf', 'user', 'votes', 'voted_users']
        for attribute in protected_attributes:
            if attributes.get(attribute):
                del attributes[attribute]

        featured = post.featured
        date_featured = post.date_featured
        if self.is_admin() and attributes.get('featured') and not featured:
            featured = True
            date_featured = datetime.now()
        if self.is_admin() and not attributes.get('featured'):
            featured = False
            date_featured = None

        attributes.update({
            'user': User(**self.get_current_user()),
            'body_html': body_html,
            'featured': featured,
            'date_featured': date_featured,
            'deleted': True if attributes.get('deleted') else False,
            'tags': tag_names,
            'score': calculate_score(post.votes, post.date_created),
        })
        post.set_fields(**attributes)
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

        id_str = self.get_current_user()['id_str']
        if not (id_str == post.user['id_str'] or self.is_admin()):
            raise tornado.web.HTTPError(403)

        # Modification page
        self.vars.update({
            'model': post,
            'errors': errors,
            'edit_mode': True,
        })
        self.render('post/new.html', **self.vars)


    def get(self, id='', action=''):
        if action == 'upvote' and id:
            self.upvote(id)
        elif action == 'feature' and id:
            self.feature(id)
        else:
            super(PostHandler, self).get(id, action)

    @tornado.web.authenticated
    def feature(self, id):
        if not self.is_admin():
            raise tornado.web.HTTPError(403)

        try:
            post = Post.objects.get(id=id)
        except Post.DoesNotExist:
            raise tornado.web.HTTPError(404)
        if not post.featured:
            post.featured = True
            post.date_featured = datetime.now()
            post.save()
        self.redirect('/')

    @tornado.web.authenticated
    def upvote(self, id):
        id_str = self.get_current_user()['id_str']
        user_q = {'$elemMatch': {'id_str': id_str}}
        post = Post.objects(id=id).fields(voted_users=user_q, votes=True, date_created=True).first()
        if not post:
            raise tornado.web.HTTPError(404)
        detail = self.get_argument('detail', '')
        if post.voted_users and not self.is_admin():
            self.redirect(('/posts/%s?error' % post.id) if detail else '/?error')
            return

        new_score = calculate_score(post.votes+1, post.date_created)
        post.update(inc__votes=1, set__score=new_score)
        if not post.voted_users:
            post.update(push__voted_users=User(**self.get_current_user()))

        self.redirect(('/posts/%s' % post.id) if detail else '/')
