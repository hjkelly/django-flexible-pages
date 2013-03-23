from django.contrib import admin

from flexible_content.admin import ContentAreaAdmin

from .admin_utils import get_preview_link
from .models import Page


class PageAdmin(ContentAreaAdmin):
    list_display = (
        'title',
        get_preview_link,
        'summary_preview',
    )
    fieldsets = (
        (None, {
            'fields': (
                'title',
                'url',
                'summary',
            ),
        }),
        (u"Advanced", {
            'fields': (
                'view',
                'template',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def summary_preview(self, obj):
        if obj.summary and len(obj.summary) > 75:
            return '%s...' % obj.summary[:50]
        else:
            return obj.summary
    summary_preview.short_description = "Summary"

admin.site.register(Page, PageAdmin)

