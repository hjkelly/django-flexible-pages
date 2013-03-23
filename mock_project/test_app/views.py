from django.http import HttpResponse
from django.views.generic import View

class HomepageView(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("standard homepage view")
homepage_view = HomepageView.as_view()

def custom_view(request, flexible_page=None):
    return HttpResponse("custom view")

