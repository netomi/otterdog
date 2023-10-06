# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

"""Data classes for events received via webhook from GitHub."""


from __future__ import annotations

from abc import ABC
from typing import Optional

from pydantic import BaseModel


class Installation(BaseModel):
    """The installation that is associated with the event."""

    id: int
    node_id: str


class Organization(BaseModel):
    """The organization that is associated with the event."""

    login: str
    id: int
    node_id: str


class Repository(BaseModel):
    """A reference to the repository."""

    id: int
    node_id: str
    name: str
    full_name: str
    private: bool
    owner: Actor


class Actor(BaseModel):
    """An actor, can be either of type 'User' or 'Organization'."""

    login: str
    id: int
    node_id: str
    type: str


class Ref(BaseModel):
    """A ref in a repository."""

    label: str
    ref: str
    sha: str
    user: Actor
    repo: Repository


class PullRequest(BaseModel):
    """Represents a pull request."""

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


class Event(ABC, BaseModel):
    """Base class of events"""

    action: str
    installation: Installation
    organization: Organization
    sender: Actor


class PullRequestEvent(Event):
    """A payload sent for pull request specific events."""

    number: int
    pull_request: PullRequest
    repository: Repository
