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
    repo_slug = origin.url.removeprefix("git@github.com:").removesuffix(".git")
    origin.set_url(f"https://{args.token}@github.com/{repo_slug}.git")

    gh_repo = Github(args.token).get_repo(repo_slug)

    with repo.config_writer("global") as config:
        config.set_value("user", "name", "github-actions")
        config.set_value("user", "email", "github-action@users.noreply.github.com")

    # Get current PRs HEAD in the repository.
    pr_heads = [pr.head.label for pr in gh_repo.get_pulls(state="open")]

    for submodule in repo.submodules:
        print("updating", submodule.name)

        with change_branch(submodule) as branch:

            pr_exist = f"github-actions:{branch}" in pr_heads
            if pr_exist:
                origin.pull(branch)

            # Update submodule from remote.
            repo.git.config(
                f"submodule.{submodule.name}.branch", "main", file=".gitmodules"
            )
            repo.git.submodule("sync", submodule.path)
            repo.git.submodule("update", "--remote", submodule.path)

            if repo.is_dirty():

                repo.git.add(submodule.path)
                repo.git.commit(message="[UPDATE] submodule to most recent version.")
                print(repo.git.log())
                print(repo.git.status())
                repo.git.push("origin", branch)
                print("pushed", submodule.name, "to", branch)

                if not pr_exist:
                    print(
                        "TRYING to PR",
                        submodule.name,
                        "from",
                        branch,
                        "to",
                        gh_repo.default_branch,
                    )
                    gh_repo.create_pull(
                        title=f"[UPDATE] submodule to most recent version. ({submodule.name})",
                        body=f"""## Description
A new version of {submodule.name} exists.
This is an automatic update of the submodule.""",
                        head=branch,
                        base=gh_repo.default_branch,
                    )
                print(
                    "PR", submodule.name, "from", branch, "to", gh_repo.default_branch
                )
