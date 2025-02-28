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

import re

import dateutil.parser
import marshmallow
from marshmallow import fields, post_load, pre_load
from marshmallow.validate import Length
from marshmallow_sqlalchemy import auto_field
from sqlalchemy import func

from app import ma
from app.models import Cases, GlobalTasks, User, Client, Notes, NotesGroup, CaseAssets, Ioc, CasesEvent, CaseTasks, \
    CaseReceivedFile

task_status = ['To do', 'In progress', 'On hold', 'Done', 'Canceled']


class CaseNoteSchema(ma.SQLAlchemyAutoSchema):
    csrf_token = fields.String(required=False)

    class Meta:
        model = Notes
        load_instance = True


class CaseAddNoteSchema(ma.Schema):
    note_id = fields.Integer(required=False)
    note_title = fields.String(required=True, validate=Length(min=1))
    note_content = fields.String(required=False, validate=Length(min=1))
    group_id = fields.Integer(required=True)
    csrf_token = fields.String(required=False)

    def verify_group_id(self, data, **kwargs):
        group = NotesGroup.query.filter(
            NotesGroup.group_id == data.get('group_id'),
            NotesGroup.group_case_id == kwargs.get('caseid')
        ).first()
        if group:
            return data

        raise marshmallow.exceptions.ValidationError("Invalid group id for note",
                                                     field_name="group_id")


class CaseGroupNoteSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = NotesGroup
        load_instance = True


class CaseAssetsSchema(ma.SQLAlchemyAutoSchema):
    asset_name = auto_field('asset_name', required=True, validate=Length(min=2))
    ioc_links = fields.List(fields.String, required=False)

    class Meta:
        model = CaseAssets
        include_fk = True
        load_instance = True


class IocSchema(ma.SQLAlchemyAutoSchema):
    ioc_value = auto_field('ioc_value', required=True, validate=Length(min=1))

    class Meta:
        model = Ioc
        load_instance = True
        include_fk = True


class EventSchema(ma.SQLAlchemyAutoSchema):
    event_title = auto_field('event_title', required=True, validate=Length(min=2))
    event_category = fields.Integer(required=True)
    event_assets = fields.List(fields.Integer, required=True)
    event_date = fields.String(required=True)
    event_time = fields.String(required=True)
    event_tz = fields.String(required=True)

    class Meta:
        model = CasesEvent
        load_instance = True
        include_fk = True

    def validate_date(self, event_date, event_time, event_tz):
        date_time = "{}T{}{}".format(event_date, event_time, event_tz)
        date_time_wtz = "{}T{}".format(event_date, event_time)

        try:

            self.event_date = dateutil.parser.isoparse(date_time)
            event_date_wtz = dateutil.parser.isoparse(date_time_wtz)

        except Exception as e:
            raise marshmallow.exceptions.ValidationError("Invalid date time",
                                                         field_name="event_date")

        return self.event_date, event_date_wtz


class CaseSchema(ma.SQLAlchemyAutoSchema):
    case_name = auto_field('name', required=True, validate=Length(min=2))
    case_description = auto_field('description', required=True, validate=Length(min=2))
    case_soc_id = auto_field('soc_id', required=True)
    case_customer = auto_field('client_id', required=True)
    csrf_token = fields.String(required=False)

    class Meta:
        model = Cases
        include_fk = True
        load_instance = True
        exclude = ['name', 'description', 'soc_id', 'client_id']


class GlobalTasksSchema(ma.SQLAlchemyAutoSchema):
    task_id = auto_field('id')
    task_assignee = auto_field('task_assignee_id', required=True)
    task_title = auto_field('task_title', required=True, validate=Length(min=2))
    csrf_token = fields.String(required=False)

    class Meta:
        model = GlobalTasks
        include_fk = True
        load_instance = True
        exclude = ['id', 'task_assignee_id']

    @pre_load
    def verify_assignee(self, data, **kwargs):
        user = User.query.filter(User.id == data.get('task_assignee')).first()
        if user:
            return data

        raise marshmallow.exceptions.ValidationError("Invalid user id for assignee",
                                                     field_name="task_assignee")

    @pre_load
    def verify_status(self, data, **kwargs):
        if data.get('task_status') in task_status:
            return data

        raise marshmallow.exceptions.ValidationError("Invalid status string",
                                                     field_name="task_status")


class CustomerSchema(ma.SQLAlchemyAutoSchema):
    customer_name = auto_field('name', required=True, validate=Length(min=2))
    csrf_token = fields.String(required=False)

    class Meta:
        model = Client
        load_instance = True
        exclude = ['name']

    @post_load
    def verify_unique(self, data, **kwargs):
        client = Client.query.filter(func.upper(Client.name) == data.name.upper()).first()
        if client:
            raise marshmallow.exceptions.ValidationError(
                "Customer already exists with this particular name",
                field_name="customer_name"
            )

        return data


class TaskLogSchema(ma.Schema):
    log_content = fields.String(required=False, validate=Length(min=1))
    csrf_token = fields.String(required=False)


class CaseTaskSchema(ma.SQLAlchemyAutoSchema):
    task_assignee_id = fields.Integer(required=True)
    task_title = auto_field('task_title', required=True, validate=Length(min=2))

    class Meta:
        model = CaseTasks
        load_instance = True


class CaseEvidenceSchema(ma.SQLAlchemyAutoSchema):
    filename = auto_field('filename', required=True, validate=Length(min=2))

    class Meta:
        model = CaseReceivedFile
        load_instance = True


class UserSchema(ma.SQLAlchemyAutoSchema):
    user_roles_str = fields.List(fields.String, required=False)
    user_name = auto_field('name', required=True, validate=Length(min=2))
    user_login = auto_field('user', required=True, validate=Length(min=2))
    user_email = auto_field('email', required=True, validate=Length(min=2))
    user_password = auto_field('password', required=True, validate=Length(min=2))
    user_isadmin = fields.Boolean(required=True)
    csrf_token = fields.String(required=False)
    user_id = fields.Integer(required=False)

    class Meta:
        model = User
        load_instance = True
        include_fk = True
        exclude = ['api_key', 'password', 'ctx_case', 'ctx_human_case', 'user', 'name', 'email']

    @pre_load()
    def verify_username(self, data, **kwargs):
        user = data.get('user_login')
        user_id = data.get('user_id')
        luser = User.query.filter(
            User.user == user
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise marshmallow.exceptions.ValidationError('User name already taken',
                                                             field_name="user_login")

        return data

    @pre_load()
    def verify_email(self, data, **kwargs):
        email = data.get('user_email')
        user_id = data.get('user_id')
        luser = User.query.filter(
            User.email == email
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise marshmallow.exceptions.ValidationError('User email already taken',
                                                             field_name="user_email")

        return data

    @pre_load()
    def verify_password(self, data, **kwargs):
        password = data.get('user_password')
        if data.get('user_password') == '' and data.get('user_id') != 0:
            # Update
            data.pop('user_password')

        else:
            if not re.match('\d.*[A-Z]|[A-Z].*\d', password):
                raise marshmallow.exceptions.ValidationError('Password must contain 1 capital letter and 1 number',
                                                             field_name="user_password")

            if len(password) < 12:
                raise marshmallow.exceptions.ValidationError('Password must be longer than 12 characters',
                                                             field_name="user_password")

        return data
