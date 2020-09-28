# Generated by Django 2.2.16 on 2020-09-28 09:28

from django.db import migrations, models
import django_countries.fields
import gsheets.mixins
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('gmmp', '0005_special_questions_gsheet_integration'),
    ]

    operations = [
        migrations.CreateModel(
            name='CountryUser',
            fields=[
                ('guid', models.CharField(default=uuid.uuid4, max_length=255, primary_key=True, serialize=False)),
                ('Country', django_countries.fields.CountryField(default='KE', max_length=2)),
                ('Firstname', models.CharField(max_length=127)),
                ('Lastname', models.CharField(max_length=127)),
                ('Username', models.CharField(max_length=127)),
                ('Email', models.CharField(max_length=127)),
                ('Designation', models.CharField(max_length=127)),
            ],
            bases=(gsheets.mixins.SheetPullableMixin, models.Model),
        ),
    ]
