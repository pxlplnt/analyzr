import subprocess
import json

from jinja2 import Environment, FileSystemLoader
from xml.dom import minidom
from decimal import Decimal
from tempfile import TemporaryFile

from parsr.metrics import Metric

from analyzr.settings import CONFIG_PATH, PROJECT_PATH


class CheckerException(Exception):

    def __init__(self, checker, cmd, stdout="", stderr=""):
        self.checker = checker
        self.cmd = cmd

        self.stdout = stdout
        self.stderr = stderr

        super(CheckerException, self).__init__()

    def __str__(self):
        value = "STDOUT:\n%s\n\nSTDERR:\n%s" % (self.stdout, self.stderr)

        return "%s raised an error while running command:\n\n%s\n\n%s" % (
            self.checker,
            " ".join(self.cmd),
            value
        )

    def __repr__(self):
        return self.__unicode__()

class Checker(object):

    def __init__(self, config_path, result_path):
        self.measures = {}
        self.env = Environment(loader=FileSystemLoader(CONFIG_PATH))

        self.config_path = config_path
        self.result_path = result_path

    def __str__(self):
        return self.__unicode__()

    def config_file(self, revision):
        return "%s/%s.xml" % (self.config_path, revision.identifier)

    def result_file(self, revision):
        return "%s/%s.xml" % (self.result_path, revision.identifier)

    def get_decimal(self, value):
        return Decimal("%d" % round(float(value), 2))

    def execute(self, cmd):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = proc.communicate()

        if not proc.returncode == 0:
            raise CheckerException(self, cmd, stdout=stdout, stderr=stderr)

    def configure(self, files, revision, connector):
        pass

    def run(self):
        pass

    def parse(self, connector):
        return {}


class Checkstyle(Checker):

    def __init__(self, config_path, result_path):
        self.name = "checkstyle"

        super(Checkstyle, self).__init__(config_path, result_path)

    def __unicode__(self):
        return "Checkstyle Checker"

    def configure(self, files, revision, connector):
        self.measures = {}

        template = self.env.get_template("%s.xml" % self.name)

        filename = self.config_file(revision)
        result_file = self.result_file(revision)

        options = {
            "checker": self.name,
            "project_path": PROJECT_PATH,
            "base_path": connector.get_repo_path(),
            "target": result_file,
            "files": files
        }

        with open(filename, "wb") as f:
            f.write(template.render(options))

        self.configuration = filename
        self.results = result_file

        return filename, result_file

    def run(self):
        if not self.configuration:
            return

        cmd = ["ant", "-f", self.configuration, "measure"]
        self.execute(cmd)

        # Don't allow multiple runs with the same configuration
        self.configuration = None

    def parse_violation(self, filename, violation):
        source = violation.attributes["source"].value

        kind = source.replace("com.puppycrawl.tools.checkstyle.checks.metrics.", "")\
                     .replace("Check", "")

        metric = Metric.get(kind)

        if not metric:
            return

        value = metric.parse(violation)

        if not filename in self.measures:
            self.measures[filename] = []

        self.measures[filename].append({
            "kind": kind,
            "value": value
        })

    def aggregate_values(self, filename):
        if not filename in self.measures:
            return

        metrics = {}

        for measure in self.measures[filename]:
            if not measure["kind"] in metrics:
                metrics["kind"] = []

            metrics["kind"].append(measure["value"])

        self.measures[filename] = []

        for metric, values in metrics.iteritems():
            self.measures[filename].append({
                "kind": metric,
                "value": sum(values) / len(values)
            })

    def parse(self, connector):
        if not self.results:
            return

        xml_doc = minidom.parse(self.results)
        files = xml_doc.getElementsByTagName("file")

        for f in files:
            # replace leading / as files are internally stored without it.
            name = f.attributes["name"].value.replace(connector.get_repo_path(), "")\
                                             .replace("/", "", 1)

            violations = f.getElementsByTagName("error")

            for violation in violations:
                self.parse_violation(name, violation)

            self.aggregate_values(name)

        # Parse results only once
        self.results = None

        return self.measures

