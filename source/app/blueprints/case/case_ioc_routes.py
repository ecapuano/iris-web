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
import marshmallow
from flask import Blueprint, request
from flask import render_template, url_for, redirect
from flask_login import current_user

from app import db
from app.configuration import misp_url
from app.datamgmt.case.case_assets_db import get_assets_types
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_iocs_db import get_detailed_iocs, get_ioc_links, add_ioc, add_ioc_link, \
    get_tlps, get_ioc, delete_ioc
from app.datamgmt.states import get_ioc_state, update_ioc_state
from app.forms import ModalAddCaseAssetForm, ModalAddCaseIOCForm
from app.iris_engine.utils.tracker import track_activity
from app.models.models import Ioc
from app.schema.marshables import IocSchema
from app.util import response_success, response_error, login_required, api_login_required

case_ioc_blueprint = Blueprint('case_ioc',
                               __name__,
                               template_folder='templates')

choices_ioc_types = ["IP", "Domain", "Hash", "File", "Path", "Account", "Other"]


# CONTENT ------------------------------------------------
@case_ioc_blueprint.route('/case/ioc', methods=['GET', 'POST'])
@login_required
def case_ioc(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid))

    form = ModalAddCaseAssetForm()
    form.asset_id.choices = get_assets_types()

    # Retrieve the assets linked to the investigation
    case = get_case(caseid)

    return render_template("case_ioc.html", case=case, form=form)


@case_ioc_blueprint.route('/case/ioc/list', methods=['GET'])
@api_login_required
def case_list_ioc(caseid):
    iocs = get_detailed_iocs(caseid)

    ret = {}
    ret['ioc'] = []
    for ioc in iocs:
        out = ioc._asdict()
        # Get links of the IoCs seen in other cases
        ial = get_ioc_links(ioc.ioc_id, caseid)

        out['link'] = [row._asdict() for row in ial]
        out['misp_link'] = misp_url

        ret['ioc'].append(out)

    ret['state'] = get_ioc_state(caseid=caseid)

    return response_success("", data=ret)


@case_ioc_blueprint.route('/case/ioc/state', methods=['GET'])
@api_login_required
def case_ioc_state(caseid):
    os = get_ioc_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No IOC state for this case.')


@case_ioc_blueprint.route('/case/ioc/add', methods=['POST'])
@api_login_required
def case_add_ioc(caseid):

    try:
        # validate before saving
        add_ioc_schema = IocSchema()
        jsdata = request.get_json()
        ioc = add_ioc_schema.load(jsdata)

        if ioc.ioc_type not in choices_ioc_types:
            return response_error("Not a valid IOC type")

        ioc, existed = add_ioc(ioc=ioc,
                               user_id=current_user.id,
                               caseid=caseid
                               )
        link_existed = add_ioc_link(ioc.ioc_id, caseid)

        if link_existed:
            return response_error("IOC already exists and linked to this case")

        if ioc:
            track_activity("added ioc {}".format(ioc.ioc_value), caseid=caseid)

            msg = "IOC already existed in DB. Updated with info on DB." if existed else "IOC added"

            return response_success(msg=msg, data=add_ioc_schema.dump(ioc))

        return response_error("Unable to create IOC for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_ioc_blueprint.route('/case/ioc/add/modal', methods=['GET'])
@login_required
def case_add_ioc_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid))

    form = ModalAddCaseIOCForm()
    form.ioc_type.choices = [(row, row) for row in choices_ioc_types]
    form.ioc_tlp_id.choices = get_tlps()

    return render_template("modal_add_case_ioc.html", form=form, ioc=Ioc())


@case_ioc_blueprint.route('/case/ioc/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def case_delete_ioc(cur_id, caseid):

    ioc = get_ioc(cur_id, caseid)

    if not ioc:
        return response_error('Not a valid IOC for this case')

    if not delete_ioc(ioc, caseid):
        track_activity("unlinked IOC ID {}".format(cur_id))
        return response_success("IOC unlinked")

    track_activity("deleted IOC ID {}".format(cur_id))
    return response_success("IOC deleted")


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/modal', methods=['GET'])
@login_required
def case_view_ioc_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid))

    form = ModalAddCaseIOCForm()
    ioc = get_ioc(cur_id, caseid)
    if not ioc:
        return response_error("Invalid IOC ID for this case")

    form.ioc_type.choices = [(row, row) for row in choices_ioc_types]
    form.ioc_tlp_id.choices = get_tlps()

    # Render the IOC
    form.ioc_tags.render_kw = {'value': ioc.ioc_tags}
    form.ioc_description.data = ioc.ioc_description
    form.ioc_value.data = ioc.ioc_value

    return render_template("modal_add_case_ioc.html", form=form, ioc=ioc)


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>', methods=['GET'])
@api_login_required
def case_view_ioc(cur_id, caseid):

    ioc_schema = IocSchema()
    ioc = get_ioc(cur_id, caseid)
    if not ioc:
        return response_error("Invalid IOC ID for this case")

    return response_success(data=ioc_schema.dump(ioc))


@case_ioc_blueprint.route('/case/ioc/update/<int:cur_id>', methods=['POST'])
@api_login_required
def case_update_ioc(cur_id, caseid):

    try:
        ioc = get_ioc(cur_id, caseid)
        if not ioc:
            return response_error("Invalid note ID for this case")

        # validate before saving
        ioc_schema = IocSchema()
        ioc_sc = ioc_schema.load(request.get_json(), instance=ioc)
        ioc_sc.user_id = current_user.id

        update_ioc_state(caseid=caseid)
        db.session.commit()

        if ioc_sc:
            track_activity("updated ioc {}".format(ioc_sc.ioc_value), caseid=caseid)
            return response_success("Updated ioc {}".format(ioc_sc.ioc_value))

        return response_error("Unable to update ioc for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)

