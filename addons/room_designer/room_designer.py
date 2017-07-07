import bpy
import bmesh
import math
import os
from . import unit, utils
from .assembly import Assembly
from bpy_extras import view3d_utils
from .opengl import TextBox

DEFAULT_ROOM_HEIGHT = unit.inch(108)
DEFAULT_WALL_DEPTH = unit.inch(6)
WALL_NAME = "Wall"

preview_collections = {} 

def get_roombuilder_props(context):
    """ 
    returns the room builder scene props
    
    **Parameters:**
    
    * **context** (bpy.context)
    
    **Returns:** bpy.context.scene.room_builder
    """    
    return context.scene.room_builder

def create_image_preview_collection():
    """ 
    creates image preview collection used for images

    **Returns:** bpy.utils.previews.ImagePreviewCollection
    """      
    import bpy.utils.previews #I'm not sure why i have to import this here
    col = bpy.utils.previews.new()
    col.my_previews_dir = ""
    col.my_previews = ()
    return col

def get_image_enum_previews(path,key,force_reload=False):
    """ 
    retrieves images from a path to store in an image preview
    collection

    **Parameters:**
    
    * **path** (string) - The path to collect the images from
    * **key** (string) - The dictionary key the previews will be stored in
    * **force_reload** (boolean, (optional)) - If True, force running 
        thumbnail manager even if preview already exists in cache.

    **Returns:** bpy.utils.previews.ImagePreviewCollection
    """
    
    enum_items = []
    if len(key.my_previews) > 0:
        return key.my_previews
    
    if path and os.path.exists(path):
        image_paths = []
        for fn in os.listdir(path):
            if fn.lower().endswith(".png"):
                image_paths.append(fn)

        for i, name in enumerate(image_paths):
            filepath = os.path.join(path, name)
            thumb = key.load(filepath, filepath, 'IMAGE',force_reload)
            filename, ext = os.path.splitext(name)
            enum_items.append((filename, filename, filename, thumb.icon_id, i))
    
    key.my_previews = enum_items
    key.my_previews_dir = path
    return key.my_previews

def get_folder_enum_previews(path,key):
    """ 
    retrieves folders from a path to store in an image preview
    collection

    **Parameters:**
    
    * **path** (string) - The path to collect the folders from
    * **key** (string) - The dictionary key the previews will be stored in

    **Returns:** bpy.utils.previews.ImagePreviewCollection
    """
    enum_items = []
    if len(key.my_previews) > 0:
        return key.my_previews
    
    if path and os.path.exists(path):
        folders = []
        for fn in os.listdir(path):
            if os.path.isdir(os.path.join(path,fn)):
                folders.append(fn)

        for i, name in enumerate(folders):
            filepath = os.path.join(path, name)
            thumb = key.load(filepath, "", 'IMAGE')
            filename, ext = os.path.splitext(name)
            enum_items.append((filename, filename, filename, thumb.icon_id, i))
    
    key.my_previews = enum_items
    key.my_previews_dir = path
    return key.my_previews


preview_collections["floor_material_categories"] = create_image_preview_collection()   
preview_collections["floor_materials"] = create_image_preview_collection()   
 
def enum_flooring_categories(self,context):
    if context is None:
        return []
     
    icon_dir = os.path.join(os.path.dirname(__file__),"assets","Floor Materials")
    pcoll = preview_collections["floor_material_categories"]
    return get_folder_enum_previews(icon_dir,pcoll)
 
def enum_flooring(self,context):
    if context is None:
        return []

    icon_dir = os.path.join(os.path.dirname(__file__),"assets","Floor Materials",self.flooring_category)
    pcoll = preview_collections["floor_materials"]
    return get_image_enum_previews(icon_dir,pcoll)
 
def update_floring_category(self,context):
    if preview_collections["floor_materials"]:
        bpy.utils.previews.remove(preview_collections["floor_materials"])
        preview_collections["floor_materials"] = create_image_preview_collection()     
         
    enum_flooring(self,context)

