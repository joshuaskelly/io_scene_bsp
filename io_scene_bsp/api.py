from functools import lru_cache

from .utils import dot


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
