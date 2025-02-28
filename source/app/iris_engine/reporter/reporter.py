#!/usr/bin/env python3
#
#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# IMPORTS ------------------------------------------------

# VARS ---------------------------------------------------

# CONTENT ------------------------------------------------
import logging as log
import os
from datetime import datetime

from flask_login import current_user
from sqlalchemy import create_engine, text, and_, or_, desc

from app import app
from app.datamgmt.activities.activities_db import get_auto_activities, get_manual_activities
from app.datamgmt.reporter.report_db import export_case_json
from app.iris_engine.connectors.misp4iris import Misp4Iris
from app.models import CasesDatum, HashLink, FileContentHash, FileName, PathName, CasesEvent, IocLink, Ioc, \
    IocAssetLink, CaseAssets, AssetsType, CaseEventsAssets, CaseReceivedFile, CaseTemplateReport
from app.util import task_success, task_failure
from app.datamgmt.case.case_db import case_get_desc_crc

from docx_generator.docx_generator import DocxGenerator
from docx_generator.exceptions import rendering_error

LOG_FORMAT = '%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s'
log.basicConfig(level=log.INFO, format=LOG_FORMAT)


class IrisReporter(object):
    def __init__(self, task_self, task_args):
        self._case_id = task_args.get('case_id')
        self._case_name = task_args['case_name']
        self._user = task_args.get('user')
        self.task = task_self
        self._logger = log.getLogger(self.__str__())
        self.message_queue = []
        handler = QueuingHandler(message_queue=self.message_queue,
                                 level=log.INFO,
                                 task_self=task_self
                                 )
        formatter = log.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._report = {}

    def _ret_task_success(self, data=None):
        """
        Return a comprehensive success response to the task manager
        :param data: Data containing the JSON report
        :return: JSON task response
        """
        return task_success(
            user=self._user,
            case_name=self._case_name,
            logs=list(self.message_queue),
            data=data
        )

    def _ret_task_failure(self, data=None):
        """
        Return a comprehensive response failure to the task manager
        :param data: Data containing the JSON report
        :return: JSON task response
        """
        return task_failure(
            user=self._user,
            case_name=self._case_name,
            logs=list(self.message_queue),
            data=data
        )

    def make_report(self):
        """
        Start the actual creation of the report
        :return:
        """
        # self._report['computers'] = self._get_case_computers()
        # self._report['vt_detection'] = self._get_vt_detection()
        self._report['misp_detection'] = self._get_misp_matches()

        return self._report

    def _get_vt_detection(self):
        """
        Search for low VT score and tagged malware
        :return:
        """
        res = CasesDatum.query \
            .with_entities(
                FileName.filename,
                PathName.path,
                FileContentHash.vt_score,
                FileContentHash.flag,
                FileContentHash.comment,
                FileContentHash.seen_count,
                FileContentHash.vt_url
        ).filter(
            and_(
                or_(
                    FileContentHash.vt_score >= 3.0,
                    FileContentHash.flag == "1",
                    FileContentHash.flag == "2"
                ),
                CasesDatum.case_id == self._case_id
            )
        ).join(CasesDatum.hash_link, HashLink.file_content_hash, HashLink.file_name, HashLink.path_name)

        data = [row._asdict() for row in res]

        return data

    def _get_misp_matches(self):
        """
        For every hashs linked to the case, look for it in MISP and report
        :return:
        """
        # Create an instance of MISP
        m4i = Misp4Iris()
        exec_res = {}

        # Get the
        res = CasesDatum.query \
            .with_entities(
                FileName.filename,
                PathName.path,
                FileContentHash.content_hash
        ).filter(
            CasesDatum.case_id == self._case_id
        ).join(CasesDatum.hash_link, HashLink.file_content_hash, HashLink.file_name,
               HashLink.path_name).all()
        if res:
            tab = []
            tot = len(res) * 1.0
            idx = 0.0
            for element in res:
                tab.append(element.filename)
                if len(tab) > 200:
                    print('\r{} % ({} / {}) done'.format((idx / tot) * 100, idx, tot), end="")
                    rt = m4i.search_fn(tab)
                    if rt:
                        exec_res.update(rt)
                    tab = []
                idx += 1.0
        else:
            print("Empty set")

        return exec_res


