from django.http import HttpResponse

from pages.views import BasePageView


class HomepageView(BasePageView):
    template_name = 'pages/home.html'
homepage_view = HomepageView.as_view()


class CustomView(BasePageView):
    template_name = 'pages/custom.html'
custom_view = CustomView.as_view()
