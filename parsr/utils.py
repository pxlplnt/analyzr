from smtplib import SMTP

from pygments import highlight
from pygments.lexers import PythonTracebackLexer
from pygments.formatters import HtmlFormatter, NullFormatter

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from analyzr.settings import ADMINS, EMAIL


def send_mail(traceback):
    for name, email in ADMINS:
        message = MIMEMultipart("alternative")
        message["From"] = EMAIL["account"]
        message["To"] = email
        message["Subject"] = "Something went terribly wrong!"

        lexer = PythonTracebackLexer()
        html_formatter = HtmlFormatter(full=True, noclasses=True)
        raw_formatter = NullFormatter()

        html = highlight(traceback, lexer, html_formatter)
        text = highlight(traceback, lexer, raw_formatter)

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")

        message.attach(part1)
        message.attach(part2)

        connection = SMTP(EMAIL["host"])
        connection.login(EMAIL["account"], EMAIL["password"])
        connection.sendmail(EMAIL["account"], email, message.as_string())
        connection.quit()


def previous(cls, instance, filters={}):
    filters["date__lt"] = instance.date

    try:
        return cls.objects.filter(**filters).order_by("-date")[0]
    except:
        filters.pop("date__lt")
        filters["date__lte"] = instance.date

        objects = cls.objects.filter(**filters).order_by("-date")

        if objects.count() > 1:
            # multiple edits in one minute. we pick something.
            # hopefully does not happen too often
            return objects[1]

        return None
