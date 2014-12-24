# -*- coding: utf-8 -*-
# copiado de la actividad write
# Copyright (C) 2006, Martin Sevior
# Copyright (C) 2006-2007, Marc Maurer <uwog@uwog.net>
# Copyright (C) 2007, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
from gettext import gettext as _
import logging
import os
import time

from gi.repository import Gtk, Gdk

from sugar3.graphics import style
from sugar3.graphics.palette import Palette
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics.toolcombobox import ToolComboBox
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palettemenu import PaletteMenuBox
from sugar3.graphics.colorbutton import ColorToolButton
from sugar3.graphics.objectchooser import ObjectChooser
try:
    from sugar3.graphics.objectchooser import FILTER_TYPE_GENERIC_MIME
except:
    FILTER_TYPE_GENERIC_MIME = 'generic_mime'

from fontcombobox import FontComboBox
from fontcombobox import FontSize
import globos


DEFAULT_TIME = 10
MIN_TIME = 1
MAX_TIME = 60


##Class to manage the Text Color
class TextButtonColor(ColorToolButton):
    ##The Constructor
    def __init__(self, page):
        ColorToolButton.__init__(self)
        self._page = page

        self.connect('color-set', self._color_button_cb)

    def _color_button_cb(self, widget):
        color = self.get_color()
        self.set_text_color(color)

    def set_text_color(self, color):
        globo_activo = self._page.get_globo_activo()
        if globo_activo is not None:
            texto = globo_activo.texto
            texto.color = (color.red, color.green, color.blue)
            self._page.get_active_box().redraw()


logger = logging.getLogger('fototoon-activity')


