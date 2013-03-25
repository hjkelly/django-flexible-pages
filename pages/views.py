from django.views.generic import DetailView

from .mixins import FlexiblePageMixin
from .models import Page


class BasePageView(FlexiblePageMixin, DetailView):
    model = Page

    def get_object(self, queryset=None):
        return self.get_flexible_page()

    def get_template_names(self):
        """
        Assemble a template list, honoring this item's custom template name
        field.
        """
        # Get the view's default template list.
        base_template_names = super(BasePageView, self).get_template_names()

        # Prepend with the custom template, if necessary.
        return self.get_customized_template_names(base_template_names)


class DefaultPageView(BasePageView):
    pass
default_page_view = DefaultPageView.as_view()
