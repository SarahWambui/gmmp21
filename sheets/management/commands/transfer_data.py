import os

from django.core.management.base import BaseCommand
from django.conf import settings

from sheets.extractor_script import get_journalist, get_people, get_sheet, read_coding_sheet
from sheets.utils import (
            merge_data,
            get_common_coding_data,
            get_newspaper_coding_data,
            get_radio_coding_data,
            get_tv_coding_data,
            get_internet_coding_data,
            get_twitter_coding_data,
            format_date,
            format_time,
            save_newspaper_news_data,
            save_radio_news_data,
            save_tv_news_data,
            save_internent_news_data,
            save_twitter_news_data,
)

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--filename', help="Specify a filename inorder to transfer a single file")

    def handle(self, *args, **options):
        if options['filename']:
            filenames = [options['filename']]
        else:
            files_location =  settings.BASE_DIR + '/sheets/data_transfer/data/'
            # Ignore the extension
            filenames = [file_name.split('.')[0] for file_name in os.listdir(files_location) if file_name.endswith('xlsx')]
        
        for filename in filenames:
            coding_dict = read_coding_sheet(filename)
            #functions to run
            journalists = get_journalist(coding_dict.copy())
            people = get_people(coding_dict.copy())
            sheets = get_sheet(coding_dict.copy())
            # We can't merge people and journalists since they both have sex and age fields
            data = merge_data(sheets, people)

            newspaper_coding_data = get_newspaper_coding_data(data.get('NewspaperCoding', {}))
            journalist_newspaper_coding_data = get_newspaper_coding_data(journalists.get('NewspaperCoding', {}))
            radio_coding_data = get_radio_coding_data(data.get('RadioCoding', {}))
            journalist_radio_coding_data = get_radio_coding_data(journalists.get('RadioCoding', {}))
            tv_coding_data = get_tv_coding_data(data.get('TelevisionCoding', {}))
            journalist_tv_coding_data = get_tv_coding_data(journalists.get('TelevisionCoding', {}))
            internet_coding_data = get_internet_coding_data(data.get('InternetCoding', {}))
            journalist_internet_coding_data = get_internet_coding_data(journalists.get('InternetCoding', {}))
            twitter_coding_data = get_twitter_coding_data(data.get('TwitterCoding', {}))
            journalist_twitter_coding_data = get_twitter_coding_data(journalists.get('TwitterCoding', {}))

            save_newspaper_news_data(newspaper_coding_data, journalist_newspaper_coding_data)
            save_radio_news_data(radio_coding_data, journalist_radio_coding_data)
            save_tv_news_data(tv_coding_data, journalist_tv_coding_data)
            save_internent_news_data(internet_coding_data, journalist_internet_coding_data)
            save_twitter_news_data(twitter_coding_data, journalist_twitter_coding_data)