import arcade
import pymunk
import math
import random
import timeit

SCALE = 4
GRID = 20
SCREEN_WIDTH = int(16 * SCALE * GRID)
SCREEN_HEIGHT = int(9 * SCALE * GRID)

SCREEN_TITLE = 'Careenium'

OBJECT_MODES = ['Circle', 'Box', 'Pipe', 'Static', 'Moving Pipe']

JOINT_MODES = ['Pin', 'Slide']

GAME_MODES = ['Gravity', 'Setup', 'No Gravity']

textures = [f'images/{i}.png' for i in ['boxCrate', 'boxCrate_double', 'line', 'wood_joint', 'pipe', 'hudPlayer_beige', 'hudPlayer_blue', 'hudPlayer_green', 'hudPlayer_pink', 'hudPlayer_yellow']]

FRICTION = 0.95


'''more generally switch over from using pymunk objects to using holders, hopefully that will make
object attributes easier to set, mainly useful for deleting box sprites for joints.

bugs:
    joints can be made between lines and other objects'''


class PhysicsSprite(arcade.Sprite):
    def __init__(self, pymunk_shape, filename):
        super().__init__(filename, center_x=pymunk_shape.body.position.x, center_y=pymunk_shape.body.position.y)
        self.pymunk_shape = pymunk_shape


class CircleSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename, pipe_vel=0):
        super().__init__(pymunk_shape, filename)
        self.width = pymunk_shape.radius * 2
        self.height = pymunk_shape.radius * 2
        self.pipe_vel = pipe_vel


class BoxSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename, width, height):
        super().__init__(pymunk_shape, filename)
        self.width = width
        self.height = height


