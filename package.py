"""Packages the addon and dependency"""
import os
import zipfile

import vgio
import io_scene_bsp

ignored_directories = (
    '__pycache__',
    '.DS_Store'
)


def gather_files(basedir, arc_prefix=''):
    """Walk the given directory and return a sequence of filepath, archive name
    pairs.

    Args:
        basedir: The directory to start the walk

        arc_prefix: A path to join to the front of the relative (to basedir)
            file path

    Returns:
        A sequence of (filepath, archive name) pairs
    """
    results = []

    for path, subdirectories, files in os.walk(basedir):
        if os.path.basename(path) in ignored_directories:
            continue

        for file in files:
            relative_path = os.path.join(path, file)
            full_path = os.path.abspath(relative_path)
            arcname = os.path.relpath(full_path, os.path.dirname(basedir))
            arcname = os.path.join(arc_prefix, arcname)

            results.append((full_path, arcname))

    return results


def run():
    try:
        os.mkdir('dist')

    except FileExistsError:
        pass

    zip_entries = gather_files('io_scene_bsp')
    zip_entries += gather_files(os.path.dirname(vgio.__file__), 'modules')

    with zipfile.ZipFile(f'dist\\io_scene_bsp-{io_scene_bsp.__version__}.zip', 'w') as dist_zip:
        for filename, arcname in zip_entries:
            dist_zip.write(filename, arcname)


if __name__ == '__main__':
    run()
