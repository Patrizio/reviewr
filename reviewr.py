import cgi
import cStringIO
import logging
import urllib
import os

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class Review(ndb.Model):
    """Models an individual Review entry with author, content, and date."""
    author = ndb.StringProperty()
    content = ndb.StringProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)


def session_key(session_name=None):
    """Constructs a Datastore key for a Session entity with session_name"""
    return ndb.Key('Session', session_name or 'default_session')


class MainPage(webapp2.RequestHandler):
    def get(self):
        session_name = self.request.get('session_name')

        user = users.get_current_user()

        reviews = self.get_reviews(session_name)
        
        #self.response.write(reviews)

        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'user': user,
            'reviews': reviews,
            'session_name': urllib.quote_plus(session_name),
            'url': url,
            'url_linktext': url_linktext,
        }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

    def get_reviews(self, session_name):
        """
        get_reviews()
        Checks the cache to see if there are cached reviews.
        If not, call render_reviews and set the cache

        Args:
          session_name: Session entity group key (string).

        Returns:
          Collection of reviews.
        """
        reviews = memcache.get('{}:reviews'.format(session_name))
        if reviews is None:
            reviews = self.render_reviews(session_name)
            if not memcache.add('{}:reviews'.format(session_name),
                                reviews, 20):
                logging.error('Memcache set failed.')
        return reviews

    def render_reviews(self, session_name):
        """
        render_reviews()
        Queries the database for reviews.

        Args:
          session_name: Session entity group key (string).

        Returns:
          Collection of reviews.
        """
       
        reviews_query = Review.query(ancestor=session_key(session_name)).order(-Review.date)
        reviews = reviews_query.fetch(20)

        return reviews


class Session(webapp2.RequestHandler):
    def post(self):
        # We set the same parent key on the 'Review' to ensure each reviews
        # is in the same entity group. Queries across the single entity group
        # are strongly consistent. However, the write rate to a single entity
        # group is limited to ~1/second.
        session_name = self.request.get('session_name')
        review = Review(parent=session_key(session_name))

        if users.get_current_user():
            review.author = users.get_current_user().nickname()

        review.content = self.request.get('content')
        review.put()
        memcache.delete('{}:reviews'.format(session_name))
        self.redirect('/?' +
                      urllib.urlencode({'session_name': session_name}))


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/sign', Session)],
                              debug=True)