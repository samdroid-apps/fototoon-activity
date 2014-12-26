# -*- coding: UTF-8 -*-

import os
import tempfile
import shutil
import cairo
import dbus
import logging
from gettext import gettext as _
import time

from gi.repository import Gst
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf

from sugar3.activity import activity
from sugar3.graphics.toolbarbox import ToolbarBox, ToolbarButton
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics.toolbutton import ToolButton
from sugar3.datastore import datastore
from sugar3 import profile
from sugar3.graphics import style
from sugar3.graphics.alert import Alert
from sugar3.graphics.icon import Icon
from sugar3.graphics.palette import Palette

import globos
import persistencia
from toolbar import TextToolbar
from toolbar import GlobesManager
from slideview import SlideView
from reorderwindow import ReorderView
from reorderwindow import ImageEditorView


DEFAULT_TIME = 10
MIN_TIME = 1
MAX_TIME = 60

VIDEO_PIPELINE = ('multifilesrc location="{}" index=0 '
                  'caps="image/png,framerate=\(fraction\)1/1" '
                  '! pngdec ! videoconvert ! videorate ! theoraenc '
                  '! oggmux ! filesink location={}')


class HistorietaActivity(activity.Activity):

    _EXPORT_FORMATS = [['image/png', _('Save as Image'), _('PNG'), ""]]

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self.set_title('FotoToon')

        self._max_participants = 1

        toolbar_box = ToolbarBox()
        activity_button = ActivityToolbarButton(self)
        activity_toolbar = activity_button.page
        toolbar_box.toolbar.insert(activity_button, 0)

        edit_toolbar_btn = ToolbarButton()
        edit_toolbar = Gtk.Toolbar()
        edit_toolbar_btn.props.page = edit_toolbar
        edit_toolbar_btn.props.icon_name = 'toolbar-edit'
        edit_toolbar_btn.label = _('Edit')
        toolbar_box.toolbar.insert(edit_toolbar_btn, -1)

        view_toolbar_btn = ToolbarButton()
        view_toolbar = Gtk.Toolbar()
        view_toolbar_btn.props.page = view_toolbar
        view_toolbar_btn.props.icon_name = 'toolbar-view'
        view_toolbar_btn.label = _('View')
        toolbar_box.toolbar.insert(view_toolbar_btn, -1)

        slideview_btn = ToggleToolButton('slideshow')
        slideview_btn.set_tooltip(_('Slideshow'))
        slideview_btn.set_active(False)
        slideview_btn.connect('clicked', self._switch_view_mode, False)
        view_toolbar.insert(slideview_btn, -1)
        slideview_btn.show()

        slideview_timings_btn = ToggleToolButton('slideshow-stopwatch')
        slideview_timings_btn.set_tooltip(_('Slideshow with Timings'))
        slideview_timings_btn.set_active(False)
        slideview_timings_btn.connect('clicked', self._switch_view_mode, True)
        view_toolbar.insert(slideview_timings_btn, -1)
        slideview_timings_btn.show()

        time_button = ToolButton('stopwatch')
        time_button.set_tooltip(_('Set Image Duration in Slideshow (Seconds)'))
        view_toolbar.insert(time_button, -1)
        time_button.show()

        self._time_spin = Gtk.SpinButton.new_with_range(MIN_TIME, MAX_TIME, 1)
        self._time_spin.connect('value-changed', self.__time_spin_changed_cb)
        self._time_spin.props.value = DEFAULT_TIME
        self._time_spin.props.update_policy = \
            Gtk.SpinButtonUpdatePolicy.IF_VALID

        palette = time_button.get_palette()
        palette.connect('popup', self.__time_button_popup_cb)
        time_button.connect('clicked', lambda *args:
            palette.popup(immediate=True, state=Palette.SECONDARY))

        alignment = Gtk.Alignment()
        alignment.set_padding(style.DEFAULT_PADDING, style.DEFAULT_PADDING,
                              style.DEFAULT_PADDING, style.DEFAULT_PADDING)
        alignment.add(self._time_spin)
        self._time_spin.show()
        palette.set_content(alignment)
        alignment.show()

        fullscreen_btn = ToolButton('view-fullscreen')
        fullscreen_btn.set_tooltip(_('Fullscreen'))
        fullscreen_btn.props.accelerator = '<Alt>Return'
        fullscreen_btn.connect('clicked', lambda w: self.fullscreen())
        view_toolbar.insert(fullscreen_btn, -1)
        fullscreen_btn.show()

        self.set_toolbar_box(toolbar_box)

        toolbar = toolbar_box.toolbar

        self.page = Page()

        self.globes_manager = GlobesManager(toolbar, edit_toolbar, self)

        # fonts
        self._text_button = ToolbarButton()
        self._text_button.props.page = TextToolbar(self.page)
        self._text_button.props.icon_name = 'format-text-size'
        self._text_button.props.label = _('Text')
        self._toolbar_box.toolbar.insert(self._text_button, -1)

        reorder_img_btn = ToolButton('thumbs-view')
        reorder_img_btn.set_icon_name('thumbs-view')
        reorder_img_btn.set_tooltip(_('Change image order'))
        reorder_img_btn.connect('clicked', self.__image_order_cb)
        edit_toolbar.insert(reorder_img_btn, -1)
        reorder_img_btn.show()

        bgchange = ToolButton(icon_name='contract-coordinates')
        bgchange.set_tooltip(_('Edit background image'))
        bgchange.connect('clicked', self.__bgchange_clicked_cb)
        edit_toolbar.insert(bgchange, -1)
        bgchange.show()

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)

        toolbar_box.toolbar.insert(separator, -1)

        stop = StopButton(self)
        toolbar_box.toolbar.insert(stop, -1)

        toolbar_box.show_all()

        # add export button

        separator_2 = Gtk.SeparatorToolItem()
        separator_2.show()
        activity_toolbar.insert(separator_2, -1)

        self.bt_save_as_image = ToolButton()
        self.bt_save_as_image.props.icon_name = 'save-as-image'
        self.bt_save_as_image.connect('clicked', self.write_image)
        self.bt_save_as_image.set_tooltip(_('Save as Image'))
        activity_toolbar.insert(self.bt_save_as_image, -1)
        self.bt_save_as_image.show()

        save_as_pdf = ToolButton()
        save_as_pdf.props.icon_name = 'save-as-pdf'
        save_as_pdf.connect('clicked', self._save_as_pdf)
        save_as_pdf.set_tooltip(_('Save as a Book (PDF)'))
        activity_toolbar.insert(save_as_pdf, -1)
        save_as_pdf.show()

        save_as_ogg = ToolButton()
        save_as_ogg.props.icon_name = 'save-as-ogg'
        save_as_ogg.connect('clicked', self.__save_as_ogg_cb)
        save_as_ogg.set_tooltip(_('Save as a Movie (OGG)'))
        activity_toolbar.insert(save_as_ogg, -1)
        save_as_ogg.show()

        activity_button.page.title.connect("focus-in-event", self.on_title)

        scrolled = Gtk.ScrolledWindow()
        #scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        scrolled.add_with_viewport(self.page)
        scrolled.set_kinetic_scrolling(False)
        scrolled.show_all()

        self._slideview = SlideView(self)
        self._slideview.show_all()

        self._notebook = Gtk.Notebook()
        self._notebook.set_show_tabs(False)
        self._notebook.append_page(scrolled, None)
        self._notebook.append_page(self._slideview, None)
        self._notebook.show_all()

        self.set_canvas(self._notebook)
        self.show()
        self.metadata['mime_type'] = 'application/x-fototoon-activity'

        self.page.empty_page = handle.object_id is None
        self._key_press_signal_id = None

    def on_title(self, widget, event):
        # unselect the active globe when editting the title
        logging.debug('Editing the title')
        if self.page.get_active_box() is not None:
            box = self.page.get_active_box()
            self.page.set_active_box(None)
            box.glob_press = False
            box.set_globo_activo(None)
            box.redraw()

            logging.debug('After edit the title')

    def write_file(self, file_path):
        self._commit_all_changes()
        persistence = persistencia.Persistence()
        persistence.write(file_path, self.page)

    def _commit_all_changes(self):
        # be sure all the changes are commited
        active_globe = self.page.get_globo_activo()
        if active_globe is not None:
            active_globe.set_selected(False)

    def read_file(self, file_path):
        persistence = persistencia.Persistence()
        persistence.read(file_path, self.page)

    def _get_image_size(self):
        image_height, image_width = 0, 0
        posi = 0
        for box in self.page.boxs:
            if posi > 0:
                try:
                    reng = int((posi + 1) / 2)
                    column = (posi + 1) - (reng * 2)
                    #logging.error("reng %d column %d" % (reng, column))
                    if column == 0:
                        image_height = image_height + box.height
                except:
                    pass
            else:
                image_width = box.width
                image_height = image_height + box.height
            # hide the cursor
            for globe in box.globos:
                globe.set_selected(False)

            posi = posi + 1

        return image_width, image_height

    def write_image(self, button):
        self._commit_all_changes()
        # calculate image size
        image_width, image_height = self._get_image_size()

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                     image_width + 1, image_height + 1)
        ctx = cairo.Context(surface)

        ctx.set_source_rgb(1, 1, 1)
        ctx.rectangle(0, 0, image_width + 1, image_height + 1)
        ctx.fill()

        posi = 0
        y_posi = 0
        for box in self.page.boxs:

            if posi > 0:
                try:
                    reng = int((posi + 1) / 2)
                    column = (posi + 1) - (reng * 2)
                    ctx.rectangle(column * box.width, y_posi,
                                  (column + 1) * box.width,
                                  y_posi + box.height)
                    ctx.set_source_rgb(0, 0, 0)
                    ctx.stroke()
                    ctx.translate(column * box.width, y_posi)
                    box.draw_in_context(ctx)
                    ctx.translate(column * box.width * - 1, y_posi * - 1)
                    if column == 1:
                        y_posi = y_posi + box.height
                except:
                    pass
            else:
                box.draw_in_context(ctx)
                y_posi = box.height

            posi = posi + 1

        temp_file_name = os.path.join(self.get_activity_root(), 'instance',
                                      'tmp-%i.png' % time.time())

        surface.write_to_png(temp_file_name)

        self.dl_jobject = datastore.create()

        self.dl_jobject.metadata['progress'] = '0'
        self.dl_jobject.metadata['keep'] = '0'
        self.dl_jobject.metadata['buddies'] = ''
        self.dl_jobject.metadata['icon-color'] = \
            profile.get_color().to_string()
        self.dl_jobject.metadata['mime_type'] = 'image/png'

        self.dl_jobject.metadata['title'] = \
            self._jobject.metadata['title'] + " as image"
        self.dl_jobject.metadata['description'] = ""
        self.dl_jobject.metadata['progress'] = '100'
        self.dl_jobject.file_path = temp_file_name

        self.dl_jobject.metadata['preview'] = \
            self._get_preview_image(temp_file_name)

        datastore.write(self.dl_jobject, transfer_ownership=True)
        self._object_id = self.dl_jobject.object_id
        self._show_journal_alert(_('Success'),
                                 _('A image was created in the Journal'))

    def __image_order_cb(self, button):
        reorderwin = ReorderView(self)
        reorderwin.show_all()

    def __bgchange_clicked_cb(self, button):
        editorwin = ImageEditorView(self.page.get_active_box())
        editorwin.show_all()

    def _save_as_pdf(self, widget):
        self._commit_all_changes()

        file_name = os.path.join(self.get_activity_root(), 'instance',
                                 'tmp-%i.pdf' % time.time())
        file_obj = open(file_name, 'w')

        page_width = self.page.boxs[1].width
        page_height = self.page.boxs[1].height

        surface = cairo.PDFSurface(file_obj, page_width, page_height)

        context = cairo.Context(surface)

        for box in self.page.boxs[0:]:
            context.save()
            if box.width != page_width:
                # for the first box, scale and center
                scale = float(page_width) / float(box.width)
                top_margin = (page_height - box.height) / 2
                context.translate(0, top_margin)
                context.scale(scale, scale)

            box.draw_in_context(context)
            context.show_page()
            context.restore()

        surface.finish()
        file_obj.close()

        jobject = datastore.create()
        jobject.metadata['icon-color'] = \
            profile.get_color().to_string()
        jobject.metadata['mime_type'] = 'application/pdf'

        jobject.metadata['title'] = \
            self.metadata['title'] + " as book"
        jobject.file_path = file_name

        #jobject.metadata['preview'] = \
        #    self._get_preview_image(file_name)

        datastore.write(jobject, transfer_ownership=True)
        self._object_id = jobject.object_id

        self._show_journal_alert(_('Success'),
                                 _('A PDF was created in the Journal'))

    def __save_as_ogg_cb(self, button):
        self._commit_all_changes()

        directory = tempfile.mkdtemp()
        output_path = os.path.join(directory, 'output.ogv')

        width = self.page.boxs[1].width
        height = self.page.boxs[1].height

        i = 0
        for box in self.page.boxs[1:]:
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
            context = cairo.Context(surface)
            box.draw_in_context(context)

            for __ in range(int(box.slideshow_duration)):
                path = os.path.join(directory, '{}.png'.format(i))
                surface.write_to_png(path)
                i += 1

        Gst.init(None)
        pipeline_string = VIDEO_PIPELINE.format(
            os.path.join(directory, '%d.png'), output_path)
        pipeline = Gst.parse_launch(pipeline_string)

        pipeline.set_state(Gst.State.PLAYING)
        pipeline.get_bus().timed_pop_filtered(
            Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)
        pipeline.set_state(Gst.State.NULL)

        jobject = datastore.create()
        jobject.metadata['icon-color'] = profile.get_color().to_string()
        jobject.metadata['mime_type'] = 'video/ogg'
        jobject.metadata['title'] = \
             _('{} as a movie').format(self.metadata['title'])
        jobject.file_path = output_path

        datastore.write(jobject, transfer_ownership=True)
        self._object_id = jobject.object_id

        self._show_journal_alert(_('Success'),
                                 _('A movie was saved in the Journal'))


    def _show_journal_alert(self, title, msg):
        _stop_alert = Alert()
        _stop_alert.props.title = title
        _stop_alert.props.msg = msg
        _stop_alert.add_button(Gtk.ResponseType.APPLY,
                               _('Show in Journal'),
                               Icon(icon_name='zoom-activity'))
        _stop_alert.add_button(Gtk.ResponseType.OK, _('Ok'),
                               Icon(icon_name='dialog-ok'))
        # Remove other alerts
        for alert in self._alerts:
            self.remove_alert(alert)

        self.add_alert(_stop_alert)
        _stop_alert.connect('response', self.__stop_response_cb)
        _stop_alert.show_all()

    def __stop_response_cb(self, alert, response_id):
        if response_id is Gtk.ResponseType.APPLY:
            activity.show_object_in_journal(self._object_id)
        self.remove_alert(alert)

    def _get_preview_image(self, file_name):
        preview_width, preview_height = style.zoom(300), style.zoom(225)

        pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_name)
        width, height = pixbuf.get_width(), pixbuf.get_height()

        scale = 1
        if (width > preview_width) or (height > preview_height):
            scale_x = preview_width / float(width)
            scale_y = preview_height / float(height)
            scale = min(scale_x, scale_y)

        pixbuf2 = GdkPixbuf.Pixbuf.new(
            GdkPixbuf.Colorspace.RGB, pixbuf.get_has_alpha(),
            pixbuf.get_bits_per_sample(), preview_width, preview_height)
        pixbuf2.fill(style.COLOR_WHITE.get_int())

        margin_x = int((preview_width - (width * scale)) / 2)
        margin_y = int((preview_height - (height * scale)) / 2)

        pixbuf.scale(pixbuf2, margin_x, margin_y,
                     preview_width - (margin_x * 2),
                     preview_height - (margin_y * 2),
                     margin_x, margin_y, scale, scale,
                     GdkPixbuf.InterpType.BILINEAR)

        succes, preview_data = pixbuf2.save_to_bufferv('png', [], [])
        return dbus.ByteArray(preview_data)

    def _switch_view_mode(self, widget, use_timings):
        if widget.get_active():
            self._notebook.set_current_page(1)
            self._slideview.stop()
            self._slideview.set_boxes(self.page.boxs)
            self._slideview.set_current_box(0)
            self._slideview.start(use_timings)
            #disable edition mode in the globes
            for box in self.page.boxs:
                box.set_globo_activo(None)

            self._key_press_signal_id = self.connect(
                'key_press_event', self._slideview.key_press_cb)
        else:
            self._slideview.stop()
            self._notebook.set_current_page(0)
            if self._key_press_signal_id is not None:
                self.disconnect(self._key_press_signal_id)
        self.globes_manager.set_buttons_sensitive(not widget.get_active())
        self._text_button.set_sensitive(not widget.get_active())

    def __time_button_popup_cb(self, palette):
        self._time_spin.props.value = \
            self.page.get_active_box().slideshow_duration

    def __time_spin_changed_cb(self, button):
        self.page.get_active_box().slideshow_duration = \
            self._time_spin.props.value


