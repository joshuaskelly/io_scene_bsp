if 'perfmon' in locals():
    import importlib as il
    il.reload(api)
    il.reload(nodes)
    il.reload(perfmon)
    il.reload(utils)
    # print('io_scene_bsp.import_bsp: reload ready.')

else:
    from . import api
    from . import nodes
    from . import perfmon
    from . import utils

import os

import bpy
import bmesh
from mathutils import Matrix, Vector

from .perfmon import PerformanceMonitor
from .utils import datablock_lookup

performance_monitor = None


@datablock_lookup('images')
def create_image(name, image_data):
    if image_data is None:
        image = bpy.data.images.new(f'{name}(Missing)', 0, 0)

    else:
        image = bpy.data.images.new(name, image_data.width, image_data.height)
        pixels = list(map(lambda x: x / 255, image_data.pixels))
        image.pixels[:] = pixels
        image.update()
        image.pack(as_png=True)

    return image


@datablock_lookup('materials')
def create_material(name, image):
    # Create new material
    material = bpy.data.materials.new(name)
    material.diffuse_color = 1, 1, 1, 1
    material.specular_intensity = 0
    material.use_nodes = True

    # Remove default Principled BSDF shader
    default_node = material.node_tree.nodes.get('Principled BSDF')
    material.node_tree.nodes.remove(default_node)

    # Create an image texture node
    texture_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    texture_node.name = 'Miptexture'
    texture_node.image = image
    texture_node.interpolation = 'Closest'
    texture_node.location = 0, 0

    # Create a bsdf node
    bsdf_node = material.node_tree.nodes.new('ShaderNodeGroup')

    if name.startswith('sky') or name.startswith('*'):
        bsdf_node.node_tree = nodes.unlit_bsdf()

    elif name.startswith('{'):
        bsdf_node.node_tree = nodes.unlit_alpha_mask_bsdf()
        material.blend_method = 'CLIP'

    else:
        bsdf_node.node_tree = nodes.lightmapped_bsdf()

    bsdf_node.location = 300, 0
    material.node_tree.links.new(texture_node.outputs[0], bsdf_node.inputs[0])

    output_node = material.node_tree.nodes.get('Material Output')
    output_node.location = 500, 0
    material.node_tree.links.new(bsdf_node.outputs[0], output_node.inputs[0])

    return material


def load(operator,
         context,
         filepath='',
         global_scale=1.0,
         use_worldspawn_entity=True,
         use_brush_entities=True,
         use_point_entities=True):

    if not api.is_bspfile(filepath):
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

    bsp = api.Bsp(filepath)

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
    for i, image in enumerate(bsp.images):
        miptex = bsp.miptextures[i]

        if miptex:
            create_image(miptex.name, image)

    performance_monitor.step('Creating materials...')

    # Create materials
    for i, image in enumerate(bsp.images):
        miptex = bsp.miptextures[i]

        if miptex:
            create_material(miptex.name, bpy.data.images[miptex.name])

    global_matrix = Matrix.Scale(global_scale, 4)

    # Create point entities
    if use_point_entities:
        performance_monitor.step('Creating point entities...')

        for entity in [_ for _ in bsp.entities if hasattr(_, 'origin')]:
            vec = tuple(map(float, entity.origin.split(' ')))
            ob = bpy.data.objects.new(entity.classname + '.000', None)
            ob.location = Vector(vec) * global_scale
            ob.empty_display_size = 16 * global_scale
            ob.empty_display_type = 'CUBE'

            entity_subcollection = get_subcollection(entity_collection, entity.classname)
            entity_subcollection.objects.link(ob)
            ob.select_set(True)

    performance_monitor.step('Creating brush entities...')

    brush_entities = {int(m.model.strip('*')): m.classname for m in bsp.entities if hasattr(m, 'model') and m.model.startswith('*')}
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
