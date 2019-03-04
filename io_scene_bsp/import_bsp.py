if 'perfmon' in locals():
    import importlib as il
    il.reload(perfmon)
    il.reload(api)
    print('io_scene_bsp.import_bsp: reload ready.')

else:
    from . import perfmon
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

    bsp_file = Bsp.open(filepath)
    bsp_file.close()
    bsp = api.Bsp(bsp_file)

    map_name = os.path.basename(filepath)

    root_collection = bpy.data.collections.new(map_name)
    bpy.context.scene.collection.children.link(root_collection)

    if use_worldspawn_entity or use_brush_entities:
        brush_collection = bpy.data.collections.new('brush entities')
        root_collection.children.link(brush_collection)

    if use_point_entities:
        entity_collection = bpy.data.collections.new('point entities')
        root_collection.children.link(entity_collection)

    subcollections = {}

    def get_subcollection(parent_collection, name):
        """Helper method for creating collections based on name.

        Args:
            parent_collection: The collection to parent the new collection to.

            name: The entity name to use to determine the new collection name.

        Returns:
            A collection
        """
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
    for i, image in enumerate(bsp_file.images()):
        miptex = bsp_file.miptextures[i]

        if miptex:
            api.create_image(miptex.name, image)

    performance_monitor.step('Creating materials...')

    # Create materials
    for i, image in enumerate(bsp_file.images()):
        miptex = bsp_file.miptextures[i]

        if miptex:
            api.create_material(miptex.name, bpy.data.images[miptex.name])

    global_matrix = Matrix.Scale(global_scale, 4)
    entities = []

    # Create point entities
    if use_point_entities:
        performance_monitor.step('Creating point entities...')
        entities = Map.loads(bsp_file.entities)

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
        entities = Map.loads(bsp_file.entities)

    brush_entities = {int(m.model.strip('*')):m.classname for m in entities if hasattr(m, 'model') and m.model.startswith('*')}
    brush_entities[0] = 'worldspawn'

    # Create mesh objects
    for model_index, model in enumerate(bsp.models):
        if model_index == 0 and not use_worldspawn_entity:
            continue

        if model_index > 0 and not use_brush_entities:
            break

        name = brush_entities.get(model_index) or 'brush'
        ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        bm = bmesh.new()
        uv_layer = bm.loops.layers.uv.new()

        def process_vertices(vertices):
            """Helper function to create Blender vertices from a sequence of
            tuples.

            Args:
                vertices: A sequence of three-tuples

            Returns:
                A sequence of Blender vertices
            """
            result = []
            for vertex in vertices:
                bv = bm.verts.new(vertex)
                bv.co = global_matrix @ bv.co
                result.append(bv)

            return result

        def get_material_index(name):
            """Get the material slot index of the given material name. If the
            material is not currently assigned to the mesh, it will be added.

            Args:
                name: The name of the material

            Returns:
                The index of the material in the object's material slots
            """
            material = ob.data.materials.get(name)
            if not material:
                ob.data.materials.append(bpy.data.materials[name])
                material = ob.data.materials.get(name)

            return ob.data.materials[:].index(material)

        for face in model.faces:
            if not face.vertices:
                continue

            bface = bm.faces.new(process_vertices(face.vertices))
            bface.material_index = get_material_index(face.texture_name)

            for uv, loop in zip(face.uvs, bface.loops):
                loop[uv_layer].uv = uv

        bm.faces.ensure_lookup_table()
        bm.to_mesh(ob.data)
        bm.free()

        entity_subcollection = get_subcollection(brush_collection, ob.name)
        entity_subcollection.objects.link(ob)
        ob.select_set(True)

    performance_monitor.pop_scope()
    performance_monitor.pop_scope('Import finished.')

    return {'FINISHED'}
