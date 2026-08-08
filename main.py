"""JDK Vault Builder CLI entrypoint.

Phase 1 scaffold: only argument parsing is wired up. Real subcommands are
added in Phase 7.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jdk-vault-builder",
        description=(
            "Builds and maintains an Obsidian vault documenting Java JDK changes "
            "from a CSV of release links."
        ),
    )
    parser.parse_args()


if __name__ == "__main__":
    main()
