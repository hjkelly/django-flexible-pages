import hashlib

from django.core.cache import cache
from django.core.exceptions import ValidationError, ViewDoesNotExist
from django.core.urlresolvers import get_callable, resolve
from django.db import models
from django.http import Http404
from django.utils.translation import ugettext as _

from flexible_content.models import ContentArea

from . import validators
from .managers import PageManager


class Page(ContentArea):
    """
    These pages can be placed outside of urls.py and be resolved via 
    middleware, hence the URL field below.
    """

    TITLE_HELP_TEXT = _("This will be shown on the site, and as a label "
                        "within this CMS.")
    URL_HELP_TEXT = _("This is a root-relative URL that the page should live "
                      "at. This shouldn't include the domain, but only what "
                      "comes after it. It should both start and end with a "
                      "forward slash (/), and it's a best practice not to "
                      "have any uppercase letters or symbols (other than a "
                      "hyphen).")
    SUMMARY_HELP_TEXT = _("This may be used on a list page (beneath the "
                          "title), or on search results, or in meta tags for "
                          "SEO purposes.")
    VIEW_HELP_TEXT = _("This lets you change how a page functions by "
                       "specifying a different 'view', such as "
                       "'website.views.homepage'. If that doesn't make total "
                       "sense to you, leave this alone! Note that custom "
                       "views may ignore any custom templates you specify "
                       "below.")
    TEMPLATE_HELP_TEXT = _("Enter a custom template name here, such as "
                           "'home.html' or 'posts/custom-list-page.html'. If "
                           "this isn't found in any of the template "
                           "directories, that could cause problems, so tread "
                           "carefully!")

    title = models.CharField(max_length=150, help_text=TITLE_HELP_TEXT)
    url = models.CharField(max_length=200, verbose_name="URL", unique=True,
                           validators=[validators.root_relative_url],
                           help_text=URL_HELP_TEXT)
    summary = models.CharField(max_length=250, blank=True,
                               help_text=SUMMARY_HELP_TEXT)

    # These fields allow you to customize a page without messing up your
    # lovely code. :)
    view = models.CharField(max_length=100, blank=True, null=True,
                            help_text=VIEW_HELP_TEXT)
    template = models.CharField(max_length=250, blank=True, null=True,
                                help_text=TEMPLATE_HELP_TEXT)

    # Content will be pulled in using the managed content functionality.

    objects = PageManager()

    class Meta:
        ordering = ('url',)
        verbose_name = "Page"

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return self.url

    def delete(self, *args, **kwargs):
        # Store the URL for after we delete it.
        path_to_clear = unicode(self.url)

        super(Page, self).delete(*args, **kwargs)

        # Delete this entry from the cache, to avoid confusion.
        cache.delete(Page.get_key_for_path(path_to_clear))

    def save(self, *args, **kwargs):
        # Force validation and save.
        self.full_clean()
        super(Page, self).save(*args, **kwargs)

        # Delete this entry from the cache, to avoid confusion.
        cache.delete(Page.get_key_for_path(self.url))

    @classmethod
    def get_key_for_path(cls, path):
        """
        This returns an ASCII-safe key specific to what we're caching here
        (the path/url on a given page object).
        """
        key = hashlib.sha224(path).hexdigest()
        return 'flexible_page_url_{}'.format(key)

    # VIEW RESOLUTION ---------------------------------------------------------

    def get_custom_view(self):
        """
        Return the view specified in the instance's view field, or None.
        """
        view = None

        # Try to load a custom view.
        if self.view:
            try:
                view = get_callable(self.view)
            except (ImportError, ViewDoesNotExist) as e:
                pass

        return view

    def get_urlpattern_view(self):
        """
        Return the view specified by a matching URLpattern, or None.
        """

        # Use Django's built-in to resolve this path.
        try:
            urlpattern_match = resolve(self.url)
        # If no match was found, that's cool. If we return None, it'll indicate
        # that there was no URLpattern view.
        except Http404:
            view = None
        # If we _did_ find an URLpattern match, use its view.
        else:
            view = urlpattern_match.func

        return view

    def get_view(self):
        """
        Return the view callable based on the URLs and the custom view field.

        There is a default view provided. There are two reasons why it wouldn't
        be used:
        1.  The page's view field specified an existing view.
        2.  The page's URL matches a URLpattern. For example, if you're 
            providing the content for a standard page, like: /blog/
        """
        from .views import default_page_view
        return (self.get_custom_view() or
                self.get_urlpattern_view() or
                default_page_view)

    def get_rendered_content(self, request):
        """
        Delegate to the view and return its response.
        """
        view = self.get_view()
        # Call its view with the request and this model.
        return view(request, flexible_page=self)

    # VALIDATION CODE BELOW ---------------------------------------------------

    def validate_view(self):
        """
        If they specified a view, but we can't load it, it's invalid.
        """
        if self.view and self.get_custom_view() is None:
            raise ValidationError("Custom view couldn't be loaded: {}".
                                  format(self.view))

    def clean(self):
        self.validate_view()