class JHawk(Checkstyle):

    def __init__(self, config_path, result_path):
        super(JHawk, self).__init__(config_path, result_path)

        self.name = "jhawk"

    def configure(self, files, revision, connector):
        super(JHawk, self).configure(files, revision, connector)

        self.revision = revision

    def run(self):
        if not self.configuration:
            return

        cmd = [
            "ant",
            "-lib", "%s/lib/%s/JHawkCommandLine.jar" % (PROJECT_PATH, self.name),
            "-f", self.configuration
        ]

        self.execute(cmd)

        # Don't allow multiple runs with the same configuration
        self.configuration = None

        return True

    def get_metrics(self, parent):
        for node in parent.childNodes:
            if node.localName == "Metrics":
                return node

    def get_node_value(self, parent, node_name):
        for node in parent.childNodes:
            if node.localName == node_name:
                return node.firstChild.nodeValue

    def get_name(self, parent):
        return self.get_node_value(parent, "Name")

    def add_halstead_metrics(self, filename, metrics):
        volume = self.get_decimal(self.get_node_value(metrics, "halsteadCumulativeVolume"))
        effort = self.get_decimal(self.get_node_value(metrics, "halsteadEffort"))
        difficulty = effort / volume

        self.measures[filename].append({
            "kind": "Halstead",
            "value": {
                "volume": volume,
                "difficulty": difficulty,
                "effort": effort
            }
        })

    def parse(self, connector):
        if not self.results:
            return

        xml_doc = minidom.parse("%s.xml" % self.results)
        packages = xml_doc.getElementsByTagName("Package")

        for package in packages:
            name = self.get_name(package)
            classes = package.getElementsByTagName("Class")

            path = name.replace(".", "/")

            for cls in classes:
                class_metrics = self.get_metrics(cls)
                class_name = self.get_node_value(cls, "ClassName")

                if "$" in class_name:
                    # private class inside of class
                    # ignore!
                    continue

                filename = "%s/%s.java" % (path, class_name)

                if not self.revision.includes(filename):
                    # JHawk analyzes _everything_ therefore we must
                    # filter files, which are not present in the current revision
                    continue

                if not filename in self.measures:
                    self.measures[filename] = []

                self.add_halstead_metrics(filename, class_metrics)

                methods = cls.getElementsByTagName("Method")

                complexities = []

                for method in methods:
                    method_metrics = self.get_metrics(method)

                    complexities.append(self.get_node_value(method_metrics, "cyclomaticComplexity"))

                if len(methods) == 0:
                    continue

                self.measures[filename].append({
                    "kind": "CyclomaticComplexity",
                    "value": self.get_decimal(sum([float(complexity) for complexity in complexities]) / len(methods))
                })

        return self.measures


    def result_file(self, revision):
        return "%s/%s" % (self.result_path, revision.identifier)

    def __unicode__(self):
        return "JHawk Java Checker"

class ComplexityReport(Checker):

    def __unicode__(self):
        return "Complexity Report JavaScript Checker"

    def result_file(self, revision):
        return "%s/%s" % (self.result_path, revision.identifier)

    def configure(self, files, revision, connector):
        self.result = self.result_file(revision)
        self.files = files
        self.base_path = connector.get_repo_path()

    def get_file_path(self, f):
        return "%s/%s" % (self.base_path, f.full_path())

    def run(self):
        for f in self.files:
            path = self.get_file_path(f)
            result = "%s_%s.json" % (self.result, f.get_identifier())

            cmd = ["cr", "-f", "json", "-o", result, path]

            try:
                self.execute(cmd)
            except CheckerException, e:
                if not e.stdout.startswith("Fatal error") and not e.stderr.startswith("Fatal error"):
                    raise e

                # Ignore syntax errors in checked files
                return False

        return True

    def average(self, functions):
        # maybe use median here instead
        return sum([function["cyclomatic"] for function in functions]) / len(functions)

    def parse(self, connector):
        results = {}

        for f in self.files:
            path = "%s_%s.json" % (self.result, f.get_identifier())

            with open(path) as result:
                contents = json.load(result)

                if not contents or not "reports" in contents or not contents["reports"]:
                    continue

                data = contents["reports"][0]

                halstead = data["aggregate"]["halstead"]

                if len(data["functions"]) == 0:
                    continue

                results[f.full_path()] = [
                    {
                        "kind": "CyclomaticComplexity",
                        "value": self.get_decimal(self.average(data["functions"]))
                    },
                    {
                        "kind": "Halstead",
                        "value": {
                            "volume": self.get_decimal(halstead["volume"]),
                            "difficulty": self.get_decimal(halstead["difficulty"]),
                            "effort": self.get_decimal(halstead["effort"])
                        }
                    }
                ]

        return results
