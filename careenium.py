import arcade
import pymunk
import math
import random
import timeit
from collections import namedtuple

GRID = 24
SCALE = int(860 / 9 / GRID)
SCREEN_WIDTH = int(16 * SCALE * GRID)
SCREEN_HEIGHT = int(9 * SCALE * GRID)

SCREEN_TITLE = 'Careenium'

OBJECT_MODES = ['Circle', 'Box', 'Pipe', 'Static', 'Moving Pipe', 'Plank']

JOINT_MODES = ['Pin', 'Slide', 'Motor', 'Bridge']

GAME_MODES = ['Gravity', 'Setup', 'No Gravity']

textures = [f'images/{i}.png' for i in
            ['boxCrate', 'boxCrate_double', 'line', 'wood_joint', 'pipe',
             'hudPlayer_beige', 'hudPlayer_blue', 'hudPlayer_green',
             'hudPlayer_pink', 'hudPlayer_yellow']]

FRICTION = 0.95

Pos = namedtuple('Position', 'x y')


'''more generally switch over from using pymunk objects to using holders, hopefully that will make
object attributes easier to set, mainly useful for deleting box sprites for joints.

bugs:
    joints can be made between lines and other objects'''


class PhysicsSprite(arcade.Sprite):
    def __init__(self, pymunk_shape, filename, is_static=False):
        super().__init__(filename, center_x=pymunk_shape.body.position.x, center_y=pymunk_shape.body.position.y)
        self.pymunk_shape = pymunk_shape
        self.is_static = is_static

    def __repr__(self):
        return f'{self.pymunk_shape} {self.pymunk_shape.body}, Static: {self.is_static}'


class CircleSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename, pipe_vel=0, is_static=False):
        super().__init__(pymunk_shape, filename)
        self.width = pymunk_shape.radius * 2
        self.height = pymunk_shape.radius * 2
        self.pipe_vel = pipe_vel
        self.is_static = is_static


class BoxSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename, width, height, is_static=False):
        super().__init__(pymunk_shape, filename)
        self.width = width
        self.height = height
        self.is_static = is_static


