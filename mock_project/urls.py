from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),

    url(r'^$', 'mock_project.test_app.views.homepage_view'),
) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
