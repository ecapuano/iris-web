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
from flask import Blueprint, request, redirect, url_for
from flask import render_template

from app import db
from app.datamgmt.manage.manage_users_db import get_users_list, create_user, update_user, get_user
from app.forms import AddUserForm
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import UserSchema
from app.util import admin_required, login_required, response_error, response_success, api_admin_required


manage_users_blueprint = Blueprint('manage_users',
                                   __name__,
                                   template_folder='templates')


# CONTENT ------------------------------------------------
@manage_users_blueprint.route('/manage/users', methods=['GET'])
@admin_required
def manage_users_index(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_users.manage_users', cid=caseid))

    return render_template("manage_users.html")


@manage_users_blueprint.route('/manage/users/list', methods=['GET'])
@api_admin_required
def manage_users_list(caseid):
    users = get_users_list()

    return response_success('', data=users)


@manage_users_blueprint.route('/manage/users/add/modal', methods=['GET'])
@admin_required
def add_user_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_users.add_user', cid=caseid))

    user = None
    form = AddUserForm()

    return render_template("modal_add_user.html", form=form, user=user)


@manage_users_blueprint.route('/manage/users/add', methods=['POST'])
@api_admin_required
def add_user(caseid):
    try:

        # validate before saving
        user_schema = UserSchema()
        jsdata = request.get_json()
        jsdata['user_id'] = 0
        jsdata['active'] = True
        cuser = user_schema.load(jsdata, partial=True)
        user = create_user(user_name=cuser.name,
                    user_login=cuser.user,
                    user_email=cuser.email,
                    user_password=cuser.password,
                    user_isadmin=jsdata.get('user_isadmin'))

        db.session.commit()

        if cuser:
            track_activity("created user {}".format(user.user), caseid=caseid)
            return response_success("user created", data=user_schema.dump(user))

        return response_error("Unable to create user for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@manage_users_blueprint.route('/manage/users/<int:cur_id>', methods=['GET'])
@api_admin_required
def view_user(cur_id, caseid):
    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID")

    user_schema = UserSchema()
    cuser = user_schema.load({}, instance=user)
    cuser.user_roles_str = [role.name for role in user.roles]

    return response_success(data=user_schema.dump(cuser))


@manage_users_blueprint.route('/manage/users/<int:cur_id>/modal', methods=['GET'])
@login_required
def view_user_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_users.add_user', cid=caseid))

    form = AddUserForm()
    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID")

    form.user_login.render_kw = {'value': user.user}
    form.user_name.render_kw = {'value': user.name}
    form.user_email.render_kw = {'value': user.email}

    roles = [role.name for role in user.roles]
    form.user_isadmin.data = 'administrator' in roles

    return render_template("modal_add_user.html", form=form, user=user)


@manage_users_blueprint.route('/manage/users/update/<int:cur_id>', methods=['POST'])
@api_admin_required
def update_user_api(cur_id, caseid):
    try:
        user = get_user(cur_id)
        if not user:
            return response_error("Invalid user ID for this case")

        # validate before saving
        user_schema = UserSchema()
        jsdata = request.get_json()
        jsdata['user_id'] = cur_id
        cuser = user_schema.load(jsdata, instance=user, partial=True)
        uadm = jsdata.get('user_isadmin') or False
        update_user(password=jsdata.get('user_password'),
                    user_isadmin=uadm,
                    user=user)
        db.session.commit()

        if cuser:
            track_activity("updated user {}".format(user.user), caseid=caseid)
            return response_success("User updated", data=user_schema.dump(user))

        return response_error("Unable to update user for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@manage_users_blueprint.route('/manage/users/delete/<int:cur_id>', methods=['GET'])
@api_admin_required
def view_delete_user(cur_id, caseid):
    try:
        user = get_user(cur_id)
        if not user:
            return response_error("Invalid user ID")

        db.session.delete(user)
        db.session.commit()

        track_activity(message="deleted user ID {}".format(cur_id), caseid=caseid)
        return response_success("Deleted user ID {}".format(cur_id))

    except Exception as e:
        db.session.rollback()
        track_activity(message="tried to delete active user ID {}".format(cur_id), caseid=caseid)
        return response_error("Cannot delete active user")
