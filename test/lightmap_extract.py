import os
import sys
from math import ceil, floor
from typing import List, NamedTuple, Tuple

from PIL import Image

import numpy
from numpy import ndarray

import block_packer

from vgio.quake.bsp import Bsp as BspFile
from vgio.quake.bsp import is_bspfile
from vgio.quake.bsp.bsp29 import (
    Edge,
    Face,
    Model,
    Vertex, Bsp
)

Edges = List[Edge]
Faces = List[Face]
Models = List[Model]
Vertexes = List[Vertex]
Indexes = List[int]

LightInfo = NamedTuple("LightInfo", size=Tuple[int, int], offset=int)


def error(message: str):
    print(f'CLI: {message}', file=sys.stderr)
    sys.exit(-1)


def get_lightmap_array(bsp_file: Bsp) -> ndarray:
    lightmap = numpy.frombuffer(bsp_file.lighting, numpy.uint8)

    faces: Faces = [face for face in bsp_file.faces]

    def get_light_info(face: Face) -> LightInfo:
        """Returns a LightInfo object for the give face."""

        # Get all vertexes unordered
        surf_edges: Indexes = bsp_file.surf_edges[
                              face.first_edge:face.first_edge + face.number_of_edges]
        edges: Edges = [bsp_file.edges[abs(i)] for i in surf_edges]
        vertexes: List[ndarray] = [numpy.array(bsp_file.vertexes[vertex][:])
                                   for edge in edges for vertex in
                                   edge.vertexes]

        # Project vertexes to 2D plane
        plane = bsp_file.planes[face.plane_number]
        index = plane.type % 3
        sts = numpy.delete(vertexes, index, axis=1)

        # Reduce resolution. One lightmap texel is 16x16 pixels.
        sts = sts / 16

        # Determine mins and maxs
        min_s = min([s for s, t in sts])
        max_s = max([s for s, t in sts])
        min_t = min([t for s, t in sts])
        max_t = max([t for s, t in sts])

        # Return light info object
        size = ceil(max_s - min_s) + 1, floor(max_t - min_t) + 1
        offset = face.light_offset

        return LightInfo(size, offset)

    light_infos: List[LightInfo] = [get_light_info(face) for face in faces]

    packer = block_packer

    size, offsets = packer.pack(light_infos)

    pixels = numpy.zeros(size)

    def blit(light_info: LightInfo, offset: Tuple[int, int]):
        start = light_info.offset
        end = start + light_info.size[0] * light_info.size[1]

        if start == -1:
            return

        x, y = offset
        w, h = light_info.size
        shape = light_info.size[1], light_info.size[0]

        pixels[y: y + h, x: x + w] = numpy.reshape(lightmap[start: end], shape)

    for l, o in zip(light_infos, offsets):
        if o is None:
            continue

        blit(l, o)

    return pixels


def extract(source_path, out_path):
    # Verify source data
    if not os.path.exists(source_path):
        error(f'cannot find {source_path}')

    if not is_bspfile(source_path):
        error(f'{source_path} is not a bsp file')

    # Get bsp object
    bsp_file = BspFile.open(source_path)
    bsp_file.close()

    if not bsp_file.lighting:
        error('no light map data')

    pixels = get_lightmap_array(bsp_file)

    im = Image.fromarray(pixels)
    im.convert('RGB').save(out_path)
