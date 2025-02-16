#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from logging import getLogger

from pydantic import ValidationError
from quart import Response, current_app

from otterdog.webapp.db.service import (
    get_installation,
    update_installation_status,
    update_installations_from_config,
)
from otterdog.webapp.policies import create_policy
from otterdog.webapp.tasks.apply_changes import ApplyChangesTask
from otterdog.webapp.tasks.check_sync import CheckConfigurationInSyncTask
from otterdog.webapp.tasks.fetch_config import FetchConfigTask
from otterdog.webapp.tasks.fetch_policies import FetchPoliciesTask
from otterdog.webapp.tasks.help_comment import HelpCommentTask
from otterdog.webapp.tasks.retrieve_team_membership import RetrieveTeamMembershipTask
from otterdog.webapp.tasks.update_pull_request import UpdatePullRequestTask
from otterdog.webapp.tasks.validate_pull_request import ValidatePullRequestTask
from otterdog.webapp.utils import refresh_global_policies, refresh_otterdog_config

from .comment_handlers import (
    ApplyCommentHandler,
    CheckSyncCommentHandler,
    CommentHandler,
    DoneCommentHandler,
    HelpCommentHandler,
    MergeCommentHandler,
    TeamInfoCommentHandler,
    ValidateCommentHandler,
)
from .github_models import (
    Commit,
    InstallationEvent,
    IssueCommentEvent,
    PullRequestEvent,
    PullRequestReviewEvent,
    PushEvent,
    WorkflowJobEvent,
)
from .github_webhook import GitHubWebhook

webhook = GitHubWebhook()

comment_handlers: list[CommentHandler] = [
    HelpCommentHandler(),
    TeamInfoCommentHandler(),
    CheckSyncCommentHandler(),
    DoneCommentHandler(),
    ApplyCommentHandler(),
    MergeCommentHandler(),
    ValidateCommentHandler(),
]

logger = getLogger(__name__)


@webhook.hook("pull_request")
async def on_pull_request_received(data):
    try:
        event = PullRequestEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load pull request event data", exc_info=True)
        return success()

    if event.installation is None or event.organization is None:
        return success()

    if not await targets_config_repo(event.repository.name, event.installation.id):
        return success()

    if event.action in [
        "opened",
        "closed",
        "ready_for_review",
        "converted_to_draft",
        "ready_for_review",
        "reopened",
        "synchronize",
    ]:
        current_app.add_background_task(
            UpdatePullRequestTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request,
            )
        )

    if event.action in ["opened", "ready_for_review"] and event.pull_request.draft is False:
        current_app.add_background_task(
            HelpCommentTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request.number,
            )
        )

        current_app.add_background_task(
            RetrieveTeamMembershipTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request.number,
            )
        )

    if (
        event.action in ["opened", "synchronize", "ready_for_review", "reopened"]
        and event.pull_request.state == "open"
        and event.pull_request.draft is False
    ):
        # schedule a validate task
        current_app.add_background_task(
            ValidatePullRequestTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request,
            )
        )

        # schedule a check-sync task
        current_app.add_background_task(
            CheckConfigurationInSyncTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request,
            )
        )

    elif event.action in ["closed"] and event.pull_request.merged is True:
        if event.pull_request.base.ref != event.repository.default_branch:
            return success()

        current_app.add_background_task(
            ApplyChangesTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request,
            )
        )

    return success()


@webhook.hook("pull_request_review")
async def on_pull_request_review_received(data):
    try:
        event = PullRequestReviewEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load pull request review event data", exc_info=True)
        return success()

    if event.installation is None or event.organization is None:
        return success()

    if not await targets_config_repo(event.repository.name, event.installation.id):
        return success()

    if event.action in ["submitted", "edited", "dismissed"]:
        current_app.add_background_task(
            UpdatePullRequestTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request,
                event.review,
            )
        )

    return success()


@webhook.hook("issue_comment")
async def on_issue_comment_received(data):
    try:
        event = IssueCommentEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load issue comment event data", exc_info=True)
        return success()

    if event.installation is None or event.organization is None:
        return success()

    # currently we only handle comments to pull requests
    if event.issue.pull_request is None:
        return success()

    if not await targets_config_repo(event.repository.name, event.installation.id):
        return success()

    if event.action in ["created", "edited"]:
        for handler in comment_handlers:
            match = handler.matches(event.comment.body)
            if match is not None:
                handler.process(match, event)
                break

    return success()