class IrisMakeDocReport(object):
    """
    Generates a DOCX report for the case
    """

    def __init__(self, tmp_dir, report_id, caseid):
        self._tmp = tmp_dir
        self._report_id = report_id
        self._case_info = {}
        self._caseid = caseid

    def generate_doc_report(self, type):
        """
        Actually generates the report
        :return:
        """
        if type == 'Investigation':
            case_info = self._get_case_info()
        elif type == 'Activities':
            case_info = self._get_activity_info()
        else:
            log.error("Unknown report type")
            return None

        report = CaseTemplateReport.query.filter(CaseTemplateReport.id == self._report_id).first()

        name = "{}".format("{}.docx".format(report.naming_format))
        name = name.replace("%code_name%", case_info['doc_id'])
        name = name.replace('%customer%', case_info['case'].get('for_customer'))
        name = name.replace('%case_name%', case_info['case'].get('name'))
        name = name.replace('%date%', datetime.utcnow().strftime("%Y-%m-%d"))
        output_file_path = os.path.join(self._tmp, name)

        try:
            generator = DocxGenerator()
            generator.generate_docx("/",
                                    os.path.join(app.config['TEMPLATES_PATH'], report.internal_reference),
                                    case_info,
                                    output_file_path
                                    )

            return output_file_path

        except rendering_error.RenderingError:
            return None

    def _get_activity_info(self):
        auto_activities = get_auto_activities(self._caseid)
        manual_activities = get_manual_activities(self._caseid)
        case_info_in = self._get_case_info()

        # Format information and generate the activity report #
        doc_id = "{}".format(datetime.utcnow().strftime("%y%m%d_%H%M"))

        case_info = {
            'auto_activities': auto_activities,
            'manual_activities': manual_activities,
            'date': datetime.utcnow(),
            'gen_user': current_user.name,
            'case': {'name': case_info_in['case'].get('name'),
                     'open_date': case_info_in['case'].get('open_date'),
                     'for_customer': case_info_in['case'].get('for_customer')
                     },
            'doc_id': doc_id
        }

        return case_info

    def _get_case_info(self):
        """
        Retrieve information of the case
        :return:
        """
        case_info = export_case_json(self._caseid)

        # Get customer, user and case title
        case_info['doc_id'] = IrisMakeDocReport.get_docid()
        case_info['user'] = current_user.name

        # Set date
        case_info['date'] = datetime.utcnow().strftime("%Y-%m-%d")

        return case_info

    @staticmethod
    def get_case_summary(caseid):
        """
        Retrieve the case summary from thehive
        :return:
        """

        _crc32, descr = case_get_desc_crc(caseid)

        # return IrisMakeDocReport.markdown_to_text(descr)
        return descr

    @staticmethod
    def get_case_files(caseid):
        """
        Retrieve the list of files with their hashes
        :return:
        """
        files = CaseReceivedFile.query.filter(
            CaseReceivedFile.case_id == caseid
        ).with_entities(
            CaseReceivedFile.filename,
            CaseReceivedFile.date_added,
            CaseReceivedFile.file_hash
        ).order_by(
            CaseReceivedFile.date_added
        ).all()

        if files:
            return [row._asdict() for row in files]

        else:
            return []

    @staticmethod
    def get_case_timeline(caseid):
        """
        Retrieve the case timeline
        :return:
        """
        timeline = CasesEvent.query.filter(
            CasesEvent.case_id == caseid
        ).order_by(
            CasesEvent.event_date
        ).all()

        cache_id = {}
        ras = {}
        tim = []
        for row in timeline:
            ras = row
            setattr(ras, 'asset', None)

            as_list = CaseEventsAssets.query.with_entities(
                CaseAssets.asset_id,
                CaseAssets.asset_name,
                AssetsType.asset_name.label('type')
            ).filter(
                CaseEventsAssets.event_id == row.event_id
            ).join(CaseEventsAssets.asset, CaseAssets.asset_type).all()

            alki = []
            for asset in as_list:
                alki.append("{} ({})".format(asset.asset_name, asset.type))

            setattr(ras, 'asset', "\r\n".join(alki))

            tim.append(ras)

        return tim

    @staticmethod
    def get_case_ioc(caseid):
        """
        Retrieve the list of IOC linked to the case
        :return:
        """
        res = IocLink.query.distinct().with_entities(
            Ioc.ioc_value,
            Ioc.ioc_type,
            Ioc.ioc_description
        ).filter(
            IocLink.case_id == caseid
        ).join(IocLink.ioc).order_by(Ioc.ioc_type).all()

        if res:
            return [row._asdict() for row in res]

        else:
            return []

    @staticmethod
    def get_case_assets(caseid):
        """
        Retrieve the assets linked ot the case
        :return:
        """
        ret = []

        res = CaseAssets.query.distinct().with_entities(
            CaseAssets.asset_id,
            CaseAssets.asset_name,
            CaseAssets.asset_description,
            CaseAssets.asset_compromised.label('compromised'),
            AssetsType.asset_name.label("type")
        ).filter(
            CaseAssets.case_id == caseid
        ).join(
            CaseAssets.asset_type
        ).order_by(desc(CaseAssets.asset_compromised)).all()

        for row in res:
            row = row._asdict()
            row['light_asset_description'] = row['asset_description']

            ial = IocAssetLink.query.with_entities(
                Ioc.ioc_value,
                Ioc.ioc_type,
                Ioc.ioc_description
            ).filter(
                IocAssetLink.asset_id == row['asset_id']
            ).join(
                IocAssetLink.ioc
            ).all()

            if ial:
                row['asset_ioc'] = [row._asdict() for row in ial]
            else:
                row['asset_ioc'] = []

            ret.append(row)

        return ret

    @staticmethod
    def get_docid():
        return "{}".format(
            datetime.utcnow().strftime("%y%m%d_%H%M"))

    @staticmethod
    def markdown_to_text(markdown_string):
        """
        Converts a markdown string to plaintext
        """
        return markdown_string.replace('\n', '</w:t></w:r><w:r/></w:p><w:p><w:r><w:t xml:space="preserve">').replace(
            '#', '')


class QueuingHandler(log.Handler):
    """A thread safe logging.Handler that writes messages into a queue object.

       Designed to work with LoggingWidget so log messages from multiple
       threads can be shown together in a single ttk.Frame.

       The standard logging.QueueHandler/logging.QueueListener can not be used
       for this because the QueueListener runs in a private thread, not the
       main thread.

       Warning:  If multiple threads are writing into this Handler, all threads
       must be joined before calling logging.shutdown() or any other log
       destinations will be corrupted.
    """

    def __init__(self, *args, task_self, message_queue, **kwargs):
        """Initialize by copying the queue and sending everything else to superclass."""
        log.Handler.__init__(self, *args, **kwargs)
        self.message_queue = message_queue
        self.task_self = task_self

    def emit(self, record):
        """Add the formatted log message (sans newlines) to the queue."""
        self.message_queue.append(self.format(record).rstrip('\n'))
        self.task_self.update_state(state='PROGRESS',
                                    meta=list(self.message_queue))
