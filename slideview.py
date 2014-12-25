#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2012 Agustin Zubiaga <aguz@sugarlabs.org>
# Copyright (C) 2014 Sam Parkinson <sam@sugarlabs.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


from gi.repository import Gtk
from gi.repository import GObject

from sugar3.graphics import style
from sugar3.graphics.icon import Icon


class SlideView(Gtk.EventBox):

    def __init__(self, activity):
        Gtk.EventBox.__init__(self)

        self._area = Gtk.DrawingArea()
        self._area.connect('draw', self._area_draw_cb)

        self._boxes = []
        self._current_box = None
        self._timeout_id = None

        prev_btn = Gtk.EventBox()
        prev_btn.connect('button-press-event', self._prev_slide)
        self._prev_icon = Icon(pixel_size=100)
        self._prev_icon.props.icon_name = 'go-previous'
        prev_btn.add(self._prev_icon)

        next_btn = Gtk.EventBox()
        next_btn.connect('button-press-event', self._next_slide)
        self._next_icon = Icon(pixel_size=100)
        self._next_icon.props.icon_name = 'go-next'
        next_btn.add(self._next_icon)

        hbox = Gtk.Box()
        hbox.set_border_width(10)
        hbox.pack_start(prev_btn, True, False, 0)
        hbox.pack_start(self._area, False, False, 0)
        hbox.pack_end(next_btn, True, False, 0)

        self.add(hbox)

        self.show_all()

    def _area_draw_cb(self, widget, context):
        if self._current_box is None:
            return

        box = self._boxes[self._current_box]
        self._area.set_size_request(box.width + 1, box.height + 1)

        context.move_to(box.width - style.zoom(40),
                        box.height + style.zoom(25))
        context.set_font_size(style.zoom(20))
        context.show_text('%s/%s' % (self._current_box + 1,
                                     str(len(self._boxes))))

        if self._current_box == len(self._boxes) - 1:
            self._next_icon.set_fill_color(style.COLOR_BUTTON_GREY.get_html())
        else:
            self._next_icon.set_fill_color(None)

        if self._current_box == 0:
            self._prev_icon.set_fill_color(style.COLOR_BUTTON_GREY.get_html())
        else:
            self._prev_icon.set_fill_color(None)

        box.draw_in_context(context)

    def set_boxes(self, boxes):
        # Discard the title box
        self._boxes = boxes[1:]

    def set_current_box(self, box):
        self._current_box = box
        self._area.queue_draw()

    def start(self, use_timings):
        if not use_timings:
            self._prev_icon.show()
            self._next_icon.show()
            return

        self._prev_icon.hide()
        self._next_icon.hide()

        box = self._boxes[self._current_box]
        duration = box.slideshow_duration
        self._timeout_id = \
            GObject.timeout_add_seconds(duration, self.__slideshow_timeout_cb)

    def stop(self):
        if self._timeout_id:
            GObject.source_remove(self._timeout_id)

    def __slideshow_timeout_cb(self, *args):
        if self._current_box + 1 > len(self._boxes) - 1:
            return False

        self._current_box += 1
        self._area.queue_draw()

        box = self._boxes[self._current_box]
        duration = box.slideshow_duration
        self._timeout_id = \
            GObject.timeout_add_seconds(duration, self.__slideshow_timeout_cb)
        return False

    def _next_slide(self, widget, event):
        self._current_box += 1
        if self._current_box > len(self._boxes) - 1:
            self._current_box -= 1
        self._area.queue_draw()

    def _prev_slide(self, widget, event):
        self._current_box -= 1
        if self._current_box < 0:
            self._current_box += 1
        self._area.queue_draw()

    def key_press_cb(self, widget, event):
        if event.keyval == 65361:
            self._prev_slide(None, None)

        elif event.keyval == 65363:
            self._next_slide(None, None)
