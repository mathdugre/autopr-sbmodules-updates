#!/usr/bin/env python3
import argparse
from contextlib import contextmanager
import re

from github import Github
import git


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create PR for updated submodules in repository"
    )
    parser.add_argument(
        "token",
        type=str,
        help="Github token with access to the owner repository.",
    )

    return parser.parse_args()


@contextmanager
def change_branch(submodule):

    initial_branch = submodule.repo.active_branch.name
    target_branch_name = f"submodule-update/{submodule.name}"

    if not any(
        [
            re.match("(\*|\s)\s" + target_branch_name, branch)
            for branch in repo.git.branch().split("\n")
        ]
    ):
        submodule.repo.git.branch(target_branch_name)

    submodule.repo.git.checkout(target_branch_name)
    yield submodule.repo.active_branch.name
    submodule.repo.git.checkout(initial_branch)


if __name__ == "__main__":
    args = parse_args()

    repo = git.Repo()

    origin = repo.remote(name="origin")
    repo_slug = (
        lambda r: r.url.removesuffix(".git")
        .removeprefix("git@github.com:")
        .removeprefix("https://github.com/")
    )
    origin.set_url(f"https://{args.token}@github.com/{repo_slug(origin)}.git")

    gh = Github(args.token)
    gh_repo = gh.get_repo(repo_slug(origin))

    with repo.config_writer("global") as config:
        config.set_value("user", "name", "github-actions")
        config.set_value("user", "email", "github-action@users.noreply.github.com")

    # Get current PRs HEAD in the repository.
    pr_heads = [pr.head.label for pr in gh_repo.get_pulls(state="open")]

    for submodule in repo.submodules:
        print("updating", submodule.name)

        with change_branch(submodule) as branch:

            pr_exist = f"{gh.get_user().login}:{branch}" in pr_heads
            if pr_exist:
                repo.git.pull("origin", branch)

            # Update submodule from remote.
            submodule_gh_repo = gh.get_repo(repo_slug(submodule))
            repo.git.config(
                f"submodule.{submodule.name}.branch",
                submodule_gh_repo.default_branch,
                file=".gitmodules",
            )
            repo.git.submodule("sync", submodule.path)
            repo.git.submodule("update", "--remote", submodule.path)

            if repo.is_dirty(path=submodule.path):
                repo.git.add(submodule.path)
                repo.git.commit(message="[UPDATE] submodule to most recent version.")
                repo.git.push("origin", branch)

                if not pr_exist:
                    gh_repo.create_pull(
                        title=f"[UPDATE] submodule to most recent version. ({submodule.name})",
                        body=f"""## Description
A new version of {submodule.name} exists.
This is an automatic update of the submodule.""",
                        head=branch,
                        base=gh_repo.default_branch,
                    )
