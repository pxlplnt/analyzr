from datetime import datetime
from hashlib import md5
from urllib import urlencode
from shutil import rmtree

from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Count, Sum, Avg
from django.db.models.signals import post_save, pre_save, pre_delete
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.dispatch import receiver

from timezone_field import TimeZoneField

from mimetypes import guess_type

from parsr.connectors import Connector, Action
from parsr.analyzers import Analyzer
from parsr import sql

from analyzr.settings import TIME_ZONE, CONTRIBUTORS_PER_PAGE


class Repo(models.Model):

    TYPES = (
        ("svn", "Subversion"),
        ("git", "Git"),
        ("mercurial", "Mercurial")
    )

    url = models.CharField(max_length=255)
    kind = models.CharField(max_length=255, choices=TYPES)
    anonymous = models.BooleanField(default=True)
    timezone = TimeZoneField(default=TIME_ZONE)

    ignored_folders = models.CharField(max_length=255, null=True, blank=True)
    ignored_files = models.CharField(max_length=255, null=True, blank=True)

    user = models.CharField(max_length=255, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)

    def __unicode__(self):
        return "%s repository at: %s" % (self.kind, self.url)

    def href(self):
        return reverse("parsr.views.repo.index", kwargs={"repo_id": self.id})

    def busy(self):
        return self.analyzing() or self.measuring()

    def analyzing(self):
        return Branch.objects.filter(repo=self, analyzing=True).count() > 0

    def analyzed(self):
        return Branch.objects.filter(repo=self, analyzed=True).count() > 0

    def measuring(self):
        return Branch.objects.filter(repo=self, measuring=True).count() > 0

    def measurable(self):
        return Branch.objects.filter(repo=self, analyzed=True).count() > 0

    def measured(self):
        return Branch.objects.filter(repo=self, measured=True).count() > 0

    def get_status(self):
        branch = None
        status = "ready"

        if self.analyzing():
            branch = Branch.objects.get(repo=self, analyzing=True)

            status = "analyzing"

        if self.measuring():
            branch = Branch.objects.get(repo=self, measuring=True)

            status = "measuring"

        return {
            "action": status,
            "rep": branch.json() if branch else None
        }

    def branches(self):
        return Branch.objects.filter(repo=self)

    def branch_count(self):
        return Branch.objects.filter(repo=self).count()

    def author_count(self):
        return Author.objects.filter(revision__branch__repo=self).distinct().count()

    def default_branch(self):
        default = Branch.objects.filter(repo=self, analyzed=True)[0:1]

        if default:
            return default[0]

        return None

    def ignores(self, package, filename):
        if not package.startswith("/"):
            package = "/%s" % package

        if not package.endswith("/"):
            package = "%s/" % package

        for pkg in self.ignored_folders.split(","):
            if pkg and pkg in package:
                return True

        for name in self.ignored_files.split(","):
            if name and filename.startswith(name):
                return True

        return False

    def json(self):
        return {
            "href": self.href(),
            "rel": "repo",
            "rep": {
                "id": self.id,
                "name": self.url,
                "kind": self.kind,
                "busy": self.busy(),
                "status": self.get_status(),
                "anonymous": self.anonymous,
                "analyzed": self.analyzed(),
                "analyzing": self.analyzing(),
                "measurable": self.measurable(),
                "measured": self.measured(),
                "measuring": self.measuring(),
                "branchCount": self.branch_count(),
                "authorCount": self.author_count(),
                "branches": [branch.json() for branch in self.branch_set.all()]
            }
        }


@receiver(post_save, sender=Repo)
def add_branches_to_repo(sender, **kwargs):
    instance = kwargs["instance"]

    if instance.branch_count() > 0:
        return

    connector = Connector.get(instance)

    for name, path in connector.get_branches():
        branch, created = Branch.objects.get_or_create(
            name=name,
            path=path,
            repo=instance
        )


@receiver(pre_save, sender=Repo)
def clean_ignores(sender, instance, **kwargs):
    filenames = []
    foldernames = []

    if instance.ignored_files:
        for filename in instance.ignored_files.split(","):
            filenames.append(filename.strip())

    instance.ignored_files = ",".join(filenames)

    if instance.ignored_folders:
        for foldername in instance.ignored_folders.split(","):
            if not foldername.startswith("/"):
                foldername = "/%s" % foldername

            if not foldername.endswith("/"):
                foldername = "%s/" % foldername

            foldernames.append(foldername)

    instance.ignored_folders = ",".join(foldernames)


