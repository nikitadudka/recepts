"""Find the photograph boundaries in a generated 4x4 sheet without altering pixels."""
from statistics import median
from PIL import Image, ImageChops


def gradients(image, horizontal):
    width,height=image.size
    if horizontal:
        delta=ImageChops.difference(image.crop((0,1,width,height)),image.crop((0,0,width,height-1)))
        return list(delta.convert('L').resize((1,height-1),Image.Resampling.BOX).tobytes())
    delta=ImageChops.difference(image.crop((1,0,width,height)),image.crop((0,0,width-1,height)))
    return list(delta.convert('L').resize((width-1,1),Image.Resampling.BOX).tobytes())


def seam(values, expected, radius):
    low=max(1,round(expected-radius));high=min(len(values),round(expected+radius))
    candidates=range(low,high+1)
    peak=max(candidates,key=lambda point:values[point-1])
    baseline=median(values[low-1:high])
    return peak if values[peak-1]>=max(18,baseline*2.2) else round(expected)


def photo_rectangles(image):
    image=image.convert('RGB');width,height=image.size
    horizontal=gradients(image,True);vertical=gradients(image,False)
    rows=[0]+[seam(horizontal,height*n/4,height*.09) for n in range(1,4)]+[height]
    columns=[0]+[seam(vertical,width*n/4,width*.05) for n in range(1,4)]+[width]
    rectangles=[]
    for row in range(4):
        band=image.crop((0,rows[row]+2,width,rows[row+1]-2))
        local=gradients(band,False)
        boundaries=[0]+[seam(local,columns[n],14) for n in range(1,4)]+[width]
        for column in range(4):
            strip=image.crop((boundaries[column]+2,0,boundaries[column+1]-2,height))
            local_rows=gradients(strip,True)
            top=seam(local_rows,rows[row],10) if row else 0
            bottom=seam(local_rows,rows[row+1],10) if row<3 else height
            # A small inset excludes the seam itself and compression around it.
            x=boundaries[column]+2;y=top+2
            rectangles.append({'x':x,'y':y,'width':boundaries[column+1]-2-x,'height':bottom-2-y})
    return rectangles