class Careenium(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)

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
        self.mouse_pos = 0, 0
        self.mouse_button = None
        self.joints = []
        self.need_move = False

        self.tick = 0
        self.draw_time = 0
        self.processing_time = 0

        self.game_mode = 0
        self.object_mode = 0
        self.joint_mode = 0
        self.pointer = arcade.Sprite('images/hudX.png')
        self.pointer.scale = 0.25
        self.pointer.alpha = 200

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
        print('deleting ', obj)
        obj.kill()
        for joint in self.joints:
            print('step 1')
            if obj.pymunk_shape.body in [joint[-1].a, joint[-1].b]:
                self.joints.remove(joint)
                self.space.remove(joint[-1])
                if len(joint) == 2:
                    self.background_sprite_list.remove(joint[0])
                else:
                    for j in joint[:-1]:
                        self.background_sprite_list.remove(j)
        for pipe in self.pipes:
            if pipe.pymunk_shape == obj.pymunk_shape:
                self.pipes.remove(pipe)
        self.space.remove(obj.pymunk_shape, obj.pymunk_shape.body)
        print('deleted ', obj)

    def clear_variables(self):  # just a holder function to clear everything
        self.point_pair = None
        self.shape_being_dragged = None
        self.mouse_down = False
        self.mouse_button = None
        self.shape_a = None
        self.shape_a_connection_point = None

    def on_draw(self):
        arcade.start_render()

        draw_start_time = timeit.default_timer()
        self.background_sprite_list.draw()
        self.sprite_list.draw()
        if self.point_pair and self.mouse_down and self.point_pair != self.mouse_pos:
            if self.mouse_button == 4:
                arcade.draw_line(color=arcade.color.GREEN, start_x=self.point_pair[0], start_y=self.point_pair[1], end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], line_width=2)
            elif self.mouse_button == 1 and self.object_mode < 4:
                arcade.draw_line(color=arcade.color.RED, start_x=self.point_pair[0], start_y=self.point_pair[1], end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], line_width=2)
            elif self.mouse_button == 1:
                arcade.draw_line(color=arcade.color.BLUE, start_x=self.point_pair[0], start_y=self.point_pair[1], end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], line_width=2)

        output = f"Processing time: {self.processing_time*1000:.0f}"
        arcade.draw_text(output, 20, SCREEN_HEIGHT - 20, arcade.color.WHITE)

        output = f"Drawing time: {self.draw_time*1000:.0f}"
        arcade.draw_text(output, 20, SCREEN_HEIGHT - 40, arcade.color.WHITE)
        arcade.draw_text(text=f"{GAME_MODES[self.game_mode]}", start_x=400, start_y=32, color=arcade.color.WHITE, font_size=16, align='right')

        arcade.draw_text(text=f"{OBJECT_MODES[self.object_mode]}", start_x=20, start_y=32, color=arcade.color.WHITE, font_size=16, align='right')
        arcade.draw_text(text=f"{JOINT_MODES[self.joint_mode]}", start_x=100, start_y=32, color=arcade.color.WHITE, font_size=16, align='right')

        if self.grid:
            self.pointer.position = self.mouse_pos
            self.pointer.draw()

        self.draw_time = timeit.default_timer() - draw_start_time

    def make_circle(self, pos, vel=(0, 0)):
        size = GRID
        mass = 12.0
        moment = pymunk.moment_for_circle(mass, 0, size, (0, 0))
        body = pymunk.Body(mass, moment)
        body.position = pymunk.Vec2d(pos)
        body.velocity = vel
        shape = pymunk.Circle(body, size, pymunk.Vec2d(0, 0))
        shape.friction = FRICTION
        shape.elasticity = 0.3
        self.space.add(body, shape)
        shape.filter = pymunk.ShapeFilter(mask=0b0001, categories=0b0001)
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
        shape.filter = pymunk.ShapeFilter(mask=0b0001, categories=0b0001)
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
        shape.filter = pymunk.ShapeFilter(mask=0b0010, categories=0b0010)
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
        shape.filter = pymunk.ShapeFilter(mask=0b0010, categories=0b0010)
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
        sprite = BoxSprite(shape, "images/boxCrate_double.png", width=size, height=size)
        self.sprite_list.append(sprite)

    def make_pin_joint(self, shape_a, shape_b, point_a, point_b):
        try:
            length = self.ol_pythag(point_a, point_b) / 2
        except TypeError:
            return
        vertices = ((length, 2), (length, -2), (-length, -2), (-length, 2))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(point_a[0] + (point_b[0] - point_a[0]) / 2, point_a[1] + (point_b[1] - point_a[1]) / 2)
        shape = pymunk.Poly(body, vertices)
        body.angle = math.atan2(point_b[1] - point_a[1], point_b[0] - point_a[0])
        sprite = BoxSprite(shape, "images/wood_joint.png", width=length * 2, height=4)
        self.background_sprite_list.append(sprite)
        joint = pymunk.PinJoint(shape_a.body, shape_b.body, shape_a.body.world_to_local(point_a), shape_b.body.world_to_local(point_b))
        self.joints.append((sprite, joint))
        self.space.add(joint)

    def make_slide_joint(self, shape_a, shape_b, point_a, point_b):

        joint_len = self.ol_pythag(shape_a.body.position, shape_b.body.position)

        vertices = ((0, 2), (0, -2), (-joint_len, -2), (-joint_len, 2))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(point_a[0] + (point_b[0] - point_a[0]) / 2, point_a[1] + (point_b[1] - point_a[1]) / 2)
        body.angle = math.atan2(point_b[1] - point_a[1], point_b[0] - point_a[0])
        shape = pymunk.Poly(body, vertices)
        sprite_a = BoxSprite(shape, "images/wood_joint.png", width=joint_len * 2, height=4)
        self.background_sprite_list.append(sprite_a)

        vertices = ((joint_len, 2), (joint_len, -2), (0, -2), (0, 2))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(point_a[0] + (point_b[0] - point_a[0]) / 2, point_a[1] + (point_b[1] - point_a[1]) / 2)
        body.angle = math.atan2(point_b[1] - point_a[1], point_b[0] - point_a[0])
        shape = pymunk.Poly(body, vertices)
        sprite_b = BoxSprite(shape, "images/brickGrey.png", width=joint_len * 2, height=4)
        self.background_sprite_list.append(sprite_b)

        joint = pymunk.SlideJoint(shape_a.body, shape_b.body, shape_a.body.world_to_local(point_a), shape_b.body.world_to_local(point_b), min=joint_len, max=joint_len * 2)
        self.space.add(joint)
        self.joints.append((sprite_a, sprite_b, joint))

    def make_line(self, start, end):
        line_len = self.ol_pythag(start, end) / 2
        verticies = ((line_len, 1), (line_len, -2), (-line_len, -2), (-line_len, 1))
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(start[0] + (end[0] - start[0]) / 2, start[1] + (end[1] - start[1]) / 2)
        body.angle = math.atan2(end[1] - start[1], end[0] - start[0])
        shape = pymunk.Poly(body, verticies)
        shape.friction = FRICTION
        shape.elasticity = 0.95
        sprite = BoxSprite(shape, "images/line.png", width=line_len * 2, height=3)

        self.space.add(body, shape)
        self.background_sprite_list.append(sprite)

    def get_shape(self, pos):
        shape_list = self.space.point_query(pos, 2, pymunk.ShapeFilter(mask=0b01111, categories=0b01111))
        if shape_list:
            for sprite in self.sprite_list:
                if sprite.pymunk_shape == shape_list[0].shape:
                    return sprite
            for sprite in self.background_sprite_list:
                if sprite.pymunk_shape == shape_list[0].shape:
                    return sprite
        return None

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        self.mouse_down = True
        self.mouse_button = button
        self.point_pair = self.mouse_pos
        cur_shape = self.get_shape(self.mouse_pos)
        if button == 1:
            if modifiers in [0, 16]:
                if cur_shape:
                    self.mouse_down = False
                    self.shape_being_dragged = cur_shape
                    print('cool')
                else:
                    self.mouse_down = True
            elif cur_shape:
                self.delete_object(cur_shape)
        elif button == 4 and cur_shape:
            self.shape_a = cur_shape.pymunk_shape
            self.shape_a_connection_point = self.mouse_pos

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int):
        cur_shape = self.get_shape(self.mouse_pos)
        if self.mouse_down:
            if self.mouse_button == 1 and modifiers in [0, 16]:
                vel = ((self.point_pair[0] - self.mouse_pos[0]) * 4, (self.point_pair[1] - self.mouse_pos[1]) * 4)
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
            elif button == 4 and cur_shape and type(cur_shape.pymunk_shape) in [pymunk.shapes.Circle, pymunk.shapes.Poly]:  # add clause to ignore line polygons
                cur_shape.pymunk_shape.velocity = 0, 0
                if self.joint_mode == 0:
                    self.make_pin_joint(self.shape_a, cur_shape.pymunk_shape, self.shape_a_connection_point, self.mouse_pos)
                elif self.joint_mode == 1:
                    self.make_slide_joint(self.shape_a, cur_shape.pymunk_shape, self.shape_a_connection_point, self.mouse_pos)
            elif self.mouse_button == 4:
                self.make_line(self.point_pair, self.mouse_pos)
        self.clear_variables()

    def on_mouse_motion(self, x, y, dx, dy):
        if self.snapping:
            if self.point_pair:
                if abs(self.rr(x) - self.point_pair[0]) < abs(self.rr(y) - self.point_pair[1]):
                    self.mouse_pos = self.point_pair[0], self.rr(y)
                else:
                    self.mouse_pos = self.rr(x), self.point_pair[1]
            else:
                self.mouse_pos = self.rr(x), self.rr(y)
        else:
            self.mouse_pos = self.rr(x), self.rr(y)
        if self.mouse_button == 2 and self.mouse_down:
            self.move_everybody((dx, dy))

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
        if not self.game_mode == 1:
            self.tick += 1

            if self.tick % 60 == 0:
                for pipe in self.pipes:
                    if pipe.pymunk_shape.body.body_type == 0:
                        pipe.pymunk_shape.body.velocity = -pipe.pipe_vel[0], -pipe.pipe_vel[1]
                    self.make_circle(pipe.pymunk_shape.body.position, pipe.pipe_vel)

        self.space.step(1 / 60.0)

        if self.shape_being_dragged:
            self.shape_being_dragged.pymunk_shape.body.position = self.mouse_pos
            self.shape_being_dragged.pymunk_shape.body.velocity = 0, 0

        for sprite in self.sprite_list:
            sprite.center_x = sprite.pymunk_shape.body.position.x
            sprite.center_y = sprite.pymunk_shape.body.position.y
            sprite.angle = math.degrees(sprite.pymunk_shape.body.angle)
            if not(-SCREEN_WIDTH * 9 < sprite.pymunk_shape.body.position.y < SCREEN_WIDTH * 10) or not(-SCREEN_HEIGHT * 9 < sprite.pymunk_shape.body.position.y < SCREEN_HEIGHT * 10):
                cur_shape = self.get_shape(sprite.pymunk_shape.body.position)
                self.delete_object(cur_shape)
        for sprite in self.background_sprite_list:
            sprite.center_x = sprite.pymunk_shape.body.position.x
            sprite.center_y = sprite.pymunk_shape.body.position.y
            sprite.angle = math.degrees(sprite.pymunk_shape.body.angle)
            if not(-SCREEN_WIDTH * 9 < sprite.pymunk_shape.body.position.y < SCREEN_WIDTH * 10) or not(-SCREEN_HEIGHT * 9 < sprite.pymunk_shape.body.position.y < SCREEN_HEIGHT * 10):
                cur_shape = self.get_shape(sprite.pymunk_shape.body.position)
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
                start = joint[2].a.local_to_world(joint[2].anchor_a)
                end = joint[2].b.local_to_world(joint[2].anchor_b)
                joint[0].center_x = start[0] + (end[0] - start[0]) / 4
                joint[0].center_y = start[1] + (end[1] - start[1]) / 4
                joint[0].width = min(joint[2].min, self.ol_pythag(start, end))
                joint[0].angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))

                joint[1].center_x = start[0] + ((end[0] - start[0]) * 3) / 4
                joint[1].center_y = start[1] + ((end[1] - start[1]) * 3) / 4
                joint[1].width = joint[2].min
                joint[1].angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))

        self.processing_time = timeit.default_timer() - start_time


if __name__ == '__main__':
    window = Careenium(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    arcade.run()



