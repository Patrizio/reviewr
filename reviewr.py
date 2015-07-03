import cgi
import cStringIO
import logging
import urllib

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import ndb

import webapp2


class Greeting(ndb.Model):
    """Models an individual Guestbook entry with author, content, and date."""
    author = ndb.StringProperty()
    content = ndb.StringProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)


def guestbook_key(guestbook_name=None):
    """Constructs a Datastore key for a Guestbook entity with guestbook_name"""
    return ndb.Key('Guestbook', guestbook_name or 'default_guestbook')


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.out.write('<html><body>')
        guestbook_name = self.request.get('guestbook_name')

        user = users.get_current_user()

        greetings = self.get_greetings(guestbook_name)
        
        self.response.write(greetings)

        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        self.response.write("""
          <form action="/sign?{}" method="post">
            <div><textarea name="content" rows="3" cols="60"></textarea></div>
            <div><input type="submit" value="Sign Guestbook"></div>
          </form>
          <hr>
          <form>Guestbook name: <input value="{}" name="guestbook_name">
          <input type="submit" value="switch"></form>

        </body>
      </html>""".format(urllib.urlencode({'guestbook_name': guestbook_name}),
                        cgi.escape(guestbook_name)))

    def get_greetings(self, guestbook_name):
        """
        get_greetings()
        Checks the cache to see if there are cached greetings.
        If not, call render_greetings and set the cache

        Args:
          guestbook_name: Guestbook entity group key (string).

        Returns:
          A string of HTML containing greetings.
        """
        greetings = memcache.get('{}:greetings'.format(guestbook_name))
        if greetings is None:
            greetings = self.render_greetings(guestbook_name)
            if not memcache.add('{}:greetings'.format(guestbook_name),
                                greetings, 10):
                logging.error('Memcache set failed.')
        return greetings

    def render_greetings(self, guestbook_name):
        """
        render_greetings()
        Queries the database for greetings, iterate through the
        results and create the HTML.

        Args:
          guestbook_name: Guestbook entity group key (string).

        Returns:
          A string of HTML containing greetings
        """
        greetings = ndb.gql('SELECT * '
                            'FROM Greeting '
                            'WHERE ANCESTOR IS :1 '
                            'ORDER BY date DESC LIMIT 10',
                            guestbook_key(guestbook_name))
        output = cStringIO.StringIO()
        for greeting in greetings:
            if greeting.author:
                output.write('<b>{}</b> wrote:'.format(greeting.author))
            else:
                output.write('An anonymous person wrote:')
            output.write('<blockquote>{}</blockquote>'.format(
                cgi.escape(greeting.content)))
        return output.getvalue()


class Guestbook(webapp2.RequestHandler):
    def post(self):
        # We set the same parent key on the 'Greeting' to ensure each greeting
        # is in the same entity group. Queries across the single entity group
        # are strongly consistent. However, the write rate to a single entity
        # group is limited to ~1/second.
        guestbook_name = self.request.get('guestbook_name')
        greeting = Greeting(parent=guestbook_key(guestbook_name))

        if users.get_current_user():
            greeting.author = users.get_current_user().nickname()

        greeting.content = self.request.get('content')
        greeting.put()
        memcache.delete('{}:greetings'.format(guestbook_name))
        self.redirect('/?' +
                      urllib.urlencode({'guestbook_name': guestbook_name}))


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/sign', Guestbook)],
                              debug=True)