@receiver(pre_delete, sender=Repo)
def remove_repo(sender, instance, **kwargs):
    connector = Connector.get(instance)

    path = connector.get_repo_path()
    rmtree(path)


class Branch(models.Model):

    name = models.CharField(max_length=255)
    path = models.CharField(max_length=255)

    repo = models.ForeignKey("Repo", null=True)

    analyzed = models.BooleanField(default=False)
    analyzing = models.BooleanField(default=False)
    analyzed_date = models.DateTimeField(null=True, blank=True)

    measured = models.BooleanField(default=False)
    measuring = models.BooleanField(default=False)

    revision_count = models.IntegerField(default=0)
    last_analyze_error = models.TextField(null=True, blank=True)
    last_measure_error = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return "Branch %s at %s" % (self.name, self.path)

    def json(self):
        info = {}

        if self.analyzing:
            info["action"] = "analyzing"
            info["count"] = self.revision_count,
            info["progress"] = self.revision_set.all().count()

        if self.measuring:
            info["action"] = "measuring"
            info["progress"] = self.revision_set.filter(measured=True).count()
            info["count"] = self.revision_set.all().count()

        return {
            "href": self.href(),
            "rel": "branch",
            "rep": {
                "id": self.id,
                "name": self.name,
                "path": self.path,
                "analyze": {
                    "running": self.analyzing,
                    "finished": self.analyzed,
                    "interrupted": self.analyzing_interrupted(),
                    "lastError": self.last_analyze_error
                },
                "measure": {
                    "running": self.measuring,
                    "finished": self.measured,
                    "interrupted": self.measuring_interrupted(),
                    "lastError": self.last_measure_error
                },
                "activity": info
            }
        }

    def analyzing_interrupted(self):
        return not self.analyzed and self.revision_set.count() > 0

    def measuring_interrupted(self):
        measured = self.revision_set.filter(measured=True).count()

        return measured > 0 and not measured == self.revision_set.all().count()

    def href(self):
        return reverse("parsr.views.branch.index", kwargs={"branch_id": self.id})

    def cleanup(self):
        self.remove_all(File, File.objects.filter(revision__branch=self))
        self.remove_all(Revision, Revision.objects.filter(branch=self))
        self.remove_all(Author, Author.objects.filter(revision__branch=self))

    def remove_all(self, cls, elements):
        query = sql.delete(cls, str(elements.values("id").query))

        sql.execute(query)

    def analyze(self, resume=False):
        self.last_analyze_error = None

        self.analyzed = False
        self.analyzing = True

        self.measured = False
        self.measuring = False
        self.save()

        if not resume:
            self.cleanup()

        revision = None

        if resume:
            revision = self.last_analyzed_revision()

        connector = Connector.get(self.repo)
        connector.analyze(self, revision)

        self.analyzing = False
        self.analyzed = True
        self.analyzed_date = datetime.now(self.repo.timezone)
        self.save()

    def abort_analyze(self, error):
        self.analyzed = False
        self.analyzing = False

        self.last_analyze_error = error

        self.save()

    def last_analyzed_revision(self):
        return self.revision_set.get(previous=None)

    def last_measured_revision(self):
        revisions = self.revision_set.filter(measured=True).order_by("-date")

        if revisions.count() == 0:
            return None

        return revisions[0]

    def measure(self, resume=False):
        self.last_measure_error = None

        self.measured = False
        self.measuring = True
        self.save()

        if not resume:
            sql.reset(self)

        revision = None

        if resume:
            revision = self.last_measured_revision()

        analyzer = Analyzer(self.repo, self)
        analyzer.start(revision)

        self.measuring = False
        self.measured = True
        self.save()

    def abort_measure(self, error):
        self.measured = False
        self.measuring = False

        self.last_measure_error = error

        self.save()

    def age(self):
        if not self.analyzed or self.revision_set.count() == 0:
            return "n/a"

        start = self.revision_set.order_by("date")[0:1][0]
        end = self.revision_set.order_by("-date")[0:1][0]

        return end.date - start.date

    def set_options(self, response, options):
        for key, value in options.iteritems():
            response["info"]["options"][key] = value

    def contributors(self, page=None):
        response = self.response_stub()

        paginator = Paginator(self.authors(), CONTRIBUTORS_PER_PAGE)

        try:
            authors = paginator.page(page)
        except PageNotAnInteger:
            page = 1
            authors = paginator.page(1)
        except EmptyPage:
            page = paginator.num_pages
            authors = paginator.page(paginator.num_pages)

        response["data"] = [author.json(self) for author in authors]

        self.set_options(response, {
            "hasNext": not page == paginator.num_pages,
            "hasPrevious": not page == 1,
            "page": int(page),
            "pages": paginator.num_pages,
            "perPage": CONTRIBUTORS_PER_PAGE
        })

        return response

    def punchcard(self, author=None, language=None, start=None, end=None):
        filters = {
            "branch": self
        }

        if author:
            filters["author"] = author

        response = self.response_stub(language=language, start=start, end=end)

        result = Revision.objects.filter(**filters).values("weekday", "hour").annotate(count=Count("hour"))

        hour_max = 0

        for revision in result:
            weekday = revision["weekday"]
            hour = revision["hour"]
            count = revision["count"]

            hour_max = max(count, hour_max)

            if not weekday in response["data"]:
                response["data"][weekday] = {}

            response["data"][weekday][hour] = count

        self.set_options(response, {
            "max": hour_max
        })

        return response

    def file_statistics(self, author=None, language=None, start=None, end=None):
        response = self.response_stub(language=language, start=start, end=end)
        filters = {
            "revision__branch": self
        }

        if author:
            # Author specific stats need to consider all files and changes to them
            # but not deletes
            filters["mimetype__in"] = Analyzer.parseable_types()
            filters["revision__author"] = author
            filters["change_type__in"] = [Action.ADD, Action.MODIFY, Action.MOVE]

            files = File.objects.filter(**filters)

            count = files.values("mimetype").count()

            for stat in files.values("mimetype").annotate(count=Count("mimetype")).order_by("count"):
                response["data"][stat["mimetype"]] = stat["count"] / (1.0 * count)

            return response

        # raw query processing seems to work a little different. that is why we need to
        # manually put the strings into quotes.
        filters["mimetype__in"] = ["'%s'" % t for t in Analyzer.parseable_types()]

        query = sql.newest_files(str(File.objects.filter(**filters).query))
        count = File.objects.raw(sql.count_entries(query))[0].count

        # Order by
        for stat in File.objects.raw(sql.mimetype_count(query)):
            response["data"][stat.mimetype] = stat.count / (1.0 * count)

        return response

    def commit_history(self, author=None, language=None, start=None, end=None):
        filters = {
            "branch": self
        }

        if author:
            filters["author"] = author

        response = self.response_stub()

        result = Revision.objects.filter(**filters).values("year", "month", "day").annotate(count=Count("day"))

        count_max = 0

        for revision in result:
            count_max = max(revision["count"], count_max)

            year = revision["year"]
            month = revision["month"]
            day = revision["day"]
            count = revision["count"]

            if not year in response["data"]:
                response["data"][year] = {}

            if not month in response["data"][year]:
                response["data"][year][month] = {}

            response["data"][year][month][day] = {
                "commits": count,
                "files": File.objects.filter(revision__day=day,
                                             revision__month=month,
                                             revision__year=year,
                                             revision__branch=self).count()
            }

        self.set_options(response, {
            "upper": count_max
        })

        return response

    def authors(self):
        return Author.objects.filter(revision__branch=self)\
                             .annotate(rev_count=Count("revision"))\
                             .order_by("-rev_count")

    def author_count(self):
        return Author.objects.filter(revision__branch=self).distinct().count()

    def first_revision(self):
        revisions = self.revision_set.all().order_by("date")

        if revisions.count() == 0:
            return None

        return revisions[0]

    def revisions(self, author=None, language=None, start=None, end=None):
        filters = {
            "branch": self
        }

        if author:
            filters["author"] = author

        if language == "all":
            # all is a special value for the language attribute
            # which will reset it so that no filtering will take place
            language = None

        if language:
            filters["file__mimetype"] = language

        if start:
            filters["date__gte"] = start

        if end:
            filters["date__lte"] = end

        return Revision.objects.filter(**filters).order_by("date")

    def files(self, author=None, language=None, start=None, end=None):
        filters = {
            "revision__branch": self,
            "change_type": Action.readable()
        }

        if author:
            filters["author"] = author

        if language:
            filters["mimetype"] = language

        if start:
            filters["date__gte"] = start

        if end:
            filters["date__lte"] = end

        return File.objects.filter(**filters).order_by("date")

    def create_revision(self, identifier):
        return Revision.objects.create(
            branch=self,
            identifier=identifier
        )

    def get_languages(self):
        languages = File.objects\
            .filter(revision__branch=self, mimetype__in=Analyzer.parseable_types())\
            .values("mimetype").distinct()

        return [language["mimetype"] for language in languages]

    def get_earliest_revision(self):
        return self.revision_set.order_by("date")[0:1][0]

    def get_latest_revision(self):
        return self.revision_set.order_by("-date")[0:1][0]

    def response_stub(self, language=None, start=None, end=None):
        return {
            "info": {
                "dates": [],
                "languages": self.get_languages(),
                "options": {
                    "language": language,
                    "startDate": start.isoformat() if start else None,
                    "endDate": end.isoformat() if end else None,
                    "minDate": self.get_earliest_revision().date.isoformat(),
                    "maxDate": self.get_latest_revision().date.isoformat()
                }
            },
            "data": {}
        }

    def metrics(self, author, language=None, start=None, end=None):
        result = self.response_stub(language=language, start=start, end=end)

        if not language:
            return result

        files = self.files(author, language=language, start=start, end=end)

        for f in files:
            date = f.date.isoformat()

            if not date in result["info"]["dates"]:
                result["info"]["dates"].append(date)

            path = f.full_path()

            if not path in result["data"]:
                result["data"][path] = []

            result["data"][path].append({
                "date": date,
                "deleted": f.change_type == Action.DELETE,
                "complexity": {
                    "Cyclomatic Complexity": float(f.cyclomatic_complexity),
                    "Halstead Volume": float(f.halstead_volume),
                    "Halstead Difficulty": float(f.halstead_difficulty),
                    "Halstead Effort": float(f.halstead_effort)
                },
                "structure": {
                    "Fan In": float(f.fan_in),
                    "Fan Out": float(f.fan_out),
                    "SLOC": f.sloc,
                    "Information Flow": float(f.hk)
                }
            })

        files = files.values("date").annotate(
            cyclomatic_complexity=Avg("cyclomatic_complexity"),
            halstead_volume=Avg("halstead_volume"),
            halstead_difficulty=Avg("halstead_difficulty"),
            halstead_effort=Avg("halstead_effort")
        )

        result["data"]["all"] = []

        for rev in files:
            result["data"]["all"].append({
                "date": rev["date"].isoformat(),
                "complexity": {
                    "Cyclomatic Complexity": rev["cyclomatic_complexity"],
                    "Halstead Volume": rev["halstead_volume"],
                    "Halstead Difficulty": rev["halstead_difficulty"],
                    "Halstead Effort": rev["halstead_effort"]
                }
            })

        return result

    def churn(self, author, language=None, start=None, end=None):
        response = self.response_stub(language=language, start=start, end=end)

        if not language:
            self.set_options(response, {
                "upperBound": 1,
                "lowerBound": -1
            })

            return response

        max_added = 0
        max_removed = 0

        revisions = self.revisions(author, language=language, start=start, end=end)
        revisions = revisions.annotate(added=Sum("file__lines_added"), removed=Sum("file__lines_removed"))

        for revision in revisions:
            response["info"]["dates"].append(revision.date.isoformat())

            max_added = max(max_added, revision.added)
            max_removed = max(max_removed, revision.removed)

            response["data"][revision.date.isoformat()] = {
                "added": revision.added,
                "removed": revision.removed
            }

        self.set_options(response, {
            "startDate": revisions[0].date.isoformat(),
            "endDate": revisions[len(revisions) - 1].date.isoformat(),
            "upperBound": max_added,
            "lowerBound": -1 * max_removed
        })

        return response

