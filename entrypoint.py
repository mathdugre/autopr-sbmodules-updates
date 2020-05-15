#!/usr/bin/env python3
import argparse
from contextlib import contextmanager
import os
import re
from typing import List, Generator, NoReturn

import git
import requests


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create PR for updated submodules in repository"
    )

    parser.add_argument("owner", type=str, help="Name of the repository owner.")
    parser.add_argument("repo", type=str, help="Name of the repository.")
    parser.add_argument(
        "github_token",
        type=str,
        help="Github token with access to the owner repository.",
    )
    parser.add_argument("user", type=str, help="Name of the fork user.")
    parser.add_argument(
        "user_github_token", type=str, help="GitHub API token for of the fork user."
    )

    return parser.parse_args()


def create_pr(submodule, PROJECT_SLUG, GITHUB_TOKEN, head):
    r = requests.post(
        f"https://api.github.com/repos/{PROJECT_SLUG}/pulls?access_token={GITHUB_TOKEN}",
        json={
            "title": f"[UPDATE] submodule to most recent version. ({submodule.name})",
            "body": "## Description"
            + f"\nA new version of {submodule.name} exists."
            + "This is an automatic update of the submodule.",
            "head": head,
            "base": "master",
        },
    )


@contextmanager
def change_branch(submodule):

    initial_branch = submodule.repo.active_branch.name
    target_branch_name = f"update/{submodule.name}"

    if not any(
        [
            re.match("(\*|\s)\s" + target_branch_name, branch)
            for branch in repo.git.branch().split("\n")
        ]
    ):
        submodule.repo.git.branch(target_branch_name)

    submodule.repo.git.checkout(target_branch_name)
    yield submodule.repo.active_branch
    submodule.repo.git.checkout(initial_branch)


if __name__ == "__main__":
    args = parse_args()
    PROJECT_SLUG = f"{args.owner}/{args.repo}"

    repo_path = os.path.join(os.getcwd(), args.repo)
    git.Repo.clone_from(f"https://github.com/{PROJECT_SLUG}.git", repo_path)

    repo = git.Repo(repo_path)

    with repo.config_writer("global") as config:
        config.set_value("user", "name", args.user)
        config.set_value("user", "email", "github-action@users.noreply.github.com")

    # Use GitHub token for authentication.
    upstream = repo.create_remote(
        "upstream",
        f"https://{args.user}:{args.user_github_token}@github.com/{args.user}/{args.repo}.git",
    )

    # Get current PRs HEAD in the repository.
    pull_requests = requests.get(
        f"https://api.github.com/repos/{PROJECT_SLUG}/pulls"
    ).json()
    pr_heads = [pr["head"]["label"] for pr in pull_requests]

    for submodule in repo.submodules:

        with change_branch(submodule) as branch:

            pr_exist = f"{args.user}:{branch}" in pr_heads
            if pr_exist:
                upstream.pull(branch)

            # Update submodule from remote.
            repo.git.submodule("sync", submodule.path)
            repo.git.submodule("update", "--remote", submodule.path)

            if repo.is_dirty():

                repo.git.add(submodule.path)
                repo.git.commit(message="[UPDATE] submodule to most recent version.")
                upstream.push(branch)

                if not pr_exist:
                    create_pr(
                        submodule,
                        PROJECT_SLUG,
                        args.github_token,
                        head=f"{args.user}:{branch}",
                    )
