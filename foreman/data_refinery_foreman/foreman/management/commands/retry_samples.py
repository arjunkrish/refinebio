import random
import sys
import time
from typing import Dict, List

from django.core.management.base import BaseCommand
from nomad import Nomad

from data_refinery_common.models import (
    DownloaderJob,
    DownloaderJobOriginalFileAssociation,
    Experiment,
    ExperimentOrganismAssociation,
    ExperimentSampleAssociation,
    Organism,
    OriginalFile,
    ProcessorJob,
    ProcessorJobOriginalFileAssociation,
    Sample,
)
from data_refinery_common.job_lookup import ProcessorPipeline, Downloaders
from data_refinery_common.logging import get_and_configure_logger
from data_refinery_common.message_queue import send_job
from data_refinery_common.utils import get_env_variable, get_active_volumes, create_downloader_job


logger = get_and_configure_logger(__name__)

PAGE_SIZE=2000

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--source-database",
            type=str,
            help=("The name of a source database, such as Array Express, GEO, or SRA."
                  "All samples from this source database will have downloader "
                  "jobs requeued for them.")
        )

    def handle(self, *args, **options):
        """Requeues all unprocessed RNA-Seq samples for an organism.
        """
        if options["source_database"] is None:
            logger.error("You must specify a source-database.")
            sys.exit(1)
        else:
            source_database = options["source_database"]

        samples_with_computed_files = SampleComputedFileAssociation.objects.
        unprocessed_samples = Sample.objects.filter(computed_files=[])
        sra_samples = Sample.objects.filter(
            source_database="SRA"
        ).prefetch_related(
            "computed_files",
            "original_files"
        )

        paginator = Paginator(sra_samples, PAGE_SIZE)
        page = paginator.page()
        page_count = 0

        while page.has_next():
            for sample in page.object_list:
                if sample.computed_files.count() == 0:
                    create_downloader_job(sample.original_files, force=True)

            # 2000 samples queued up every five minutes should be fast
            # enough and also not thrash the DB.
            time.sleep(60 * 5)