class GlobesManager():

    def __init__(self, toolbar, edit_toolbar, activity):

        self._page = activity.page
        self._activity = activity

        # agregar cuadro
        self.add_photo = ToolButton()
        self.add_photo.props.icon_name = 'insert-picture'
        self.add_photo.connect('clicked', self.__add_photo_clicked_cb)
        self.add_photo.set_tooltip(_('Add Photo'))
        toolbar.insert(self.add_photo, -1)

        self._globes = {
            'globe': _('Globe'), 'think': _('Think'),
            'whisper': _('Whisper'), 'exclamation': _('Exclamation'),
            'box': _('Box')}

        self._globes_menu = ToolButton(icon_name='globe')
        self._globes_menu.props.tooltip = _('Add a globe')
        self._globes_menu.props.hide_tooltip_on_click = False
        self._globes_menu.palette_invoker.props.toggle_palette = True

        menu_box = PaletteMenuBox()
        self._globes_menu.props.palette.set_content(menu_box)
        menu_box.show()

        for globe in self._globes.keys():
            menu_item = PaletteMenuItem(icon_name=globe,
                                        text_label=self._globes[globe])
            menu_item.connect('activate', self.__activate_add_globe_cb, globe)
            menu_box.append_item(menu_item)
            menu_item.show()
        toolbar.insert(self._globes_menu, -1)

        # lineas de movimiento
        # Agregar aqui el nombre de archivo de una linea de moviemiento
        self._lines = {
            'curves': _('Curves'), 'straight': _('Straight'),
            'highlight': _('Highlight'), 'idea': _('Idea')}

        self._lines_menu = ToolButton(icon_name='curves')
        self._lines_menu.props.tooltip = _('Choose a movement line')
        self._lines_menu.props.hide_tooltip_on_click = False
        self._lines_menu.palette_invoker.props.toggle_palette = True

        menu_box = PaletteMenuBox()
        self._lines_menu.props.palette.set_content(menu_box)
        menu_box.show()

        for line in self._lines.keys():
            menu_item = PaletteMenuItem(icon_name=line,
                                        text_label=self._lines[line])
            menu_item.connect('activate', self.__activate_add_line_cb, line)
            menu_box.append_item(menu_item)
            menu_item.show()
        toolbar.insert(self._lines_menu, -1)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        toolbar.insert(separator, -1)

        # girar
        self.b_girar = ToolButton('object-rotate-right')
        self.b_girar.connect('clicked', self.girar)
        self.b_girar.set_tooltip(_('Turn'))
        self.b_girar.show()
        edit_toolbar.insert(self.b_girar, -1)

        # borrar
        self.b_borrar = ToolButton('gtk-delete')
        self.b_borrar.connect('clicked', self.borrar)
        self.b_borrar.set_tooltip(_('Delete'))
        self.b_borrar.show()
        edit_toolbar.insert(self.b_borrar, -1)

        time_button = ToolButton('stopwatch')
        time_button.set_tooltip(_('Set Image Duration in Slideshow (Seconds)'))
        edit_toolbar.insert(time_button, -1)
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

    def set_buttons_sensitive(self, sensitive):
        self._globes_menu.set_sensitive(sensitive)
        self.add_photo.set_sensitive(sensitive)
        self.b_borrar.set_sensitive(sensitive)
        self.b_girar.set_sensitive(sensitive)
        self._lines_menu.set_sensitive(sensitive)

    def __time_button_popup_cb(self, palette):
        self._time_spin.props.value = \
            self._page.get_active_box().slideshow_duration

    def __time_spin_changed_cb(self, button):
        self._page.get_active_box().slideshow_duration = \
            self._time_spin.props.value

    def __activate_add_line_cb(self, widget, image_name):
        active_box = self._page.get_active_box()
        active_box.add_imagen("icons/" + image_name + ".svg", 60, 60)

    def __activate_add_globe_cb(self, widget, globe):
        selected_font_name = self._activity.page.selected_font_name

        if globe == 'globe':
            self._page.get_active_box().add_globo(
                60, 60, font_name=selected_font_name)

        if globe == 'think':
            self._page.get_active_box().add_nube(
                60, 60, font_name=selected_font_name)

        if globe == 'whisper':
            self._page.get_active_box().add_globo(
                60, 60, gmodo="despacio", font_name=selected_font_name)

        if globe == 'exclamation':
            self._page.get_active_box().add_grito(
                60, 60, font_name=selected_font_name)

        if globe == 'box':
            self._page.get_active_box().add_rectangulo(
                60, 60, font_name=selected_font_name)

    def __add_photo_clicked_cb(self, button):
            self.add_image()

    def girar(self, boton):
        #veo cual es el globo seleccionado y o giro
        box = self._page.get_active_box()
        if box.get_globo_activo() is not None:
            globe = box.get_globo_activo()
            if globe.girar():
                box.redraw()

    def borrar(self, boton):
        box = self._page.get_active_box()
        if box.get_globo_activo() is not None:
            # Do no remove the title globe
            if box.get_globo_activo() == box.title_globe:
                return

            box.globos.remove(box.get_globo_activo())
            box.set_globo_activo(None)
            box.redraw()
        else:
            # Borrar un box es mas complicado
            pos_box = self._page.boxs.index(box)
            if (len(self._page.boxs) > pos_box):
                for i in range(pos_box, len(self._page.boxs) - 1):
                    box1 = self._page.boxs[i]
                    box2 = self._page.boxs[i + 1]
                    box1.image = None
                    box1.image_name = box2.image_name
                    box1.globos = []
                    box1.globos.extend(box2.globos)
                    box1.redraw()
            last_box = self._page.boxs[-1]
            last_box.image = None
            last_box.image_name = ""
            last_box.globos = []
            last_box.redraw()
            self._page.boxs.pop()

    def add_image(self):
        try:
            chooser = ObjectChooser(self._activity, what_filter='Image',
                                    filter_type=FILTER_TYPE_GENERIC_MIME,
                                    show_preview=True)
        except:
            # for compatibility with older versions
            chooser = ObjectChooser(self._activity, what_filter='Image')

        try:
            result = chooser.run()
            if result == Gtk.ResponseType.ACCEPT:
                logging.error('ObjectChooser: %r' %
                              chooser.get_selected_object())
                jobject = chooser.get_selected_object()
                if jobject and jobject.file_path:
                    logging.error("imagen seleccionada: %s",
                                  jobject.file_path)
                    tempfile_name = \
                        os.path.join(self._activity.get_activity_root(),
                                     'instance', 'tmp%i' % time.time())
                    os.link(jobject.file_path, tempfile_name)
                    logging.error("tempfile_name: %s", tempfile_name)
                    self._page.add_box_from_journal_image(tempfile_name)
        finally:
            chooser.destroy()
            del chooser


