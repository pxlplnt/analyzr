# -*- coding: utf-8 -*-
from datetime import datetime

from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def normalize_date(self, date, tzinfo):
        return datetime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=date.hour,
            minute=date.minute,
            tzinfo=tzinfo
        )

    def forwards(self, orm):
        for revision in orm.Revision.objects.all():
            rev_date = revision.revision_date

            date = self.normalize_date(rev_date.date, revision.branch.repo.timezone)

            revision.date = date
            revision.year = date.year
            revision.month = date.month
            revision.day = date.day
            revision.hour = date.hour
            revision.minute = date.minute
            revision.weekday = date.weekday()

            revision.save()

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'parsr.author': {
            'Meta': {'object_name': 'Author'},
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'parsr.branch': {
            'Meta': {'object_name': 'Branch'},
            'analyzed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'analyzed_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'analyzing': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_analyze_error': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'last_measure_error': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'measured': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'measuring': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'repo': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['parsr.Repo']", 'null': 'True'}),
            'revision_count': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'parsr.file': {
            'Meta': {'object_name': 'File'},
            'change_type': ('django.db.models.fields.CharField', [], {'max_length': '1', 'null': 'True'}),
            'copy_of': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['parsr.File']", 'null': 'True'}),
            'cyclomatic_complexity': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'cyclomatic_complexity_delta': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'halstead_difficulty': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'halstead_difficulty_delta': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'halstead_effort': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'halstead_effort_delta': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'halstead_volume': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            'halstead_volume_delta': ('django.db.models.fields.DecimalField', [], {'default': '0', 'max_digits': '15', 'decimal_places': '2'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lines_added': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'lines_removed': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'mimetype': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'package': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'revision': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['parsr.Revision']"})
        },
        u'parsr.repo': {
            'Meta': {'object_name': 'Repo'},
            'anonymous': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ignored_files': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'ignored_folders': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'kind': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'timezone': ('timezone_field.fields.TimeZoneField', [], {'default': "'Europe/Berlin'"}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'user': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'})
        },
        u'parsr.revision': {
            'Meta': {'object_name': 'Revision'},
            'author': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['parsr.Author']", 'null': 'True'}),
            'branch': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['parsr.Branch']", 'null': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'day': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'hour': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'identifier': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'measured': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'minute': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'month': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'next': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'previous'", 'null': 'True', 'to': u"orm['parsr.Revision']"}),
            'revision_date': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['parsr.RevisionDate']", 'null': 'True'}),
            'weekday': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year': ('django.db.models.fields.IntegerField', [], {'null': 'True'})
        },
        u'parsr.revisiondate': {
            'Meta': {'object_name': 'RevisionDate'},
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'day': ('django.db.models.fields.IntegerField', [], {}),
            'hour': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'minute': ('django.db.models.fields.IntegerField', [], {}),
            'month': ('django.db.models.fields.IntegerField', [], {}),
            'weekday': ('django.db.models.fields.IntegerField', [], {}),
            'year': ('django.db.models.fields.IntegerField', [], {})
        }
    }

    complete_apps = ['parsr']
    symmetrical = True