class Revision(models.Model):

    identifier = models.CharField(max_length=255)

    branch = models.ForeignKey("Branch", null=True)
    author = models.ForeignKey("Author", null=True)

    next = models.ForeignKey("Revision", related_name='previous', null=True)

    measured = models.BooleanField(default=False)

    date = models.DateTimeField(null=True)

    year = models.IntegerField(null=True)
    month = models.IntegerField(null=True)
    day = models.IntegerField(null=True)
    hour = models.IntegerField(null=True)
    minute = models.IntegerField(null=True)
    weekday = models.IntegerField(null=True)

    def __unicode__(self):
        return "%s created by %s in %s of %s" % (self.identifier, self.author, self.branch, self.branch.repo)

    def add_file(self, filename, action, original=None):
        package, filename = File.parse_name(filename)

        if self.branch.repo.ignores(package, filename):
            return

        mimetype, encoding = guess_type(filename)

        if original:
            original = File.objects\
                           .filter(name=filename, package=package, revision__branch=self.branch)\
                           .order_by("-revision__date")[0:1]

        File.objects.create(
            revision=self,
            author=self.author,
            date=self.date,
            name=filename,
            package=package,
            mimetype=mimetype.split("/")[1] if mimetype else None,
            change_type=action,
            copy_of=original[0] if original else None
        )

    def set_author(self, name, email=None):
        author, created = Author.objects.get_or_create(
            name=name,
            email=email
        )

        self.author = author

    def normalize_date(self, date, tzinfo):
        return datetime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=date.hour,
            minute=date.minute,
            tzinfo=tzinfo
        )

    def set_date(self, date):
        date = self.normalize_date(date, self.branch.repo.timezone)

        self.date = date
        self.year = date.year
        self.month = date.month
        self.day = date.day
        self.weekday = date.weekday()
        self.hour = date.hour
        self.minute = date.minute

    def get_previous(self):
        if self.previous.all().count() > 0:
            return self.previous.all()[0]

        return None

    def represents(self, identifier):
        return self.identifier == identifier

    def modified_files(self):
        return self.file_set.filter(change_type=Action.readable(), mimetype__in=Analyzer.parseable_types())

    def includes(self, filename):
        package, filename = File.parse_name(filename)

        return not self.file_set.filter(name=filename,
                                        package__endswith=package,
                                        change_type=Action.readable()).count() == 0

    def get_file(self, filename):
        package, filename = File.parse_name(filename)

        try:
            return self.file_set.get(name=filename,
                                     package__endswith=package,
                                     change_type=Action.readable())
        except File.DoesNotExist:
            message = "Could not find file using package: %s and filename: %s.\nRevision: %s" % (
                package,
                filename,
                self
            )

            raise Exception(message)