class TextToolbar(Gtk.Toolbar):

    def __init__(self, page):
        self._colorseldlg = None

        Gtk.Toolbar.__init__(self)

        self._page = page
        page._text_toolbar = self

        self._bold = ToggleToolButton('format-text-bold')
        self._bold.set_tooltip(_('Bold'))
        self._bold_id = self._bold.connect('clicked', self._bold_cb)
        self.insert(self._bold, -1)

        self._italic = ToggleToolButton('format-text-italic')
        self._italic.set_tooltip(_('Italic'))
        self._italic_id = self._italic.connect('clicked', self._italic_cb)
        self.insert(self._italic, -1)

        """
        self._underline = ToggleToolButton('format-text-underline')
        self._underline.set_tooltip(_('Underline'))
        self._underline_id = self._underline.connect('clicked',
                self._underline_cb)
        self.insert(self._underline, -1)
        self._underline.show()
        """

        self._text_color = TextButtonColor(page)
        self._text_color.set_title(_('Text Color'))
        item = Gtk.ToolItem()
        item.add(self._text_color)
        self.insert(item, -1)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        self.insert(separator, -1)

        self._font_size_combo = FontSize()
        self._font_size_changed_id = self._font_size_combo.connect(
            'changed', self._font_size_changed_cb)
        self.insert(self._font_size_combo, -1)

        # font
        self._font_combo = FontComboBox()
        self._font_combo.set_font_name(globos.DEFAULT_FONT)
        self._fonts_changed_id = self._font_combo.connect(
            'changed', self._font_changed_cb)
        self.insert(ToolComboBox(self._font_combo), -1)

        self.show_all()

    def get_text_selected_handler(self):
        return self._text_selected_handler

    def _add_widget(self, widget, expand=False):
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(expand)
        tool_item.add(widget)
        widget.show()
        self.insert(tool_item, -1)
        tool_item.show()

    def _bold_cb(self, button):
        globo_activo = self._page.get_globo_activo()
        if globo_activo is not None and globo_activo.texto is not None:
            globo_activo.texto.bold = not globo_activo.texto.bold
            self._page.get_active_box().redraw()

    def _italic_cb(self, button):
        globo_activo = self._page.get_globo_activo()
        if globo_activo is not None and globo_activo.texto is not None:
            globo_activo.texto.italic = not globo_activo.texto.italic
            self._page.get_active_box().redraw()

    # para la version 0.82
    def _text_color_cb(self, button):
        globo_activo = self._page.get_globo_activo()
        if globo_activo is not None and globo_activo.texto is not None:
            color = self._text_color.get_color()
            texto = globo_activo.texto
            texto.color = (color.red, color.green, color.blue)
            self._page.get_active_box().redraw()

    def _font_size_changed_cb(self, widget):
        size = widget.get_font_size()
        logger.debug('Setting font size: %d', size)
        globo_activo = self._page.get_globo_activo()
        if globo_activo is not None and globo_activo.texto is not None:
            globo_activo.texto.font_size = size
            self._page.get_active_box().redraw()

    def _font_changed_cb(self, widget):
        font_name = widget.get_font_name()
        logger.debug('Setting font name: %s', font_name)
        globo_activo = self._page.get_globo_activo()
        if globo_activo is not None and globo_activo.texto is not None:
            globo_activo.texto.font_type = font_name
            self._page.selected_font_name = font_name
            self._page.get_active_box().redraw()

    """
    Estos son los metodos para setear los contrles de la barra en base a el
    texto del globo como el globo va a tener un solo font seleccionado, voy
    a hacer un solo metodo
    """
    def setToggleButtonState(self, button, b, id):
        button.handler_block(id)
        button.set_active(b)
        button.handler_unblock(id)

    def setToolbarState(self, globeText):
        # seteo bold
        self.setToggleButtonState(self._bold, globeText.bold, self._bold_id)
        # seteo italic
        self.setToggleButtonState(self._italic, globeText.italic,
                                  self._italic_id)
        # color
        self._text_color.set_color(Gdk.Color(*globeText.color))
        # font size
        logging.error('Setting font size from globe %s %s',
                      globeText.font_size, globeText.font_size.__class__)
        self._font_size_combo.handler_block(self._font_size_changed_id)
        self._font_size_combo.set_font_size(int(globeText.font_size))
        self._font_size_combo.handler_unblock(self._font_size_changed_id)

        # font seleccionada
        self._font_combo.handler_block(self._fonts_changed_id)
        self._font_combo.set_font_name(globeText.font_type)
        self._page.selected_font_name = globeText.font_type
        self._font_combo.handler_unblock(self._fonts_changed_id)
