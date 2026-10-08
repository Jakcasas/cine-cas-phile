"""Personal-use Mirella companion with original Latin glyphs and drawn accents.

Original font remains untouched; added geometric diacritics are project artwork.
"""
from pathlib import Path
import unicodedata
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'web/assets/fonts/mirella'


def main():
    font=TTFont(FOLDER/'Mirella.ttf');mapping=font.getBestCmap();order=font.getGlyphOrder()
    glyf=font['glyf'];metrics=font['hmtx'].metrics
    shapes={
        '\u0301':[(-53,0),(-35,0),(60,85),(33,85)],
        '\u0300':[(-60,85),(-33,85),(53,0),(35,0)],
        '\u0302':[(-85,0),(-66,0),(0,70),(66,0),(85,0),(12,88),(-12,88)],
        '\u0303':[(-85,22),(-67,39),(-42,44),(20,17),(51,15),(78,38),(87,27),(61,1),(30,0),(-31,26),(-55,26),(-77,10)],
        '\u0323':[(-12,0),(12,0),(12,24),(-12,24)],
    }
    mark_names={}
    for mark in [*shapes,'\u0306','\u031b']:
        name='ccpMark'+format(ord(mark),'04X');pen=TTGlyphPen(None)
        if mark in shapes:
            points=shapes[mark];pen.moveTo(points[0])
            for point in points[1:]:pen.lineTo(point)
            pen.closePath()
        elif mark=='\u0306':
            pen.moveTo((-78,72));pen.qCurveTo((-70,0),(0,0));pen.qCurveTo((70,0),(78,72));pen.lineTo((63,72));pen.qCurveTo((58,20),(0,20));pen.qCurveTo((-58,20),(-63,72));pen.closePath()
        else:
            pen.moveTo((-12,0));pen.qCurveTo((60,5),(58,88));pen.lineTo((35,88));pen.qCurveTo((44,20),(-12,18));pen.closePath()
        glyf[name]=pen.glyph();metrics[name]=(0,0);order.append(name);mark_names[mark]=name
    font.setGlyphOrder(order)
    added=0
    for cp in range(0x00C0,0x1F00):
        if cp in mapping:continue
        decomposed=unicodedata.normalize('NFD',chr(cp))
        if len(decomposed)<2 or ord(decomposed[0]) not in mapping or any(m not in mark_names for m in decomposed[1:]):continue
        base=mapping[ord(decomposed[0])];g=glyf[base]
        if not hasattr(g,'yMax'):continue
        center=round((g.xMin+g.xMax)/2);top=g.yMax+35
        pen=TTGlyphPen(font.getGlyphSet());pen.addComponent(base,(1,0,0,1,0,0))
        for mark in decomposed[1:]:
            if mark=='\u0323':x,y=center,-110
            elif mark=='\u031b':x,y=g.xMax-15,g.yMax-24
            else:
                x,y=center,top;top+=120
            pen.addComponent(mark_names[mark],(1,0,0,1,x,y))
        name='ccpUni'+format(cp,'04X');glyf[name]=pen.glyph();metrics[name]=metrics[base];order.append(name)
        for table in font['cmap'].tables:
            if table.isUnicode() and table.format in {4,12}:table.cmap[cp]=name
        mapping[cp]=name;added+=1;font.setGlyphOrder(order)
    for char,base in [('Đ','D'),('đ','d')]:
        cp=ord(char);base=mapping[ord(base)];g=glyf[base]
        bar='ccpBar'+str(cp);pen=TTGlyphPen(None);y=round(g.yMax*.54)
        pen.moveTo((g.xMin-8,y));pen.lineTo((g.xMax*.7,y));pen.lineTo((g.xMax*.7,y+19));pen.lineTo((g.xMin-8,y+19));pen.closePath()
        glyf[bar]=pen.glyph();metrics[bar]=(0,0);order.append(bar);font.setGlyphOrder(order)
        pen=TTGlyphPen(font.getGlyphSet());pen.addComponent(base,(1,0,0,1,0,0));pen.addComponent(bar,(1,0,0,1,0,0))
        name='ccpUni'+format(cp,'04X');glyf[name]=pen.glyph();metrics[name]=metrics[base];order.append(name)
        for table in font['cmap'].tables:
            if table.isUnicode() and table.format in {4,12}:table.cmap[cp]=name
        font.setGlyphOrder(order)
    for record in font['name'].names:
        if record.nameID in {1,4,6}:
            text='Mirella CCP Personal' if record.nameID!=6 else 'MirellaCCP-Personal'
            record.string=text.encode(record.getEncoding())
    font['hhea'].ascent=1050;font['hhea'].descent=-250;font['hhea'].lineGap=0
    os2=font['OS/2'];os2.sTypoAscender=1050;os2.sTypoDescender=-250;os2.sTypoLineGap=0;os2.usWinAscent=1050;os2.usWinDescent=250
    os2.fsSelection|=1<<7
    final_order=list(glyf.glyphs)
    glyf.setGlyphOrder(final_order);font.setGlyphOrder(final_order)
    font.save(FOLDER/'Mirella-CCP-Personal.ttf')
    print(f'Added {added+2} accented characters; original font retained.')


if __name__=='__main__':main()