def get_selection_point(context, event, ray_max=10000.0,objects=None,floor=None):
    """Gets the point to place an object based on selection"""
    # get the context arguments
    scene = context.scene
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y
 
    # get the ray from the viewport and mouse
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    ray_target = ray_origin + view_vector
 
    def visible_objects_and_duplis():
        """Loop over (object, matrix) pairs (mesh only)"""
 
        for obj in context.visible_objects:
             
            if objects:
                if obj in objects:
                    yield (obj, obj.matrix_world.copy())
             
            else:
                if floor is not None and obj == floor:
                    yield (obj, obj.matrix_world.copy())
                     
                if obj.draw_type != 'WIRE':
                    if obj.type == 'MESH':
                        if obj.mv.type not in {'BPASSEMBLY','BPWALL'}:
                            yield (obj, obj.matrix_world.copy())
         
                    if obj.dupli_type != 'NONE':
                        obj.dupli_list_create(scene)
                        for dob in obj.dupli_list:
                            obj_dupli = dob.object
                            if obj_dupli.type == 'MESH':
                                yield (obj_dupli, dob.matrix.copy())
 
            obj.dupli_list_clear()
 
    def obj_ray_cast(obj, matrix):
        """Wrapper for ray casting that moves the ray into object space"""
        try:
            # get the ray relative to the object
            matrix_inv = matrix.inverted()
            ray_origin_obj = matrix_inv * ray_origin
            ray_target_obj = matrix_inv * ray_target
            ray_direction_obj = ray_target_obj - ray_origin_obj
     
            # cast the ray
            success, location, normal, face_index = obj.ray_cast(ray_origin_obj, ray_direction_obj)
     
            if success:
                return location, normal, face_index
            else:
                return None, None, None
        except:
            print("ERROR IN obj_ray_cast",obj)
            return None, None, None
             
    best_length_squared = ray_max * ray_max
    best_obj = None
    best_hit = scene.cursor_location
    for obj, matrix in visible_objects_and_duplis():
        if obj.type == 'MESH':
            if obj.data:
                hit, normal, face_index = obj_ray_cast(obj, matrix)
                if hit is not None:
                    hit_world = matrix * hit
                    length_squared = (hit_world - ray_origin).length_squared
                    if length_squared < best_length_squared:
                        best_hit = hit_world
                        best_length_squared = length_squared
                        best_obj = obj
                        
    return best_hit, best_obj    
    
class PROPS_Room_Builder(bpy.types.PropertyGroup):
    
    wall_height = bpy.props.FloatProperty(name="Wall Height",default=unit.inch(108),unit='LENGTH')
    wall_depth = bpy.props.FloatProperty(name="Wall Depth",default=unit.inch(6),unit='LENGTH')
    
    show_wall_dimensions = bpy.props.BoolProperty(name="Show Dimensions",default=True)
    
    room_builder_tabs = bpy.props.EnumProperty(name="Room Builder Tabs",
        items=[('MAIN',"Main Options","Displays the Main Room Builder Options"),
               ('PROPS',"Properties","Products"),
               ('2D',"2D Views","Inserts")],
        default='MAIN')
    
    show_wall_names = bpy.props.BoolProperty(name="Show Names",default=True)
    show_wall_obj_bp = bpy.props.BoolProperty(name="Show Wall BP Object",default=False)
    show_wall_obj_x = bpy.props.BoolProperty(name="Show Wall X Object",default=False)
    show_wall_obj_y = bpy.props.BoolProperty(name="Show Wall Y Object",default=False)
    show_wall_obj_z = bpy.props.BoolProperty(name="Show Wall Z Object",default=False)
    
    test_object = bpy.props.PointerProperty(name="Wall Depth",type=bpy.types.Object)
    
    show_expanded_material = bpy.props.BoolProperty(name="Show Expanded Material",default=False)
    
    flooring_category = bpy.props.EnumProperty(name="Flooring Category",
                                               items=enum_flooring_categories,
                                               update=update_floring_category)
     
    flooring_material = bpy.props.EnumProperty(name="Flooring Material",
                                               items=enum_flooring)    
    
