# coding=utf-8
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.utils import IntegrityError
from django.http import Http404, HttpResponse
from django.test import SimpleTestCase, TestCase
from django.test.client import Client, RequestFactory

from mock_project.test_app import views as test_app_views

from .models import Page
from .views import default_page_view


VALID_PATHS = [
    '/',
    '/blah/',
    '/test-slug/',
    '/two/levels/',
    '/three/darn/levels-with-dashes-and-stuff/',
    '/numbers-are-c001-too/',
]

INVALID_PATHS = [
    '',
    'asdf',
    '/asdf',
    'asdf/',
    'asdf.jpg',
    '/asdf.jpg',
    'asdf.jpg/',
    '/spec!al/',
    '/ch@racters/',
    '/no+/',
    '/UPPERCASE-SHOULD-NOT-WORK/',
    '/underscores_are_ugly/',
    '/allowe|)/',
    u'/german-letter-\u00DF/',
    u'/encyclop\u00E6dia/',
]

rf = RequestFactory()


class PageUnitTest(SimpleTestCase):

    def test_get_absolute_url(self):
        """
        The URL should contain exactly what's on the url field.
        """
        test_url = '/my-funky-url/'
        self.assertEqual(Page(url=test_url).get_absolute_url(), test_url)

    # VIEW RESOLUTION ---------------------------------------------------------

    def test_get_custom_view(self):
        """
        If there's a custom view, make sure we get that as the view.
        """
        page = Page(url='/',
                    view='mock_project.test_app.views.custom_view')
        self.assertEqual(page.get_view(), test_app_views.custom_view)

    def test_get_urlpattern_view(self):
        """
        There's no custom view, but a matching URLpattern, so return its view.
        """
        page = Page(url='/')
        self.assertEqual(page.get_view(), test_app_views.homepage_view)

    def test_get_default_view(self):
        """
        When there's no custom view or matching URLpattern, return the default.
        """
        page = Page(url='/my-page/')
        self.assertEqual(page.get_view(), default_page_view)

    def test_get_custom_view_that_doesnt_exist_returns_urlpattern(self):
        """
        This view doesn't exist, but there's a URLpattern view we should get
        as a backup.
        """
        page = Page(url='/',
                    view='mock_project.test_app.views.nonexistent_view')
        self.assertEqual(page.get_view(), test_app_views.homepage_view)

    def test_get_custom_view_that_doesnt_exist_returns_default(self):
        """
        This view doesn't exist; we should get the default view.
        """
        page = Page(url='/my-page/',
                    view='mock_project.test_app.views.nonexistent_view')
        self.assertEqual(page.get_view(), default_page_view)

    # RENDERING THE PAGE ------------------------------------------------------

    def test_get_rendered_content_custom(self):
        request = rf.get('/')
        page = Page(title="Custom View", url='/',
                    view='mock_project.test_app.views.custom_view')
        html = unicode(page.get_rendered_content(request))
        # We should find the text from custom_view in this response.
        self.assertTrue("custom view" in html)

    def test_get_rendered_content_urlpattern(self):
        request = rf.get('/')
        page = Page(title="Standard Homepage", url='/')
        html = unicode(page.get_rendered_content(request))
        # We should find the text from custom_view in this response.
        self.assertTrue("standard homepage view" in html)

    def test_get_rendered_content_default(self):
        request = rf.get('/my-page/')
        title = "Custom Page with Default View"
        page = Page.objects.create(title=title, url='/my-page/')
        response = page.get_rendered_content(request)
        response.render()
        html = unicode(response)
        # We should find the text from custom_view in this response.
        self.assertTrue(title in html)


