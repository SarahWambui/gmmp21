# Python
import StringIO
from collections import Counter, OrderedDict
import logging
import datetime

# Django
from django.db import connection
from django.db.models import Count, FieldDoesNotExist
from django.conf import settings

# 3rd Party
import xlsxwriter

# Project
from forms.models import (
    NewspaperPerson, TelevisionJournalist,
    person_models, sheet_models, journalist_models,
    tm_person_models, tm_sheet_models, tm_journalist_models,
    dm_person_models, dm_sheet_models, dm_journalist_models, all_models)
from forms.modelutils import (TOPICS, GENDER, SPACE, OCCUPATION, FUNCTION, SCOPE,
    YESNO, AGES, SOURCE, VICTIM_OF, SURVIVOR_OF, IS_PHOTOGRAPH, AGREE_DISAGREE,
    RETWEET, TV_ROLE, MEDIA_TYPES, TM_MEDIA_TYPES, DM_MEDIA_TYPES, CountryRegion,
    TV_ROLE_ANNOUNCER, TV_ROLE_REPORTER, REPORTERS)
from report_details import *  # noqa
from reports.models import Weights
from reports.historical import Historical, canon

SHEET_MEDIA_GROUPS = [
    (TM_MEDIA_TYPES, tm_sheet_models),
    (DM_MEDIA_TYPES, dm_sheet_models)
]

PERSON_MEDIA_GROUPS = [
    (TM_MEDIA_TYPES, tm_person_models),
    (DM_MEDIA_TYPES, dm_person_models)
]

JOURNO_MEDIA_GROUPS = [
    (TM_MEDIA_TYPES, tm_journalist_models),
    (DM_MEDIA_TYPES, dm_journalist_models)
]

media_split = [
    "Print, Radio, Television",
    "Internet",
    "Twitter"
]

COUNTRY_RECODES = {
    u'B1': u'BE',  # Belgium - French -> Belgium
    u'B2': u'BE',  # Belgium - English -> Belgium
    u'EN': u'UK',  # England -> United Kingdom
    u'IE': u'UK',  # Ireland -> United Kingdom
    u'SQ': u'UK',  # Scotland -> United Kingdom
    u'WL': u'UK',  # Wales -> United Kingdom
}


# =================
# General utilities
# =================

def has_field(model, fld):
    try:
        model._meta.get_field(fld)
        return True
    except FieldDoesNotExist:
        return False

def p(n, d):
    """ Helper to calculate the percentage of n / d,
    returning 0 if d == 0.
    """
    if d == 0:
        return 0.0
    return float(n) / d

def clean_title(text):
    """
    Return the string passed in stripped of its numbers and parentheses
    """
    if text != "Congo (the Democratic Republic of the)":
        return text[text.find(')')+1:].lstrip()
    return text

def get_sheet_model_name_field(media_type):
    if media_type == "Internet":
        return "website_name"
    elif media_type == "Twitter":
        return "media_name"
    elif media_type == "Print":
        return "newspaper_name"
    elif media_type == "Television":
        return "station_name"
    elif media_type == "Radio":
        return "station_name"


