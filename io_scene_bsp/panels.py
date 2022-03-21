import bpy


class BSP_PT_import_include(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Include"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == 'IMPORT_SCENE_OT_bsp'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        sublayout = layout.column(heading="Entities")
        sublayout.prop(operator, 'use_worldspawn_entity', text='Worldspawn')
        sublayout.prop(operator, 'use_brush_entities', text='Brush')
        sublayout.prop(operator, 'use_point_entities', text='Point')

        layout.prop(operator, 'load_lightmap', text='Lightmaps')


class BSP_PT_import_transform(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Transform"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == 'IMPORT_SCENE_OT_bsp'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, 'global_scale')


def register():
    bpy.utils.register_class(BSP_PT_import_include)
    bpy.utils.register_class(BSP_PT_import_transform)


def unregister():
    bpy.utils.unregister_class(BSP_PT_import_include)
    bpy.utils.unregister_class(BSP_PT_import_transform)
