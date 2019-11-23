import arcade
import pymunk
import math
import random
from pymunk import Vec2d

GRID = 24

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_TITLE = 'Careenium'

OBJECT_MODES = ['Circle', 'Box', 'Plank', 'Pipe']
CONSTRAINT_MODES = ['Pin', 'Slide', 'Motor', 'Bridge']
GAME_MODES = ['Gravity', 'Setup', 'Space']

FRICTION = 0.95
ELASTICITY = 0.4

textures = [f'images/{i}.png' for i in
            ['boxCrate', 'boxCrate_double', 'line', 'wood_joint', 'pipe',
             'hudPlayer_beige', 'hudPlayer_blue', 'hudPlayer_green',
             'hudPlayer_pink', 'hudPlayer_yellow', 'bridgeC.png', 'ui/blue_hover.png',
             'ui/blue_normal.png', 'ui/blue_pressed.png', 'ui/locked.png']]

class PhysicsSprite(arcade.Sprite):
    def __init__(self, pymunk_shape, filename):
        super().__init__(filename, center_x=pymunk_shape.body.position.x, center_y=pymunk_shape.body.position.y)
        self.pymunk_shape = pymunk_shape

    def __repr__(self):
        return f'{self.pymunk_shape} {self.pymunk_shape.body}'


class CircleSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename):
        super().__init__(pymunk_shape, filename)
        self.width = pymunk_shape.radius * 2
        self.height = pymunk_shape.radius * 2


class PipeSprite(CircleSprite):
    def __init__(self, pymunk_shape, filename, pipe_shape, pipe_velocity):
        super().__init__(pymunk_shape, filename)
        self.pipe_shape = pipe_shape
        self.pipe_velocity = pipe_velocity


class BoxSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename, width, height):
        super().__init__(pymunk_shape, filename)
        self.width = width
        self.height = height


class Button(arcade.Sprite):
    def __init__(self, position, value, list_of_vals):
        super().__init__('images/ui/blue_normal.png')
        self.value = value
        self.list_of_vals = list_of_vals
        self.position = position
        self.textures = [arcade.load_texture('images/ui/blue_normal.png'),
                         arcade.load_texture('images/ui/blue_hover.png'),
                         arcade.load_texture('images/ui/blue_pressed.png'),
                         arcade.load_texture('images/ui/locked.png')]
        self.state = 0
        self.my_x = (self.center_x - self.width / 2, self.center_x + self.width / 2)
        self.my_y = (self.center_y - self.height / 2, self.center_y + self.height / 2)

    def draw(self):
        arcade.draw_texture_rectangle(center_x=self.position.x,
                                      center_y=self.position.y,
                                      width=GRID*4, height=GRID*2,
                                      texture=self.textures[self.state])
        arcade.draw_text(text=f"{self.list_of_vals[self.value]}",
                         start_x=self.center_x, start_y=self.center_y,
                         color=arcade.color.WHITE, font_size=16,
                         anchor_x='center', anchor_y='center', align='center')
        if self.state == 2:
            self.update_val()
            #  return true if the mouse was pressed and that needs to be reset, otherwise do nothing
            return True
        return False

    def check_pos(self, pos):
        if self.my_x[0] < pos.x < self.my_x[1] and self.my_y[0] < pos.y < self.my_y[1]:
            return True
        return False

    def update_val(self):
        if self.value < len(self.list_of_vals) - 1:
            self.value += 1
        else:
            self.value = 0