@webhook.hook("push")
async def on_push_received(data):
    try:
        event = PushEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load push event data", exc_info=True)
        return success()

    # check if the push targets the default branch of the config repo of an installation,
    # in such a case, update the current config in the database
    if event.installation is not None and event.organization is not None:
        if event.ref != f"refs/heads/{event.repository.default_branch}":
            return success()

        if not await targets_config_repo(event.repository.name, event.installation.id):
            return success()

        current_app.add_background_task(
            FetchConfigTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
            )
        )

        def policy_path(path: str) -> bool:
            return path.startswith("otterdog/policies")

        def modifies_any_policy(commit: Commit) -> bool:
            return (
                any(map(policy_path, commit.added))
                or any(map(policy_path, commit.modified))
                or any(map(policy_path, commit.removed))
            )

        policies_modified = any(map(modifies_any_policy, event.commits))
        if policies_modified is True:
            global_policies = await refresh_global_policies()
            current_app.add_background_task(
                FetchPoliciesTask(
                    event.installation.id,
                    event.organization.login,
                    event.repository.name,
                    global_policies,
                )
            )

        return success()

    # if the otterdog config repo has been update, update all installations
    if (
        event.repository.name == current_app.config["OTTERDOG_CONFIG_REPO"]
        and event.repository.owner.login == current_app.config["OTTERDOG_CONFIG_OWNER"]
    ):
        if event.ref != f"refs/heads/{event.repository.default_branch}":
            return success()

        async def update_installations() -> None:
            config = await refresh_otterdog_config(event.after)
            policies = await refresh_global_policies(event.after)
            await update_installations_from_config(config, policies)

        current_app.add_background_task(update_installations)
        return success()

    return success()


@webhook.hook("installation")
async def on_installation_received(data):
    try:
        event = InstallationEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load installation event data", exc_info=True)
        return success()

    current_app.add_background_task(update_installation_status, event.installation.id, event.action)
    return success()


@webhook.hook("workflow_job")
async def on_workflow_job_received(data):
    try:
        event = WorkflowJobEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load workflow job event data", exc_info=True)
        return success()

    if event.installation is None or event.organization is None:
        return success()

    if event.action in ["queued"]:
        logger.debug(f"workflow job queued on runner: {', '.join(event.workflow_job.labels)}")

        from otterdog.webapp.db.service import find_policy
        from otterdog.webapp.policies import PolicyType
        from otterdog.webapp.policies.macos_large_runners import (
            MacOSLargeRunnersUsagePolicy,
        )

        policy_model = await find_policy(event.organization.login, PolicyType.MACOS_LARGE_RUNNERS_USAGE)
        if policy_model is not None:
            policy = create_policy(policy_model.id.policy_type, policy_model.config)
            assert isinstance(policy, MacOSLargeRunnersUsagePolicy)

            if not policy.is_workflow_job_permitted(event.workflow_job.labels):
                from otterdog.webapp.utils import get_rest_api_for_installation

                org_id = event.organization.login
                repo_name = event.repository.name
                run_id = event.workflow_job.run_id

                rest_api = await get_rest_api_for_installation(event.installation.id)
                cancelled = await rest_api.action.cancel_workflow_run(org_id, repo_name, run_id)
                logger.info(f"cancelled workflow run #{run_id} in repo '{org_id}/{repo_name}': success={cancelled}")

    return success()


def _uses_macos_larger_runner(labels: list[str]) -> bool:
    def larger_runner(label: str) -> bool:
        return label.startswith("macos") and label.endswith("large")

    return any(map(larger_runner, labels))


async def targets_config_repo(repo_name: str, installation_id: int) -> bool:
    installation = await get_installation(installation_id)
    if installation is None:
        logger.warning(f"received event for unknown installation '{installation_id}'")
        return False

    return repo_name == installation.config_repo


def success() -> Response:
    return Response({}, mimetype="application/json", status=200)
