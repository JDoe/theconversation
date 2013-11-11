import app.basic
import tornado.web
import settings
import datetime

from lib import postsdb
from lib import userdb

class AdminHome(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self):
    if self.current_user not in settings.get('staff'):
      self.redirect('/')
    else:
      self.render('admin/admin_home.html')

class AdminStats(app.basic.BaseHandler):
  def get(self):
    if self.current_user not in settings.get('staff'):
      self.redirect('/')
    else:
      total_posts = postsdb.get_post_count()
      total_users = userdb.get_user_count()

    self.render('admin/admin_stats.html', total_posts=total_posts, total_users=total_users)

class BanUser(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self, screen_name):
    if self.current_user in settings.get('staff'):
      user = userdb.get_user_by_screen_name(screen_name)
      if user:
        user['user']['is_blacklisted'] = True
        userdb.save_user(user)
    self.redirect('/')

class BumpUp(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self, slug):
    post = postsdb.get_post_by_slug(slug)

    if self.current_user_can('super_upvote_posts'):
      post['sort_score'] += 0.25
      postsdb.save_post(post)

    self.redirect('/?sort_by=hot')

class BumpDown(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self, slug):
    post = postsdb.get_post_by_slug(slug)

    if self.current_user_can('downvote_posts'):
      post['sort_score'] -= 0.25
      postsdb.save_post(post)

    self.redirect('/?sort_by=hot')

class DeletedPosts(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self):
    if not self.current_user_can('delete_posts'):
      self.redirect('/')
    else:
      page = abs(int(self.get_argument('page', '1')))
      per_page = abs(int(self.get_argument('per_page', '10')))

      deleted_posts = postsdb.get_deleted_posts(per_page, page)
      total_count = postsdb.get_deleted_posts_count()

      self.render('admin/deleted_posts.html', deleted_posts=deleted_posts, total_count=total_count, page=page, per_page=per_page)

class DeleteUser(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self):
    if not self.current_user_can('delete_users'):
      self.redirect('/')
    else:
      msg = self.get_argument('msg', '')
      self.render('admin/delete_user.html', msg=msg)

  @tornado.web.authenticated
  def post(self):
    if not self.current_user_can('delete_users'):
      self.redirect('/')
    else:
      msg = self.get_argument('msg', '')
      post_slug = self.get_argument('post_slug', '')
      post = postsdb.get_post_by_slug(post_slug)
      if post:
        # get the author of this post
        screen_name = post['user']['screen_name']
        postsdb.delete_all_posts_by_user(screen_name)
      self.ender('admin/delete_user.html', msg=msg)

class Mute(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self, slug):
    post = postsdb.get_post_by_slug(slug)

    if post and self.current_user_can('mute_posts'):
      post['muted'] = True
      postsdb.save_post(post)

    self.redirect('/?sort_by=hot')

class ReCalculateScores(app.basic.BaseHandler):
  def get(self):
    # set our config values up
    staff_bonus = int(self.get_argument('staff_bonus', -3))
    time_penalty_multiplier = float(self.get_argument('time_penalty_multiplier', 2.0))
    grace_period = float(self.get_argument('grace_period', 6.0))
    comments_multiplier = float(self.get_argument('comments_multiplier', 3.0))
    votes_multiplier = float(self.get_argument('votes_multiplier', 1.0))
    min_votes = float(self.get_argument('min_votes', 2))

    # get all the posts that have at least the 'min vote threshold'
    posts = postsdb.get_posts_with_min_votes(min_votes)

    data = []
    for post in posts:
      # determine how many hours have elapsed since this post was created
      tdelta = datetime.datetime.now() - post['date_created']
      hours_elapsed = tdelta.seconds/3600 + tdelta.days*24

      # determine the penalty for time decay
      time_penalty = 0
      if hours_elapsed > grace_period:
        time_penalty = hours_elapsed - grace_period
      if hours_elapsed > 12:
        time_penalty = time_penalty * 1.5
      if hours_elapsed > 18:
        time_penalty = time_penalty * 2

      # get our base score from downvotes
      base_score = post['downvotes'] * -1

      # determine if we should assign a staff bonus or not
      staff_bonus = 0
      if post['user']['screen_name'] in settings.get('staff'):
        staff_bonus = staff_bonus

      # determine how to weight votes
      votes_base_score = 0
      if post['votes'] == 1 and post['comment_count'] > 2:
        votes_base_score = -2
      if post['votes'] > 8 and post['comment_count'] == 0:
        votes_base_score = -2

      # now actually calculate the score
      score = base_score
      score += (votes_base_score + post['votes'] * votes_multiplier)
      score += (post['comment_count'] * comments_multiplier)
      score += staff_bonus
      score += (time_penalty * time_penalty_multiplier * -1)

      # and save the new score
      postsdb.update_post_score(post['slug'], score)

      data.append({
        'username': post['user']['username'],
        'title': post['title'],
        'slug': post['id'],
        'date_created': post['date_created'],
        'hours_elapsed': ['hours_elapsed'],
        'votes': ['votes'],
        'comment_count': post['comment_count'],
        'staff_bonus': staff_bonus,
        'time_penalty': time_penalty,
        'score': score,
      })

    data = sorted(data, key=lambda k: k['score'], reverse=True)

    self.render('admin/recalc_scores.html', data=data, staff_bonus=staff_bonus, time_penalty_multiplier=time_penalty_multiplier, grace_period=grace_period, comments_multiplier=comments_multiplier, votes_multiplier=votes_multiplier, min_votes=min_votes)

class UnBanUser(app.basic.BaseHandler):
  @tornado.web.authenticated
  def get(self, screen_name):
    if self.current_user in settings.get('staff'):
      user = userdb.get_user_by_screen_name(screen_name)
      if user:
        user['user']['is_blacklisted'] = False
        userdb.save_user(user)
    self.redirect('/')

