from django.conf.urls import patterns, url

urlpatterns = patterns('parsr.views.author',

    url(r"^$", "info"),
    url(r"^/view$", "view"),

)