class Careenium(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        self.set_viewport(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)
        arcade.set_background_color((80, 120, 132))

        self.space = pymunk.Space()
        # replace call to set gravity to call with modeswitcher
        self.background_sprite_list: arcade.SpriteList[PhysicsSprite] = arcade.SpriteList()
        self.background_sprite_list.preload_textures(textures)

        self.sprite_list: arcade.SpriteList[PhysicsSprite] = arcade.SpriteList()
        self.sprite_list.preload_textures(textures)

        self.buttons = []

        self.shape_being_dragged = None
        self.last_shape = None
        self.last_shape_connection_point = None
        self.follow_shape = None
        self.cur_shape = None
        self.point_pair = None
        self.joints = []
        self.walls = []
        self.pipes = []
        self.static_shapes = []

        self.camera_offset = Vec2d(0, 0)

        self.mouse_down = False
        self.mouse_button = None
        self.mouse_pos = Vec2d(0, 0)

        self.grid = False
        self.straight_lines = False
        self.snap_to_center = False
        self.debug = True
        self.shape_static = False

        self.tick = 0
        self.loading_time = 0

        self.game_mode = 0
        self.object_mode = 0
        self.constraint_mode = 0

        self.pointer = arcade.Sprite('images/hudX.png')
        self.pointer.scale = 0.25
        self.pointer.alpha = 200

        self.loading_bar = arcade.Sprite('images/line.png')
        self.loading_bar.height = 10
        self.loading_bar.width = 1

        self.highlight_circle = arcade.Sprite('images/highlight_circle.png')
        self.highlight_circle.alpha = 150

        self.highlight_box = arcade.Sprite('images/highlight_box.png')
        self.highlight_box.alpha = 150

        self.object_mode_button = Button(position=Vec2d(GRID*3, GRID), value=0, list_of_vals=OBJECT_MODES)
        self.game_mode_button = Button(position=Vec2d(GRID*9, GRID), value=0, list_of_vals=GAME_MODES)
        self.constraint_mode_button = Button(position=Vec2d(GRID*15, GRID), value=0, list_of_vals=CONSTRAINT_MODES)
        self.grid_button = Button(position=Vec2d(GRID*21, GRID), value=0, list_of_vals=['Grid\nOff', 'Grid\nOn'])
        self.snap_to_center_button = Button(position=Vec2d(GRID*27, GRID), value=0, list_of_vals=['Snapping\nOff', 'Snapping\nOn'])
        self.shape_static_button = Button(position=Vec2d(GRID*33, GRID), value=0, list_of_vals=['Static\nOff', 'Static\nOn'])
        self.straight_lines_button = Button(position=Vec2d(GRID*39, GRID), value=0, list_of_vals=['Straighten\nOff', 'Straighten\nOn'])
        self.buttons.extend([self.object_mode_button, self.game_mode_button,
                             self.constraint_mode_button, self.grid_button,
                             self.snap_to_center_button, self.shape_static_button,
                             self.straight_lines_button])

        self.mode_setter()

    def mode_setter(self):
        """Sets gamemode"""
        if GAME_MODES[self.game_mode] == 'Gravity':
            self.space.gravity = (0.0, -900.0)
            self.space.damping = 0.95
        if GAME_MODES[self.game_mode] == 'Setup':
            self.space.gravity = (0.0, 0.0)
            self.space.damping = 0
        if GAME_MODES[self.game_mode] == 'Space':
            self.space.gravity = (0.0, 0.0)
            self.space.damping = 1


    def get_shape(self, pos):
        shape_list = self.space.point_query(pos, 4, pymunk.ShapeFilter())
        if shape_list:
            for sprite in self.sprite_list:
                if sprite.pymunk_shape == shape_list[0].shape:
                    return sprite
            for sprite in self.background_sprite_list:
                if sprite.pymunk_shape == shape_list[0].shape:
                    return sprite
        return None

    def highlight_shape(self, shape):
        if type(shape.pymunk_shape) == pymunk.shapes.Circle:
            self.highlight_circle.width = shape.width + 6
            self.highlight_circle.height = shape.height + 6
            self.highlight_circle.center_x = shape.center_x
            self.highlight_circle.center_y = shape.center_y
            self.highlight_circle.angle = shape.angle
        else:
            self.highlight_box.width = shape.width + 6
            self.highlight_box.height = shape.height + 6
            self.highlight_box.center_x = shape.center_x
            self.highlight_box.center_y = shape.center_y
            self.highlight_box.angle = shape.angle

    def delete_object(self, obj):
        """Deletes a given object from the world, as well as from anywhere it may be referenced."""
        for _ in range(len(obj.pymunk_shape.body.constraints)):
            for joint in self.joints:
                if obj.pymunk_shape.body in [joint[0].a, joint[0].b]:
                    self.space.remove(joint[0])
                    for j in joint[1:]:
                        self.background_sprite_list.remove(j)
                    self.joints.remove(joint)
        for pipe in self.pipes:
            if pipe.pymunk_shape == obj.pymunk_shape:
                self.pipes.remove(pipe)

        for static_shape in self.static_shapes:
            if static_shape.pymunk_shape == obj.pymunk_shape:
                self.static_shapes.remove(static_shape)
        self.space.remove(obj.pymunk_shape, obj.pymunk_shape.body)
        obj.remove_from_sprite_lists()

    def clear_variables(self):
        self.shape_being_dragged = None
        self.last_shape = None
        self.last_shape_connection_point = None
        self.cur_shape = None
        self.point_pair = None
        self.mouse_down = False
        self.mouse_button = None

    def on_draw(self):
        arcade.start_render()

        if self.cur_shape:
            if type(self.cur_shape.pymunk_shape) == pymunk.shapes.Circle:
                self.highlight_circle.draw()
            else:
                self.highlight_box.draw()
        self.background_sprite_list.draw()
        self.sprite_list.draw()
        if not self.shape_being_dragged and self.point_pair and self.mouse_down and self.point_pair != self.mouse_pos:
            if self.mouse_button == 4:
                arcade.draw_line(color=arcade.color.GREEN, start_x=self.point_pair.x, start_y=self.point_pair.y, end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, line_width=2)
            elif self.mouse_button == 1 and self.object_mode < 4:
                arcade.draw_line(color=arcade.color.RED, start_x=self.point_pair.x, start_y=self.point_pair.y, end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, line_width=2)
            elif self.mouse_button == 1:
                arcade.draw_line(color=arcade.color.BLUE, start_x=self.point_pair.x, start_y=self.point_pair.y, end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, line_width=2)

        for button in self.buttons:
            check =  int(button.check_pos(self.mouse_pos))
            button.state = check + int(self.mouse_down) * check
            if button.draw():
                self.mouse_down = False

        self.pointer.draw()


    def make_circle(self, pos, vel=(0, 0), friction=FRICTION, elasticity=ELASTICITY, mass=12.0):
        pos = Vec2d(pos)
        size = GRID - 1
        moment = pymunk.moment_for_circle(mass, 0, size, (0, 0))
        body = pymunk.Body(mass, moment)
        body.position = Vec2d(pos)
        body.velocity = vel
        shape = pymunk.Circle(body, size, Vec2d(0, 0))
        shape.friction = friction
        shape.elasticity = elasticity
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b001, categories=0b001)
        sprite = CircleSprite(shape, f"images/hudPlayer_{random.choice(['beige', 'blue', 'green', 'pink', 'yellow'])}.png")
        self.sprite_list.append(sprite)
        if self.shape_static:
            self.static_shapes.append(sprite)
        return sprite

    def make_box(self, pos, vel=(0, 0), friction=FRICTION, elasticity=ELASTICITY, mass=12.0):
        pos = Vec2d(pos)
        size = GRID * 2
        moment = pymunk.moment_for_box(mass, (size, size))
        body = pymunk.Body(mass, moment)
        body.position = Vec2d(pos)
        body.velocity = vel
        shape = pymunk.Poly.create_box(body, (size, size))
        shape.elasticity = elasticity
        shape.friction = friction
        shape.filter = pymunk.ShapeFilter(mask=0b001, categories=0b001)
        self.space.add(body, shape)
        sprite = BoxSprite(shape, "images/boxCrate.png", width=size, height=size)
        self.sprite_list.append(sprite)
        if self.shape_static:
            self.static_shapes.append(sprite)
        return sprite

    def make_pipe(self, pos, shape_to_drop, vel=(0, 0), friction=FRICTION, elasticity=ELASTICITY, mass=14.0):
        pos = Vec2d(pos)
        size = GRID + 1
        moment = pymunk.moment_for_circle(mass, 0, size, Vec2d(0, 0))
        body = pymunk.Body(mass, moment)
        body.position = Vec2d(pos)
        shape = pymunk.Circle(body, size, (0, 0))
        shape.friction = friction
        shape.elasticity = elasticity
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b010, categories=0b010)
        sprite = PipeSprite(pymunk_shape=shape, filename="images/pipe.png", pipe_shape=shape_to_drop, pipe_velocity=vel)
        self.background_sprite_list.append(sprite)
        self.pipes.append(sprite)
        if self.shape_static:
            self.static_shapes.append(sprite)
        return sprite

    def make_plank(self, start, end, vel=(0, 0), friction=FRICTION, elasticity=ELASTICITY, mass=12.0):
        start = Vec2d(start)
        end = Vec2d(end)
        length = start.get_distance(end) / 2
        verticies = ((length, 4), (length, -4), (-length, -4), (-length, 4))
        moment = pymunk.moment_for_poly(mass, verticies)
        body = pymunk.Body(mass, moment)
        body.position = start + (end-start) / 2
        body.angle = math.atan2(end.y - start.y, end.x - start.x)
        body.velocity = vel
        shape = pymunk.Poly(body, verticies)
        shape.elasticity = elasticity
        shape.friction = friction
        shape.filter = pymunk.ShapeFilter(mask=0b001, categories=0b001)
        self.space.add(body, shape)
        sprite = BoxSprite(shape, "images/plank.png", width=length * 2, height=8)
        self.sprite_list.append(sprite)
        if self.shape_static:
            self.static_shapes.append(sprite)
        return sprite


    def make_pin_joint(self, shape_a, shape_b, point_a, point_b):
        point_a = Vec2d(point_a)
        point_b = Vec2d(point_b)
        world_a = shape_a.body.local_to_world(point_a)
        world_b = shape_b.body.local_to_world(point_b)
        length = world_a.get_distance(world_b) / 2
        vertices = ((length, 2), (length, -2), (-length, -2), (-length, 2))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = world_a + (world_b-world_a) / 2
        body.angle = math.atan2(point_b.y-point_a.y, point_b.x-point_a.x)
        shape = pymunk.Poly(body, vertices)
        sprite = BoxSprite(shape, "images/plank.png", width=length * 2, height=4)
        self.background_sprite_list.append(sprite)

        joint = pymunk.PinJoint(shape_a.body, shape_b.body, point_a, point_b)
        self.joints.append((joint, sprite))
        self.space.add(joint)

    def make_slide_joint(self, shape_a, shape_b, point_a, point_b):
        point_a = Vec2d(point_a)
        point_b = Vec2d(point_b)
        world_a = shape_a.body.local_to_world(point_a)
        world_b = shape_b.body.local_to_world(point_b)
        length = world_a.get_distance(world_b) / 2
        vertices = ((length, 2), (length, -2), (-length, -2), (-length, 2))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = world_a + (world_b-world_a) / 2
        shape = pymunk.Poly(body, vertices)
        body.angle = math.atan2(point_b.y-point_a.y, point_b.x-point_a.x)
        sprite = BoxSprite(shape, "images/plank.png", width=length * 2, height=4)
        self.background_sprite_list.append(sprite)
        joint = pymunk.SlideJoint(shape_a.body, shape_b.body, point_a, point_b, min=length * 2, max=length * 4)
        self.joints.append((sprite, joint))
        self.space.add(joint)

    def make_motor(self, shape, power):
        # instead of tying two bodies together, an unused body is created instead
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        joint = pymunk.SimpleMotor(shape.body, body, power)
        self.space.add(joint)

    def make_line(self, start, end, vel=(0, 0), friction=FRICTION, elasticity=ELASTICITY):
        start = Vec2d(start)
        end = Vec2d(end)
        length = start.get_distance(end) / 2
        verticies = ((length, 1), (length, -1), (-length, -1), (-length, 1))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = start + (end-start) / 2
        body.angle = math.atan2(end.y - start.y, end.x - start.x)
        body.velocity = vel
        shape = pymunk.Poly(body, verticies)
        shape.elasticity = elasticity
        shape.friction = friction
        shape.filter = pymunk.ShapeFilter(mask=0b111, categories=0b111)
        self.space.add(body, shape)
        sprite = BoxSprite(shape, "images/line.png", width=length * 2, height=2)
        self.background_sprite_list.append(sprite)

    def make_bridge(self, shape_a, shape_b):
        point_a = shape_a.body.position
        point_b = shape_b.body.position
        diff = point_a - point_b
        num_points = int(point_a.get_distance(point_b) / GRID / 2) + 1
        interval = diff / num_points
        points = [Vec2d(point_a.x - (interval.x * i), point_a.y - (interval.y * i)) for i in range(1, num_points)]
        point_list = list(zip(points[:-1], points[1:]))
        link_list = []
        for link in point_list:  # make this into a call to make_plank()
            cur_link = self.make_plank(*link, mass=4.0)
            joint_spot = GRID - GRID / 4
            if not link_list:
                self.make_pin_joint(shape_a, cur_link.pymunk_shape,  (0, 0), (-joint_spot, 0))
            elif len(link_list) < len(point_list) - 1:
                self.make_pin_joint(cur_link.pymunk_shape, link_list[-1].pymunk_shape, (-joint_spot, 0),  (joint_spot, 0))
            else:
                self.make_pin_joint(cur_link.pymunk_shape, shape_b, (joint_spot, 0), (0, 0))
                self.make_pin_joint(cur_link.pymunk_shape, link_list[-1].pymunk_shape, (-joint_spot, 0),  (joint_spot, 0))
            link_list.append(cur_link)


    def on_mouse_press(self, x, y, button, modifiers):
        self.mode_setter()
        self.mouse_down = True
        self.mouse_button = button
        self.point_pair = self.mouse_pos
        self.cur_shape = self.get_shape(self.mouse_pos)

        if self.mouse_button == 1:
            if modifiers in [0, 16]:
                if self.cur_shape:
                    self.shape_being_dragged = self.cur_shape
            else:
                self.delete_object(self.cur_shape)
        elif self.mouse_button == 4 and self.cur_shape:
            self.last_shape = self.cur_shape
            self.last_shape_connection_point = self.last_shape.pymunk_shape.body.world_to_local(self.mouse_pos)
        elif self.mouse_button == 2:
            if self.cur_shape:
                self.follow_shape = self.cur_shape
            else:
                self.follow_shape = None

    def on_mouse_release(self, x, y, button, modifiers):
        self.cur_shape = self.get_shape(self.mouse_pos)
        if not self.shape_being_dragged:
            vel = (self.point_pair - self.mouse_pos) * 4
            if self.mouse_button == 1 and modifiers in [0, 16]:
                mode = OBJECT_MODES[self.object_mode]
                if mode == 'Circle':
                    self.make_circle(pos=self.point_pair, vel=vel)
                if mode == 'Box':
                    self.make_box(pos=self.point_pair, vel=vel)
                if mode == 'Pipe':
                    self.make_pipe(pos=self.point_pair, shape_to_drop='Circle', vel=vel)
                if mode == 'Plank' and self.mouse_pos.get_distance(self.point_pair) > GRID:
                    self.make_plank(start=self.point_pair, end=self.mouse_pos)
            elif button == 4 and self.mouse_pos.get_distance(self.point_pair) > GRID:
                mode = CONSTRAINT_MODES[self.constraint_mode]
                if self.cur_shape and (type(self.cur_shape.pymunk_shape.body) is not pymunk.Body.KINEMATIC or type(self.last_shape.pymunk_shape.body) is not pymunk.Body.KINEMATIC):
                    self.cur_shape.pymunk_shape.body.velocity = 0, 0
                    if mode == 'Pin':
                        self.make_pin_joint(self.last_shape.pymunk_shape, self.cur_shape.pymunk_shape, self.last_shape_connection_point, self.cur_shape.pymunk_shape.body.world_to_local(self.mouse_pos))
                    elif mode == 'Slide':
                        self.make_slide_joint(self.last_shape.pymunk_shape, self.cur_shape.pymunk_shape, self.last_shape_connection_point, self.cur_shape.pymunk_shape.body.world_to_local(self.mouse_pos))
                    elif mode == 'Bridge':
                        if self.point_pair.get_distance(self.mouse_pos) > GRID * 6:
                            self.make_bridge(self.last_shape.pymunk_shape, self.cur_shape.pymunk_shape)
                elif mode == 'Motor':
                    intensity = min(self.mouse_pos.get_distance(self.point_pair) / 16, 20)
                    direction = int(self.point_pair.x - self.mouse_pos.x > 0) or -1
                    self.make_motor(self.last_shape.pymunk_shape, intensity*direction)
                elif self.mouse_pos.get_distance(self.point_pair) > 10:
                    self.make_line(self.point_pair, self.mouse_pos)
        self.clear_variables()

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        if self.grid:
            pos = Vec2d((x + (GRID // 2)) // GRID * GRID, (y + (GRID // 2)) // GRID * GRID)
        else:
            pos = Vec2d(x, y)
        if self.straight_lines:
            if self.point_pair:
                if abs(pos.x - self.point_pair.x) > abs(pos.y - self.point_pair.y):
                    self.mouse_pos = Vec2d(self.point_pair.x + self.camera_offset.x, pos.y + self.camera_offset.y)
                else:
                    self.mouse_pos = Vec2d(pos.x + self.camera_offset.x, self.point_pair.y + self.camera_offset.y)
            else:
                self.mouse_pos = Vec2d(pos + self.camera_offset)
        else:
            self.mouse_pos = Vec2d(pos + self.camera_offset)

        if self.shape_being_dragged:
            if self.grid:
                self.cur_shape.pymunk_shape.body.position = self.mouse_pos
            else:
                self.cur_shape.pymunk_shape.body.position += dx, dy
        elif self.cur_shape and self.snap_to_center:  # as a prereq for there being a cur_shape, the mouse must be down.
            self.mouse_pos = self.cur_shape.pymunk_shape.body.position
        elif self.mouse_button == 2 and self.mouse_down:
            self.camera_offset -= dx, dy
            self.set_viewport(self.camera_offset.x, self.camera_offset.x+SCREEN_WIDTH, self.camera_offset.y, self.camera_offset.y+SCREEN_HEIGHT)
        self.pointer.position = self.mouse_pos
        cur_high = self.get_shape(self.mouse_pos)
        if cur_high:
            self.highlight_shape(cur_high)


    def on_key_press(self, symbol: int, modifiers: int):

        if symbol == arcade.key.SPACE:
            self.grid = not self.grid
        if symbol == arcade.key.LSHIFT or arcade.key.RSHIFT:
            self.straight_lines = True

        if symbol == arcade.key.UP and self.game_mode < len(GAME_MODES) - 1:
            self.game_mode += 1
            self.mode_switcher()
        if symbol == arcade.key.DOWN and 0 < self.game_mode:
            self.game_mode -= 1
            self.mode_switcher()

        if symbol == arcade.key.KEY_1:
            self.constraint_mode = 0
        if symbol == arcade.key.KEY_2:
            self.constraint_mode = 1
        if symbol == arcade.key.KEY_3:
            self.constraint_mode = 2
        if symbol == arcade.key.KEY_4:
            self.constraint_mode = 3

        if symbol == arcade.key.G:
            self.snap_to_center = not self.snap_to_center

    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.LSHIFT or arcade.key.RSHIFT:
            self.straight_lines = False


    def on_update(self, delta_time):
        self.object_mode = self.object_mode_button.value
        self.game_mode = self.game_mode_button.value
        self.constraint_mode = self.constraint_mode_button.value
        self.grid = bool(self.grid_button.value)
        self.snap_to_center = bool(self.snap_to_center_button.value)
        self.shape_static = bool(self.shape_static_button.value)

        if not self.game_mode == 1:
            self.tick += 1
            if self.tick % 60 == 0:
                for pipe in self.pipes:
                    pipe.pymunk_shape.body.velocity -= pipe.pipe_velocity
                    if pipe.pipe_shape == 'Circle':
                        self.make_circle(pipe.pymunk_shape.body.position, pipe.pipe_velocity)
                    if pipe.pipe_shape == 'Box':
                        self.make_box(pipe.pymunk_shape.body.position, pipe.pipe_velocity)

        if self.cur_shape:
            self.cur_shape.pymunk_shape.body.velocity = 0, 0

        if self.last_shape:
            self.highlight_shape(self.last_shape)

        if self.follow_shape:
            self.camera_offset.x =int(self.follow_shape.pymunk_shape.body.position.x) - SCREEN_WIDTH / 2
            self.camera_offset.y = int(self.follow_shape.pymunk_shape.body.position.y) - SCREEN_HEIGHT / 2
            self.set_viewport(self.camera_offset.x, self.camera_offset.x+SCREEN_WIDTH, self.camera_offset.y, self.camera_offset.y+SCREEN_HEIGHT)


        self.space.step(1 / 240.0)  # some code needs to be rewritten so this doesnt allow "static" objects to fall a lil
        self.space.step(1 / 240.0)
        self.space.step(1 / 240.0)

        for sprite in self.sprite_list:
            sprite.center_x = sprite.pymunk_shape.body.position.x
            sprite.center_y = sprite.pymunk_shape.body.position.y
            sprite.angle = math.degrees(sprite.pymunk_shape.body.angle)
            if sprite == self.cur_shape:
                self.highlight_shape(self.cur_shape)
            if not (-SCREEN_WIDTH * 9 < sprite.pymunk_shape.body.position.y < SCREEN_WIDTH * 10) or not (-SCREEN_HEIGHT * 9 < sprite.pymunk_shape.body.position.y < SCREEN_HEIGHT * 10):
                cur_shape = self.get_shape(sprite.pymunk_shape.body.position)
                if cur_shape:
                    self.delete_object(cur_shape)
            if sprite in self.static_shapes:
                sprite.pymunk_shape.body.velocity = 0,0
                sprite.pymunk_shape.body.angular_velocity = 0

        for sprite in self.background_sprite_list:
            sprite.center_x = sprite.pymunk_shape.body.position.x
            sprite.center_y = sprite.pymunk_shape.body.position.y
            sprite.angle = math.degrees(sprite.pymunk_shape.body.angle)
            if not (-SCREEN_WIDTH * 9 < sprite.pymunk_shape.body.position.y < SCREEN_WIDTH * 10) or not (-SCREEN_HEIGHT * 9 < sprite.pymunk_shape.body.position.y < SCREEN_HEIGHT * 10):
                cur_shape = self.get_shape(sprite.pymunk_shape.body.position)
                if cur_shape:
                    self.delete_object(cur_shape)

        for joint in self.joints:
            if type(joint[0]) is pymunk.constraint.PinJoint:
                start = joint[0].a.local_to_world(joint[0].anchor_a)
                end = joint[0].b.local_to_world(joint[0].anchor_b)
                joint[1].center_x = start.x + (end.x - start.x) / 2
                joint[1].center_y = start.y + (end.y - start.y) / 2
                joint[1].width = start.get_distance(end)
                joint[1].angle = math.degrees(math.atan2(end.y - start.y, end.x - start.x))


if __name__ == '__main__':
    window = Careenium(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    arcade.run()
