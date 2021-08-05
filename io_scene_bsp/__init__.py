bl_info = {
    'name': 'Quake engine BSP format',
    'author': 'Joshua Skelton',
    'version': (1, 1, 1),
    'blender': (2, 80, 0),
    'location': 'File > Import-Export',
    'description': 'Load a Quake engine BSP file.',
    'warning': '',
    'wiki_url': '',
    'support': 'COMMUNITY',
    'category': 'Import-Export'}

__version__ = '.'.join(map(str, bl_info['version']))


if 'operators' in locals():
    import importlib as il
    il.reload(operators)
    il.reload(panels)
    print('io_scene_bsp: reload ready')

else:
    print('io_scene_bsp: ready')


def register():
    from .patch import ensure_modules_dir_on_path
    ensure_modules_dir_on_path()

    from . import operators
    operators.register()

    from . import panels
    panels.register()


def unregister():
    from . import operators
    operators.unregister()

    from . import panels
    panels.unregister()


if __name__ == '__main__':
    register()
