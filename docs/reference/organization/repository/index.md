# Repository

Definition of a Repository for a GitHub organization, the following properties are supported:

| Key                                   | Value                                                     | Description                                                                             | Notes                                                                                    |
|---------------------------------------|-----------------------------------------------------------|-----------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| _name_                                | string                                                    | Name of the repository                                                                  |                                                                                          |
| _aliases_                             | list[string]                                              | List of repository alias names, need to add previous name when renaming a repository    |                                                                                          |
| _description_                         | string or null                                            | Project description                                                                     |                                                                                          |
| _homepage_                            | string or null                                            | Link to the homepage                                                                    |                                                                                          |
| _topics_                              | list[string]                                              | The list of topics of this repository.                                                  |                                                                                          |
| _private_                             | boolean                                                   | If the project is private                                                               |                                                                                          |
| _archived_                            | boolean                                                   | If the repo is archived                                                                 |                                                                                          |
| _allow_auto_merge_                    | boolean                                                   | If auto merges are permitted                                                            |                                                                                          |
| _allow_forking_                       | boolean                                                   | If the repo allows private forking                                                      |                                                                                          |
| _allow_merge_commit_                  | boolean                                                   | If merge commits are permitted                                                          |                                                                                          |
| _allow_rebase_merge_                  | boolean                                                   | If rebase merges are permitted                                                          |                                                                                          |
| _allow_squash_merge_                  | boolean                                                   | If squash merges are permitted                                                          |                                                                                          |
| _allow_update_branch_                 | boolean                                                   | If pull requests should suggest updates                                                 |                                                                                          |
| _auto_init_                           | boolean                                                   | If the repository shall be auto-initialized during creation                             | only considered during creation                                                          |
| _default_branch_                      | string                                                    | Name of the default branch                                                              |                                                                                          |
| _delete_branch_on_merge_              | boolean                                                   | If branches shall automatically be deleted after a merge                                |                                                                                          |
| _dependabot_alerts_enabled_           | boolean                                                   | If the repo has dependabot alerts enabled                                               |                                                                                          |
| _dependabot_security_updates_enabled_ | boolean                                                   | If the repo has dependabot security updates enabled                                     |                                                                                          |
| _gh_pages_build_type_                 | string                                                    | If the repo has GitHub Pages enabled                                                    | `disabled`, `legacy` or `workflow`. Build-type `legacy` refers to building from a branch |
| _gh_pages_source_branch_              | string or null                                            | The branch from which GitHub Pages should be built                                      | only taken into account when `gh_pages_build_type` is set to `legacy`                    |
| _gh_pages_source_path_                | string or null                                            | The folder from which GitHub Pages should be built                                      | only taken into account when `gh_pages_build_type` is set to `legacy`                    |
| _has_discussions_                     | boolean                                                   | If the repo has discussions enabled                                                     |                                                                                          |
| _has_issues_                          | boolean                                                   | If the repo can have issues                                                             |                                                                                          |
| _has_projects_                        | boolean                                                   | If the repo can have projects                                                           |                                                                                          |
| _has_wiki_                            | boolean                                                   | If the repo has a wiki                                                                  |                                                                                          |
| _is_template_                         | boolean                                                   | If the repo is can be used as a template repository                                     |                                                                                          |
| _merge_commit_message_                | string                                                    | Can be PR_BODY, PR_TITLE, or BLANK for a default merge commit message                   |                                                                                          |
| _merge_commit_title_                  | string                                                    | Can be PR_TITLE or MERGE_MESSAGE for a default merge commit title                       |                                                                                          |
| _post_process_template_content_       | list[string]                                              | A list of content paths in a template repository that shall be processed after creation | only considered during creation                                                          | 
| _secret_scanning_                     | string                                                    | If secret scanning is "enabled" or "disabled"                                           |                                                                                          |
| _secret_scanning_push_protection_     | string                                                    | If secret scanning push protection is "enabled" or "disabled"                           |                                                                                          |
| _squash_merge_commit_message_         | string                                                    | Can be PR_BODY, COMMIT_MESSAGES, or BLANK for a default squash merge commit message     |                                                                                          |
| _squash_merge_commit_title_           | string                                                    | Can be PR_TITLE or COMMIT_OR_PR_TITLE for a default squash merge commit title           |                                                                                          |
| _template_repository_                 | string or null                                            | The template repository to use when creating the repo                                   | read-only                                                                                |
| _web_commit_signoff_required_         | boolean                                                   | If the repo requires web commit signoff                                                 |                                                                                          |
| _webhooks_                            | list\[[Webhook](webhook.md)\]                             | webhooks defined for this repo, see section above for details                           |                                                                                          |
| _secrets_                             | list\[[RepositorySecret](secret.md)\]                     | secrets defined for this repo, see section below for details                            |                                                                                          |
| _environments_                        | list\[[Environment](environment.md)\]                     | environments defined for this repo, see section below for details                       |                                                                                          |
| _branch_protection_rules_             | list\[[BranchProtectionRule](branch-protection-rule.md)\] | branch protection rules of the repo, see section below for details                      |                                                                                          |

## Jsonnet Function

=== "new"
    ``` jsonnet
    orgs.newRepo('<name>') {
      <key>: <value>
    }
    ```

=== "extend"
    ``` jsonnet
    orgs.extendRepo('<name>') {
      <key>: <value>
    }
    ```

!!! note

    In general, you will only ever use `orgs.newRepo` as this function will define a new repository with default
    values. However, in some cases it might be needed to change properties for a repo that has already been defined 
    in the default configuration. In such situation, you should use `orgs.extendRepo`.

## Validation rules

- TODO

!!! note

    When enabling GitHub Pages by setting `gh_pages_build_type` to either `legacy` or `workflow`, you should also
    define a `github-pages` environment, as it will be created automatically by GitHub.

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('adoptium') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('.github') {
          allow_auto_merge: true,
          allow_merge_commit: false,
          allow_update_branch: false,
          dependabot_alerts_enabled: false,
          web_commit_signoff_required: false,
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main'),
          ],
        },
    }
    ```