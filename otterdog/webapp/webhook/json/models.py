# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Installation(BaseModel):
    id: int
    node_id: str


class Organization(BaseModel):
    login: str
    id: int
    node_id: str


class Repository(BaseModel):
    id: int
    node_id: str
    name: str
    full_name: str
    private: bool
    owner: Actor


class Actor(BaseModel):
    login: str
    id: int
    node_id: str
    type: str


class Ref(BaseModel):
    label: str
    ref: str
    sha: str
    user: Actor
    repo: Repository


class Event(BaseModel):
    action: str
    installation: Installation
    organization: Organization
    sender: Actor


class PullRequestEvent(Event):
    number: int
    pull_request: PullRequest
    repository: Repository


class PullRequest(BaseModel):
    id: int
    node_id: str
    number: int
    state: str
    locked: bool
    title: str
    body: Optional[str]
    draft: bool
    merged: bool
    user: Actor

    head: Ref
    base: Ref
