#!/usr/bin/env python3
#
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
import os

from flask import Blueprint
from flask import render_template, url_for, redirect
from flask_wtf import FlaskForm


import app
from app.datamgmt.activities.activities_db import get_all_user_activities
from app.util import response_success, login_required, api_login_required

activities_blueprint = Blueprint(
    'activities',
    __name__,
    template_folder='templates'
)

basedir = os.path.abspath(os.path.dirname(app.__file__))


# CONTENT ------------------------------------------------
@activities_blueprint.route('/activities', methods=['GET'])
@login_required
def activities_index(caseid: int, url_redir):
    if url_redir:
        return redirect(url_for('activities.activities_index', cid=caseid))

    form = FlaskForm()

    return render_template('activities.html', form=form)


@activities_blueprint.route('/activities/list', methods=['GET'])
@api_login_required
def list_activities(caseid):
    # Get User activites from database
    user_activities = get_all_user_activities()

    data = [row._asdict() for row in user_activities]
    data = sorted(data, key=lambda i: i['activity_date'], reverse=True)

    return response_success("", data=data)
