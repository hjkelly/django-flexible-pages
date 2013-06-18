from .models import Page


class PageMiddleware(object):
    def process_request(self, request):
        """
        Before even hitting URLs.py, see if a given URL is covered by a Page.
        """
        # Check for this page in the CMS.
        try:
            cms_match = Page.objects.get_for_url(request.path)
        # If none was found, give up and leave it to URLpatterns.
        except Page.DoesNotExist:
            return

        # Should we just let the URLpattern view do its thing, or should we
        # render here based on the custom (or default) view?
        if not cms_match.get_custom_view() and cms_match.get_urlpattern_view():

            # The URLpattern view should take precedence, so give up.
            return

        # If there's a custom view, or if there's no URLpattern-driven view
        # to pick up the slack, just let the page do what it wants.
        # would.
        response = cms_match.get_response(request)

        # If it's a class-based view that isn't rendered yet (Django's resolver
        # does that normally), do it ourselves.
        if not response.is_rendered:
            response.render()

        return response
