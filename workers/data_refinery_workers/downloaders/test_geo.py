import os
from django.test import TestCase
from unittest.mock import patch

from data_refinery_common.models import (
    DownloaderJob,
    OriginalFile,
    DownloaderJobOriginalFileAssociation,
    Sample,
    SampleAnnotation,
    OriginalFileSampleAssociation,
    ProcessorJob,
    ProcessorJobOriginalFileAssociation
)
from data_refinery_workers.downloaders import geo, utils

def create_processor_jobs_for_original_files_no_send(original_files, pipeline):
    # Iterate over all of our samples.
    # If we have raw, send it to the correct processor.
    # Else, treat it as a "NO-OP"
    for original_file in original_files:
        processor_job = ProcessorJob()
        if not pipeline:
            if not original_file.has_raw:
                processor_job.pipeline_applied = "NO_OP"
            else:
                if 'CEL' in original_file.filename.upper():
                    processor_job.pipeline_applied = "AFFY_TO_PCL"
                else:
                    processor_job.pipeline_applied = "AGILENT_TWOCOLOR_TO_PCL"
        else:
            processor_job.pipeline_applied = pipeline

        # Save the Job and create the association
        processor_job.save()
        assoc = ProcessorJobOriginalFileAssociation()
        assoc.original_file = original_file
        assoc.processor_job = processor_job
        assoc.save()

class DownloadGeoTestCase(TestCase):
    def setUp(self):
        return

    def test_download_and_extract_file(self):

        # Download function requires a DownloaderJob object,
        # can be blank for the simple case.
        dlj = DownloaderJob()
        dlj.save()

        # *_family.xml.tgz
        geo._download_file('ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE10nnn/GSE10241/miniml/GSE10241_family.xml.tgz', '/home/user/data_store/GSE10241/raw/GSE10241_family.xml.tgz', dlj)
        files = geo._extract_tgz('/home/user/data_store/GSE10241/raw/GSE10241_family.xml.tgz', 'GSE10241')

        self.assertEqual(8, len(files))

        # GPL File
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GPL6102-tbl-1.txt'))
        
        # GSM Files
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GSM258515-tbl-1.txt'))
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GSM258516-tbl-1.txt'))
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GSM258530-tbl-1.txt'))
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GSM258517-tbl-1.txt'))

        # Original family file
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GSE10241_family.xml'))
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GSE10241_family.xml.tgz'))
        self.assertTrue(os.path.isfile('/home/user/data_store/GSE10241/raw/GSE10241_family.xml.tar'))

        # .txt.gz
        geo._download_file('ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM254nnn/GSM254828/suppl/GSM254828.txt.gz', '/home/user/data_store/GSM254828/raw/GSM254828.txt.gz', dlj)
        files = geo._extract_gz('/home/user/data_store/GSM254828/raw/GSM254828.txt.gz', 'GSM254828')
        self.assertEqual(1, len(files))
        self.assertTrue(os.path.isfile('/home/user/data_store/GSM254828/raw/GSM254828.txt'))

        geo._download_file("ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE22nnn/GSE22427/suppl/GSE22427%5Fnon%2Dnormalized%2Etxt%2Egz", '/home/user/data_store/GSE22427/raw/GSE22427_non-normalized.txt.gz',  dlj)
        files = geo._extract_gz('/home/user/data_store/GSE22427/raw/GSE22427_non-normalized.txt.gz', 'GSE22427')
        self.assertEqual(1, len(files))

        self.assertTrue(os.path.isfile('/home/user/data_store/GSE22427/raw/GSE22427_non-normalized.txt'))

    @patch('data_refinery_workers.downloaders.utils.create_processor_jobs_for_original_files', side_effect=create_processor_jobs_for_original_files_no_send)
    def test_download_geo(self, mock_send_task):
        """ Tests the main 'download_geo' function. """

        dlj = DownloaderJob()
        dlj.accession_code = 'GSE22427'
        dlj.save()

        original_file = OriginalFile()
        original_file.source_url = "ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE22nnn/GSE22427/suppl/GSE22427_non-normalized.txt.gz"
        original_file.source_filename = "GSE22427_non-normalized.txt.gz"
        original_file.save()

        assoc = DownloaderJobOriginalFileAssociation()
        assoc.original_file = original_file
        assoc.downloader_job = dlj
        assoc.save()

        sample = Sample()
        sample.accession_code = 'GSE22427'
        sample.save()

        sample_annotation = SampleAnnotation()
        sample_annotation.sample = sample
        sample_annotation.data = {'label_protocol_ch1': 'Agilent', 'label_protocol_ch2': 'Agilent'}
        sample_annotation.save()

        og_assoc = OriginalFileSampleAssociation()
        og_assoc.sample = sample
        og_assoc.original_file = original_file
        og_assoc.save()

        download_result = geo.download_geo(dlj.id)

        file_assocs = DownloaderJobOriginalFileAssociation.objects.filter(downloader_job=dlj)
        original_file = file_assocs[0].original_file

        # Make sure it worked
        self.assertTrue(download_result)
        self.assertTrue(dlj.failure_reason is None)
        self.assertTrue(original_file.is_downloaded)
        self.assertTrue(len(ProcessorJob.objects.all()) > 0)
        self.assertEqual(ProcessorJob.objects.all()[0].pipeline_applied, "AGILENT_TWOCOLOR_TO_PCL")