class File(models.Model):

    @classmethod
    def parse_name(cls, filename):
        parts = filename.rsplit("/", 1)

        if not len(parts) == 2:
            parts = [""] + parts

        return parts

    CHANGE_TYPES = (
        (Action.ADD, "Added"),
        (Action.MODIFY, "Modified"),
        (Action.MOVE, "Copied"),
        (Action.DELETE, "Deleted")
    )

    KNOWN_LANGUAGES = Analyzer.parseable_types() + [
        "x-python",
        "html",
        "json",
        "x-sql"
    ]

    revision = models.ForeignKey("Revision")
    author = models.ForeignKey("Author", null=True)
    date = models.DateTimeField(null=True)

    name = models.CharField(max_length=255)
    package = models.CharField(max_length=255)

    mimetype = models.CharField(max_length=255, null=True)

    change_type = models.CharField(max_length=1, null=True, choices=CHANGE_TYPES)
    copy_of = models.ForeignKey("File", null=True)

    cyclomatic_complexity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cyclomatic_complexity_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    halstead_volume = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    halstead_volume_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    halstead_difficulty = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    halstead_difficulty_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    halstead_effort = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    halstead_effort_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    fan_in = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fan_in_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fan_out = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fan_out_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    sloc = models.IntegerField(default=0)
    sloc_delta = models.IntegerField(default=0)

    hk = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    hk_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    lines_added = models.IntegerField(default=0)
    lines_removed = models.IntegerField(default=0)

    def __unicode__(self):
        return self.name

    def get_previous(self):
        if self.change_type == Action.ADD:
            return None

        try:
            return File.objects.filter(name=self.name, revision__date__lt=self.revision.date)\
                               .order_by("-revision__date")[0]
        except:
            files = File.objects.filter(name=self.name, revision__date__lte=self.revision.date)\
                                .order_by("-revision__date")

            if files.count() > 1:
                # multiple edits in one minute. we pick something.
                # hopefully does not happen too often
                return files[1]

            return None

    def add_measures(self, measures):
        previous = self.get_previous()

        for measure in measures:
            kind = measure["kind"]

            if kind == "CyclomaticComplexity":
                self.cyclomatic_complexity = measure["value"]

                if previous:
                    self.cyclomatic_complexity_delta = measure["value"] - previous.cyclomatic_complexity

            if kind == "Halstead":
                volume = measure["value"]["volume"]
                difficulty = measure["value"]["difficulty"]
                effort = measure["value"]["effort"]

                self.halstead_volume = volume
                self.halstead_difficulty = difficulty
                self.halstead_effort = effort

                if previous:
                    self.halstead_volume_delta = volume - previous.halstead_volume
                    self.halstead_difficulty_delta = difficulty - previous.halstead_difficulty
                    self.halstead_effort_delta = effort - previous.halstead_effort

            if kind == "churn":
                self.lines_added = measure["value"]["added"]
                self.lines_removed = measure["value"]["removed"]

            if kind == "FanIn":
                self.fan_in = measure["value"]
                self.fan_in_delta = self.fan_in - previous.fan_in

            if kind == "FanOut":
                self.fan_out = measure["value"]
                self.fan_out_delta = self.fan_out - previous.fan_out

            if kind == "SLOC":
                self.sloc = measure["value"]
                self.sloc_delta = self.sloc - previous.sloc

        if self.fan_in and self.fan_out and self.sloc:
            self.hk = self.sloc * pow(self.fan_in * self.fan_out, 2)
            self.hk_delta = self.hk - previous.hk

        self.save()

    def add_churn(self, churn=None):
        if not churn:
            return

        self.lines_added = churn["added"]
        self.lines_removed = churn["removed"]

        self.save()

    def get_identifier(self):
        return md5(self.name).hexdigest()

    def full_path(self):
        return "%s/%s" % (self.package, self.name)


