from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.utils import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.test.client import Client, RequestFactory

from flexible_content.default_item_types.models import PlainText
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

client = Client()


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
            Page.objects.create(title="Welcome home!", url='/')
            Page.objects.create(title="New page!", url='/')
        except (ValidationError, IntegrityError):
            pass
        else:
            self.fail("The Page model isn't properly enforcing the uniqueness "
                      "of its URL field.")

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

    def test_invalid_urls(self):
        page = Page(title="Test Page")
        try:
            for invalid_url in INVALID_PATHS:
                page.url = invalid_url.encode('utf-8')
                page.save()
        except ValidationError:
            pass
        else:
            self.fail("Bad path was allowed into the database! The "
                      "dangerous path: '{path}'".format(path=page.url))

    def test_url_normalization(self):
        try:
            test_page = Page.objects.create(title="Welcome home!",
                                            url='/posts/../posts/')
        except (ValidationError, IntegrityError):
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
            Page.objects.create(title="Company Blog", url='/blog/',
                                view='website.this.view.doesnt.exist')
        except ValidationError:
            pass
        else:
            self.fail("A non-existent view was allowed into the database!")


class PageIntegrationTest(TestCase):
    """
    Ensure that, from a client-facing side, the responses work as expected.
    """
    fixtures = ['test-data.json']

    def setUp(self):
        cache.clear()

    def test_standalone_page(self):
        """
        Case 1: Page exists only in the CMS. Can we get its content?
        """
        response = unicode(client.get('/test/'))

        self.assertIn("This is a random page!", response,
                      msg="Response was missing the page instance's title.")
        self.assertIn("Text on a random page!", response,
                      msg="Response was missing text from a content item.")
        
    def test_urlpattern_view_instead_of_default(self):
        """
        Case 2: Page exists in the CMS and as a URLpattern-driven view, so
        use the URLpattern-driven view by default.
        """
        response = unicode(client.get('/'))

        self.assertIn("<h1>Welcome!</h1>", response,
                      msg="Response was missing the page instance's title.")
        self.assertIn("<p>This is our homepage's baked-in text.</p>", response,
                      msg="Response was missing the baked-in text from the template.")
        self.assertIn("Sample text!", response,
                      msg="Response was missing text from a content item.")

    def test_urlpattern_view_overridden_by_custom(self):
        """
        Case 3: Page has a URLpattern-driven view, but is overridden by a
        custom view entered in the CMS.
        """
        # Change the page to have a custom view first.
        page = Page.objects.get(url='/')
        page.view = 'mock_project.test_app.views.custom_view'
        page.save()

        # Fetch the page!
        response = unicode(client.get('/'))

        # Make sure the stuff from the URLpattern-driven view wasn't included.
        self.assertNotIn("<p>This is our homepage's baked-in text.</p>", response,
                         msg="Response wrongly used the standard template.")

        # Ensure that the custom view's stuff shows instead.
        self.assertIn("<p>This is NOT the default template, but a custom one!</p>",
                      response,
                      msg="Response didn't include text from the custom template.")
        self.assertIn("Sample text!", response,
                      msg="Response was missing text from a content item.")

    def test_nonexistent_page(self):
        """
        Case 4: Page doesn't exist.
        """
        response = client.get('/page-does-not-exist/')
        self.assertEquals(response.status_code, 404)

    def test_custom_template(self):
        """
        Make sure custom templates are honored, too.
        """
        # Give it a custom template.
        page = Page.objects.get(url='/')
        page.template = 'pages/custom.html'
        page.save()

        # Fetch the page!
        response = unicode(client.get('/'))

        # We should find a different bit of baked-in text.
        self.assertIn("<p>This is NOT the default template, but a custom one!</p>",
                      response,
                      msg="Response didn't include text from the custom template.")