class PANEL_Room_Builder_Library(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "objectmode"
    bl_label = "Room Builder"
    bl_category = "Design Tools"
    
    def draw_main_options(self,context,layout,rm_props):
        box = layout.box()
        row = box.row(align=True)
        row.label("Draw Walls:",icon='MOD_BUILD')      
        row = box.row(align=True)  
        row.prop(rm_props,"wall_height",text="Wall Height")
        row.prop(rm_props,"wall_depth",text="Wall Depth") 
        row = box.row()    
        row.scale_y = 1.2   
        row.operator("room_builder.draw_wall",text="Draw Walls",icon='GREASEPENCIL')     

        row = box.row(align=True)
        row.label("Draw Shapes:",icon='MESH_GRID')     
        row = box.row()    
        row.scale_y = 1.2   
        row.operator("room_builder.draw_cube",text="Draw Plane",icon='MESH_PLANE') #TODO
        row.operator("room_builder.draw_cube",text="Draw Cube",icon='MESH_CUBE')

        box = layout.box()
        row = box.row()
        row.label("Place Windows and Doors:",icon='MESH_CUBE')
        row.label("Press W")
        row = box.row(align=True)
        row.prop(rm_props,"show_expanded_material",text="",emboss=False,icon='TRIA_DOWN' if rm_props.show_expanded_material else 'TRIA_RIGHT')
        row.separator()
        row.prop(rm_props,'flooring_category',text="",icon='FILE_FOLDER')        
        row.prop(rm_props,'flooring_material',text="")    
        row.operator('object.lamp_add',text="",icon='FILE_REFRESH')
        row.operator('object.lamp_add',text="",icon='BRUSH_DATA')
        if rm_props.show_expanded_material:
            box.template_icon_view(rm_props,"flooring_material",show_labels=True)  

        box = layout.box()
        row = box.row()
        row.label("Place Furniture:",icon='MESH_CUBE')
        row = box.row(align=True)
        row.prop(rm_props,"show_expanded_material",text="",emboss=False,icon='TRIA_DOWN' if rm_props.show_expanded_material else 'TRIA_RIGHT')
        row.separator()
        row.prop(rm_props,'flooring_category',text="",icon='FILE_FOLDER')        
        row.prop(rm_props,'flooring_material',text="")    
        row.operator('object.lamp_add',text="",icon='FILE_REFRESH')
        row.operator('object.lamp_add',text="",icon='BRUSH_DATA')
        if rm_props.show_expanded_material:
            box.template_icon_view(rm_props,"flooring_material",show_labels=True)  

        box = layout.box()
        row = box.row()
        row.label("Room Materials:",icon='MATERIAL_DATA')
        row = box.row(align=True)
        row.prop(rm_props,"show_expanded_material",text="",emboss=False,icon='TRIA_DOWN' if rm_props.show_expanded_material else 'TRIA_RIGHT')
        row.separator()        
        row.prop(rm_props,'flooring_category',text="",icon='FILE_FOLDER')        
        row.prop(rm_props,'flooring_material',text="")    
        row.operator('object.lamp_add',text="",icon='FILE_REFRESH')
        row.operator('object.lamp_add',text="",icon='BRUSH_DATA')
        if rm_props.show_expanded_material:
            box.template_icon_view(rm_props,"flooring_material",show_labels=True)
            
        box = layout.box()
        box.label("Room Lighting:",icon='OUTLINER_OB_LAMP')
        row = box.row()
        row.scale_y = 1.2
        row.operator('object.lamp_add',text="Place Spot Lamp",icon='LAMP_SPOT').type = 'AREA'
        row.operator('object.lamp_add',text="Place Area Lamp",icon='LAMP_AREA').type = 'AREA'
    
    def draw_props(self,context,layout,rm_props):
        box = layout.box()
        row = box.row()
        row.label("Wall Options:",icon='MOD_BUILD')
        row = box.row(align=True)

        row = box.row(align=True)
        row.operator('object.lamp_add',text="Show Selected Wall Properties",icon='SETTINGS').type = 'AREA'
    
        box = layout.box()
        row = box.row()
        row.label("Display Settings:",icon='RESTRICT_VIEW_OFF')
        row = box.row()
        row.prop(rm_props,"show_wall_dimensions")
        row.prop(rm_props,"show_wall_names")
        split = box.split()
        row = split.row()
        row.label("Show Handles:")
        row = split.row()
        row.prop(rm_props,"show_wall_obj_x",text="X")
        row.prop(rm_props,"show_wall_obj_y",text="Y")
        row.prop(rm_props,"show_wall_obj_z",text="Z")
    
    def draw(self, context):
        layout = self.layout
        rm_props = get_roombuilder_props(context)
        
        main_box = layout.box()
        row = main_box.row(align=True)
        row.prop_enum(rm_props, "room_builder_tabs", 'MAIN', icon='INFO', text="Main") 
        row.prop_enum(rm_props, "room_builder_tabs", 'PROPS', icon='RESTRICT_VIEW_OFF', text="Properties") 
        row.prop_enum(rm_props, "room_builder_tabs", '2D', icon='MATERIAL', text="2D Views")         

        col = main_box.column(align=True)
        
        if rm_props.room_builder_tabs == 'MAIN':
            self.draw_main_options(context, col, rm_props)
        if rm_props.room_builder_tabs == 'PROPS':
            self.draw_props(context,col,rm_props)
        if rm_props.room_builder_tabs == '2D':
            pass

        
class OPS_draw_walls(bpy.types.Operator):
    bl_idname = "room_builder.draw_wall"
    bl_label = "Draws Walls"
    bl_options = {'UNDO'}
    
    #READONLY
    drawing_plane = None
    wall = None
    previous_wall = None
    is_disconnected = False
    mouse_x = 0
    mouse_y = 0    
    
    typed_value = ""
    
    starting_point = (0,0,0)
    header_text = "(Esc, Right Click) = Cancel Command  :  (Left Click) = Place Wall  :  (Ctrl) = Disconnect/Move Wall"
    
    state =""
    
    cursor_help_text = ""
    
    ray_obj_list = []
    
    def cancel_drop(self,context,event):
        utils.delete_object_and_children(self.wall.obj_bp)
        context.window.cursor_set('DEFAULT')
        utils.delete_obj_list([self.drawing_plane])
        context.space_data.draw_handler_remove(self._draw_handle, 'WINDOW')
        return {'FINISHED'}
        
    def __del__(self):
        bpy.context.area.header_text_set()
        
    def create_wall(self):
        self.wall = Assembly()
        self.wall.create_assembly()
        obj_mesh = self.wall.add_mesh("wall")
        self.wall.obj_bp.location = self.starting_point
        obj_mesh.draw_type = 'WIRE'
        self.wall.obj_z.location.z = DEFAULT_ROOM_HEIGHT
        self.wall.obj_y.location.y = DEFAULT_WALL_DEPTH
        if self.previous_wall:
            constraint = self.wall.obj_bp.constraints.new('COPY_LOCATION')
            constraint.target = self.previous_wall.obj_x
            constraint.use_x = True
            constraint.use_y = True
            constraint.use_z = True

    def position_wall_base_point(self,p):
        x = p[0] - self.starting_point[0]
        y = p[1] - self.starting_point[1]
        self.wall.obj_bp.location.x = x
        self.wall.obj_bp.location.y = y
        self.wall.obj_y.location.y = 0   
        self.wall.obj_z.location.z = 0    
        
    def position_wall_length(self,p):
        x = p[0] - self.starting_point[0]
        y = p[1] - self.starting_point[1]
        
        self.wall.obj_z.location.z = DEFAULT_ROOM_HEIGHT
        self.wall.obj_y.location.y = DEFAULT_WALL_DEPTH
        for child in self.wall.obj_bp.children:
            child.draw_type = 'WIRE'  
                    
        if math.fabs(x) > math.fabs(y):
            if x > 0:
                self.wall.obj_bp.rotation_euler.z = math.radians(0)
            else:
                self.wall.obj_bp.rotation_euler.z = math.radians(180)
            if self.typed_value == "":
                self.wall.obj_x.location.x = math.fabs(x)
            else:
                value = eval(self.typed_value)
                if bpy.context.scene.unit_settings.system == 'METRIC':
                    self.wall.obj_x.location.x = unit.millimeter(float(value))
                else:
                    self.wall.obj_x.location.x = unit.inch(float(value))
            
        if math.fabs(y) > math.fabs(x):
            if y > 0:
                self.wall.obj_bp.rotation_euler.z = math.radians(90)
            else:
                self.wall.obj_bp.rotation_euler.z = math.radians(-90)
            if self.typed_value == "":
                self.wall.obj_x.location.x = math.fabs(y)
            else:
                value = eval(self.typed_value)
                if bpy.context.scene.unit_settings.system == 'METRIC':
                    self.wall.obj_x.location.x = unit.millimeter(float(value))
                else:
                    self.wall.obj_x.location.x = unit.inch(float(value))

    def set_type_value(self,event):
        if event.value == 'PRESS':
            if event.type == "ONE" or event.type == "NUMPAD_1":
                self.typed_value += "1"
            if event.type == "TWO" or event.type == "NUMPAD_2":
                self.typed_value += "2"
            if event.type == "THREE" or event.type == "NUMPAD_3":
                self.typed_value += "3"
            if event.type == "FOUR" or event.type == "NUMPAD_4":
                self.typed_value += "4"
            if event.type == "FIVE" or event.type == "NUMPAD_5":
                self.typed_value += "5"
            if event.type == "SIX" or event.type == "NUMPAD_6":
                self.typed_value += "6"
            if event.type == "SEVEN" or event.type == "NUMPAD_7":
                self.typed_value += "7"
            if event.type == "EIGHT" or event.type == "NUMPAD_8":
                self.typed_value += "8"
            if event.type == "NINE" or event.type == "NUMPAD_9":
                self.typed_value += "9"
            if event.type == "ZERO" or event.type == "NUMPAD_0":
                self.typed_value += "0"
            if event.type == "PERIOD" or event.type == "NUMPAD_PERIOD":
                last_value = self.typed_value[-1:]
                if last_value != ".":
                    self.typed_value += "."
            if event.type == 'BACK_SPACE':
                if self.typed_value != "":
                    self.typed_value = self.typed_value[:-1]
            
    def place_first_wall(self):
        pass        
    
    def place_wall(self):
        if self.previous_wall:
            for child in self.wall.obj_bp.children:
                child.draw_type = 'TEXTURED'
                self.ray_obj_list.append(child)
            
        self.starting_point = (self.wall.obj_x.matrix_world[0][3], self.wall.obj_x.matrix_world[1][3], self.wall.obj_x.matrix_world[2][3])

        if self.previous_wall:
            self.previous_wall = self.wall
            self.create_wall()
        else:
            self.previous_wall = self.wall

        self.typed_value = ""
        self.is_disconnected = False
        
    def event_is_place_wall(self,event):
        if not event.ctrl:
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                return True
            elif event.type == 'NUMPAD_ENTER' and event.value == 'PRESS':
                return True
            elif event.type == 'RET' and event.value == 'PRESS':
                return True
            else:
                return False
        else:
            return False
        
    def event_is_cancel(self,event):
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            return True
        elif event.type == 'ESC' and event.value == 'PRESS':
            return True
        else:
            return False
        
    def get_wall_count(self):
        wall_number = 0
        for grp in bpy.data.groups:
            if grp.handy.type == "BPWALL":
                wall_number += 1
        return wall_number
            
    def modal(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        context.area.tag_redraw()
        selected_point, selected_obj = get_selection_point(context,event,objects=self.ray_obj_list) #Pass in Drawing Plane
        bpy.ops.object.select_all(action='DESELECT')

        if self.previous_wall:
            self.set_type_value(event)
            wall_length_text = str(unit.meter_to_active_unit(round(self.wall.obj_x.location.x,4)))
            wall_length_unit = '"' if context.scene.unit_settings.system == 'IMPERIAL' else 'mm'
            context.area.header_text_set(text=self.header_text + '   (Current Wall Length = ' + wall_length_text + wall_length_unit + ')')
            self.cursor_help_text = 'Left Click to Place Wall\nType Number to Set Length\nType A to change angle\n(Current Wall Length = ' + wall_length_text + wall_length_unit + ')'                  
            self.position_wall_length(selected_point)  
        else:
            self.cursor_help_text = "Left Click to Draw Walls"
            self.position_wall_base_point(selected_point)  

        if self.event_is_place_wall(event):
            self.place_wall()

        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
            
        if self.event_is_cancel(event):
            return self.cancel_drop(context,event)
            
        return {'RUNNING_MODAL'}
        
    def draw_menu(self,context):
        self.help_box.draw()
        self.help_box.raw_text = self.cursor_help_text
        self.help_box.fit_box_width_to_text_lines()
        self.help_box.x = self.mouse_x
        self.help_box.y = self.mouse_y
        
    def execute(self,context):
        context.window.cursor_set('PAINT_BRUSH')
        self._draw_handle = context.space_data.draw_handler_add(
            self.draw_menu, (context,), 'WINDOW', 'POST_PIXEL')        
        
        self.help_box = TextBox(500,500,300,200,10,20, "Select Point to Draw Wall")
        
        self.create_wall()
        
        bpy.ops.mesh.primitive_plane_add()
        plane = context.active_object
        plane.location = (0,0,0)
        self.drawing_plane = context.active_object
        self.drawing_plane.draw_type = 'WIRE'
        self.drawing_plane.dimensions = (100,100,1)
        
        self.ray_obj_list.append(self.drawing_plane)
        
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class OPS_draw_cube(bpy.types.Operator):
    bl_idname = "room_builder.draw_cube"
    bl_label = "Draw Cube"
    bl_options = {'UNDO'}
    
    #READONLY
    _draw_handle = None
    mouse_x = 0
    mouse_y = 0
    
    drawing_plane = None
    cube = None
    ray_cast_objects = []
    placed_first_point = False
    selected_point = (0,0,0)
    
    def cancel_drop(self,context):
        utils.delete_object_and_children(self.cube.obj_bp)
        self.finish(context)
        
    def finish(self,context):
        context.space_data.draw_handler_remove(self._draw_handle, 'WINDOW')
        context.window.cursor_set('DEFAULT')
        if self.drawing_plane:
            utils.delete_obj_list([self.drawing_plane])
        context.area.tag_redraw()
        return {'FINISHED'}

    @staticmethod
    def _window_region(context):
        window_regions = [region
                          for region in context.area.regions
                          if region.type == 'WINDOW']
        return window_regions[0]

    def draw_opengl(self,context):     
        region = self._window_region(context)
        
        help_box = TextBox(
            x=0,y=0,
            width=500,height=0,
            border=10,margin=100,
            message="Command Help:\nLEFT CLICK: Place Wall\nRIGHT CLICK: Cancel Command")
        help_box.x = (self.mouse_x + (help_box.width) / 2 + 10) - region.x
        help_box.y = (self.mouse_y - 10) - region.y

        help_box.draw()

    def event_is_place_first_point(self,event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.placed_first_point == False:
            return True
        elif event.type == 'NUMPAD_ENTER' and event.value == 'PRESS' and self.placed_first_point == False:
            return True
        elif event.type == 'RET' and event.value == 'PRESS' and self.placed_first_point == False:
            return True
        else:
            return False

    def event_is_place_second_point(self,event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self.placed_first_point:
            return True
        elif event.type == 'NUMPAD_ENTER' and event.value == 'PRESS' and self.placed_first_point:
            return True
        elif event.type == 'RET' and event.value == 'PRESS' and self.placed_first_point:
            return True
        else:
            return False

    def position_cube(self,selected_point):
        if not self.placed_first_point:
            self.cube.obj_bp.location = selected_point
            self.selected_point = selected_point
        else:
            print(selected_point)
            self.cube.x_dim(value = selected_point[0] - self.selected_point[0])
            self.cube.y_dim(value = selected_point[1] - self.selected_point[1])
            
    def modal(self, context, event):
        context.area.tag_redraw()
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        
        selected_point, selected_obj = utils.get_selection_point(context,event,objects=self.ray_cast_objects)
        
        self.position_cube(selected_point)

        if self.event_is_place_second_point(event):
            return self.finish(context)

        if self.event_is_place_first_point(event):
            self.placed_first_point = True

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_drop(context)
            return {'CANCELLED'}
        
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}        
        
        return {'RUNNING_MODAL'}
        
    def create_drawing_plane(self,context):
        bpy.ops.mesh.primitive_plane_add()
        plane = context.active_object
        plane.location = (0,0,0)
        self.drawing_plane = context.active_object
        self.drawing_plane.draw_type = 'WIRE'
        self.drawing_plane.dimensions = (100,100,1)
        self.ray_cast_objects.append(self.drawing_plane)

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self._draw_handle = context.space_data.draw_handler_add(
            self.draw_opengl, (context,), 'WINDOW', 'POST_PIXEL')
        self.placed_first_point = False
        self.selected_point = (0,0,0)
        
        self.create_drawing_plane(context)
        
        #CREATE CUBE
        self.cube = Assembly()
        self.cube.create_assembly()
        self.cube.add_mesh("Cube")
        self.cube.x_dim(value = 0)
        self.cube.y_dim(value = 0)
        self.cube.z_dim(value = 0)
        
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

class OPS_properties(bpy.types.Operator):
    bl_idname = "blender_design.properties"
    bl_label = "Properties"

    @classmethod
    def poll(cls, context):
        if context.object:
            return True
        else:
            return False

    def check(self,context):
        return True

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label("SHOW PROPERTIES")

def register():
    bpy.utils.register_class(PROPS_Room_Builder)
    bpy.utils.register_class(PANEL_Room_Builder_Library)
        
    bpy.utils.register_class(OPS_draw_walls)
    bpy.utils.register_class(OPS_draw_cube)
    bpy.utils.register_class(OPS_properties)

    bpy.types.Scene.room_builder = bpy.props.PointerProperty(type=PROPS_Room_Builder)
    
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon:
        obj_km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
        kmi = obj_km.keymap_items.new('wm.console_toggle', 'HOME', 'PRESS', shift=True)
        kmi = obj_km.keymap_items.new('blender_design.properties', 'RIGHTMOUSE', 'PRESS')
