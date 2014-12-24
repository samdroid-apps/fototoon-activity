import os
import json
import logging
import zipfile

from sugar3.activity import activity

from toolbar import DEFAULT_TIME
import globos


class PageData:

    def __init__(self):
        self.boxs = []


class BoxData:

    def __init__(self):
        self.globos = []
        self.image_name = None


class Persistence:

    def write(self, file_name, page):

        """
        Persitencia:
        Cuadro_titulo, globos[]
        Lista de cuadros, imagen de fondo, globos[]
        por cada globo: tipo, posicion (x,y), ancho, alto,
        direccion, pos_flecha (x,y), texto,font, tamanio, color
        """
        instance_path = os.path.join(activity.get_activity_root(), 'instance')

        # Copio los datos de Page en PageData

        pageData = {}
        pageData['version'] = '1'
        pageData['boxs'] = []
        for box in page.boxs:
            boxData = {}
            boxData['img_x'] = box.img_x
            boxData['img_y'] = box.img_y
            boxData['img_w'] = box.img_w
            boxData['img_h'] = box.img_h
            boxData['image_name'] = box.image_name
            boxData['slideshow_duration'] = box.slideshow_duration
            boxData['globes'] = []
            for globo in box.globos:
                globoData = {}
                globoData['title_globe'] = (globo == box.title_globe)
                logging.debug('Saving %s', globo.globe_type)
                globoData['globe_type'] = globo.globe_type
                globoData['radio'] = globo.radio
                globoData['width'], globoData['height'] = \
                    globo.ancho, globo.alto
                if (globo.__class__ != globos.Rectangulo):
                    globoData['point_0'] = globo.punto[0]
                    globoData['point_1'] = globo.punto[1]
                globoData['direction'] = globo.direccion
                if (globo.__class__ == globos.Globo):
                    globoData['mode'] = globo.modo
                if (globo.__class__ == globos.Imagen):
                    globoData['image_name'] = globo.image_name
                globoData['x'], globoData['y'] = globo.x, globo.y

                if globo.texto is not None:
                    globoData['text_width'] = globo.texto.ancho
                    globoData['text_height'] = globo.texto.alto
                    globoData['text_text'] = globo.texto.text
                    globoData['text_color'] = globo.texto.color

                    globoData['text_font_description'] = \
                        globo.texto.font_description

                boxData['globes'].append(globoData)
            pageData['boxs'].append(boxData)

        logging.debug('pageData %s', pageData)

        data_file_name = 'data.json'
        f = open(os.path.join(instance_path, data_file_name), 'w')
        try:
            json.dump(pageData, f)
        finally:
            f.close()

        logging.debug('file_name %s', file_name)

        z = zipfile.ZipFile(file_name, 'w')
        z.write(os.path.join(instance_path, data_file_name).encode(
            'ascii', 'ignore'), data_file_name.encode('ascii', 'ignore'))
        for box in page.boxs:
            if (box.image_name != ''):
                z.write(os.path.join(
                    instance_path,
                    box.image_name).encode('ascii', 'ignore'),
                    box.image_name.encode('ascii', 'ignore'))
        z.close()

    def read(self, file_name, page):

        instance_path = os.path.join(activity.get_activity_root(), 'instance')
        z = zipfile.ZipFile(file_name, 'r')
        for file_name in z.namelist():
            if (file_name != './'):
                try:
                    logging.debug('extracting %s', file_name)
                    # la version de python en las xo no permite hacer
                    # extract :(
                    # z.extract(file_name,instance_path)
                    data = z.read(file_name)
                    fout = open(os.path.join(instance_path, file_name), 'w')
                    fout.write(data)
                    fout.close()
                except:
                    logging.error('Error extracting %s', file_name)
        z.close()
        data_file_name = 'data.json'

        pageData = PageData()
        f = open(os.path.join(instance_path, data_file_name), 'r')
        try:
            pageData = json.load(f)
        finally:
            f.close()

        primero = True
        for boxData in pageData['boxs']:
            if not primero:
                # el primero ya esta creado
                # para compatibilidad de versiones anteriores,
                # verificamos si existe o no las nuevas propiedades
                # en el archivo de persistencia
                if 'img_x' in boxData:
                    page.add_box_from_journal_image(
                        boxData['image_name'], boxData['img_x'],
                        boxData['img_y'], boxData['img_w'], boxData['img_h'])
                else:
                    page.add_box_from_journal_image(boxData['image_name'])
            primero = False
            box = page.get_active_box()
            for globoData in boxData['globes']:
                globo_x, globo_y = globoData['x'], globoData['y']
                globo_modo = None
                if ('mode' in globoData):
                    globo_modo = globoData['mode']
                globo_direccion = globoData['direction']

                tipo_globo = globoData['globe_type']
                globo = None
                if (tipo_globo == 'GLOBE'):
                    globo = globos.Globo(box, x=globo_x, y=globo_y,
                                         modo=globo_modo,
                                         direccion=globo_direccion)
                elif (tipo_globo == 'CLOUD'):
                    globo = globos.Nube(box, x=globo_x, y=globo_y,
                                        direccion=globo_direccion)
                elif (tipo_globo == 'EXCLAMATION'):
                    globo = globos.Grito(box, x=globo_x, y=globo_y,
                                         direccion=globo_direccion)
                elif (tipo_globo == 'RECTANGLE'):
                    globo = globos.Rectangulo(box, x=globo_x, y=globo_y)
                elif (tipo_globo == 'IMAGE'):
                    image_name = globoData['image_name']
                    globo = globos.Imagen(box, image_name,
                                          x=globo_x, y=globo_y)
                    globo.direccion = globo_direccion

                if globo is not None:
                    globo.radio = globoData['radio']
                    globo.ancho, globo.alto = globoData['width'], \
                        globoData['height']

                    if (tipo_globo != 'RECTANGLE'):
                        globo.punto = [globoData['point_0'],
                                       globoData['point_1']]

                    globo.x, globo.y = globoData['x'], globoData['y']

                    if (tipo_globo != 'IMAGE'):
                        globo.texto.ancho = globoData['text_width']
                        globo.texto.alto = globoData['text_height']
                        globo.texto.color = globoData['text_color']
                        globo.texto.set_font_description(
                            globoData['text_font_description'])
                        globo.texto.set_text(globoData['text_text'])
                    box.globos.append(globo)

                    if globoData['title_globe']:
                        box.title_globe = globo

            if 'slideshow_duration' in boxData:
                box.slideshow_duration = boxData['slideshow_duration']
            #box.redraw()