class PageEfficiencyTest(TestCase):
    fixtures = ['test-data.json']

    def setUp(self):
        # Enable this so we can count queries.
        settings.DEBUG = True
        connection.queries = []

        # Wipe out the cache, just for numbers' sake.
        cache.clear()

    def tearDown(self):
        # Disable DEBUG after each test (most importantly, after the last).
        settings.DEBUG = False

    def test_get_for_valid_url(self):
        """
        Make sure the database is only hit once when resolving this page.
        """
        QUERIES = 5

        # Query for it several times.
        results = []
        for i in range(QUERIES):
            results.append(Page.objects.get_for_url('/'))

        # Make sure we only queried once.
        self.assertEqual(len(connection.queries), 1,
                         msg="We queried more than once for the same page - "
                             "a total of {} times.".
                             format(len(connection.queries)))

        # Make sure the first result matched the last.
        self.assertEqual(results[0], results[QUERIES-1],
                         msg="The first result didn't match the last, when "
                             "resolving an existing page multiple times. "
                             "First: {};  Last: {}".format(results[0],
                                                           results[QUERIES-1]))

    def test_get_for_nonexistent_url(self):
        """
        Make sure the database is only hit once when missing a page.
        """
        QUERIES = 5

        # Query for it several times.
        results = []
        for i in range(QUERIES):
            try:
                results.append(Page.objects.get_for_url('/not-a-real-page/'))
            except Page.DoesNotExist:
                results.append(None)

        # Make sure we only queried once.
        self.assertEqual(len(connection.queries), 1,
                         msg="The system queried {} times for the same, non-"
                             "existent page. It should have queried once.".
                             format(len(connection.queries)))

        # Make sure it didn't return a page.
        self.assertEqual(results[0], None,
                         msg="We were given a page when testing a non-"
                             "existent URL: {}".format(results[0]))

        # Make sure the result was consistent.
        self.assertEqual(results[0], results[QUERIES-1],
                         msg="The first result didn't match the last when "
                             "testing a non-existent URL.")

    def test_get_for_invalid_url(self):
        """
        Make sure the page resolution unit is smart enough not to query for
        URLs that shouldn't be allowed in the database.
        """

        for invalid_path in INVALID_PATHS:
            try:
                Page.objects.get_for_url(invalid_path)
            except Page.DoesNotExist:
                pass
        # Fail if it hit the database at all.
        self.assertEqual(len(connection.queries), 0,
                         msg="The system still queried {} times for pages "
                             "that can't exist, because its path isn't valid.".
                             format(len(connection.queries)))

    def test_cache_emptied_upon_delete(self):
        """
        If a page is cached, deleting it should remove it from the cache.
        """
        PAGE_URL = '/'

        # Figure out what it'll be labeled as in the cache.
        cache_key = Page.get_key_for_path(PAGE_URL)

        # Hit the homepage.
        page = Page.objects.get_for_url('/')
        # That should have put it in the cache.
        self.assertIsInstance(cache.get(cache_key, None), Page)

        # Delete the page!
        page.delete()
        # That should have removed it from the cache.
        cache_value = cache.get(cache_key)
        self.assertNotIsInstance(cache.get(cache_key, None), Page)

    def test_cache_emptied_upon_save(self):
        """
        If a page is cached, saving it should remove it from the cache.
        """
        PAGE_URL = '/'

        # Figure out what it'll be labeled as in the cache.
        cache_key = Page.get_key_for_path(PAGE_URL)

        # Hit the homepage.
        page = Page.objects.get_for_url('/')
        # That should have put it in the cache.
        self.assertIsInstance(cache.get(cache_key, None), Page)

        # Save the page.
        page.save()
        connection.queries = []
        # That should have removed it from the cache, so this will incur 
        # another query.
        page = Page.objects.get_for_url('/')
        self.assertEqual(len(connection.queries), 1)


