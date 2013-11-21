from django.conf.urls import patterns, url
from django.contrib import admin

from parsr.models import Repo, Revision, Author, File

admin.site.register(Repo)
admin.site.register(Revision)
admin.site.register(Author)
admin.site.register(File)

urlpatterns = patterns('parsr.views',
    url(r"^$", "index"),

    url(r"^repositories$", "repos"),

    url(r"^repo/(?P<repo_id>\d+)$", "repo"),
    url(r"^repo/(?P<repo_id>\d+)/edit$", "edit"),
    url(r"^repo/(?P<repo_id>\d+)/remove$", "remove"),
    url(r"^repo/(?P<repo_id>\d+)/branch/(?P<branch_id>\d+)", "repo"),

    url(r"^branch/(?P<branch_id>\d+)$", "branch"),
    url(r'^branch/(?P<branch_id>\d+)/contributors$', 'contributors'),
    url(r'^branch/(?P<branch_id>\d+)/author/(?P<author_id>\d+)$', 'branch_author'),
    url(r'^branch/(?P<branch_id>\d+)/author/(?P<author_id>\d+)/commits$', "commits"),
    url(r'^branch/(?P<branch_id>\d+)/commits$', "commits"),
    url(r'^branch/(?P<branch_id>\d+)/author/(?P<author_id>\d+)/stats$', "file_stats"),
    url(r'^branch/(?P<branch_id>\d+)/stats$', "file_stats"),
    url(r'^branch/(?P<branch_id>\d+)/author/(?P<author_id>\d+)/metrics$', 'metrics'),
    url(r'^branch/(?P<branch_id>\d+)/author/(?P<author_id>\d+)/churn$', 'churn'),
    url(r'^branch/(?P<branch_id>\d+)/author/(?P<author_id>\d+)/punchcard$', "punchcard"),
    url(r'^branch/(?P<branch_id>\d+)/punchcard$', "punchcard"),
    url(r"^branch/(?P<branch_id>\d+)/analyze$", "analyze"),
    url(r"^branch/(?P<branch_id>\d+)/measure$", "measure"),

    url(r"^author/(?P<author_id>\d+)$", "author"),

    url(r"^create$", "create"),
    url(r"^create/save$", "save"),
)
