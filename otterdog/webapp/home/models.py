# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from sqlalchemy import Column, Integer, String

from .. import db


class Organizations(db.Model):
    __tablename__ = 'Organizations'

    id = Column(Integer, primary_key=True)
    github_id = Column(String(100), unique=True)
    eclipse_project = Column(String(100), unique=True)

    def __repr__(self) -> str:
        return f"Organization(id={self.id!r}, github_id={self.github_id!r}, eclipse_project={self.eclipse_project!r})"