class Careenium(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)

        self.set_mouse_visible(False)
        width, height = self.get_size()
        self.set_viewport(0, width, 0, height)

        arcade.set_background_color((80, 120, 132))

        self.space = pymunk.Space()
        self.space.gravity = (0.0, -900.0)
        self.background_sprite_list: arcade.SpriteList[PhysicsSprite] = arcade.SpriteList()
        self.background_sprite_list.preload_textures(textures)

        self.sprite_list: arcade.SpriteList[PhysicsSprite] = arcade.SpriteList()
        self.sprite_list.preload_textures(textures)

        self.shape_being_dragged = None  # if a shape is being moved it will be stored here
        self.shape_a = None  # if two bodies are being tethered they will be stored here
        self.shape_a_connection_point = None
        self.point_pair = None
        self.joints = []
        self.joint_objects = None
        self.walls = []
        self.wall_objects = None
        self.pipes = []
        self.mouse_down = False
        self.grid = False
        self.snapping = False
        self.mouse_pos = Pos(0, 0)
        self.mouse_button = None
        self.joints = []
        self.need_move = False
        self.cur_shape = None
        self.grid_fixer = [0, 0]
        self.snap_to_center = False
        self.debug = False

        self.tick = 0
        self.draw_time = 0
        self.processing_time = 0

        self.game_mode = 0
        self.object_mode = 0
        self.joint_mode = 0
        self.pointer = arcade.Sprite('images/hudX.png')
        self.loading_bar = arcade.Sprite('images/line.png')
        self.highlight_circle = arcade.Sprite('images/highlight_circle.png')
        self.setup()

    def setup(self):
        self.pointer.scale = 0.25
        self.pointer.alpha = 200

        self.loading_bar.height = 10
        self.loading_bar.width = 1
        if not self.debug:
            self.loading_bar.alpha = 0

    def rr(self, val):
        if self.grid:
            return (val + (GRID // 2)) // GRID * GRID
        else:
            return val

    @staticmethod
    def ol_pythag(a, b):
        return math.sqrt((a[0]-b[0]) ** 2 + (a[1]-b[1]) ** 2)

    def mode_switcher(self):
        if self.game_mode == 0:
            self.space.gravity = (0.0, -900.0)
            self.space.damping = 0.95
        if self.game_mode == 1:
            self.space.gravity = (0.0, 0.0)
            self.space.damping = 0
        if self.game_mode == 2:
            self.space.gravity = (0.0, 0.0)
            self.space.damping = 1

    def delete_object(self, obj):
        """Deletes a given object from the world, as well as from anywhere it may be referenced."""
        for _ in range(len(obj.pymunk_shape.body.constraints)):
            for joint in self.joints:  # note: you could also grep the joints with obj.pymunk_shape.body.constraints
                if obj.pymunk_shape.body in [joint[-1].a, joint[-1].b]:
                    self.space.remove(joint[-1])
                    for j in joint[:-1]:
                        self.background_sprite_list.remove(j)
                    self.joints.remove(joint)
        for pipe in self.pipes:
            if pipe.pymunk_shape == obj.pymunk_shape:
                self.pipes.remove(pipe)
        self.space.remove(obj.pymunk_shape, obj.pymunk_shape.body)
        obj.remove_from_sprite_lists()

    def clear_variables(self):  # just a holder function to clear everything
        self.point_pair = None
        self.shape_being_dragged = None
        self.mouse_down = False
        self.mouse_button = None
        self.shape_a = None
        self.shape_a_connection_point = None
        self.cur_shape = None

    def on_draw(self):
        arcade.start_render()

        draw_start_time = timeit.default_timer()
        if self.cur_shape:
            self.highlight_circle.draw()
        self.background_sprite_list.draw()
        self.sprite_list.draw()
        if self.point_pair and self.mouse_down and self.point_pair != self.mouse_pos:
            if self.mouse_button == 4:
                arcade.draw_line(color=arcade.color.GREEN, start_x=self.point_pair.x, start_y=self.point_pair.y, end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, line_width=2)
            elif self.mouse_button == 1 and self.object_mode < 4:
                arcade.draw_line(color=arcade.color.RED, start_x=self.point_pair.x, start_y=self.point_pair.y, end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, line_width=2)
            elif self.mouse_button == 1:
                arcade.draw_line(color=arcade.color.BLUE, start_x=self.point_pair.x, start_y=self.point_pair.y, end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, line_width=2)

        arcade.draw_text(text=f"{GAME_MODES[self.game_mode]}", start_x=SCREEN_WIDTH-128 + self.grid_fixer[0], start_y=32 + self.grid_fixer[1], color=arcade.color.WHITE, font_size=16)
        arcade.draw_text(text=f"{OBJECT_MODES[self.object_mode]}", start_x=32 + self.grid_fixer[0], start_y=32 + self.grid_fixer[1], color=arcade.color.WHITE, font_size=16)
        arcade.draw_text(text=f"{JOINT_MODES[self.joint_mode]}", start_x=256 + self.grid_fixer[0], start_y=32 + self.grid_fixer[1], color=arcade.color.WHITE, font_size=16)

        if self.debug:
            self.loading_bar.width = SCREEN_WIDTH / 30 * (self.draw_time * 5000 + self.processing_time * 5000)
            self.loading_bar.draw()

        self.pointer.draw()

        self.draw_time = timeit.default_timer() - draw_start_time

    def make_circle(self, pos, vel=(0, 0)):
        size = GRID - 1
        mass = 12.0
        moment = pymunk.moment_for_circle(mass, 0, size, (0, 0))
        body = pymunk.Body(mass, moment)
        body.position = pymunk.Vec2d(pos)
        body.velocity = vel
        shape = pymunk.Circle(body, size, pymunk.Vec2d(0, 0))
        shape.friction = FRICTION
        shape.elasticity = 0.3
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b001, categories=0b001)
        sprite = CircleSprite(shape, f"images/hudPlayer_{random.choice(['beige', 'blue', 'green', 'pink', 'yellow'])}.png")
        self.sprite_list.append(sprite)

    def make_box(self, pos, vel=(0, 0)):
        size = GRID * 2
        mass = 12.0
        moment = pymunk.moment_for_box(mass, (size, size))
        body = pymunk.Body(mass, moment)
        body.position = pymunk.Vec2d(pos)
        body.velocity = vel
        shape = pymunk.Poly.create_box(body, (size, size))
        shape.elasticity = 0.3
        shape.friction = FRICTION
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b001, categories=0b001)
        sprite = BoxSprite(shape, "images/boxCrate.png", width=size, height=size)
        self.sprite_list.append(sprite)

    def make_pipe(self, pos, vel):
        size = (GRID * 2) // 2 + (GRID // 8)
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(pos)
        shape = pymunk.Circle(body, size, pymunk.Vec2d(0, 0))
        shape.friction = FRICTION
        shape.elasticity = 0.3
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b010, categories=0b010)
        sprite = CircleSprite(shape, "images/pipe.png", pipe_vel=vel)
        self.background_sprite_list.append(sprite)
        self.pipes.append(sprite)

    def make_moving_pipe(self, pos, vel):
        size = (GRID * 2) // 2 + (GRID // 8)
        mass = 12.0
        moment = pymunk.moment_for_circle(mass, 0, size, (0, 0))
        body = pymunk.Body(mass, moment)
        body.position = pymunk.Vec2d(pos)
        shape = pymunk.Circle(body, size, pymunk.Vec2d(0, 0))
        shape.friction = FRICTION
        shape.elasticity = 0.3
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b010, categories=0b010)
        sprite = CircleSprite(shape, "images/pipe.png", pipe_vel=vel)
        self.background_sprite_list.append(sprite)
        self.pipes.append(sprite)

    def make_static(self, pos):
        size = GRID * 2
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(pos)
        shape = pymunk.Poly.create_box(body, (size, size))
        shape.friction = FRICTION
        shape.elasticity = 1.0
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b011, categories=0b011)
        sprite = BoxSprite(shape, "images/boxCrate_double.png", width=size, height=size)
        self.sprite_list.append(sprite)

    def make_plank(self, start, end):
        line_len = self.ol_pythag(start, end) / 2
        if line_len < 10:
            return
        verticies = ((line_len, 4), (line_len, -4), (-line_len, -4), (-line_len, 4))
        mass = 12.0
        moment = pymunk.moment_for_poly(mass, verticies)
        body = pymunk.Body(mass, moment)
        body.position = pymunk.Vec2d(start[0] + (end[0] - start[0]) / 2, start[1] + (end[1] - start[1]) / 2)
        body.angle = math.atan2(end[1] - start[1], end[0] - start[0])
        shape = pymunk.Poly(body, verticies)
        shape.friction = FRICTION
        shape.elasticity = 0.3
        shape.filter = pymunk.ShapeFilter(mask=0b001, categories=0b001)
        sprite = BoxSprite(shape, "images/plank.png", width=line_len * 2, height=8)
        self.space.add(body, shape)
        self.sprite_list.append(sprite)

    def make_pin_joint(self, shape_a, shape_b, point_a, point_b, internal_call=False):
        try:
            length = self.ol_pythag(point_a, point_b) / 2
        except TypeError:
            return
        if self.snap_to_center:
            point_a, point_b = shape_a.body.position, shape_b.body.position
        vertices = ((length, 2), (length, -2), (-length, -2), (-length, 2))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(point_a[0] + (point_b[0] - point_a[0]) / 2, point_a[1] + (point_b[1] - point_a[1]) / 2)
        shape = pymunk.Poly(body, vertices)
        body.angle = math.atan2(point_b[1] - point_a[1], point_b[0] - point_a[0])
        sprite = BoxSprite(shape, "images/plank.png", width=length * 2, height=4)
        self.background_sprite_list.append(sprite)
        if not internal_call:
            joint = pymunk.PinJoint(shape_a.body, shape_b.body, shape_a.body.world_to_local(point_a), shape_b.body.world_to_local(point_b))
        else:
            joint = pymunk.PinJoint(shape_a, shape_b, point_a, point_b)
        self.joints.append((sprite, joint))
        self.space.add(joint)

    def make_slide_joint(self, shape_a, shape_b, point_a, point_b):
        try:
            length = self.ol_pythag(point_a, point_b) / 2
        except TypeError:
            return
        if self.snap_to_center:
            point_a, point_b = shape_a.body.position, shape_b.body.position
        vertices = ((length, 2), (length, -2), (-length, -2), (-length, 2))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(point_a[0] + (point_b[0] - point_a[0]) / 2, point_a[1] + (point_b[1] - point_a[1]) / 2)
        shape = pymunk.Poly(body, vertices)
        body.angle = math.atan2(point_b[1] - point_a[1], point_b[0] - point_a[0])
        sprite = BoxSprite(shape, "images/plank.png", width=length * 2, height=4)
        self.background_sprite_list.append(sprite)
        joint = pymunk.SlideJoint(shape_a.body, shape_b.body, shape_a.body.world_to_local(point_a), shape_b.body.world_to_local(point_b), min=length * 2, max=length * 4)
        self.joints.append((sprite, joint))
        self.space.add(joint)

    def make_motor(self, shape_a, power):
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        joint = pymunk.SimpleMotor(shape_a.body, body, power)
        self.space.add(joint)

    def make_line(self, start, end):
        line_len = self.ol_pythag(start, end) / 2
        verticies = ((line_len, 1), (line_len, -1), (-line_len, -1), (-line_len, 1))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(start[0] + (end[0] - start[0]) / 2, start[1] + (end[1] - start[1]) / 2)
        body.angle = math.atan2(end[1] - start[1], end[0] - start[0])
        shape = pymunk.Poly(body, verticies)
        shape.friction = FRICTION
        shape.elasticity = 0.95
        sprite = BoxSprite(shape, "images/line.png", width=line_len * 2, height=2, is_static=True)

        self.space.add(body, shape)
        self.background_sprite_list.append(sprite)

    def get_shape(self, pos):
        shape_list = self.space.point_query(pos, 5, pymunk.ShapeFilter())
        if shape_list:
            for sprite in self.sprite_list:
                if sprite.pymunk_shape == shape_list[0].shape:
                    return sprite
            for sprite in self.background_sprite_list:
                if sprite.pymunk_shape == shape_list[0].shape:
                    return sprite
        return None

    def make_bridge(self, shape_a, shape_b):
        point_a = shape_a.body.position
        point_b = shape_b.body.position
        diff_x = point_a[0] - point_b[0]
        diff_y = point_a[1] - point_b[1]
        num_points = int(self.ol_pythag(point_a, point_b) / GRID / 2) + 1
        interval_x = diff_x / num_points
        interval_y = diff_y / num_points
        points = [Pos(point_a[0] - (interval_x * i), point_a[1] - (interval_y * i)) for i in range(1, num_points )]
        point_list = list(zip(points[:-1], points[1:]))
        bridge_len = max(self.ol_pythag(*point_list[0]) - 10, 10)
        link_list = []
        for link in point_list:
            vertices = ((bridge_len, 2), (bridge_len, -2), (-bridge_len, -2), (-bridge_len, 2))
            mass = 4.0
            moment = pymunk.moment_for_poly(mass, vertices)
            body = pymunk.Body(mass, moment)
            body.position = pymunk.Vec2d(link[0].x + (link[1].x - link[0].x) / 2, link[0].y + (link[1].y - link[0].y) / 2)
            shape = pymunk.Poly(body, vertices)
            body.angle = math.atan2(link[0].y - link[1].y, link[0].x - link[1].x)
            sprite = BoxSprite(shape, "images/bridgeC.png", width=bridge_len, height=8)
            self.sprite_list.append(sprite)
            self.space.add(body, shape)
            joint_spot = (bridge_len - 5) / 2
            if not link_list:
                self.make_pin_joint(shape_a.body, sprite.pymunk_shape.body,  (0, 0), (joint_spot, 0), internal_call=True)
            elif len(link_list) < len(point_list) - 1:
                self.make_pin_joint(sprite.pymunk_shape.body, link_list[-1].pymunk_shape.body, (joint_spot, 0),  (-joint_spot, 0), internal_call=True)
            else:
                self.make_pin_joint(sprite.pymunk_shape.body, shape_b.body, (-joint_spot, 0), (0, 0), internal_call=True)
                self.make_pin_joint(sprite.pymunk_shape.body, link_list[-1].pymunk_shape.body, (joint_spot, 0),  (-joint_spot, 0), internal_call=True)
            link_list.append(sprite)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        self.mouse_down = True
        self.mouse_button = button
        self.point_pair = self.mouse_pos
        self.cur_shape = self.get_shape(self.mouse_pos)
        if button == 1:
            if modifiers in [0, 16]:
                if self.cur_shape and not self.cur_shape.is_static:
                    self.mouse_down = False
                    self.shape_being_dragged = self.cur_shape
                else:
                    self.mouse_down = True
            elif self.cur_shape:
                self.delete_object(self.cur_shape)
        elif button == 4 and self.cur_shape and not self.cur_shape.is_static:
            self.shape_a = self.cur_shape.pymunk_shape
            self.shape_a_connection_point = self.mouse_pos

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int):
        self.cur_shape = self.get_shape(self.mouse_pos)
        if self.mouse_down:
            vel = ((self.point_pair.x - self.mouse_pos.x) * 4, (self.point_pair.y - self.mouse_pos.y) * 4)
            if self.mouse_button == 1 and modifiers in [0, 16]:
                if self.object_mode == 0:
                    self.make_circle(self.point_pair, vel=vel)
                elif self.object_mode == 1:
                    self.make_box(self.point_pair, vel=vel)
                elif self.object_mode == 2:
                    self.make_pipe(self.point_pair, vel=vel)
                elif self.object_mode == 3:
                    self.make_static(self.point_pair)
                elif self.object_mode == 4:
                    self.make_moving_pipe(self.point_pair, vel=vel)
                elif self.object_mode == 5:
                    self.make_plank(self.mouse_pos, self.point_pair)
            elif button == 4:
                if self.cur_shape and not self.cur_shape.is_static:
                    self.cur_shape.pymunk_shape.velocity = 0, 0
                    if self.joint_mode == 0 and self.shape_a != self.cur_shape.pymunk_shape:
                        self.make_pin_joint(self.shape_a, self.cur_shape.pymunk_shape, self.shape_a_connection_point, self.mouse_pos)
                    elif self.joint_mode == 1 and self.shape_a != self.cur_shape.pymunk_shape:
                        self.make_slide_joint(self.shape_a, self.cur_shape.pymunk_shape, self.shape_a_connection_point, self.mouse_pos)
                    elif self.joint_mode == 3 and self.shape_a != self.cur_shape.pymunk_shape:
                        self.make_bridge(self.shape_a, self.cur_shape.pymunk_shape)
                elif self.joint_mode == 2 and self.shape_a:
                    intensity = min(self.ol_pythag(self.mouse_pos, self.point_pair) / 16, 20)
                    d = int(self.point_pair.x - self.mouse_pos.x > 0 or -1)
                    self.make_motor(self.shape_a, intensity * d)
                elif self.ol_pythag(self.point_pair, self.mouse_pos) > 10:
                    self.make_line(self.point_pair, self.mouse_pos)
        self.clear_variables()

    def on_mouse_motion(self, x, y, dx, dy):
        if self.snapping:
            if self.point_pair:
                if abs(self.rr(x) - self.point_pair.x) < abs(self.rr(y) - self.point_pair.y):
                    self.mouse_pos = Pos(self.point_pair.x + self.grid_fixer[1], self.rr(y + self.grid_fixer[1]))
                else:
                    self.mouse_pos = Pos(self.rr(x + self.grid_fixer[0]), self.point_pair.y + self.grid_fixer[1])
            else:
                self.mouse_pos = Pos(self.rr(x + self.grid_fixer[0]), self.rr(y + self.grid_fixer[1]))
        else:
            self.mouse_pos = Pos(self.rr(x + self.grid_fixer[0]), self.rr(y + self.grid_fixer[1]))
        highlight_shape = self.get_shape(self.mouse_pos)
        if self.mouse_down and self.snap_to_center and highlight_shape:
            self.mouse_pos = highlight_shape.pymunk_shape.body.position
        if self.mouse_button == 2 and self.mouse_down:
            self.grid_fixer[0] -= dx
            self.grid_fixer[1] -= dy
            self.set_viewport(self.grid_fixer[0], self.grid_fixer[0]+SCREEN_WIDTH, self.grid_fixer[1], self.grid_fixer[1]+SCREEN_HEIGHT)
        elif self.cur_shape and not self.mouse_down and self.mouse_button == 1:
            if self.grid:
                self.cur_shape.pymunk_shape.body.position = self.mouse_pos
            else:
                self.cur_shape.pymunk_shape.body.position = self.cur_shape.pymunk_shape.body.position.x + dx, self.cur_shape.pymunk_shape.body.position.y + dy

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if (scroll_y > 0 and self.object_mode < len(OBJECT_MODES) - 1) or self.object_mode > 0 > scroll_y:
            self.object_mode += scroll_y

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.SPACE:
            self.grid = not self.grid
        if symbol == arcade.key.LSHIFT or arcade.key.RSHIFT:
            self.snapping = True
        if symbol == arcade.key.UP and self.game_mode < len(GAME_MODES) - 1:
            self.game_mode += 1
            self.mode_switcher()
        if symbol == arcade.key.DOWN and 0 < self.game_mode:
            self.game_mode -= 1
            self.mode_switcher()
        if symbol == arcade.key.KEY_1:
            self.joint_mode = 0
        if symbol == arcade.key.KEY_2:
            self.joint_mode = 1
        if symbol == arcade.key.KEY_3:
            self.joint_mode = 2
        if symbol == arcade.key.KEY_4:
            self.joint_mode = 3
        if symbol == arcade.key.G:
            self.snap_to_center = not self.snap_to_center

    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.LSHIFT or arcade.key.RSHIFT:
            self.snapping = False

    def move_everybody(self, dest: (int, int)):
        for shape in self.space.shapes:
            if type(shape) in [pymunk.shapes.Circle, pymunk.shapes.Poly]:
                shape.body.position = shape.body.position.x + dest[0],  shape.body.position.y + dest[1]
            else:
                shape.unsafe_set_endpoints((shape.a.x + dest[0], shape.a.y + dest[1]), (shape.b.x + dest[0], shape.b.y + dest[1]))

    def on_update(self, delta_time):
        start_time = timeit.default_timer()
        self.pointer.position = self.mouse_pos

        if not self.game_mode == 1:
            self.tick += 1

            if self.tick % 60 == 0:
                for pipe in self.pipes:
                    if pipe.pymunk_shape.body.body_type == 0:
                        pipe.pymunk_shape.body.velocity = pipe.pymunk_shape.body.velocity[0] - pipe.pipe_vel[0], pipe.pymunk_shape.body.velocity[1] - pipe.pipe_vel[1]
                    self.make_circle(pipe.pymunk_shape.body.position, pipe.pipe_vel)

        if self.cur_shape:
            self.cur_shape.pymunk_shape.body.velocity = 0, 0

        self.space.step(1 / 60.0)

        for sprite in self.sprite_list:
            sprite.center_x = sprite.pymunk_shape.body.position.x
            sprite.center_y = sprite.pymunk_shape.body.position.y
            sprite.angle = math.degrees(sprite.pymunk_shape.body.angle)
            if sprite == self.cur_shape:
                self.highlight_circle.width = sprite.width + 6
                self.highlight_circle.height = sprite.height + 6
                self.highlight_circle.center_x = sprite.center_x
                self.highlight_circle.center_y = sprite.center_y
                self.highlight_circle.angle = sprite.angle
            if not(-SCREEN_WIDTH * 9 < sprite.pymunk_shape.body.position.y < SCREEN_WIDTH * 10) or not(-SCREEN_HEIGHT * 9 < sprite.pymunk_shape.body.position.y < SCREEN_HEIGHT * 10):
                cur_shape = self.get_shape(sprite.pymunk_shape.body.position)
                if cur_shape:
                    self.delete_object(cur_shape)
        for sprite in self.background_sprite_list:
            sprite.center_x = sprite.pymunk_shape.body.position.x
            sprite.center_y = sprite.pymunk_shape.body.position.y
            sprite.angle = math.degrees(sprite.pymunk_shape.body.angle)
            if not(-SCREEN_WIDTH * 9 < sprite.pymunk_shape.body.position.y < SCREEN_WIDTH * 10) or not(-SCREEN_HEIGHT * 9 < sprite.pymunk_shape.body.position.y < SCREEN_HEIGHT * 10):
                cur_shape = self.get_shape(sprite.pymunk_shape.body.position)
                if cur_shape:
                    self.delete_object(cur_shape)

        for joint in self.joints:
            if type(joint[-1]) is pymunk.constraint.PinJoint:
                start = joint[1].a.local_to_world(joint[1].anchor_a)
                end = joint[1].b.local_to_world(joint[1].anchor_b)
                joint[0].center_x = start[0] + (end[0] - start[0]) / 2
                joint[0].center_y = start[1] + (end[1] - start[1]) / 2
                joint[0].width = self.ol_pythag(start, end)
                joint[0].angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
            elif type(joint[-1]) is pymunk.constraint.SlideJoint:
                start = joint[1].a.local_to_world(joint[1].anchor_a)
                end = joint[1].b.local_to_world(joint[1].anchor_b)
                joint[0].center_x = start[0] + (end[0] - start[0]) / 2
                joint[0].center_y = start[1] + (end[1] - start[1]) / 2
                joint[0].width = self.ol_pythag(start, end)
                joint[0].angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))

        self.processing_time = timeit.default_timer() - start_time


if __name__ == '__main__':
    window = Careenium(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    arcade.run()
