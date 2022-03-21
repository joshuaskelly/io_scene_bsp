import argparse
import os
import sys

import lightmap_extract


class ResolvePathAction(argparse.Action):
    """Action to resolve paths and expand environment variables"""
    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, list):
            fullpath = [os.path.expanduser(v) for v in values]
        else:
            fullpath = os.path.expanduser(values)

        setattr(namespace, self.dest, fullpath)


def main():
    parser = argparse.ArgumentParser(
        prog='cli',
        description='Test cli',
        epilog='example: cli e1m1.bsp => creates the svg file e1m1.svg'
    )

    parser.add_argument(
        'file',
        metavar='file.bsp',
        action=ResolvePathAction
    )

    parser.add_argument(
        '-d',
        metavar='file.png',
        dest='dest',
        default=f'{os.getcwd()}\\file.png',
        action=ResolvePathAction,
        help='svg file to create'
    )

    parser.add_argument(
        '-i', '--ignore',
        dest='ignore',
        metavar='name',
        nargs='*',
        default=[],
        help='texture names to ignore'
    )

    parser.add_argument(
        '-q',
        dest='quiet',
        action='store_true',
        help='quiet mode'
    )

    args = parser.parse_args()
    lightmap_extract.extract(args.file, args.dest)


if __name__ == '__main__':
    import timeit

    print(timeit.timeit(main, number=1))

    sys.exit()