DEF_SPACING = 6
DEF_WIDTH = 4

SCREEN_HEIGHT = Gdk.Screen.height()
# HACK: This is to calculate the scrollbar width
# defined in sugar-artwork gtk-widgets.css.em
if style.zoom(1):
    scrollbar_width = 15
else:
    scrollbar_width = 11

SCREEN_WIDTH = Gdk.Screen.width() - scrollbar_width - 5
BOX_HEIGHT = 450

THUMB_SIZE = activity.PREVIEW_SIZE


class Page(Gtk.VBox):

    def __init__(self):
        Gtk.VBox.__init__(self, False, 0)

        self._internal_box = Gtk.VBox()

        self.set_homogeneous(False)

        self.boxs = []
        self._active_box = None
        self.selected_font_name = globos.DEFAULT_FONT

        logging.error('SCREEN WIDTH %d DEF_SPACING %d', SCREEN_WIDTH,
                      DEF_SPACING)

        # Add title box
        self.title_box = ComicBox(self, None, 0)
        self.title_box.set_size_request(SCREEN_WIDTH, 100)
        self.title_box.width, self.title_box.height = SCREEN_WIDTH, 100
        self._internal_box.pack_start(self.title_box, False, False, 0)
        self.set_active_box(self.title_box)
        self.boxs.append(self.title_box)

        # Add a table for the other boxes
        self.table = Gtk.Table(10, 2, True)
        self.table.set_homogeneous(True)
        self.table.set_row_spacings(DEF_SPACING)
        self.table.set_col_spacings(DEF_SPACING)
        self._internal_box.pack_start(self.table, False, False, 0)
        self.pack_start(self._internal_box, True, True, 0)
        self.show_all()

    def add_box_from_journal_image(self, image_file_name, x=0, y=0,
                                   w=-1, h=-1):
        posi = len(self.boxs) - 1
        box = ComicBox(self, image_file_name, posi + 1, x, y, w, h)
        reng = int(posi / 2)
        column = posi - (reng * 2)

        self.table.attach(box, column, column + 1, reng, reng + 1)
        self.set_active_box(box)
        self.boxs.append(box)

    def set_active_box(self, box):
        if self._active_box == box:
            return
        box_anterior = None
        if self._active_box is not None:
            box_anterior = self._active_box
        self._active_box = box
        if box is not None:
            box.redraw()
        if box_anterior is not None:
            for g in box_anterior.globos:
                g.set_selected(False)
            box_anterior.redraw()

    def get_active_box(self):
        return self._active_box

    def get_globo_activo(self):
        box = self.get_active_box()
        if box is not None:
            if box.get_globo_activo() is not None:
                return box.get_globo_activo()
        return None


