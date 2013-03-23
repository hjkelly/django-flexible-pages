from .models import Page

class FlexiblePageMixin(object):
    """
    Offers flexible page awareness to a custom view.

    Whenever you have a page that should accept a flexible page from the CMS,
    add this in. If you haven't looked at BasePageView yet, that's a more
    comprehensive foundation that may work for you.

    In other words, say you have a standard, Django-tutorial-esque page that's
    hard-coded in your URLpatterns. However, you either intend people to enter
    its content via the CMS, or you just want to make it 'compatible' for that
    in the future.

    How would this work? Well, there are probably multiple ways you could use
    it, but the ultimate goal is to get it into your context. If you're using
    Django's generic DetailView, it might look like this:

    my_project/my_app/views.py:
        from django.views.generic import DetailView
        from flexible_content.mixins import FlexiblePageMixin

        class AboutPageView(FlexiblePageMixin, DetailView):
            def get_object(self):
                return self.get_flexible_page()

    The above example would deliver the flexible page to the template as 
    'object' (that's just how DetailView works).

    If you're using a different type of view, you can do the following:

    my_project/my_app/views.py:
        ...
        class MyCustomView(...):
            def get_context_data(self, **kwargs):
                context = super(MyCustomView, self).get_context_data(**kwargs)
                context['flexible_page'] = self.get_flexible_page()
                return context

    This would provide the page to the template as 'flexible_page'.

    Note that the default page view supports changing the template (per the
    model's 'template' field). This mixin doesn't include that functionality,
    so can chooose to support it yourself.
    """
    flexible_page = None

    def get_flexible_page(self):
        if self.flexible_page is None:
            # Use the class-based view's request.path to find the page.
            self.flexible_page = Page.objects.get_for_url(self.request.path)
        return self.flexible_page

    def get_customized_template_names(self, base_template_names):
        template_names = base_template_names

        # If the page has a custom template, add that in here.
        obj = self.get_object()
        custom_template_name = getattr(obj, 'template', None)
        if custom_template_name:
            # Prepend the list-ified template list with the custom template.
            template_names = ([custom_template_name] +
                              [t for t in base_template_names])

        return template_names
        

