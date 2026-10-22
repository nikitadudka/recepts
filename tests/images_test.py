"""Asset geometry checks; no generated food photos are modified."""
import sys
import unittest
from pathlib import Path
from PIL import Image,ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sheet_geometry import photo_rectangles


class ImageSheetTests(unittest.TestCase):
    def test_uneven_rows_and_columns_never_leak_a_neighboring_photo(self):
        image=Image.new('RGB',(1024,768))
        draw=ImageDraw.Draw(image)
        rows=[0,182,369,548,768];columns=[0,251,513,761,1024]
        colors=[]
        for row in range(4):
            for column in range(4):
                color=((row*71+column*39)%256,(column*83+row*29)%256,(row*47+column*67)%256)
                colors.append(color)
                draw.rectangle((columns[column],rows[row],columns[column+1]-1,rows[row+1]-1),fill=color)
        for color,rect in zip(colors,photo_rectangles(image)):
            crop=image.crop((rect['x'],rect['y'],rect['x']+rect['width'],rect['y']+rect['height']))
            self.assertGreater(rect['width'],200)
            self.assertGreater(rect['height'],150)
            self.assertEqual(crop.getcolors(),[(rect['width']*rect['height'],color)])


if __name__=='__main__':unittest.main(verbosity=2)
