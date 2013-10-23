import settings
from models.post import Post
from models.user_info import UserInfo
from base import BaseHandler
from urlparse import urlparse
import tornado
import datetime as dt
import urllib
import datetime
import time

class AdminHandler(BaseHandler):
	def get(self, action=None):
		if action == 'update_comment_counts':
			self.update_comment_counts()
		elif action == 'sort_posts':
			self.sort_posts()
		else:
			self.index()


	def index(self):
		self.render('admin/index.html', **self.vars)
		
		
	def sort_posts(self):
		posts = Post.objects(deleted=False).order_by('-date_created')
		data = []
		
		config = {
			'staff_bonus': int(self.get_argument('staff_bonus')) 
				if 'staff_bonus' in self.request.arguments else 1,
			'time_penalty_multiplier': int(self.get_argument('time_penalty_multiplier')) 
				if 'time_penalty_multiplier' in self.request.arguments else 1,
			'grace_period': int(self.get_argument('grace_period')) 
				if 'grace_period' in self.request.arguments else 6,
			'comments_multiplier': int(self.get_argument('comments_multiplier')) 
				if 'comments_multiplier' in self.request.arguments else 6,
			'votes_multiplier': int(self.get_argument('votes_multiplier')) 
				if 'votes_multiplier' in self.request.arguments else 1,
		}
		
		for i,post in enumerate(posts):
			tdelta = datetime.datetime.now() - post.date_created
			hours_elapsed = tdelta.seconds/3600 + tdelta.days*24
			
			staff_bonus = 0
			if self.is_staff(post.user.username):
				staff_bonus = config['staff_bonus']
			
			time_penalty = 0
			if hours_elapsed > config['grace_period']:
				time_penalty = hours_elapsed - config['grace_period']
			
			scores = {
				'votes': post.votes * config['votes_multiplier'],
				'comments': post.comment_count * config['comments_multiplier'],
				'time': time_penalty * config['time_penalty_multiplier'] * -1
			}
			
			score = scores['votes'] + scores['comments'] + staff_bonus + scores['time']
			
			data.append({
				'title': post.title,
				'id': post.id,
				'date_created': post.date_created,
				'hours_elapsed': hours_elapsed,
				'votes': post.votes,
				'comment_count': post.comment_count,
				'staff_bonus': staff_bonus,
				'time_penalty': time_penalty,
				'score': score,
				'scores': scores
			})
			data = sorted(data, key=lambda k: k['score'], reverse=True)
		
		self.vars.update({
			'posts': posts,
			'data': data,
			'now': datetime.datetime.now(),
			'grace_period': config['grace_period'],
			'comments_multiplier': config['comments_multiplier'],
			'time_penalty_multiplier': config['time_penalty_multiplier'],
			'staff_bonus': config['staff_bonus'],
			'votes_multiplier': config['votes_multiplier']
		})
		self.render('admin/sort_posts.html', **self.vars)

	@tornado.web.asynchronous
	@tornado.web.authenticated
	def update_comment_counts(self):
		http = tornado.httpclient.AsyncHTTPClient()

		request_vars = {
			'api_key': settings.disqus_public_key,
			'api_secret': settings.disqus_secret_key,
			'forum': settings.disqus_apikey
		}

		base_url = "https://disqus.com/api/3.0/threads/list.json"
		complete_url = base_url + "?" + urllib.urlencode(request_vars)

		def on_disqus_response(response):
			#if response.error: raise tornado.web.HTTPError(500)
			result = tornado.escape.json_decode(response.body)
	
			for thread in result['response']:
				self.write(thread['id'] + " | " + thread['identifiers'][0] + " | " + thread['title'] + " | " + str(thread['posts']) + "<br />")
				post = Post.objects(id=thread['identifiers'][0]).first()
				try:
					post.update(set__comment_count=thread['posts'])
					#post.update(set__disqus_thread_id_str=thread['id'])
					#post.update(unset__disqus_thread_id_str=True)
					self.write("&uarr; updated<br />")    
				except: 
					self.write("&uarr; NOT updated<br />")  
					
			self.finish()
		
		http.fetch(tornado.httpclient.HTTPRequest(
			url=complete_url,
			method="GET"
			), 
			callback=on_disqus_response)

	@tornado.web.asynchronous
	@tornado.web.authenticated
	def update_disqus_urls(self):
		# EVENTUALLY, this can correct the URLs disqus stores about each thread
		# for our migration
		"""
		
		def on_disqus_response(self, response):
			#
			self.finish()
		
		http.fetch({
		'url': complete_url,
		'method': "POST"
		}, 
		callback=self.on_disqus_response)
		
		"""
		pass
