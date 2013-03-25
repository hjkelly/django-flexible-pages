from django.utils.timezone import localtime


def prettify_datetime(datetime):
    local_datetime = localtime(datetime)
    return ''.join([local_datetime.strftime('%a, %b '),
                    str(int(local_datetime.strftime('%d'))),
                    local_datetime.strftime(', %Y at %I:%M %p')])


def get_preview_link(obj):
    return """<a href="%s">%s</a>""" % (obj.get_absolute_url(),
                                        obj.get_absolute_url())
get_preview_link.short_description = u"Preview Link"
get_preview_link.allow_tags = True
