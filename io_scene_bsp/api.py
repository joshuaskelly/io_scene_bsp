if 'bpy' in locals():
    import importlib as il
    il.reload(nodes)
    il.reload(utils)
    il.reload(api)

else:
    from . import nodes
    from . import utils
    from . import api


from functools import lru_cache

import bpy
import bmesh

from .utils import datablock_lookup, dot


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


class Face:
    def __init__(self, bsp, face):
        self._bsp = bsp
        self._face = face

    @property
    @lru_cache(maxsize=1)
    def edges(self):
        return self._bsp.surf_edges[self._face.first_edge:self._face.first_edge + self._face.number_of_edges]

    @property
    @lru_cache(maxsize=1)
    def vertices(self):
        verts = []
        for edge in self.edges:
            v = self._bsp.edges[abs(edge)].vertexes

            # Flip edges with negative ids
            v0, v1 = v if edge > 0 else reversed(v)

            if len(verts) == 0:
                verts.append(v0)

            if v1 != verts[0]:
                verts.append(v1)

        # Ignore degenerate faces
        if len(verts) < 3:
            return None

        # Convert Vertexes to three-tuples and reverse their order
        return tuple(tuple(self._bsp.vertexes[i][:]) for i in reversed(verts))

    @property
    @lru_cache(maxsize=1)
    def uvs(self):
        texture_info = self._bsp.texture_infos[self._face.texture_info]
        miptex = self._bsp.miptextures[texture_info.miptexture_number]
        s, t = texture_info.s, texture_info.t
        ds, dt = texture_info.s_offset, texture_info.t_offset
        w, h = miptex.width, miptex.height

        return tuple(((dot(v, s) + ds) / w, -(dot(v, t) + dt) / h) for v in self.vertices)

    @property
    @lru_cache(maxsize=1)
    def texture_name(self):
        texture_info = self._bsp.texture_infos[self._face.texture_info]
        miptex = self._bsp.miptextures[texture_info.miptexture_number]

        return miptex.name


class Model:
    def __init__(self, bsp, model):
        self._bsp = bsp
        self._model = model
        self._faces = bsp.faces[model.first_face:model.first_face + model.number_of_faces]

    def get_face(self, face_index):
        return Face(self._bsp, self._faces[face_index])

    @property
    def faces(self):
        for face in self._faces:
            if face:
                yield Face(self._bsp, face)


class Bsp:
    def __init__(self, bsp):
        self._bsp = bsp

    def get_model(self, model_index):
        return Model(self._bsp, self._bsp.models[model_index])

    @property
    def models(self):
        for model in self._bsp.models:
            yield Model(self._bsp, model)
