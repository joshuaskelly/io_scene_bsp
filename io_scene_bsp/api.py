from functools import lru_cache

from vgio.quake.bsp import Bsp as BspFile
from vgio.quake.bsp import is_bspfile
from vgio.quake import map as Map

from .utils import dot


class Face:
    def __init__(self, bsp, face):
        self._bsp_file = bsp
        self._face = face

    @property
    @lru_cache(maxsize=1)
    def edges(self):
        return self._bsp_file.surf_edges[self._face.first_edge:self._face.first_edge + self._face.number_of_edges]

    @property
    @lru_cache(maxsize=1)
    def vertices(self):
        verts = []
        for edge in self.edges:
            v = self._bsp_file.edges[abs(edge)].vertexes

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
        return tuple(tuple(self._bsp_file.vertexes[i][:]) for i in reversed(verts))

    @property
    @lru_cache(maxsize=1)
    def uvs(self):
        texture_info = self._bsp_file.texture_infos[self._face.texture_info]
        miptex = self._bsp_file.miptextures[texture_info.miptexture_number]
        s, t = texture_info.s, texture_info.t
        ds, dt = texture_info.s_offset, texture_info.t_offset
        w, h = miptex.width, miptex.height

        return tuple(((dot(v, s) + ds) / w, -(dot(v, t) + dt) / h) for v in self.vertices)

    @property
    @lru_cache(maxsize=1)
    def texture_name(self):
        texture_info = self._bsp_file.texture_infos[self._face.texture_info]
        miptex = self._bsp_file.miptextures[texture_info.miptexture_number]

        return miptex.name


class Model:
    def __init__(self, bsp, model):
        self._bsp_file = bsp
        self._model = model
        self._faces = bsp.faces[model.first_face:model.first_face + model.number_of_faces]

    def get_face(self, face_index):
        return Face(self._bsp_file, self._faces[face_index])

    @property
    def faces(self):
        for face in self._faces:
            if face:
                yield Face(self._bsp_file, face)


class Bsp:
    def __init__(self, file):
        self._bsp_file = BspFile.open(file)
        self._bsp_file.close()

    def get_model(self, model_index):
        return Model(self._bsp_file, self._bsp_file.models[model_index])

    @property
    def models(self):
        for model in self._bsp_file.models:
            yield Model(self._bsp_file, model)

    @property
    def images(self):
        return self._bsp_file.images()

    @property
    def miptextures(self):
        return self._bsp_file.miptextures[:]

    @property
    @lru_cache(maxsize=1)
    def entities(self):
        return Map.loads(self._bsp_file.entities)
