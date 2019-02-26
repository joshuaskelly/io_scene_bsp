if 'bpy' in locals():
    import importlib as il
    il.reload(perfmon)
    il.reload(nodes)
    il.reload(utils)

else:
    from . import perfmon
    from . import nodes
    from . import utils

import os

import bpy
import bmesh
from mathutils import Matrix, Vector

from vgio.quake.bsp import Bsp, is_bspfile
from vgio.quake import map as Map

from .perfmon import PerformanceMonitor
from .utils import datablock_lookup, dot


@datablock_lookup('images')
def _create_image(name, image_data):
    if image_data is None:
        image = bpy.data.images.new(f'{name}(Missing)', 0, 0)

    else:
        image = bpy.data.images.new(name, image_data.width, image_data.height)
        pixels = list(map(lambda x: x / 255, image_data.pixels))
        image.pixels[:] = pixels
        image.update()

    return image


@datablock_lookup('materials')
def _create_material(name, image):
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


def _create_mesh_object(name, bsp, model, matrix):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    mesh_vertices = []
    mesh_uvs = []
    mesh_faces = []
    mesh_face_miptexes = []
    applied_materials = []

    # Process BSP Faces
    faces = bsp.faces[model.first_face:model.first_face + model.number_of_faces]
    for face in faces:
        texture_info = bsp.texture_infos[face.texture_info]
        miptex = bsp.miptextures[texture_info.miptexture_number]

        if not miptex:
            continue

        if miptex.name not in applied_materials:
            applied_materials.append(miptex.name)

        s = texture_info.s
        ds = texture_info.s_offset
        t = texture_info.t
        dt = texture_info.t_offset

        w = miptex.width
        h = miptex.height

        edges = bsp.surf_edges[face.first_edge:face.first_edge + face.number_of_edges]

        verts = []
        for edge in edges:
            v = bsp.edges[abs(edge)].vertexes

            # Flip edges with negative ids
            v0, v1 = v if edge > 0 else reversed(v)

            if len(verts) == 0:
                verts.append(v0)

            if v1 != verts[0]:
                verts.append(v1)

        # Ignore degenerate faces
        if len(verts) < 3:
            continue

        # Convert Vertexes to three-tuples and reverse their order
        verts = [tuple(bsp.vertexes[i][:]) for i in reversed(verts)]

        # Convert ST coordinate space to UV coordinate space
        uvs = [((dot(v, s) + ds) / w, -(dot(v, t) + dt) / h) for v in verts]

        # Determine indices of vertices added
        start_index = len(mesh_vertices)
        stop_index = start_index + len(verts)
        vert_indices = list(range(start_index, stop_index))

        mesh_vertices += verts
        mesh_uvs += uvs
        mesh_faces.append(vert_indices)
        mesh_face_miptexes.append(miptex.name)

    # Create Blender vertices
    for vertexes in mesh_vertices:
        v = bm.verts.new(vertexes)
        v.co = matrix @ v.co

    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.new()

    # Create Blender faces
    for face_index, face in enumerate(mesh_faces):
        bverts = [bm.verts[i] for i in face]

        try:
            bface = bm.faces.new(bverts)
            material_name = mesh_face_miptexes[face_index]
            bface.material_index = applied_materials.index(material_name)

            uvs = [mesh_uvs[i] for i in face]

            for uv, loop in zip(uvs, bface.loops):
                loop[uv_layer].uv = uv

        except Exception as e:
            print(e)

    bm.faces.ensure_lookup_table()
    bm.to_mesh(mesh)
    bm.free()

    ob = bpy.data.objects.new(name, mesh)

    for material_name in applied_materials:
        ob.data.materials.append(bpy.data.materials[material_name])

    return ob

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

        return parent_collection

    performance_monitor.step('Creating images...')

    # Create images
    for i, image in enumerate(bsp.images()):
        miptex = bsp.miptextures[i]

        if miptex:
            _create_image(miptex.name, image)

    performance_monitor.step('Creating materials...')

    # Create materials
    for i, image in enumerate(bsp.images()):
        miptex = bsp.miptextures[i]

        if miptex:
            _create_material(miptex.name, bpy.data.images[miptex.name])

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

        ob = _create_mesh_object(name, bsp, model, global_matrix)
        entity_subcollection = get_subcollection(brush_collection, ob.name)
        entity_subcollection.objects.link(ob)
        ob.select_set(True)

    performance_monitor.pop_scope()
    performance_monitor.pop_scope('Import finished.')

    return {'FINISHED'}