class ComicBox(Gtk.EventBox):

    def __init__(self, page, image_file_name, posi,
                 x=0, y=0, width=0, height=0):
        Gtk.EventBox.__init__(self)

        self.img_x = x
        self.img_y = y
        self.img_w = width
        self.img_h = height

        self._page = page
        self.modify_bg(Gtk.StateType.NORMAL,
                       style.COLOR_WHITE.get_gdk_color())

        self.fixed = Gtk.Fixed()
        self.add(self.fixed)
        self._drawingarea = Gtk.DrawingArea()
        self.fixed.put(self._drawingarea, 0, 0)

        self._drawingarea.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.BUTTON_MOTION_MASK)

        #self.globos is a list with the globes in the box
        self.globos = []
        self.posi = posi

        self.glob_press = False
        self.is_dimension = False
        self.is_punto = False
        self.image_name = ''
        self.image = None
        self.image_saved = False
        self.title_globe = None
        self.thumbnail = None
        self.slideshow_duration = DEFAULT_TIME

        self.width = (int)(SCREEN_WIDTH - DEF_SPACING) / 2
        self.height = BOX_HEIGHT

        if image_file_name is not None:
            logging.error('seting image_name %s', image_file_name)
            self.image_name = image_file_name

        self._globo_activo = None

        self._drawingarea.connect("draw", self.draw_cb)
        self.connect("button_press_event", self.pressing)
        self.connect("motion_notify_event", self.mouse_move)
        self.connect("motion_notify_event", self.moving)
        self.connect("button_release_event", self.releassing)
        self.redraw()

        def size_allocate(widget, allocation):
            self.fixed.set_size_request(self.width, self.height)
            self._drawingarea.set_size_request(self.width, self.height)

        self.connect('size_allocate', size_allocate)
        self.set_size_request(self.width, self.height)
        self._drawingarea.set_size_request(self.width, self.height)
        self.fixed.set_size_request(self.width, self.height)
        self.show_all()

    def set_globo_activo(self, globo):
        if self._globo_activo is not None and self._globo_activo != globo:
            self._globo_activo.set_selected(False)
        if globo is not None:
            globo.set_selected(True)
        self._globo_activo = globo
        if globo is not None and globo.texto is not None:
            self._page._text_toolbar.setToolbarState(globo.texto)

    def redraw(self):
        self._drawingarea.queue_draw()

    def get_globo_activo(self):
        return self._globo_activo

    def add_globo(self, xpos, ypos, gmodo="normal",
                  gdireccion=globos.DIR_ABAJO,
                  font_name=globos.DEFAULT_FONT):
        globo = globos.Globo(self, x=xpos, y=ypos, modo=gmodo,
                             direccion=gdireccion, font_name=font_name)
        self.globos.append(globo)
        self._globo_activo = globo
        self.redraw()

    def add_rectangulo(self, xpos, ypos, font_name=globos.DEFAULT_FONT):
        self.globos.append(globos.Rectangulo(self, x=xpos, y=ypos,
                                             font_name=font_name))
        self.redraw()

    def add_nube(self, xpos, ypos, font_name=globos.DEFAULT_FONT):
        globo = globos.Nube(self, x=xpos, y=ypos, font_name=font_name)
        self.globos.append(globo)
        self._globo_activo = globo
        self.redraw()

    def add_imagen(self, imagen, xpos, ypos):
        globo = globos.Imagen(self, imagen, x=xpos, y=ypos)
        self.globos.append(globo)
        self._globo_activo = globo
        self.redraw()

    def add_grito(self, xpos, ypos, font_name=globos.DEFAULT_FONT):
        globo = globos.Grito(self, x=xpos, y=ypos, font_name=font_name)
        self.globos.append(globo)
        self._globo_activo = globo
        self.redraw()

    def draw_cb(self, widget, context):
        # check if is the title box and is a new page
        if self._page.title_box == self and self._page.empty_page:
            self._page.empty_page = False
            # select title box
            rect = self.get_allocation()
            x = rect.width / 2
            y = rect.height / 2
            self.add_rectangulo(x, y)
            self.title_globe = self.globos[0]
            self.title_globe.texto.set_text(_('Title:'))

        self.draw_in_context(context)
        return False

    def draw_in_context(self, ctx):
        # Draw the background image

        self.image_height = 0

        instance_path = os.path.join(activity.get_activity_root(),
                                     'instance')
        if self.image is None and (self.image_name != ''):
            # if the image path is inside the instance path,
            # was previously saved if not is from the journal
            if (not self.image_name.startswith(instance_path)):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(
                    os.path.join(instance_path, self.image_name))
            else:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.image_name)

            img_scaled = False
            if self.img_w == -1:
                self.img_w = self.width

                width_pxb = pixbuf.get_width()
                height_pxb = pixbuf.get_height()
                scale = (self.width) / (1.0 * width_pxb)
                self.img_h = int(scale * height_pxb)
                img_scaled = True

            self.pixbuf = pixbuf

            self.image = ctx.get_target().create_similar(
                cairo.CONTENT_COLOR_ALPHA, self.width, BOX_HEIGHT)

            pixb_scaled = pixbuf.scale_simple(
                int(self.img_w),
                int(self.img_h), GdkPixbuf.InterpType.BILINEAR)
            ct = cairo.Context(self.image)
            Gdk.cairo_set_source_pixbuf(ct, pixb_scaled,
                                        self.img_x, self.img_y)
            ct.paint()

            if (not self.image_saved) and img_scaled:
                self.image_saved = True
                image_file_name = 'image' + str(self.posi) + '.png'
                sav_img = ctx.get_target().create_similar(
                    cairo.CONTENT_COLOR_ALPHA, self.img_w, self.img_h)
                ct2 = cairo.Context(sav_img)
                Gdk.cairo_set_source_pixbuf(ct2, pixb_scaled, 0, 0)
                ct2.paint()
                sav_img.write_to_png(os.path.join(instance_path,
                                                  image_file_name))
                img_scaled = False

                # grabamos el nombre de la imagen sin el path
                self.image_name = image_file_name

        elif self._page.title_box != self:
            self.image = ctx.get_target().create_similar(
                cairo.CONTENT_COLOR_ALPHA, self.width, BOX_HEIGHT)

            pixb_scaled = self.pixbuf.scale_simple(
                int(self.img_w),
                int(self.img_h), GdkPixbuf.InterpType.BILINEAR)
            ct = cairo.Context(self.image)
            Gdk.cairo_set_source_pixbuf(ct, pixb_scaled,
                                        self.img_x, self.img_y)
            ct.paint()

        if self.image is not None:
            ctx.save()
            ctx.rectangle(0, 0, self.width, self.height)
            ctx.clip()
            ctx.set_source_surface(self.image, 0, 0)
            ctx.paint()
            ctx.restore()

        # Draw the border
        ctx.save()
        ctx.set_line_width(DEF_WIDTH)
        ctx.rectangle(0, 0, self.width, self.height)
        if (self._page.get_active_box() == self):
            ctx.set_source_rgb(1, 1, 1)
        else:
            ctx.set_source_rgb(0, 0, 0)
        ctx.stroke()
        ctx.set_source_rgb(0, 0, 0)
        ctx.restore()

        self.draw_globos(ctx)

    def get_thumbnail(self):
        if self.thumbnail is None:
            instance_path = os.path.join(activity.get_activity_root(),
                                         'instance')
            if (not self.image_name.startswith(instance_path)):
                self.thumbnail = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    os.path.join(instance_path, self.image_name),
                    THUMB_SIZE[0], THUMB_SIZE[1])
            else:
                self.thumbnail = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    self.image_name, THUMB_SIZE[0], THUMB_SIZE[1])
        return self.thumbnail

    def draw_globos(self, context):
        if len(self.globos) > 0:
            for g in self.globos:
                g.imprimir(context)

    def pressing(self, widget, event):
        # if is not the last box selected redraw this and the last
        # (possible optimization, draw only the border
        if (self._page.get_active_box() != self):
            self._page.set_active_box(self)

        #Check if clicked over a globe
        if self._globo_activo is not None:
            if self._globo_activo.is_selec_tam(event.x, event.y) or \
                    self._globo_activo.get_cursor_type(event.x, event.y) \
                    is not None:
                self.is_dimension = True
            elif self._globo_activo.is_selec_punto(event.x, event.y):
                self.is_punto = True

        if (not self.is_dimension) and not (self.is_punto):
            if self.globos:
                list_aux = self.globos[:]
                list_aux.reverse()
                for i in list_aux:
                    if i.is_selec(event.x, event.y):
                        self.glob_press = True
                        self.set_globo_activo(i)
                        self.redraw()
                        break

    def releassing(self, widget, event):
        self.glob_press = False
        self.is_dimension = False
        self.is_punto = False

    def mouse_move(self, widget, event):
        if self._globo_activo is not None:
            cursor_type = self._globo_activo.get_cursor_type(event.x, event.y)
            cursor = None
            if cursor_type is not None:
                cursor = Gdk.Cursor(cursor_type)
            self.get_window().set_cursor(cursor)

    def moving(self, widget, event):
        if self.is_dimension:
            self._globo_activo.set_dimension(event.x, event.y,
                                             self.get_allocation())
            self.redraw()
        elif self.is_punto:
            self._globo_activo.mover_punto(event.x, event.y,
                                           self.get_allocation())
            self.redraw()
        elif self.glob_press:
            self._globo_activo.mover_a(event.x, event.y,
                                       self.get_allocation())
            self.redraw()