class XLSXReportBuilder:
    def __init__(self, form):
        from reports.views import CountryForm, RegionForm

        self.form = form
        self.log = logging.getLogger(__name__)

        if isinstance(form, CountryForm):
            self.countries = form.filter_countries()
            self.regions = get_country_region(form.cleaned_data['country'])
            self.report_type = 'country'
        elif isinstance(form, RegionForm):
            region = [name for i, name in form.REGIONS if str(i) == form.cleaned_data['region']][0]
            self.countries = get_region_countries(region)
            self.regions = [(0, region)]
            self.report_type = 'region'
        else:
            self.countries = get_countries()
            self.regions = get_regions()
            self.report_type = 'global'

        self.country_list = [code for code, name in self.countries]
        self.region_list = [name for id, name in self.regions]

        if self.report_type == 'global':
            self.recode_countries()

        # Various utilities used for displaying details
        self.male_female = [(id, value) for id, value in GENDER if id in [1, 2]]
        self.male_female_ids = [id for id, value in self.male_female]
        self.female = [(id, value) for id, value in GENDER if id == 1]
        self.yes = [(id, value) for id, value in YESNO if id == 'Y']

        self.gmmp_year = '2015'

        self.historical = Historical()

    def recode_countries(self):
        # squash recoded countries
        self.countries = [(c, n) for c, n in self.countries if c not in COUNTRY_RECODES]
        # add UK and Belgium
        self.countries.append((u'BE', u'Belgium - French and Flemish'))
        self.countries.append((u'UK', u'United Kingdom - England, Ireland, Scotland and Wales'))
        self.countries.sort(key=lambda p: p[1])

    def build(self):
        """
        Generate an Excel spreadsheet and return it as a string.
        """
        output = StringIO.StringIO()
        workbook = xlsxwriter.Workbook(output)

        # setup formats
        self.heading = workbook.add_format(FORMATS['heading'])

        self.col_heading = workbook.add_format(FORMATS['col_heading'])
        self.col_heading_def = workbook.add_format(FORMATS['col_heading_def'])

        self.sec_col_heading = workbook.add_format(FORMATS['sec_col_heading'])
        self.sec_col_heading_def = workbook.add_format(FORMATS['sec_col_heading_def'])

        self.label = workbook.add_format(FORMATS['label'])

        self.N = workbook.add_format(FORMATS['N'])
        self.P = workbook.add_format(FORMATS['P'])

        # Use the following for specifying which reports to create during dev
        # sheets = [
        #     'ws_01', 'ws_02', 'ws_04', 'ws_05', 'ws_06', 'ws_07', 'ws_08', 'ws_09', 'ws_10',
        #     'ws_11', 'ws_12', 'ws_13', 'ws_14', 'ws_15', 'ws_16', 'ws_17', 'ws_18', 'ws_19', 'ws_20',
        #     'ws_21', 'ws_23', 'ws_24', 'ws_25', 'ws_26', 'ws_27', 'ws_28', 'ws_29', 'ws_30',
        #     'ws_31', 'ws_32', 'ws_34', 'ws_35', 'ws_36', 'ws_38', 'ws_39', 'ws_40',
        #     'ws_41', 'ws_42', 'ws_43', 'ws_44', 'ws_45', 'ws_46', 'ws_47', 'ws_48',
        #     'ws_49', 'ws_50', 'ws_51', 'ws_52', 'ws_53', 'ws_54', 'ws_55', 'ws_56', 'ws_57', 'ws_58', 'ws_59', 'ws_60',
        #     'ws_61', 'ws_62', 'ws_63', 'ws_64', 'ws_65', 'ws_66', 'ws_67', 'ws_68', 'ws_68b',
        #     'ws_75', 'ws_76', 'ws_77', 'ws_78']
        if settings.DEBUG:
            sheets = ['ws_65', 'ws_66', 'ws_67', 'ws_68', 'ws_68b']
        else:
            sheets = WS_INFO.keys()

        # choose only those suitable for this report type
        sheets = [s for s in sheets if self.report_type in WS_INFO[s]['reports']]
        sheets.sort()

        self.write_key_sheet(workbook, sheets)

        self.write_aggregate_sheet(workbook)

        for sheet in sheets:
            ws = workbook.add_worksheet(WS_INFO[sheet]['name'])
            self.write_headers(ws, WS_INFO[sheet]['title'], WS_INFO[sheet]['desc'])
            self.log.info("Building sheet %s" % sheet)
            getattr(self, sheet)(ws)
            self.log.info("Completed sheet %s" % sheet)

        if not settings.DEBUG:
            self.write_raw_data_sheets(workbook)

        workbook.close()
        output.seek(0)

        return output.read()

    def write_key_sheet(self, workbook, sheets):
        ws = workbook.add_worksheet('Key')

        ws.write(0, 0, 'Key to Query Sheets', self.heading)

        ws.write(2, 0, 'N')
        ws.write(2, 1, 'number of items (weighted)')
        ws.write(3, 0, 'N (raw)')
        ws.write(3, 1, 'number of items (NOT weighted)')

        ws.write(5, 0, 'Number', self.col_heading)
        ws.write(5, 1, 'Number in 2010 Report', self.col_heading)
        ws.write(5, 2, 'Title', self.col_heading)
        ws.write(5, 3, 'Description', self.col_heading)

        for i, sheet in enumerate(sheets):
            ws.write(6 + i, 0, WS_INFO[sheet]['name'])
            ws.write(6 + i, 1, WS_INFO[sheet]['title'])
            ws.write(6 + i, 1, WS_INFO[sheet].get('historical', ''))
            ws.write(6 + i, 2, WS_INFO[sheet]['desc'])


    def write_aggregate_sheet(self, workbook):
        ws = workbook.add_worksheet('Aggregates')
        c = 1
        ws.write(0, 0, 'Total amount of sheets, sources and reporters by country and media type.')
        for data_type, models in all_models.iteritems():
            r = 3
            ws.write(r-1, c+1, data_type)
            for i, col in enumerate(MEDIA_TYPES):
                ws.write(r, c+1+i, clean_title(col[1]), self.col_heading)
                ws.write(r + 1, c+1+i, "N (raw)")

            r = 6
            for region_id, region in self.regions:
                counts = Counter()
                for media_type, model in models.iteritems():
                    if data_type == 'Sheets':
                        country_field = 'country'
                    else:
                        country_field = model.sheet_name() + '__country'
                    rows = model.objects\
                            .values(country_field)\
                            .filter(**{country_field + '__in': self.country_list})\
                            .annotate(n=Count('id'))

                    for row in rows:
                        if row[country_field] is not None:
                            # Get media id's to assign to counts
                            media_id = [media[0] for media in MEDIA_TYPES if media[1] == media_type][0]
                            counts.update({(media_id, self.recode_country(row[country_field])): row['n']})
                self.write_primary_row_heading(ws, region, r=r)
                region_countries = [(code, country) for code, country in self.countries if code in REGION_COUNTRY_MAP[region]]

                for i, row in enumerate(region_countries):
                    row_id, row_heading = row
                    ws.write(r+i, c, clean_title(row_heading), self.label)

                c += 1
                for col_id, col_heading in MEDIA_TYPES:
                    # values for this column
                    for i, row in enumerate(region_countries):
                        row_id, row_title = row

                        n = counts.get((col_id, row_id), 0)
                        ws.write(r+i, c, n, self.N)

                    c += 1
                # Position for next region
                c -= (len(MEDIA_TYPES) + 1)
                r += (len(region_countries) + 2)

            c += (len(MEDIA_TYPES) + 3)


    def write_raw_data_sheets(self, workbook):
        for name, model in sheet_models.iteritems():
            ws = workbook.add_worksheet('Raw - %s sheets' % name)

            query = model.objects
            if self.country_list:
                query = query.filter(country__in=self.country_list)

            self.write_raw_data(ws, name, model, query)

        for name, model in person_models.iteritems():
            ws = workbook.add_worksheet('Raw - %s sources' % name)

            query = model.objects
            if self.country_list:
                query = query.filter(**{model.sheet_name() + '__country__in': self.country_list})\

            self.write_raw_data(ws, name, model, query)

        for name, model in journalist_models.iteritems():
            ws = workbook.add_worksheet('Raw - %s journalists' % name)

            query = model.objects
            if self.country_list:
                query = query.filter(**{model.sheet_name() + '__country__in': self.country_list})\

            self.write_raw_data(ws, name, model, query)

    def write_raw_data(self, ws, name, model, query):
            self.log.info("Writing raw data for %s" % model)

            # precompute the columns that are lookups
            lookups = {}
            for fld in model._meta.fields:
                if fld.choices:
                    lookups[fld.attname] = dict(fld.choices)
                # TODO: handle foreign key, too

            # headers
            c = 0
            for fld in model._meta.fields:
                if fld.attname in lookups:
                    ws.write(0, c, fld.name + '_code')
                    c += 1

                ws.write(0, c, fld.name)
                c += 1

            # values
            for r, obj in enumerate(query.all()):
                c = 0
                for fld in obj._meta.fields:
                    attr = fld.attname
                    if attr == 'country':
                        v = obj.country.code
                    else:
                        v = getattr(obj, attr)

                    if isinstance(v, datetime.datetime):
                        v = v.replace(tzinfo=None)

                    # raw value
                    if isinstance(v, basestring):
                        # if v is a URL and it contains unicode and it is
                        # very long, we get an encoding error from the warning
                        # message, so just force strings as strings
                        ws.write_string(r + 1, c, unicode(v))
                    else:
                        ws.write(r + 1, c, v)
                    c += 1

                    # write the looked-up value
                    if attr in lookups:
                        v = lookups[attr].get(v, v)
                        if v is not None:
                            v = unicode(v)
                        ws.write(r + 1, c, v)
                        c += 1

    def recode_country(self, country):
        # some split countries must be "joined" at the global report level
        if self.report_type == 'global':
            return COUNTRY_RECODES.get(country, country)
        return country

    def dictfetchall(self, cursor):
        """
        Returns all rows from a cursor as a dict
        """
        desc = cursor.description
        return [
            OrderedDict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
        ]

    def apply_weights(self, rows, db_table, media_type):
        """
        param rows: Queryset to apply the weights to
        param db_table: name of relevant sheet table
        param: media_type: media type to weigh by
        """
        query = rows.extra(
                tables=['reports_weights'],
                where=[
                    'reports_weights.country = %s.country' % (db_table),
                    'reports_weights.media_type = \'%s\'' % (media_type),
                ]).annotate()

        raw_query, params = query.query.sql_with_params()

        if self.report_type == 'country':
            weights = 'SELECT count(1) AS "n",'
        else:
            weights = 'SELECT cast(SUM(reports_weights.weight) as float) AS "n",'

        raw_query = raw_query.replace('SELECT', weights)
        cursor = connection.cursor()
        cursor.execute(raw_query, params)
        return self.dictfetchall(cursor)


    def ws_01(self, ws):
        """
        Cols: Media Type
        Rows: Region
        """
        counts_list = []
        for media_types, models in SHEET_MEDIA_GROUPS:
            counts = Counter()
            for media_type, model in models.iteritems():
                rows = model.objects\
                        .values('country_region__region')\
                        .filter(country_region__region__in=self.region_list)

                rows = self.apply_weights(rows, model._meta.db_table, media_type)

                for row in rows:
                    if row['region'] is not None:
                        # Get media and region id's to assign to counts
                        media_id = [media[0] for media in media_types if media[1] == media_type][0]
                        region_id = [region[0] for region in self.regions if region[1] == row['region']][0]
                        counts.update({(media_id, region_id): row['n']})
            counts_list.append(counts)

        self.tabulate(ws, counts_list[0], TM_MEDIA_TYPES, self.regions, row_perc=True)
        c = ws.dim_colmax + 2
        self.tabulate(ws, counts_list[1], DM_MEDIA_TYPES, self.regions, row_perc=True, c=c, write_row_headings=False)
        c = ws.dim_colmax + 2

        self.tabulate_historical(ws, '01', TM_MEDIA_TYPES, self.regions, c=c)

    def ws_02(self, ws):
        """
        Cols: Media Type
        Rows: Region, Country
        """
        r = 6
        c = 2

        weights = {(w.country, w.media_type): w.weight for w in Weights.objects.all()}
        first = True
        historical_c = None

        for region_id, region in self.regions:
            counts_list = []
            for media_types, models in SHEET_MEDIA_GROUPS:

                counts = Counter()
                for media_type, model in models.iteritems():
                    rows = model.objects\
                            .values('country')\
                            .filter(country__in=self.country_list)\
                            .annotate(n=Count('id'))

                    # rows = self.apply_distinct_weights(rows, model._meta.db_table, media_type)
                    for row in rows:
                        if row['country'] is not None:
                            weight = weights[(row['country'], media_type)]
                            # Get media id's to assign to counts
                            media_id = [media[0] for media in media_types if media[1] == media_type][0]
                            counts.update({(media_id, self.recode_country(row['country'])): row['n'] * weight})
                    for key, value in counts.iteritems():
                        counts[key] = int(round(value))
                counts_list.append(counts)

            self.write_primary_row_heading(ws, region, r=r)
            region_countries = [(code, country) for code, country in self.countries if code in REGION_COUNTRY_MAP[region]]
            self.tabulate(ws, counts_list[0], TM_MEDIA_TYPES, region_countries, row_perc=True, write_col_headings=True, r=r)
            c = 7
            self.tabulate(ws, counts_list[1], DM_MEDIA_TYPES, region_countries, row_perc=True, write_col_headings=True, write_row_headings=False, r=r, c=c)

            if historical_c is None:
                historical_c = ws.dim_colmax + 2

            self.tabulate_historical(ws, '02', TM_MEDIA_TYPES, region_countries, r=r, c=historical_c, write_year=first, write_col_headings=first)
            first = False

            r += (len(region_countries) + 2)

    def ws_03(self, ws):
        """
        Cols: Media type
        Rows: Region
        """
        # calculate total N for each media type for 2015,
        # then we'll compare it to 2010 and get a %age change

        # get the historical data for 2010
        counts = {}

        for media_type, model in sheet_models.iteritems():
            rows = model.objects\
                    .values('country_region__region')\
                    .annotate(n=Count(get_sheet_model_name_field(media_type), distinct=True))\
                    .filter(country_region__region__in=self.region_list)

            for row in rows:
                region = row['country_region__region']
                if region is not None:
                    # Get media and region id's to assign to counts
                    media_id, media = [m for m in MEDIA_TYPES if m[1] == media_type][0]
                    region_id, region = [r for r in self.regions if r[1] == region][0]

                    counts.update({(media_id, region_id): row['n']})

        self.tabulate(ws, counts, MEDIA_TYPES, self.regions, raw_values=True, write_col_totals=False, unweighted=True)
        self.tabulate_historical(ws, '03', TM_MEDIA_TYPES, self.regions, values_N=True)

    def ws_04(self, ws):
        """
        Cols: Region, Media type
        Rows: Major Topic
        """
        counts_list = []
        for media_types, models in SHEET_MEDIA_GROUPS:
            secondary_counts = OrderedDict()
            for region_id, region in self.regions:
                counts = Counter()
                for media_type, model in models.iteritems():
                    rows = model.objects\
                            .values('topic')\
                            .filter(country_region__region=region)

                    rows = self.apply_weights(rows, model._meta.db_table, media_type)

                    for r in rows:
                        # Get media id's to assign to counts
                        media_id = [media[0] for media in media_types if media[1] == media_type][0]
                        major_topic = TOPIC_GROUPS[r['topic']]
                        counts.update({(media_id, major_topic): r['n']})
                secondary_counts[region] = counts
            counts_list.append(secondary_counts)

        self.tabulate_secondary_cols(ws, counts_list[0], TM_MEDIA_TYPES, MAJOR_TOPICS, row_perc=False, show_N=True)
        c = ws.dim_colmax + 2
        self.tabulate_secondary_cols(ws, counts_list[1], DM_MEDIA_TYPES, MAJOR_TOPICS, row_perc=False, c=c, show_N=True)
        c = ws.dim_colmax + 2

        self.tabulate_historical(ws, '04', self.regions, MAJOR_TOPICS, c=c, r=7, skip_major_col_heading=True)

    def ws_05(self, ws):
        """
        Cols: Subject sex
        Rows: Major Topic
        """
        counts_list = []
        for media_types, models in PERSON_MEDIA_GROUPS:
            media_title = ', '.join(m[1] for m in media_types)
            secondary_counts = OrderedDict()

            for media_type, model in models.iteritems():
                if not media_title in secondary_counts:
                    secondary_counts[media_title] = Counter()

                counts = secondary_counts[media_title]
                topic_field = '%s__topic' % model.sheet_name()

                rows = model.objects\
                    .values('sex', topic_field)\
                    .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                    .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)
                for r in rows:
                    counts.update({(r['sex'], TOPIC_GROUPS[r['topic']]): r['n']})

            counts_list.append(secondary_counts)
        self.tabulate_secondary_cols(ws, counts_list[0], self.male_female, MAJOR_TOPICS, row_perc=True)
        c = ws.dim_colmax + 2
        self.tabulate_secondary_cols(ws, counts_list[1], self.male_female, MAJOR_TOPICS, row_perc=True, c=c, write_row_headings=False)
        c = ws.dim_colmax + 2

        self.tabulate_historical(ws, '05', self.male_female, MAJOR_TOPICS, c=c, r=7, skip_major_col_heading=True)

    def ws_06(self, ws):
        """
        Cols: Region, Subject sex: female only
        Rows: Major Topics
        """
        c = 1
        for media_types, models in PERSON_MEDIA_GROUPS:
            self.write_primary_row_heading(ws, ', '.join([m[1] for m in media_types]), c=c+1, r=4)
            secondary_counts = OrderedDict()

            for region_id, region in self.regions:
                counts = Counter()
                for media_type, model in models.iteritems():
                    topic_field = '%s__topic' % model.sheet_name()
                    rows = model.objects\
                        .values('sex', topic_field)\
                        .filter(**{model.sheet_name() + '__country_region__region':region})\
                        .filter(sex__in=self.male_female_ids)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    for r in rows:
                        counts.update({(r['sex'], TOPIC_GROUPS[r['topic']]): r['n']})
                secondary_counts[region] = counts
            self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, MAJOR_TOPICS, row_perc=True, filter_cols=self.female, show_N=True, c=c, r=8)
            c = ws.dim_colmax + 2

        self.tabulate_historical(ws, '06', self.female, MAJOR_TOPICS, major_cols=self.regions, show_N_and_P=True, r=7)

    def ws_07(self, ws):
        """
        Cols: Media Type
        Rows: Subject Sex
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            rows = model.objects\
                    .values('sex')\
                    .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                    .filter(sex__in=self.male_female_ids)

            rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

            for r in rows:
                # Get media id's to assign to counts
                media_id = [media[0] for media in MEDIA_TYPES if media[1] == media_type][0]
                counts.update({(media_id, r['sex']): r['n']})

        self.tabulate(ws, counts, TM_MEDIA_TYPES, self.male_female, row_perc=False)
        self.tabulate_historical(ws, '07', TM_MEDIA_TYPES, self.male_female, write_row_headings=False)

    def ws_08(self, ws):
        """
        Cols: Subject Sex
        Rows: Scope
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            if 'scope' in model.sheet_field().rel.to._meta.get_all_field_names():
                scope = '%s__scope' % model.sheet_name()
                rows = model.objects\
                        .values('sex', scope)\
                        .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['scope']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, SCOPE, row_perc=True, filter_cols=self.female)
        self.tabulate_historical(ws, '08', self.female, SCOPE, write_row_headings=False)

    def ws_09(self, ws):
        """
        Cols: Subject Sex
        Rows: Topic
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            topic = '%s__topic' % model.sheet_name()
            rows = model.objects\
                    .values('sex', topic)\
                    .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                    .filter(sex__in=self.male_female_ids)

            rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

            counts.update({(r['sex'], r['topic']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, TOPICS, row_perc=True, filter_cols=self.female)
        self.tabulate_historical(ws, '09', self.female, TOPICS, write_row_headings=False)

    def ws_10(self, ws):
        """
        Cols: Space
        Rows: Minor Topics
        :: Newspaper Sheets only
        """
        # Calculate row values for column
        counts = Counter()
        for media_type, model in sheet_models.iteritems():
            if media_type == 'Print':
                rows = model.objects\
                        .values('space', 'topic')\
                        .filter(country__in=self.country_list)

                rows = self.apply_weights(rows, model._meta.db_table, media_type)

                for r in rows:
                    counts.update({(r['space'], TOPIC_GROUPS[r['topic']]): r['n']})

        self.tabulate(ws, counts, SPACE, MAJOR_TOPICS, row_perc=False)

    def ws_11(self, ws):
        """
        Cols: Equality Rights
        Rows: Major Topics
        """
        counts = Counter()
        for media_type, model in tm_sheet_models.iteritems():
            if 'equality_rights' in model._meta.get_all_field_names():
                rows = model.objects\
                    .values('equality_rights', 'topic')\
                    .filter(country__in=self.country_list)

                rows = self.apply_weights(rows, model._meta.db_table, media_type)

                for r in rows:
                    counts.update({(r['equality_rights'], TOPIC_GROUPS[r['topic']]): r['n']})

        self.tabulate(ws, counts, YESNO, MAJOR_TOPICS, row_perc=True)

    def ws_12(self, ws):
        """
        Cols: Region, Equality Rights
        Rows: Major Topics
        """
        secondary_counts = OrderedDict()
        for region_id, region_name in self.regions:
            counts = Counter()
            for media_type, model in tm_sheet_models.iteritems():
                # Some models has no equality rights field
                if 'equality_rights' in model._meta.get_all_field_names():
                    rows = model.objects\
                        .values('equality_rights', 'topic')\
                        .filter(country_region__region=region_name)

                    rows = self.apply_weights(rows, model._meta.db_table, media_type)

                    for r in rows:
                        counts.update({(r['equality_rights'], TOPIC_GROUPS[r['topic']]): r['n']})
            secondary_counts[region_name] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, YESNO, MAJOR_TOPICS, row_perc=True)

    def ws_13(self, ws):
        """
        Cols: Journalist Sex, Equality Rights
        Rows: Topics
        """
        secondary_counts = OrderedDict()
        for gender_id, gender in self.male_female:
            counts = Counter()
            for media_type, model in tm_journalist_models.iteritems():
                if 'equality_rights' in model.sheet_field().rel.to._meta.get_all_field_names():
                    topic = '%s__topic' % model.sheet_name()
                    equality_rights = '%s__equality_rights' % model.sheet_name()
                    rows = model.objects\
                            .values(equality_rights, topic)\
                            .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                            .filter(sex=gender_id)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    for r in rows:
                        counts.update({(r['equality_rights'], TOPIC_GROUPS[r['topic']]): r['n']})
            secondary_counts[gender] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, YESNO, MAJOR_TOPICS, row_perc=True)

    def ws_14(self, ws):
        """
        Cols: Sex
        Rows: Occupation
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            # some Person models don't have an occupation field
            if 'occupation' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', 'occupation')\
                        .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['occupation']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, OCCUPATION, row_perc=True, filter_cols=self.female)
        self.tabulate_historical(ws, '14', self.female, OCCUPATION, write_row_headings=False)

    def ws_15(self, ws):
        """
        Cols: Sex
        Rows: Function
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            # some Person models don't have a function field
            if 'function' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', 'function')\
                        .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['function']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, FUNCTION, row_perc=True, filter_cols=self.female)
        self.tabulate_historical(ws, '15', self.female, FUNCTION, write_row_headings=False)

    def ws_16(self, ws):
        """
        Cols: Function, Sex
        Rows: Occupation
        """
        secondary_counts = OrderedDict()
        for function_id, function in FUNCTION:
            counts = Counter()
            for media_type, model in tm_person_models.iteritems():
                if 'function' in model._meta.get_all_field_names() and 'occupation' in model._meta.get_all_field_names():
                    rows = model.objects\
                            .values('sex', 'occupation')\
                            .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                            .filter(function=function_id)\
                            .filter(sex__in=self.male_female_ids)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    counts.update({(r['sex'], r['occupation']): r['n'] for r in rows})
            secondary_counts[function] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, OCCUPATION, row_perc=False)
        self.tabulate_historical(ws, '16', self.male_female, OCCUPATION, major_cols=FUNCTION)

    def ws_17(self, ws):
        """
        Cols: Age, Sex of Subject
        Rows: Function
        """
        secondary_counts = OrderedDict()
        for age_id, age in AGES:
            counts = Counter()
            for media_type, model in tm_person_models.iteritems():
                if 'function' in model._meta.get_all_field_names() and 'age' in model._meta.get_all_field_names():
                    rows = model.objects\
                            .values('sex', 'function')\
                            .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                            .filter(age=age_id)\
                            .filter(sex__in=self.male_female_ids)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    counts.update({(r['sex'], r['function']): r['n'] for r in rows})
            secondary_counts[age] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, FUNCTION, row_perc=False)
        self.tabulate_historical(ws, '17', self.male_female, FUNCTION, major_cols=AGES)

    def ws_18(self, ws):
        """
        Cols: Sex
        Rows: Age
        :: Only for print
        """
        counts = Counter()
        rows = NewspaperPerson.objects\
                .values('sex', 'age')\
                .filter(newspaper_sheet__country__in=self.country_list)\
                .filter(sex__in=self.male_female_ids)

        rows = self.apply_weights(rows, NewspaperPerson.sheet_db_table(), 'Print')
        counts.update({(r['sex'], r['age']): r['n'] for r in rows})
        self.tabulate(ws, counts, self.male_female, AGES, row_perc=True)

        self.tabulate_historical(ws, '18', self.male_female, AGES, write_row_headings=False)

    def ws_19(self, ws):
        """
        Cols: Sex
        Rows: Age
        :: Only for broadcast
        """
        counts = Counter()
        broadcast = ['Television']
        for media_type, model in person_models.iteritems():
             if media_type in broadcast:
                rows = model.objects\
                        .values('sex', 'age')\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['age']): r['n'] for r in rows})

        self.tabulate_secondary_cols(ws, {'Television': counts}, self.male_female, AGES, row_perc=True)
        self.tabulate_historical(ws, '19', self.male_female, AGES, major_cols=[(3, 'Television')], write_row_headings=False)

    def ws_20(self, ws):
        """
        Cols: Function, Sex
        Rows: Occupation
        """
        secondary_counts = OrderedDict()

        for func_id, function in FUNCTION:
            counts = Counter()
            for media_type, model in tm_person_models.iteritems():
                if 'function' in model._meta.get_all_field_names() and 'occupation' in model._meta.get_all_field_names():
                    rows = model.objects\
                            .values('sex', 'occupation')\
                            .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                            .filter(function=func_id)\
                            .filter(sex__in=self.male_female_ids)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    counts.update({(r['sex'], r['occupation']): r['n'] for r in rows})
            secondary_counts[function] = counts
        self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, OCCUPATION, row_perc=False)
        self.tabulate_historical(ws, '20', self.male_female, OCCUPATION, major_cols=FUNCTION)

    def ws_21(self, ws):
        """
        Cols: Subject Sex
        Rows: Victim type
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            if 'victim_of' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', 'victim_of')\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)\
                        .exclude(victim_of=None)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['victim_of']): r['n'] for r in rows})
        self.tabulate(ws, counts, self.male_female, VICTIM_OF, row_perc=False, show_N=True)
        self.tabulate_historical(ws, '21', self.male_female, VICTIM_OF)

    def ws_23(self, ws):
        """
        Cols: Subject Sex
        Rows: Survivor type
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            if 'survivor_of' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', 'survivor_of')\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .exclude(survivor_of=None)\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['survivor_of']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, SURVIVOR_OF, row_perc=False, show_N=True)
        self.tabulate_historical(ws, '23', self.male_female, SURVIVOR_OF)

    def ws_24(self, ws):
        """
        Cols: Subject Sex
        Rows: Family Role
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            if 'family_role' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', 'family_role')\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['family_role']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, YESNO, row_perc=False)
        self.tabulate_historical(ws, '24', self.male_female, YESNO)

    def ws_25(self, ws):
        """
        Cols: Journalist Sex, Subject Sex
        Rows: Family Role
        """
        secondary_counts = OrderedDict()
        for sex_id, sex in self.male_female:
            counts = Counter()
            for media_type, model in tm_person_models.iteritems():
                if 'family_role' in model._meta.get_all_field_names():
                    sheet_name = model.sheet_name()
                    journo_name = model._meta.get_field(model.sheet_name()).rel.to.journalist_field_name()
                    rows = model.objects\
                            .values('sex', 'family_role')\
                            .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                            .filter(**{sheet_name + '__' + journo_name + '__sex':sex_id})\
                            .filter(sex__in=self.male_female_ids)

                    if media_type in REPORTER_MEDIA:
                        rows = rows.filter(**{sheet_name + '__' + journo_name + '__role':REPORTERS})

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)
                    counts.update({(r['sex'], r['family_role']): r['n'] for r in rows})
            secondary_counts[sex] = counts

        secondary_counts['col_title_def'] = [
            'Sex of reporter',
            'Sex of news subject']

        self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, YESNO, row_perc=False)
        self.tabulate_historical(ws, '25', self.male_female, YESNO, major_cols=self.male_female, write_row_headings=False)

    def ws_26(self, ws):
        """
        Cols: Subject Sex
        Rows: Whether Quoted
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            if 'is_quoted' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', 'is_quoted')\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['is_quoted']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, YESNO, row_perc=False)
        self.tabulate_historical(ws, '26', self.male_female, YESNO, write_row_headings=False)

    def ws_27(self, ws):
        """
        Cols: Subject Sex
        Rows: Photographed
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            if 'is_photograph' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', 'is_photograph')\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['is_photograph']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, IS_PHOTOGRAPH, row_perc=False)
        self.tabulate_historical(ws, '27', self.male_female, IS_PHOTOGRAPH, write_row_headings=False)

    def ws_28(self, ws):
        """
        Cols: Medium, Journalist Sex
        Rows: Region
        :: Reporters + Presenters
        """
        if self.report_type == 'country':
            secondary_counts = OrderedDict()
            for media_type, model in tm_journalist_models.iteritems():
                counts = Counter()
                country = model.sheet_name() + '__country'
                rows = model.objects\
                        .values('sex', country)\
                        .filter(**{country + '__in': self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                for row in rows:
                    counts.update({(row['sex'], row['country']): row['n']})
                secondary_counts[media_type] = counts
            self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, self.countries, row_perc=True, show_N=True)
        else:
            secondary_counts = OrderedDict()
            for media_type, model in tm_journalist_models.iteritems():
                counts = Counter()
                region = model.sheet_name() + '__country_region__region'
                rows = model.objects\
                        .values('sex', region)\
                        .filter(**{region + '__in': self.region_list})\
                        .filter(sex__in=self.male_female_ids)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                for row in rows:
                    region_id = [r[0] for r in self.regions if r[1] == row['region']][0]

                    counts.update({(row['sex'], region_id): row['n']})
                secondary_counts[media_type] = counts
            self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, self.regions, row_perc=True, show_N=True)
            self.tabulate_historical(ws, '28', self.male_female, self.regions, r=7)

    def ws_29(self, ws):
        """
        Cols: Regions, Journalist Sex
        Rows: Scope
        :: Reporters only
        """
        if self.report_type == 'country':
            secondary_counts = OrderedDict()
            for country_code, country_name in self.countries:
                counts = Counter()
                for media_type, model in tm_journalist_models.iteritems():
                    sheet_name = model.sheet_name()
                    country = sheet_name + '__country'
                    scope =  sheet_name + '__scope'
                    if 'scope' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                        rows = model.objects\
                                .values('sex', scope)\
                                .filter(**{country + '__in': self.country_list})\
                                .filter(sex__in=self.male_female_ids)
                        if media_type in REPORTER_MEDIA:
                            rows = rows.filter(role=REPORTERS)

                        rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                        for row in rows:
                            counts.update({(row['sex'], row['scope']): row['n']})
                secondary_counts[country_name] = counts
            self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, SCOPE, row_perc=False, show_N=True)
        else:
            secondary_counts = OrderedDict()
            for region_id, region_name in self.regions:
                counts = Counter()
                for media_type, model in tm_journalist_models.iteritems():
                    sheet_name = model.sheet_name()
                    region = sheet_name + '__country_region__region'
                    scope =  sheet_name + '__scope'
                    if 'scope' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                        rows = model.objects\
                                .values('sex', scope)\
                                .filter(**{region: region_name})\
                                .filter(sex__in=self.male_female_ids)

                        if media_type in REPORTER_MEDIA:
                            rows = rows.filter(role=REPORTERS)

                        rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                        for row in rows:
                            counts.update({(row['sex'], row['scope']): row['n']})
                secondary_counts[region_name] = counts

            self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, SCOPE, row_perc=False, show_N=True)

    def ws_30(self, ws):
        """
        Cols: Region, Sex of reporter
        Rows: Major Topics
        :: Reporters only
        """
        if self.report_type == 'country':
            secondary_counts = OrderedDict()
            for country_code, country_name in self.countries:
                counts = Counter()
                for media_type, model in tm_journalist_models.iteritems():
                    sheet_name = model.sheet_name()
                    country = sheet_name + '__country'
                    topic =  sheet_name + '__topic'
                    if 'topic' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                        rows = model.objects\
                                .values('sex', topic)\
                                .filter(**{country + '__in': self.country_list})\
                                .filter(sex__in=self.male_female_ids)

                        if media_type in REPORTER_MEDIA:
                            rows = rows.filter(role=REPORTERS)

                        rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                        for row in rows:
                            major_topic = TOPIC_GROUPS[row['topic']]
                            counts.update({(row['sex'], major_topic): row['n']})
                secondary_counts[country_name] = counts
            self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, MAJOR_TOPICS, row_perc=False, show_N=True)
        else:
            secondary_counts = OrderedDict()
            for region_id, region_name in self.regions:
                counts = Counter()
                for media_type, model in tm_journalist_models.iteritems():
                    sheet_name = model.sheet_name()
                    region = sheet_name + '__country_region__region'
                    topic =  sheet_name + '__topic'
                    if 'topic' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                        rows = model.objects\
                                .values('sex', topic)\
                                .filter(**{region: region_name})\
                                .filter(sex__in=self.male_female_ids)

                        if media_type in REPORTER_MEDIA:
                            rows = rows.filter(role=REPORTERS)

                        rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                        for row in rows:
                            major_topic = TOPIC_GROUPS[row['topic']]
                            counts.update({(row['sex'], major_topic): row['n']})
                secondary_counts[region_name] = counts

            self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, MAJOR_TOPICS, row_perc=False, show_N=True)

    def ws_31(self, ws):
        """
        Cols: Sex of Reporter
        Rows: Minor Topics
        """
        counts = Counter()
        for media_type, model in tm_journalist_models.iteritems():
            sheet_name = model.sheet_name()
            topic =  sheet_name + '__topic'
            if 'topic' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', topic)\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                if media_type in REPORTER_MEDIA:
                    rows = rows.filter(role=REPORTERS)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['topic']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, TOPICS, row_perc=True, filter_cols=self.female)
        self.tabulate_historical(ws, '31', self.female, TOPICS, write_row_headings=False)

    def ws_32(self, ws):
        """
        Cols: Medium
        Rows: Topics
        :: Reporters only
        """
        secondary_counts = OrderedDict()

        for media_type, model in tm_journalist_models.iteritems():
            counts = Counter()
            sheet_name = model.sheet_name()
            topic =  sheet_name + '__topic'
            if 'topic' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', topic)\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                if media_type in REPORTER_MEDIA:
                    rows = rows.filter(role=REPORTERS)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                for row in rows:
                    counts.update({(row['sex'], row['topic']): row['n']})
            secondary_counts[media_type] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, TOPICS, row_perc=False, show_N=True)

    def ws_34(self, ws):
        """
        Cols: Sex of reporter
        Rows: Sex of subject
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            sheet_name = model.sheet_name()
            journo_name = model._meta.get_field(model.sheet_name()).rel.to.journalist_field_name()
            journo_sex = sheet_name + '__' + journo_name + '__sex'
            rows = model.objects\
                    .extra(select={"subject_sex": model._meta.db_table + ".sex"})\
                    .values(journo_sex, 'subject_sex')\
                    .filter(**{model.sheet_name() + '__country__in': self.country_list})\
                    .annotate(n=Count('id'))

            if media_type in REPORTER_MEDIA:
                rows = rows.filter(**{sheet_name + '__' + journo_name + '__role':REPORTERS})

            rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

            counts.update({(r['sex'], r['subject_sex']): r['n'] for r in rows})
        counts['col_title_def'] = 'Sex of reporter'

        self.tabulate(ws, counts, self.male_female, GENDER, row_perc=True)
        self.tabulate_historical(ws, '34', self.female, GENDER, write_row_headings=False)

    def ws_35(self, ws):
        """
        Cols: Sex of reporter
        Rows: Age of reporter
        :: Only for television
        """
        secondary_counts = OrderedDict()

        counts = Counter()
        secondary_counts[TV_ROLE_ANNOUNCER[1]] = counts
        rows = TelevisionJournalist.objects\
                .values('sex', 'age')\
                .filter(television_sheet__country__in=self.country_list)\
                .filter(sex__in=self.male_female_ids)\
                .filter(role=TV_ROLE_ANNOUNCER[0])

        rows = self.apply_weights(rows, TelevisionJournalist.sheet_db_table(), 'Television')
        counts.update({(r['sex'], r['age']): r['n'] for r in rows})

        counts = Counter()
        secondary_counts[TV_ROLE_REPORTER[1]] = counts
        rows = TelevisionJournalist.objects\
                .values('sex', 'age')\
                .filter(television_sheet__country__in=self.country_list)\
                .filter(sex__in=self.male_female_ids)\
                .filter(role=TV_ROLE_REPORTER[0])

        rows = self.apply_weights(rows, TelevisionJournalist.sheet_db_table(), 'Television')
        counts.update({(r['sex'], r['age']): r['n'] for r in rows})

        self.tabulate_secondary_cols(ws, secondary_counts, self.male_female, AGES, row_perc=False, show_N=True)

        major_cols = [TV_ROLE_ANNOUNCER, TV_ROLE_REPORTER]
        self.tabulate_historical(ws, '35', self.female, AGES, major_cols=major_cols, write_row_headings=False)

    def ws_36(self, ws):
        """
        Cols: Sex of Reporter
        Rows: Focus: about women
        """
        counts = Counter()
        for media_type, model in tm_journalist_models.iteritems():
            sheet_name = model.sheet_name()
            about_women =  sheet_name + '__about_women'
            if 'about_women' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                rows = model.objects\
                        .values('sex', about_women)\
                        .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                        .filter(sex__in=self.male_female_ids)

                if media_type in REPORTER_MEDIA:
                    rows = rows.filter(role=REPORTERS)

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                counts.update({(r['sex'], r['about_women']): r['n'] for r in rows})

        self.tabulate(ws, counts, self.male_female, YESNO, row_perc=False)
        self.tabulate_historical(ws, '36', self.male_female, YESNO, write_row_headings=False)

    def ws_38(self, ws):
        """
        Cols: Focus: about women
        Rows: Major Topics
        """
        counts = Counter()
        for media_type, model in tm_sheet_models.iteritems():
            if 'about_women' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('about_women', 'topic')\
                        .filter(country__in=self.country_list)

                rows = self.apply_weights(rows, model._meta.db_table, media_type)

                for r in rows:
                    counts.update({(r['about_women'], TOPIC_GROUPS[r['topic']]): r['n']})

        self.tabulate(ws, counts, YESNO, MAJOR_TOPICS, row_perc=True)

    def ws_39(self, ws):
        """
        Cols: Focus: about women
        Rows: Topics
        """
        counts = Counter()
        for media_type, model in tm_sheet_models.iteritems():
            if 'about_women' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('about_women', 'topic')\
                        .filter(country__in=self.country_list)

                rows = self.apply_weights(rows, model._meta.db_table, media_type)

                counts.update({(r['about_women'], r['topic']): r['n'] for r in rows})

        self.tabulate(ws, counts, YESNO, TOPICS, row_perc=True, filter_cols=self.yes)
        self.tabulate_historical(ws, '39', self.yes, TOPICS, write_row_headings=False)

    def ws_40(self, ws):
        """
        Cols: Region, Topics
        Rows: Focus: about women
        """
        secondary_counts = OrderedDict()
        for region_id, region in self.regions:
            counts = Counter()
            for media_type, model in tm_sheet_models.iteritems():
                if 'about_women' in model._meta.get_all_field_names():
                    rows = model.objects\
                            .values('topic', 'about_women')\
                            .filter(country_region__region=region)

                    rows = self.apply_weights(rows, model._meta.db_table, media_type)

                    counts.update({(r['about_women'], r['topic']): r['n'] for r in rows})
            secondary_counts[region] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, YESNO, TOPICS, row_perc=False, filter_cols=self.yes)
        self.tabulate_historical(ws, '40', self.regions, TOPICS, write_row_headings=False, r=7)

    def ws_41(self, ws):
        """
        Cols: Equality rights raised
        Rows: Topics
        """
        counts = Counter()
        for media_type, model in tm_sheet_models.iteritems():
            if 'equality_rights' in model._meta.get_all_field_names():
                rows = model.objects\
                        .values('equality_rights', 'topic')\
                        .filter(country__in=self.country_list)

                rows = self.apply_weights(rows, model._meta.db_table, media_type)

                counts.update({(r['equality_rights'], r['topic']): r['n'] for r in rows})
        self.tabulate(ws, counts, YESNO, TOPICS, row_perc=False, show_N=True)
        self.tabulate_historical(ws, '41', self.female, TOPICS, write_row_headings=False, r=6)

    def ws_42(self, ws):
        """
        Cols: Region, Equality rights raised
        Rows: Topics
        """
        secondary_counts = OrderedDict()
        for region_id, region in self.regions:
            counts = Counter()
            for media_type, model in tm_sheet_models.iteritems():
                if 'equality_rights' in model._meta.get_all_field_names():
                    rows = model.objects\
                            .values('topic', 'equality_rights')\
                            .filter(country_region__region=region)

                    rows = self.apply_weights(rows, model._meta.db_table, media_type)

                    counts.update({(r['equality_rights'], r['topic']): r['n'] for r in rows})
            secondary_counts[region] = counts
        self.tabulate_secondary_cols(ws, secondary_counts, YESNO, TOPICS, row_perc=True)

    def ws_43(self, ws):
        """
        Cols: Sex of reporter, Equality rights raised
        Cols: Topics
        """
        secondary_counts = OrderedDict()
        for gender_id, gender in self.male_female:
            counts = Counter()
            for media_type, model in tm_journalist_models.iteritems():
                sheet_name = model.sheet_name()
                topic = sheet_name + '__topic'
                equality_rights =  sheet_name + '__equality_rights'
                if 'equality_rights' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                    rows = model.objects\
                            .values(topic, equality_rights)\
                            .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                            .filter(sex=gender_id)

                    if media_type in REPORTER_MEDIA:
                        rows = rows.filter(role=REPORTERS)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    counts.update({(r['equality_rights'], r['topic']): r['n'] for r in rows})
            secondary_counts[gender] = counts
        self.tabulate_secondary_cols(ws, secondary_counts, YESNO, TOPICS, row_perc=True)

    def ws_44(self, ws):
        """
        Cols: Sex of reporter, Equality rights raised
        Rows: Region
        """
        secondary_counts = OrderedDict()
        for gender_id, gender in self.male_female:
            counts = Counter()
            for media_type, model in tm_journalist_models.iteritems():
                sheet_name = model.sheet_name()
                region = sheet_name + '__country_region__region'
                equality_rights =  sheet_name + '__equality_rights'
                if 'equality_rights' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                    rows = model.objects\
                            .values(equality_rights, region)\
                            .filter(sex=gender_id)\
                            .filter(**{region + '__in':self.region_list})

                    if media_type in REPORTER_MEDIA:
                        rows = rows.filter(role=REPORTERS)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    for r in rows:
                        region_id = [id for id, name in self.regions if name == r['region']][0]
                        counts.update({(r['equality_rights'], region_id): r['n']})
            secondary_counts[gender] = counts
        self.tabulate_secondary_cols(ws, secondary_counts, YESNO, self.regions, row_perc=True)
        self.tabulate_historical(ws, '44', self.male_female, self.regions, write_row_headings=False, r=7, skip_major_col_heading=True)

    def ws_45(self, ws):
        """
        Cols: Sex of news subject
        Rows: Region
        :: Equality rights raised == Yes
        """
        counts = Counter()
        for media_type, model in tm_person_models.iteritems():
            if 'equality_rights' in model.sheet_field().rel.to._meta.get_all_field_names():
                region = model.sheet_name() + '__country_region__region'
                equality_rights = model.sheet_name() + '__equality_rights'
                rows = model.objects\
                        .values('sex', region)\
                        .filter(**{region + '__in':self.region_list})\
                        .filter(**{equality_rights:'Y'})

                rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                for r in rows:
                    region_id = [id for id, name in self.regions if name == r['region']][0]
                    counts.update({(r['sex'], region_id): r['n']})
        self.tabulate(ws, counts, self.male_female, self.regions, row_perc=True)
        self.tabulate_historical(ws, '45', self.male_female, self.regions, write_row_headings=False)

    def ws_46(self, ws):
        """
        Cols: Region, Stereotypes
        Rows: Major Topics
        """
        secondary_counts = OrderedDict()
        for region_id, region in self.regions:
            counts = Counter()
            for media_type, model in tm_sheet_models.iteritems():
                if 'stereotypes' in model._meta.get_all_field_names():
                    rows = model.objects\
                            .values('stereotypes', 'topic')\
                            .filter(country_region__region=region)

                    rows = self.apply_weights(rows, model._meta.db_table, media_type)

                    for r in rows:
                        counts.update({(TOPIC_GROUPS[r['topic']], r['stereotypes']): r['n']})
            secondary_counts[region] = counts
        self.tabulate_secondary_cols(ws, secondary_counts, AGREE_DISAGREE, MAJOR_TOPICS, row_perc=True)

    def ws_47(self, ws):
        """
        Cols: Stereotypes
        Rows: Major Topics
        """
        counts = Counter()
        for media_type, model in tm_sheet_models.iteritems():
            rows = model.objects\
                    .values('stereotypes', 'topic')\
                    .filter(country__in=self.country_list)

            rows = self.apply_weights(rows, model._meta.db_table, media_type)

            for r in rows:
                counts.update({(r['stereotypes'], TOPIC_GROUPS[r['topic']]): r['n']})

        self.tabulate(ws, counts, AGREE_DISAGREE, MAJOR_TOPICS, row_perc=True)

    def ws_48(self, ws):
        """
        Cols: Sex of reporter, Stereotypes
        Rows: Major Topics
        """
        secondary_counts = OrderedDict()
        for gender_id, gender in self.male_female:
            counts = Counter()
            for media_type, model in tm_journalist_models.iteritems():
                sheet_name = model.sheet_name()
                topic = sheet_name + '__topic'
                stereotypes =  sheet_name + '__stereotypes'
                if 'stereotypes' in model._meta.get_field(sheet_name).rel.to._meta.get_all_field_names():
                    rows = model.objects\
                            .values(stereotypes, topic)\
                            .filter(sex=gender_id)\
                            .filter(**{model.sheet_name() + '__country__in':self.country_list})

                    if media_type in REPORTER_MEDIA:
                        rows = rows.filter(role=REPORTERS)

                    rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

                    for r in rows:
                        counts.update({(r['stereotypes'], TOPIC_GROUPS[r['topic']]): r['n']})
            secondary_counts[gender] = counts
        self.tabulate_secondary_cols(ws, secondary_counts, AGREE_DISAGREE, MAJOR_TOPICS, row_perc=True, show_N=True)

    def ws_49(self, ws):
        """
        Cols: Major Topics
        Rows: Region
        :: Internet media type only
        """
        if self.report_type == 'country':
            counts = Counter()
            model = sheet_models.get('Internet')
            rows = model.objects\
                    .values('topic', 'country')\
                    .filter(country__in=self.country_list)

            rows = self.apply_weights(rows, model._meta.db_table, 'Internet')

            for row in rows:
                major_topic = TOPIC_GROUPS[row['topic']]
                counts.update({(major_topic, row['country']): row['n']})

            self.tabulate(ws, counts, MAJOR_TOPICS, self.countries, row_perc=True)
        else:
            counts = Counter()
            model = sheet_models.get('Internet')
            rows = model.objects\
                    .values('topic', 'country_region__region')\
                    .filter(country_region__region__in=self.region_list)

            rows = self.apply_weights(rows, model._meta.db_table, 'Internet')

            for row in rows:
                region_id = [r[0] for r in self.regions if r[1] == row['region']][0]
                major_topic = TOPIC_GROUPS[row['topic']]
                counts.update({(major_topic, region_id): row['n']})

            self.tabulate(ws, counts, MAJOR_TOPICS, self.regions, row_perc=True)

    def ws_50(self, ws):
        """
        Cols: Major Topics
        Rows: Country
        :: Internet media type only
        :: Only stories shared on Twitter
        """
        counts = Counter()
        model = sheet_models.get('Internet')
        rows = model.objects\
                .values('topic', 'country')\
                .filter(country__in=self.country_list)\
                .filter(shared_via_twitter='Y')

        rows = self.apply_weights(rows, model._meta.db_table, 'Internet')

        for row in rows:
            major_topic = TOPIC_GROUPS[row['topic']]
            counts.update({(major_topic, self.recode_country(row['country'])): row['n']})

        self.tabulate(ws, counts, MAJOR_TOPICS, self.countries, row_perc=True)

    def ws_51(self, ws):
        """
        Cols: Major Topics
        Rows: Country
        :: Internet media type only
        :: Only stories shared on Facebook
        """
        counts = Counter()
        model = sheet_models.get('Internet')
        rows = model.objects\
                .values('topic', 'country')\
                .filter(country__in=self.country_list)\
                .filter(shared_on_facebook='Y')

        rows = self.apply_weights(rows, model._meta.db_table, 'Internet')

        for row in rows:
            major_topic = TOPIC_GROUPS[row['topic']]
            counts.update({(major_topic, self.recode_country(row['country'])): row['n']})

        self.tabulate(ws, counts, MAJOR_TOPICS, self.countries, row_perc=True)

    def ws_52(self, ws):
        """
        Cols: Major Topics
        Rows: Country
        :: Internet media type only
        :: Only stories with reference to gener equality
        """
        counts = Counter()
        model = sheet_models.get('Internet')
        rows = model.objects\
                .values('topic', 'country')\
                .filter(country__in=self.country_list)\
                .filter(equality_rights='Y')

        rows = self.apply_weights(rows, model._meta.db_table, 'Internet')

        for row in rows:
            major_topic = TOPIC_GROUPS[row['topic']]
            counts.update({(major_topic, self.recode_country(row['country'])): row['n']})

        self.tabulate(ws, counts, MAJOR_TOPICS, self.countries, row_perc=True)

    def ws_53(self, ws):
        """
        Cols: Topic
        Rows: Country
        :: Internet media type only
        :: Female reporters only
        """
        filter_cols = [(id, value) for id, value in GENDER if id==1]
        secondary_counts = OrderedDict()
        model = sheet_models.get('Internet')

        for major_topic, topic_ids in GROUP_TOPICS_MAP.iteritems():
            counts = Counter()
            journo_sex_field = '%s__sex' % model.journalist_field_name()
            rows = model.objects\
                .values(journo_sex_field, 'country')\
                .filter(topic__in=topic_ids)

            rows = self.apply_weights(rows, model._meta.db_table, 'Internet')
            counts.update({(r['sex'], self.recode_country(r['country'])): r['n'] for r in rows})
            major_topic_name = [mt[1] for mt in MAJOR_TOPICS if mt[0] == int(major_topic)][0]
            secondary_counts[major_topic_name] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, GENDER, self.countries, row_perc=True, filter_cols=filter_cols)

    def ws_54(self, ws):
        """
        Cols: Major Topic, sex of subject
        Rows: Country
        :: Internet media type only
        """
        secondary_counts = OrderedDict()
        model = person_models.get('Internet')
        for major_topic, topic_ids in GROUP_TOPICS_MAP.iteritems():
            counts = Counter()
            country_field = '%s__country' % model.sheet_name()
            rows = model.objects\
                .values('sex', country_field)\
                .filter(**{model.sheet_name() + '__topic__in':topic_ids})

            rows = self.apply_weights(rows, model.sheet_db_table(), 'Internet')
            counts.update({(r['sex'], self.recode_country(r['country'])): r['n'] for r in rows})
            major_topic_name = [mt[1] for mt in MAJOR_TOPICS if mt[0] == int(major_topic)][0]
            secondary_counts[major_topic_name] = counts

        self.tabulate_secondary_cols(ws, secondary_counts, GENDER, self.countries, row_perc=True)

    def ws_55(self, ws):
        """
        Cols: Occupation
        Rows: Country
        :: Show all countries
        :: Only female subjects
        :: Internet media type only
        """
        counts = Counter()
        model = person_models.get('Internet')
        country_field = '%s__country' % model.sheet_name()

        rows = model.objects\
                .values(country_field, 'occupation')\
                .filter(sex=1)

        rows = self.apply_weights(rows, model.sheet_db_table(), "Internet")
        counts.update({(r['occupation'], self.recode_country(r['country'])): r['n'] for r in rows})
        self.tabulate(ws, counts, OCCUPATION, self.countries, row_perc=True)

    def ws_56(self, ws):
        """
        Cols: Function
        Rows: Country
        :: Show all countries
        :: Internet media type only
        """
        counts = Counter()
        model = person_models.get('Internet')
        country_field = '%s__country' % model.sheet_name()
        rows = model.objects\
                .values(country_field, 'function')\
                .annotate(n=Count('id'))

        rows = self.apply_weights(rows, model.sheet_db_table(), "Internet")
        counts.update({(r['function'], self.recode_country(r['country'])): r['n'] for r in rows})
        self.tabulate(ws, counts, FUNCTION, self.countries, row_perc=True)

    def ws_57(self, ws):
        """
        Cols: Sex of subject
        Rows: Country, Family role
        :: Show all countries
        :: Internet media type only
        """
        r = 6
        self.write_col_headings(ws, GENDER)

        counts = Counter()
        model = person_models.get('Internet')
        for code, country in self.countries:
            rows = model.objects\
                    .values('sex', 'family_role')\
                    .filter(**{model.sheet_name() + '__country':code})

            rows = self.apply_weights(rows, model.sheet_db_table(), "Internet")

            counts = {(row['sex'], row['family_role']): row['n'] for row in rows}
            # If only captured countries should be displayed use
            # if counts.keys():
            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, GENDER, YESNO, row_perc=True, write_col_headings=False, r=r)
            r += len(YESNO)

    def ws_58(self, ws):
        """
        Cols: Sex of subject
        Rows: Country, is photographed
        :: Show all countries
        :: Internet media type only
        """
        r = 6
        self.write_col_headings(ws, GENDER)

        counts = Counter()
        model = person_models.get('Internet')
        for code, country in self.countries:
            rows = model.objects\
                    .values('sex', 'is_photograph')\
                    .filter(**{model.sheet_name() + '__country':code})

            rows = self.apply_weights(rows, model.sheet_db_table(), "Internet")
            counts = {(row['sex'], row['is_photograph']): row['n'] for row in rows}

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, GENDER, IS_PHOTOGRAPH, row_perc=True, write_col_headings=False, r=r)
            r += len(IS_PHOTOGRAPH)

    def ws_59(self, ws):
        """
        Cols: Sex of reporter
        Rows: Sex of subject
        :: Internet media only
        """
        counts = Counter()
        model = person_models.get('Internet')
        sheet_name = model.sheet_name()
        journo_name = model._meta.get_field(model.sheet_name()).rel.to.journalist_field_name()
        journo_sex = sheet_name + '__' + journo_name + '__sex'

        rows = model.objects\
                .extra(select={"subject_sex": model._meta.db_table + ".sex"})\
                .values(journo_sex, 'subject_sex')\
                .filter(**{model.sheet_name() + '__country__in':self.country_list})\
                .annotate(n=Count('id'))

        rows = self.apply_weights(rows, model.sheet_db_table(), "Internet")
        counts.update({(r['sex'], r['subject_sex']): r['n'] for r in rows})
        counts['col_title_def'] = 'Sex of reporter'

        self.tabulate(ws, counts, GENDER, GENDER, row_perc=False)

    def ws_60(self, ws):
        """
        Cols: Sex of subject
        Rows: Country, age
        :: Show all countries
        :: Internet media type only
        """
        r = 6
        self.write_col_headings(ws, GENDER)

        counts = Counter()
        model = person_models.get('Internet')
        for code, country in self.countries:
            rows = model.objects\
                    .values('sex', 'age')\
                    .filter(**{model.sheet_name() + '__country':code})

            rows = self.apply_weights(rows, model.sheet_db_table(), "Internet")
            counts = {(row['sex'], row['age']): row['n'] for row in rows}

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, GENDER, AGES, row_perc=True, write_col_headings=False, r=r)
            r += len(AGES)

    def ws_61(self, ws):
        """
        Cols: Sex of subject
        Rows: Country, is_quoted
        :: Show all countries
        :: Internet media type only
        """
        r = 6
        self.write_col_headings(ws, GENDER)

        counts = Counter()
        model = person_models.get('Internet')
        for code, country in self.countries:
            rows = model.objects\
                    .values('sex', 'is_quoted')\
                    .filter(**{model.sheet_name() + '__country':code})

            rows = self.apply_weights(rows, model.sheet_db_table(), "Internet")
            counts = {(row['sex'], row['is_quoted']): row['n'] for row in rows}

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, GENDER, YESNO, row_perc=True, write_col_headings=False, r=r)
            r += len(YESNO)

    def ws_62(self, ws):
        """
        Cols: Topic
        Rows: Country, equality raised
        :: Show all countries
        :: Internet media type only
        """
        r = 6
        self.write_col_headings(ws, TOPICS)

        counts = Counter()
        model = sheet_models.get('Internet')
        for code, country in self.countries:
            rows = model.objects\
                    .values('topic', 'equality_rights')\
                    .filter(country=code)

            rows = self.apply_weights(rows, model._meta.db_table, "Internet")
            counts = {(row['topic'], row['equality_rights']): row['n'] for row in rows}

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, TOPICS, YESNO, row_perc=True, write_col_headings=False, r=r)
            r += len(YESNO)

    def ws_63(self, ws):
        """
        Cols: Topic
        Rows: Country, stereotypes challenged
        :: Show all countries
        :: Internet media type only
        """
        r = 6
        self.write_col_headings(ws, TOPICS)

        counts = Counter()
        model = sheet_models.get('Internet')
        for code, country in self.countries:
            rows = model.objects\
                    .values('topic', 'stereotypes')\
                    .filter(country=code)

            rows = self.apply_weights(rows, model._meta.db_table, "Internet")
            counts = {(row['topic'], row['stereotypes']): row['n'] for row in rows}

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, TOPICS, AGREE_DISAGREE, row_perc=True, write_col_headings=False, r=r)
            r += len(AGREE_DISAGREE)

    def ws_64(self, ws):
        """
        Cols: Topic
        Rows: Country, about women
        :: Show all countries
        :: Internet media type only
        """
        r = 6
        self.write_col_headings(ws, TOPICS)

        counts = Counter()
        model = sheet_models.get('Internet')
        for code, country in self.countries:
            rows = model.objects\
                    .values('topic', 'about_women')\
                    .filter(country=code)

            rows = self.apply_weights(rows, model._meta.db_table, "Internet")
            counts = {(row['topic'], row['about_women']): row['n'] for row in rows}

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, TOPICS, YESNO, row_perc=True, write_col_headings=False, r=r)
            r += len(YESNO)

    def ws_65(self, ws):
        """
        Cols: Major Topic
        Rows: Country, tweet or retweet
        :: Show all countries
        :: Twitter media type only
        """
        r = 6
        self.write_col_headings(ws, MAJOR_TOPICS)

        counts = Counter()
        model = sheet_models.get('Twitter')
        for code, country in self.countries:
            rows = model.objects\
                    .values('topic', 'retweet')\
                    .filter(country=code)

            rows = self.apply_weights(rows, model._meta.db_table, "Twitter")

            counts.update({(TOPIC_GROUPS[row['topic']], row['retweet']): row['n'] for row in rows})

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, MAJOR_TOPICS, RETWEET, row_perc=False, write_col_headings=False, r=r)
            r += len(RETWEET)

    def ws_66(self, ws):
        """
        Cols: Major Topic
        Rows: Country, sex of news subject
        :: Show all countries
        :: Twitter media type only
        """
        r = 6
        self.write_col_headings(ws, MAJOR_TOPICS)

        counts = Counter()
        model = person_models.get('Twitter')
        topic_field = '%s__topic' % model.sheet_name()
        for code, country in self.countries:
            rows = model.objects\
                    .values(topic_field, 'sex')\
                    .filter(**{model.sheet_name() + '__country':code})

            rows = self.apply_weights(rows, model.sheet_db_table(), "Twitter")

            counts.update({(TOPIC_GROUPS[row['topic']], row['sex']): row['n'] for row in rows})

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, MAJOR_TOPICS, GENDER, row_perc=True, write_col_headings=False, r=r)
            r += len(GENDER)

    def ws_67(self, ws):
        """
        Cols: Major Topic
        Rows: Country
        :: Only female journalists
        :: Show all countries
        :: Twitter media type only
        """
        counts = Counter()
        model = sheet_models.get('Twitter')
        rows = model.objects\
                .values('topic', 'country')\
                .filter(**{model.journalist_field_name() + '__sex':1})

        rows = self.apply_weights(rows, model._meta.db_table, "Twitter")
        counts.update({(TOPIC_GROUPS[row['topic']], self.recode_country(row['country'])): row['n'] for row in rows})

        self.tabulate(ws, counts, MAJOR_TOPICS, self.countries, row_perc=True)

    def ws_68(self, ws):
        """
        Cols: Major Topic
        Rows: Country, about women
        :: Show all countries
        :: Twitter media type only
        """
        r = 6
        self.write_col_headings(ws, MAJOR_TOPICS)

        counts = Counter()
        model = sheet_models.get('Twitter')
        for code, country in self.countries:
            rows = model.objects\
                    .values('topic', 'about_women')\
                    .filter(country=code)

            rows = self.apply_weights(rows, model._meta.db_table, "Twitter")

            counts.update({(TOPIC_GROUPS[row['topic']], row['about_women']): row['n'] for row in rows})

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, MAJOR_TOPICS, YESNO, row_perc=False, write_col_headings=False, r=r)
            r += len(YESNO)

    def ws_68b(self, ws):
        """
        Cols: Topic
        Rows: Country, stereotypes
        :: Show all countries
        :: Twitter media type only
        """
        r = 6
        self.write_col_headings(ws, MAJOR_TOPICS)

        counts = Counter()
        model = sheet_models.get('Twitter')
        for code, country in self.countries:
            rows = model.objects\
                    .values('topic', 'stereotypes')\
                    .filter(country=code)

            rows = self.apply_weights(rows, model._meta.db_table, "Twitter")
            counts.update({(TOPIC_GROUPS[row['topic']], row['stereotypes']): row['n'] for row in rows})

            self.write_primary_row_heading(ws, country, r=r)
            self.tabulate(ws, counts, MAJOR_TOPICS, AGREE_DISAGREE, row_perc=True, write_col_headings=False, r=r)
            r += len(AGREE_DISAGREE)

    def ws_70(self, ws):
        ws.write(4, 0, 'See raw data sheets')

    def ws_71(self, ws):
        """
        Cols: Topic, Media type
        Rows: Country, Female news subjects
        Focus: women's overall presence
        """
        secondary_counts = OrderedDict()
        for topic_id, topic in FOCUS_TOPICS:
            actual_topic_ids = FOCUS_TOPIC_IDS[topic_id]
            counts = Counter()
            secondary_counts[topic] = counts

            for media_type, model in sheet_models.iteritems():
                media_id = [m[0] for m in MEDIA_TYPES if m[1] ==media_type][0]
                person_name = model.person_field_name()

                rows = model.objects\
                    .values('country')\
                    .filter(**{person_name + '__sex': self.female[0][0]})\
                    .filter(topic__in=actual_topic_ids)

                rows = self.apply_weights(rows, model._meta.db_table, media_type)
                counts.update({(media_id, self.recode_country(r['country'])): r['n'] for r in rows})

        self.tabulate_secondary_cols(ws, secondary_counts, MEDIA_TYPES, self.countries, write_col_totals=False, raw_values=True)

    def ws_72(self, ws):
        """
        Cols: Focus Topic, Media
        Rows: Country
        Focus: female reporters
        """
        # TODO: these values should be %age total of media in country/region

        secondary_counts = OrderedDict()
        for topic_id, topic in FOCUS_TOPICS:
            actual_topic_ids = FOCUS_TOPIC_IDS[topic_id]
            counts = Counter()
            secondary_counts[topic] = counts

            for media_type, model in sheet_models.iteritems():
                journo_name = model.journalist_field_name()
                media_id = [m[0] for m in MEDIA_TYPES if m[1] == media_type][0]

                rows = model.objects\
                    .values('country')\
                    .filter(**{journo_name + '__sex': self.female[0][0]})\
                    .filter(topic__in=actual_topic_ids)

                if media_type in REPORTER_MEDIA:
                    rows = rows.filter(**{journo_name + '__role':REPORTERS})

                rows = self.apply_weights(rows, model._meta.db_table, media_type)
                counts.update({(media_id, self.recode_country(r['country'])): r['n'] for r in rows})

        self.tabulate_secondary_cols(ws, secondary_counts, MEDIA_TYPES, self.countries, write_col_totals=False, raw_values=True)

    def ws_73(self, ws):
        """
        Cols: Sex of reporter
        Rows: Focus Topic
        Focus: Female news subject
        """
        focus_topic_ids = []
        for k, v in FOCUS_TOPIC_IDS.iteritems():
            focus_topic_ids.extend(v)
        counts = Counter()
        for media_type, model in journalist_models.iteritems():
            sheet_name = model.sheet_name()
            person_name = model.sheet_field().rel.to.person_field_name()
            topic_field = sheet_name + '__topic'
            rows = model.objects\
                        .values('sex', topic_field)\
                        .filter(**{sheet_name + '__country__in':self.country_list})\
                        .filter(**{sheet_name + '__'+ person_name + '__sex':self.female[0][0]})\
                        .filter(**{sheet_name + '__topic__in':focus_topic_ids})\
                        .filter(sex__in=self.male_female_ids)

            if media_type in REPORTER_MEDIA:
                rows = rows.filter(role=REPORTERS)

            rows = self.apply_weights(rows, model.sheet_db_table(), media_type)

            for r in rows:
                focus_topic_id = [k for k, v in FOCUS_TOPIC_IDS.iteritems() if r['topic'] in v][0]
                counts.update({(r['sex'], focus_topic_id): r['n']})

        self.tabulate(ws, counts, self.male_female, FOCUS_TOPICS, raw_values=True, write_col_totals=False)


    def ws_74(self, ws):
        """
        Cols: Focus Topic
        Rows: Country, About Women
        Focus: female reporters
        """
        c = 1
        for media_types, models in SHEET_MEDIA_GROUPS:
            self.write_primary_row_heading(ws, ', '.join([m[1] for m in media_types]), c=c+1, r=4)

            secondary_counts = OrderedDict()
            for topic_id, topic in FOCUS_TOPICS:
                counts = Counter()
                secondary_counts[topic] = counts
                actual_topic_ids = FOCUS_TOPIC_IDS[topic_id]

                for media_type, model in models.iteritems():
                    rows = model.objects\
                        .values('country', 'about_women')\
                        .filter(country__in=self.country_list)\
                        .filter(topic__in=actual_topic_ids)

                    rows = self.apply_weights(rows, model._meta.db_table, media_type)
                    counts.update({(r['about_women'], self.recode_country(r['country'])): r['n'] for r in rows})

            self.tabulate_secondary_cols(ws, secondary_counts, YESNO, self.countries, row_perc=True, c=c, r=8)
            c = ws.dim_colmax + 2

    def ws_75(self, ws):
        """
        Cols: Topic, Stereotypes
        Rows: Country
        """
        c = 1
        for media_types, models in SHEET_MEDIA_GROUPS:
            self.write_primary_row_heading(ws, ', '.join([m[1] for m in media_types]), c=c+1, r=4)

            secondary_counts = OrderedDict()
            for topic_id, topic in FOCUS_TOPICS:
                counts = Counter()
                secondary_counts[topic] = counts
                actual_topic_ids = FOCUS_TOPIC_IDS[topic_id]

                for media_type, model in models.iteritems():
                    if 'stereotypes' in model._meta.get_all_field_names():
                        rows = model.objects\
                            .values('stereotypes', 'country')\
                            .filter(topic__in=actual_topic_ids)

                        rows = self.apply_weights(rows, model._meta.db_table, media_type)
                        counts.update({(r['stereotypes'], self.recode_country(r['country'])): r['n'] for r in rows})

            self.tabulate_secondary_cols(ws, secondary_counts, AGREE_DISAGREE, self.countries, row_perc=True, c=c, r=8)
            c = ws.dim_colmax + 2

    def ws_76(self, ws):
        """
        Cols: Topic, Reference to gender equality
        Rows: Country
        """
        c = 1
        for media_types, models in SHEET_MEDIA_GROUPS:
            self.write_primary_row_heading(ws, ', '.join([m[1] for m in media_types]), c=c+1, r=4)

            secondary_counts = OrderedDict()
            for topic_id, topic in FOCUS_TOPICS:
                counts = Counter()
                actual_topic_ids = FOCUS_TOPIC_IDS[topic_id]

                for media_type, model in models.iteritems():
                    if 'equality_rights' in model._meta.get_all_field_names():
                        rows = model.objects\
                            .values('equality_rights', 'country')\
                            .filter(topic__in=actual_topic_ids)

                        rows = self.apply_weights(rows, model._meta.db_table, media_type)
                        counts.update({(r['equality_rights'], self.recode_country(r['country'])): r['n'] for r in rows})

                    secondary_counts[topic] = counts

            self.tabulate_secondary_cols(ws, secondary_counts, YESNO, self.countries, row_perc=True, c=c, r=8)
            c = ws.dim_colmax + 2

    def ws_77(self, ws):
        """
        Cols: Topic, victim_of
        Rows: Country
        """
        c = 1
        for media_types, models in PERSON_MEDIA_GROUPS:
            self.write_primary_row_heading(ws, ', '.join([m[1] for m in media_types]), c=c+1, r=4)

            secondary_counts = OrderedDict()
            for topic_id, topic in FOCUS_TOPICS:
                counts = Counter()
                actual_topic_ids = FOCUS_TOPIC_IDS[topic_id]

                for media_type, model in models.iteritems():
                    if 'victim_of' in model._meta.get_all_field_names():
                        country_field = '%s__country' % model.sheet_name()
                        rows = model.objects\
                            .values('victim_of', country_field)\
                            .filter(**{model.sheet_name() + '__topic__in':actual_topic_ids})

                        rows = self.apply_weights(rows, model.sheet_db_table(), media_type)
                        counts.update({(r['victim_of'], self.recode_country(r['country'])): r['n'] for r in rows})

                    secondary_counts[topic] = counts

            self.tabulate_secondary_cols(ws, secondary_counts, VICTIM_OF, self.countries, row_perc=True, c=c, r=8)
            c = ws.dim_colmax + 2

    def ws_78(self, ws):
        """
        Cols: Topic, survivor_of
        Rows: Country
        """
        c = 1
        for media_types, models in PERSON_MEDIA_GROUPS:
            self.write_primary_row_heading(ws, ', '.join([m[1] for m in media_types]), c=c+1, r=4)

            secondary_counts = OrderedDict()
            for topic_id, topic in FOCUS_TOPICS:
                counts = Counter()
                actual_topic_ids = FOCUS_TOPIC_IDS[topic_id]

                for media_type, model in models.iteritems():
                    if 'survivor_of' in model._meta.get_all_field_names():
                        country_field = '%s__country' % model.sheet_name()
                        rows = model.objects\
                            .values('survivor_of', country_field)\
                            .filter(**{model.sheet_name() + '__topic__in':actual_topic_ids})

                        rows = self.apply_weights(rows, model.sheet_db_table(), media_type)
                        counts.update({(r['survivor_of'], self.recode_country(r['country'])): r['n'] for r in rows})

                    secondary_counts[topic] = counts

            self.tabulate_secondary_cols(ws, secondary_counts, SURVIVOR_OF, self.countries, row_perc=True, c=c, r=8)
            c = ws.dim_colmax + 2

    # -------------------------------------------------------------------------------
    # Helper functions
    #
    def write_headers(self, ws, title, description):
        """
        Write the headers to the worksheet
        """
        ws.write(0, 0, title, self.heading)
        ws.write(1, 0, description, self.heading)
        ws.write(3, 2, self.gmmp_year, self.heading)

    def write_col_headings(self, ws, cols, c=2, r=4, show_N=False):
        """
        :param ws: worksheet to write to
        :param cols: list of `(col_id, col_title)` tuples of column ids and titles
        :param r, c: initial position where cursor should start writing to

        """
        if show_N:
            for col_id, col_title in cols:
                ws.write(r, c, clean_title(col_title), self.col_heading)
                ws.write(r + 1, c, "N")
                ws.write(r + 1, c + 1, "%")
                c += 2
        else:
            for col_id, col_title in cols:
                ws.write(r, c, clean_title(col_title), self.col_heading)
                ws.write(r + 1, c, "%")
                c += 1


    def write_primary_row_heading(self, ws, heading, c=0, r=6):
        """
        :param ws: worksheet to write to
        :param heading: row heading to write
        :param r, c: position where heading should be written to

        """
        ws.write(r, c, clean_title(heading), self.heading)

    def tabulate_secondary_cols(self, ws, secondary_counts, cols, rows, row_perc=False, write_row_headings=True, write_col_totals=True, filter_cols=None, c=1, r=7, show_N=False, raw_values=False):
        """
        :param ws: worksheet to write to
        :param secondary_counts: dict in following format:
            {'Primary column heading': Count object, ...}
        :param list cols: list of `(col_id, col_title)` tuples of column ids and titles
        :param list rows: list of `(row_id, row_heading)` tuples of row ids and titles
        :param bool row_perc: should percentages by calculated by row instead of column (default: False)
        """

        write_row_totals = row_perc and not show_N

        # row titles
        if write_row_headings:
            for i, row in enumerate(rows):
                row_id, row_heading = row
                ws.write(r + i, c, clean_title(row_heading), self.label)
            c += 1

        if 'col_title_def' in secondary_counts:
            # Write definitions of column heading titles
            ws.write(r-3, c-1, secondary_counts['col_title_def'][0], self.sec_col_heading_def)
            ws.write(r-2, c-1, secondary_counts['col_title_def'][1], self.col_heading_def)
            secondary_counts.pop('col_title_def')

        # number of columns per secondary column
        sec_cols = len(filter_cols or cols)
        if show_N:
            sec_cols *= 2
        if not show_N and row_perc:
            sec_cols += 1

        for field, counts in secondary_counts.iteritems():
            if sec_cols > 1:
                ws.merge_range(r-3, c, r-3, c+sec_cols-1, clean_title(field), self.sec_col_heading)
            else:
                ws.write(r-3, c, clean_title(field), self.sec_col_heading)

            self.tabulate(ws, counts, cols, rows, row_perc=row_perc, write_row_headings=False,
                          write_row_totals=write_row_totals, write_col_totals=write_col_totals,
                          filter_cols=filter_cols, r=r, c=c, show_N=show_N, raw_values=raw_values)
            c += sec_cols

    def tabulate(self, ws, counts, cols, rows, row_perc=False,
                 write_row_headings=True, write_col_headings=True, write_row_totals=True, write_col_totals=True,
                 filter_cols=None, c=1, r=6, show_N=False, raw_values=False, unweighted=False):
        """ Emit a table.

        :param ws: worksheet to write to
        :param dict counts: dict from `(col_id, row_id)` tuples to count for that combination.
        :param list cols: list of `(col_id, col_title)` tuples of column ids and titles
        :param list rows: list of `(row_id, row_heading)` tuples of row ids and titles
        :param bool row_perc: should percentages by calculated by row instead of column (default: False)
        :param write_row_headings: Should we write the row headings. False if already written.
        :param write_row_totals: Should we write the row totals. False if tabultae_secondary_cols was run.
        :param write_col_total: write column totals?
        :param write_col_headings: Should we write the col headings. False if already written.
        :param filter_cols: If not None, display only passed subset of columns e.g. only female
        :param raw_values: calculate percentage based on values, or just use values?
        :param r, c: initial position where cursor should start writing to
        :param unweighted: values are unweighted? default: False
        """
        if row_perc:
            # Calc percentage by row
            row_totals = {}
            for row_id, row_heading in rows:
                row_totals[row_id] = sum(int(round(counts.get((col_id, row_id), 0))) for col_id, _ in cols)  # noqa

        # row titles
        if write_row_headings:
            # else already written
            for i, row in enumerate(rows):
                row_id, row_heading = row
                ws.write(r+i, c, clean_title(row_heading), self.label)
            c += 1

        # if only filtered results should be shown
        # e.g. only print female columns
        if filter_cols:
            cols = filter_cols

        title_N = "N"
        if unweighted:
            title_N = "N (raw)"

        if 'col_title_def' in counts and write_col_headings:
            # write definition of column headings
            ws.write(r-2, c-1, counts['col_title_def'], self.col_heading_def)
            counts.pop('col_title_def')

        # values, written column by column
        for col_id, col_heading in cols:
            # column title
            if write_col_headings:
                # else already written
                if show_N:
                    ws.merge_range(r-2, c, r-2, c+1, clean_title(col_heading), self.col_heading)
                    ws.write(r-1, c, "%", self.label)
                    ws.write(r-1, c+1, title_N, self.label)
                else:
                    ws.write(r-2, c, clean_title(col_heading), self.col_heading)
                    if raw_values:
                        ws.write(r-1, c, title_N, self.label)
                    else:
                        ws.write(r-1, c, "%", self.label)

            if not row_perc:
                # calculate column totals
                total = sum(int(round(counts.get((col_id, row_id), 0))) for row_id, _ in rows)

            # values for this column
            col_total = 0
            for i, row in enumerate(rows):
                row_id, row_title = row

                if row_perc:
                    # row totals
                    total = row_totals[row_id]

                n = int(round(counts.get((col_id, row_id), 0)))
                perc = p(n, total)
                col_total += perc

                if raw_values:
                    ws.write(r+i, c, n, self.N)
                else:
                    ws.write(r+i, c, perc, self.P)
                    if show_N:
                        ws.write(r+i, c+1, n, self.N)

            if write_col_totals and not row_perc:
                ws.write(r+i+1, c, col_total, self.P)

            c += 2 if show_N else 1

        if row_perc and write_row_totals:
            if write_col_headings:
                ws.write(r-1, c, title_N)

            # Write the row totals
            for i, row in enumerate(rows):
                row_id, row_title = row
                ws.write(r+i, c, row_totals[row_id], self.N)

    def tabulate_historical(self, ws, current_ws, cols, rows, c=None, r=6, write_row_headings=True,
                            write_col_headings=True, show_N_and_P=False, major_cols=None,
                            skip_major_col_heading=False, write_year=True, values_N=False):
        """
        Write historical data table.

        :param ws: worksheet to write to
        :param current_ws: name of the current period's worksheet
        :param cols: list of (id, key) column pairs
        :param rows: list of (id, key) row pairs
        :param c: column to start at; default: furtherst column to the right
        :param r: row to start at
        :param write_row_headings: should row headings be written?
        :param write_col_headings: should col headings be written?
        :param show_N_and_P: show both N and P for a row/col value, or just show P?
        :param major_cols: the major (top) columns as a list of (id, key) pairs
        :param skip_major_col_heading: allow space for, but skip, major column headings?
        :param write_year: should we write the year?
        :param values_N: are the values we're printing N or P values? (default: False)
        """
        if c is None:
            c = ws.dim_colmax + 2

        if values_N:
            formats = [self.N, self.N]
        else:
            formats = [self.P, self.N]

        try:
            country = self.country_list[0]
            region = self.region_list[0]

            historical_data = self.historical.get(current_ws, self.report_type,
                                                  region=region, country=country)
        except KeyError as e:
            if self.report_type == 'global':
                raise e
            ws.write(r, c, "Historical data not available at the %s level." % self.report_type)
            self.log.warn(e.message)
            return

        years = sorted(historical_data.keys())

        if major_cols:
            r += 1

        values_per_col = 2 if show_N_and_P else 1

        if write_row_headings:
            # row titles
            for i, (row_id, row_heading) in enumerate(rows):
                row_heading = clean_title(row_heading)
                ws.write(r + i, c, row_heading)
            c += 1

        for year_i, year in enumerate(years):
            year_data = historical_data[year]

            if write_year:
                offset = 3
                if skip_major_col_heading or major_cols:
                    offset = 4
                ws.write(r - offset, c, year, self.heading)

            # for each major column heading
            for mcol_id, mcol_heading in (major_cols or [(None, None)]):
                if mcol_id is not None:
                    mcol_heading = clean_title(mcol_heading)
                    if canon(mcol_heading) not in year_data:
                        continue

                    if write_col_headings:
                        # major column title
                        width = len(cols) * values_per_col
                        if width > 1:
                            ws.merge_range(r - 3, c, r - 3, c + width - 1, mcol_heading, self.sec_col_heading)
                        else:
                            ws.write(r - 3, c, mcol_heading, self.sec_col_heading)

                    # get data
                    data = year_data[canon(mcol_heading)]
                else:
                    data = year_data

                # do we need to keep N aside as a special column?
                columns = cols
                if canon('N') in data:
                    columns = columns + [('N', 'N')]

                # for each minor column heading
                for col_id, col_heading in columns:
                    col_heading = clean_title(col_heading)

                    if canon(col_heading) not in data:
                        continue

                    # column title
                    value_formats = formats
                    if write_col_headings:
                        if col_heading != 'N':
                            if values_per_col > 1:
                                ws.merge_range(r - 2, c, r - 2, c + values_per_col - 1, col_heading, self.col_heading)
                            else:
                                ws.write(r - 2, c, col_heading, self.col_heading)

                            ws.write(r - 1, c, '%', self.label)
                            # if multiple values for this column, we're writing both a
                            # percentage and an N
                            if show_N_and_P:
                                ws.write(r - 1, c + 1, 'N', self.label)

                        else:
                            ws.write(r - 1, c, 'N', self.label)
                            value_formats = [self.N, self.N]

                    # row values
                    for i, (row_id, row_heading) in enumerate(rows):
                        row_heading = clean_title(row_heading)
                        value = data[canon(col_heading)].get(canon(row_heading))

                        if value is None:
                            value = ['n/a'] * values_per_col
                        elif not isinstance(value, list):
                            value = [value]

                        for v in xrange(values_per_col):
                            ws.write(r + i, c + v, value[v], value_formats[v])

                    # for next column
                    c += values_per_col
