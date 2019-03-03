if 'bpy' in locals():
    import importlib as il
    il.reload(perfmon)
    il.reload(utils)
    il.reload(api)

else:
    from . import perfmon
    from . import utils
    from . import api

import os

import bpy
import bmesh
from mathutils import Matrix, Vector

from vgio.quake.bsp import Bsp, is_bspfile
from vgio.quake import map as Map

from .perfmon import PerformanceMonitor

performance_monitor = None


def load(operator,
         context,
         filepath='',
         global_scale=1.0,
         use_worldspawn_entity=True,
         use_brush_entities=True,
         use_point_entities=True):

    if not is_bspfile(filepath):
        operator.report(
            {'ERROR'},
            '{} not a recognized BSP file'.format(filepath)
        )
        return {'CANCELLED'}

    global performance_monitor
    performance_monitor = PerformanceMonitor('BSP Import')
    performance_monitor.push_scope()
    performance_monitor.step(f'Start importing {filepath}')
    performance_monitor.push_scope()

    performance_monitor.step('Loading bsp file...')

    bsp = Bsp.open(filepath)
    bsp.close()

    map_name = os.path.basename(filepath)
    root_collection = bpy.data.collections.new(map_name)
    bpy.context.scene.collection.children.link(root_collection)

    brush_collection = bpy.data.collections.new('brush entities')
    root_collection.children.link(brush_collection)

    entity_collection = bpy.data.collections.new('point entities')
    root_collection.children.link(entity_collection)

    subcollections = {}
    def get_subcollection(parent_collection, name):
        prefix = name.split('_')[0]

        try:
            return subcollections[parent_collection.name][prefix]

        except KeyError:
            subcollection = bpy.data.collections.new(prefix)
            parent_collection.children.link(subcollection)

            if parent_collection.name not in subcollections:
                subcollections[parent_collection.name] = {}

            subcollections[parent_collection.name][prefix] = subcollection

            return subcollection

    performance_monitor.step('Creating images...')

    # Create images
    for i, image in enumerate(bsp.images()):
        miptex = bsp.miptextures[i]

        if miptex:
            api.create_image(miptex.name, image)

    performance_monitor.step('Creating materials...')

    # Create materials
    for i, image in enumerate(bsp.images()):
        miptex = bsp.miptextures[i]

        if miptex:
            api.create_material(miptex.name, bpy.data.images[miptex.name])

    global_matrix = Matrix.Scale(global_scale, 4)

    entities = []

    # Create point entities
    if use_point_entities:

        performance_monitor.step('Creating point entities...')
        entities = Map.loads(bsp.entities)

        for entity in [_ for _ in entities if hasattr(_, 'origin')]:
            vec = tuple(map(float, entity.origin.split(' ')))
            ob = bpy.data.objects.new(entity.classname + '.000', None)
            ob.location = Vector(vec) * global_scale
            ob.empty_display_size = 16 * global_scale
            ob.empty_display_type = 'CUBE'

            entity_subcollection = get_subcollection(entity_collection, entity.classname)
            entity_subcollection.objects.link(ob)
            ob.select_set(True)

    performance_monitor.step('Creating brush entities...')

    if use_brush_entities and not entities:
        entities = Map.loads(bsp.entities)

    brush_entities = {int(m.model.strip('*')):m.classname for m in entities if hasattr(m, 'model') and m.model.startswith('*')}

    for model_index, model in enumerate(bsp.models):
        # Worldspawn is always mesh 0
        if model_index == 0 and not use_worldspawn_entity:
            continue

        # Brush entities are the remaining meshes
        if model_index > 0 and not use_brush_entities:
            break

        if model_index == 0:
            name = 'worldspawn'

        else:
            name = brush_entities.get(model_index)

            if not name:
                name = f'brush.{model_index:0{len(str(len(bsp.models)))}}'

        ob = api.create_mesh_object(name, bsp, model, global_matrix)
        entity_subcollection = get_subcollection(brush_collection, ob.name)
        entity_subcollection.objects.link(ob)
        ob.select_set(True)

    performance_monitor.pop_scope()
    performance_monitor.pop_scope('Import finished.')

    return {'FINISHED'}
