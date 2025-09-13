#!/usr/bin/env python3
"""Script to synchronize and update package versions in requirements files.

This module reads package versions from source requirements files and updates
target requirements files accordingly, preserving formatting and comments.
"""
import argparse
import logging
from pathlib import Path
import re
from typing import Any

logging.basicConfig(
    format="%(levelname)s: %(message)s",
    level=logging.INFO,
)
logger: logging.Logger = logging.getLogger(__name__)


def parse_requirements(content: str) -> dict[str, str | None]:
    """Parse a requirements.txt file content and extract package names and versions.

    Args:
        content: The content of a requirements.txt file as a string

    Returns:
        A dictionary mapping package names (lowercase) to their version specifiers.
        Version will be None if no version is specified.

    Example:
        >>> content = "package1>=1.0.0
                       package2==2.0.0"
        >>> parse_requirements(content)
        {'package1': '>=1.0.0', 'package2': '==2.0.0'}

    """
    versions: dict = {}
    for line in content.splitlines():
        line_nsp: str = line.strip()
        if not line_nsp or line_nsp.startswith(("#", "-r")):
            continue

        # Handle lines with version specifiers
        if match := re.match(r"^([^=<>~!]+)((?:[=<>~!]=|>=|<=|~=|==).+)?$", line_nsp):
            package: str | Any = match.group(1).strip()
            version: str | Any | None = (
                match.group(2).strip() if match.group(2) else None
            )
            versions[package.lower()] = version
    return versions


def convert_to_compatible_release(version_spec: str | None) -> str | None:
    """Convert version specifier to compatible release operator (~=).

    Args:
        version_spec: Version specifier string like '==1.2.3' or '>=1.2.3'

    Returns:
        Version specifier converted to ~= format, or None if invalid

    """
    if not version_spec:
        return None

    match: re.Match[str] | None = re.match(r"^==(.+)$", version_spec.strip())
    if match:
        return f"~={match.group(1)}"
    return version_spec


def update_requirements_file(
    file_path: Path, version_map: dict[str, str | None]
) -> None:
    """Update package versions in a requirements file while preserving format.

    Converts exact version matches (==) to compatible release (~=) format.

    Args:
        file_path: Path object pointing to the requirements file to update
        version_map: Dictionary mapping package names to their target versions

    The function preserves comments, blank lines and -r references while
    updating only the version numbers of packages that exist in version_map.

    Example:
        >>> update_requirements_file(
        ...     Path('requirements.txt'),
        ...     {'package1': '==1.0.0', 'package2': '>=2.0.0'}
        ... )

    """
    with Path(file_path).open(encoding="UTF-8") as f:
        content: str = f.read()

    new_lines: list = []
    for line in content.splitlines():
        new_line: str = line
        if line.strip() and not line.startswith("#") and not line.startswith("-r"):
            match: re.Match[str] | None = re.match(
                r"^([^=<>~!]+)((?:[=<>~!]=|>=|<=|~=|==).+)?$", line.strip()
            )
            if match:
                package: str = match.group(1).strip()
                if package.lower() in version_map:
                    version: str | None = convert_to_compatible_release(
                        version_map[package.lower()]
                    )
                    if version:
                        new_line = f"{package}{version}"

        new_lines.append(new_line)

    with Path(file_path).open("w", encoding="UTF-8") as f:
        f.write("\n".join(new_lines) + "\n")


def main() -> None:
    """Synchronize the requirements files.

    Reads package versions from multiple source requirements files and updates the versions
    in requirements.txt and requirements_test.txt accordingly. When a package appears in
    multiple source files, the last occurrence's version is used.

    Command line arguments:
        --sources: One or more source requirements files to read versions from
        --base-path: Base path for requirements files (default: current directory)
    """
    parser = argparse.ArgumentParser(
        description="Update requirement files with versions from source files"
    )
    parser.add_argument(
        "--sources",
        "-s",
        nargs="+",
        default=["requirements_all.txt"],
        help="Source requirements files to read versions from",
    )
    parser.add_argument(
        "--base-path",
        "-b",
        default=".",
        help="Base path for requirements files",
    )

    args: argparse.Namespace = parser.parse_args()
    base_path: Path = Path(args.base_path)
    versions: dict[str, str | None] = {}

    try:
        # Read and merge all source files
        for source in args.sources:
            source_file = base_path / source

            # Read source requirements file and update versions
            with source_file.open(encoding="UTF-8") as f:
                file_versions: dict[str, str | None] = parse_requirements(f.read())
                versions.update(file_versions)
                logger.info("Read %d packages from %s", len(file_versions), source_file)

        if not versions:
            logger.error("No valid source files found")
            return

        # Update target files
        for target in ("requirements.txt", "requirements_test.txt"):
            target_file: Path = base_path / target
            if target_file.exists():
                update_requirements_file(target_file, versions)
                logger.info("Updated %s", target_file)
            else:
                logger.warning("Target file not found: %s", target_file)

    except FileNotFoundError:
        logger.exception("Source file not found: %s", source_file)


if __name__ == "__main__":
    main()