class PageIntegrityTest(TestCase):
    def test_url_unique(self):
        try:
            homepage = Page.objects.create(title="Welcome home!", url='/')
            duplicate_page = Page.objects.create(title="New page!",
                url='/')
        except (ValidationError, IntegrityError) as e:
            pass
        else:
            self.fail("The Page model isn't properly enforcing the uniqueness "
                      "of its URL field.")
        finally:
            Page.objects.all().delete()

    def test_valid_urls(self):
        page = Page(title="Test Page")
        try:
            for valid_url in VALID_PATHS:
                page.url = valid_url
                page.save()
        except ValidationError as e:
            self.fail("Perfectly good path ran into a problem when saving. "
                      "The rejected path: '{path}'\n"
                      "Reason: {reason}".format(path=page.url, reason=str(e)))
        finally:
            Page.objects.all().delete()

    def test_invalid_urls(self):
        page = Page(title="Test Page")
        try:
            for invalid_url in INVALID_PATHS:
                page.url = invalid_url.encode('utf-8')
                page.save()
        except ValidationError as e:
            pass
        else:
            self.fail("Bad path was allowed into the database! The "
                      "dangerous path: '{path}'".format(path=page.url))
        finally:
            Page.objects.all().delete()

    def test_url_normalization(self):
        try:
            test_page = Page.objects.create(title="Welcome home!",
                                            url='/posts/../posts/')
        except (ValidationError, IntegrityError) as e:
            pass
        else:
            # If it passed, it's only okay if it got normalized down to what 
            # it would be resolved to in a file system.
            if test_page.url != '/posts/':
                self.fail("The Page model isn't properly normalizing URLs.")
        finally:
            Page.objects.all().delete()

    def test_invalid_view(self):
        try:
            blog = Page.objects.create(title="Company Blog",
                                       url='/blog/',
                                       view='website.this.view.doesnt.exist')
        except ValidationError as e:
            pass
        else:
            self.fail("A non-existent view was allowed into the database!")
        finally:
            Page.objects.all().delete()


"""
class PageIntegrationTest(TestCase):
    def setUp(self):
        # Put a client on the instance so we don't have to re-create one.
        self.client = Client()

        # Insert the data all of these test cases needs.
        try:
            # Don't create a URLpattern only page: /events/
            # Create a DB-only page.
            about = Page.objects.create(title="About Us", url='/about/')
            # Create a hybrid page.
            misleading_page = Page(title="Posts... or posted events!",
                                   url='/posts/',
                                   view='ipanema.events.views.event_list')
            misleading_page.save()
        except (IntegrityError, ValidationError) as e:
            raise Exception("One or more of the pages was rejected while "
                            "trying to set up the pages. This shouldn't "
                            "happen! Exception: \n{}\nURL: {}".format(str(e)))

    def tearDown(self):
        Page.objects.all().delete()

    def test_request_non_existent_page(self):
        response = self.client.get('/this-page/should-not-exist/')

        # If we didn't get a 404, that's not right:
        if response.status_code != 404:
            self.fail("Got a response other than 404 for a non-existent page: "
                      "got {} instead.".format(response.status_code))

    def test_request_urlpattern_page(self):
        response = self.client.get('/events/')
        # If we didn't get a 200, that's a problem.
        if response.status_code != 200:
            self.fail("Got a response other than 200 for a page in "
                      "URLpatterns: got {} instead.".
                      format(response.status_code))
        # Make sure the content is correct!
        if "<h1>Events</h1>" not in response.content:
            self.fail("The rendered events listing page didn't have an h1 "
                      "with the default title, 'Events'.")

    def test_request_cms_page(self):
        response = self.client.get('/about/')

        # If we didn't get a 200, that's a problem.
        if response.status_code != 200:
            self.fail("Got a response other than 200 for a page in the DB: "
                      "got {} instead.".format(response.status_code))
        # Make sure the content is correct!
        if "<h1>About Us</h1>" not in response.content:
            self.fail("The rendered about page didn't have an h1 with the "
                      "title 'About Us'.")

    def test_request_hybrid_page(self):
        response = self.client.get('/posts/')

        # If we didn't get a 200, that's a problem.
        if response.status_code != 200:
            self.fail("Got a response other than 200 for a page in the DB "
                      "and URLpatterns: got {} instead.".
                      format(response.status_code))
        # Make sure the content is correct!
        if "<h1>Posts... or posted events!</h1>" not in response.content:
            self.fail("The rendered hybrid posts page didn't have the Page "
                      "instance's title on it.")
"""