class Author(models.Model):

    name = models.CharField(max_length=255)
    email = models.EmailField(null=True)

    def __unicode__(self):
        if self.email:
            return "%s (%s)" % (self.name, self.email)

        return self.name

    def href(self):
        return reverse("parsr.views.author.index", kwargs={"author_id": self.id})

    def revision_count(self, branch):
        revisions = Revision.objects.filter(author=self, branch=branch).distinct()

        return revisions.count()

    def get_icon(self):
        size = 40
        mail = ""

        if self.email:
            mail = md5(self.email.lower()).hexdigest()

        params = urlencode({
            's': str(size)
        })

        return "http://www.gravatar.com/avatar/%s?%s" % (mail, params)

    def get_prime_language(self, branch):
        files = File.objects.filter(
                                revision__branch=branch,
                                author=self,
                                mimetype__in=File.KNOWN_LANGUAGES
                            )\
                            .values("mimetype")\
                            .annotate(count=Count("mimetype"))\
                            .order_by("-count")

        if not files:
            return None

        return files[0]

    def get_complexity_index(self, branch):
        aggregate = File.objects.filter(revision__branch=branch, author=self)\
                            .aggregate(
                                cyclomatic=Sum("cyclomatic_complexity_delta"),
                                halstead_difficulty=Sum("halstead_difficulty_delta"),
                                halstead_effort=Sum("halstead_effort_delta"),
                                halstead_volume=Sum("halstead_volume_delta")
                            )

        return {
            "cyclomatic": float(aggregate["cyclomatic"]),
            "halstead": {
                "effort": float(aggregate["halstead_effort"]),
                "volume": float(aggregate["halstead_volume"]),
                "difficulty": float(aggregate["halstead_difficulty"])
            },
            "combined": float(
                aggregate["cyclomatic"] +
                aggregate["halstead_effort"] +
                aggregate["halstead_volume"] +
                aggregate["halstead_difficulty"]
            )
        }

    def json(self, branch):
        return {
            "href": self.href(),
            "rel": "author",
            "rep": {
                "id": self.id,
                "name": str(self),
                "icon": self.get_icon(),
                "count": self.revision_count(branch),
                "primeLanguage": self.get_prime_language(branch),
                "indicators": {
                    "complexity": self.get_complexity_index(branch)
                }
            }
        }
