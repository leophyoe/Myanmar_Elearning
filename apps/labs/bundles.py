"""Safe extraction of lab / challenge bundles into the ``cyber/`` folder.

The web app never executes bundle content — it only unpacks it into
``cyber/labs/<category>/<slug>/`` (or ``cyber/challenges/...``) so that Docker
images can be built from that tree later. Even so, a teacher-supplied archive
is still untrusted input, so everything is checked before a single byte hits
the filesystem:

* no absolute paths, no ``..`` traversal, no symlinks;
* member count and total uncompressed size are capped (zip-bomb guard);
* every file must be a source/text file (a bundle carries lab source, not
  binaries).
"""

import os
import zipfile
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

# Source text a lab/challenge bundle is expected to contain.
ALLOWED_SUFFIXES = {
    '.py', '.pyw', '.sh', '.bash', '.zsh', '.md', '.rst', '.txt',
    '.yml', '.yaml', '.toml', '.json', '.ini', '.cfg', '.conf', '.properties',
    '.sql', '.csv', '.tsv', '.log',
    '.html', '.htm', '.css', '.scss', '.js', '.ts', '.jsx', '.tsx', '.vue',
    '.c', '.h', '.cpp', '.hpp', '.cc', '.go', '.rs', '.rb', '.php', '.pl',
    '.java', '.kt', '.scala', '.cs', '.swift', '.r', '.m', '.ipynb',
    '.xml', '.svg', '.service', '.socket', '.example', '.dist',
}

# Files with no extension at all (Dockerfile, Makefile, entrypoint, ...).
ALLOWED_BASENAMES = {
    'dockerfile', 'makefile', 'readme', 'license', 'entrypoint',
    'requirements', 'procfile', 'vagrantfile', 'rakefile', 'gemfile',
    '.gitignore', '.dockerignore',
}

MAX_MEMBERS = 500


class BundleError(Exception):
    """Raised when an uploaded bundle is rejected."""


def _limit_mb() -> int:
    return getattr(settings, 'CYBER_BUNDLE_MAX_MB', 25)


def _member_suffix_ok(name: str) -> bool:
    lower = name.lower()
    base_name = Path(lower).name
    if base_name in ALLOWED_BASENAMES:
        return True
    suffix = Path(lower).suffix
    if suffix and suffix in ALLOWED_SUFFIXES:
        return True
    if any(lower.endswith(s) for s in ALLOWED_SUFFIXES if s):
        return True
    if not suffix and '.' not in base_name:
        # Extension-less files: custom scripts with no extension
        return True
    return False


def _member_is_safe(info: zipfile.ZipInfo) -> bool:
    if info.is_dir():
        return True
    name = info.filename.replace('\\', '/')

    if name.startswith('/') or name.startswith('../') or '/../' in f'/{name}/':
        return False
    if any(part == '..' for part in name.split('/')):
        return False
    # Reject symlinks / special files (unix mode lives in external_attr).
    mode = info.external_attr >> 16
    if mode and (mode & 0o170000) == 0o120000:
        return False
    return _member_suffix_ok(name)


@contextmanager
def checked_archive(archive):
    """Open the archive and run every safety check before yielding it."""
    if not zipfile.is_zipfile(archive):
        raise BundleError("The bundle must be a .zip archive.")

    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile:
        raise BundleError("The uploaded archive is corrupt.")

    try:
        infos = zf.infolist()
        if len(infos) > MAX_MEMBERS:
            raise BundleError(f"Bundle has too many files (limit {MAX_MEMBERS}).")

        total = 0
        for info in infos:
            total += info.file_size
            if total > _limit_mb() * 1024 * 1024:
                raise BundleError(
                    f"Bundle is too large once unpacked (limit {_limit_mb()} MB)."
                )
            if not _member_is_safe(info):
                raise BundleError(
                    f"Bundle contains an unsafe or unsupported file: {info.filename}"
                )
        yield zf, infos
    finally:
        zf.close()


def validate_bundle(archive) -> list:
    """Check an archive without writing anything. Returns member names."""
    with checked_archive(archive) as (_zf, infos):
        return [i.filename for i in infos if not i.is_dir()]


def extract_bundle(archive, dest_dir) -> list:
    """Extract ``archive`` into ``dest_dir``; returns relative paths written.

    Raises :class:`BundleError` before writing a single byte if the archive
    fails validation.
    """
    dest_dir = Path(dest_dir)
    with checked_archive(archive) as (zf, infos):
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_resolved = dest_dir.resolve()
        written = []
        for info in infos:
            name = info.filename.replace('\\', '/')
            while name.startswith('./'):
                name = name[2:]
            if not name:
                continue
            if name.endswith('/'):
                (dest_dir / name).mkdir(parents=True, exist_ok=True)
                continue
            target = (dest_dir / name).resolve()
            if not str(target).startswith(str(dest_resolved) + os.sep):
                raise BundleError(f"Bundle path escapes its folder: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, open(target, 'wb') as out:
                while True:
                    chunk = source.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
            written.append(name)

    if not written:
        raise BundleError("The bundle is empty.")
    return written


def bundle_dir(base_dir, category: str, slug: str) -> Path:
    """Destination folder for a bundle: ``<base>/<category>/<slug>/``."""
    return Path(base_dir) / category / slug
