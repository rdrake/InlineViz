from PIL import Image, ImageDraw, ImageFont
from tesserocr import PyTessBaseAPI, PSM, RIL
from google_translate import *
import spacy
from generate_examples import *
import os
from CAIS import *
import random
import glob
import numpy as np
import cv2
from opacityConversion import *

class InlineViz:
    """ Inline Viz wrapper object that performs all algorithm functions and 
    interfaces an image into workable components """
    # Class Variables
    img_comp = None
    img_file = None
    nlp = spacy.load("en")

    def __init__(self, fname, _translate=False, _max_size=(1024,1024), _pixel_cut_width=5, _noise_threshold=25, _spread=0):
        """ Initialize a file to work with """
        self.max_size = _max_size
        self.img_file = Image.open(fname)
        self.img_file.thumbnail(self.max_size, Image.ANTIALIAS)
        self.img_width, self.img_height = self.img_file.convert("RGBA").size
        self.line_list = self.detectLines(fname)
        self.translate = _translate
        self.spread = _spread
        self.pixel_cut_width = _pixel_cut_width
        self.noise_threshold = _noise_threshold
        self.img_patches = []
        self.img_blocks = []
        self.ocr_text = []
        self.ocr_translated = []
        self.bounding_boxes = []

    def decompose(self):
        """ Use OCR to find bounding boxes of each line in document and dissect 
        into workable parts """
        with PyTessBaseAPI() as api:
            api.SetImage(self.img_file)
            # Interate over lines using OCR
            boxes = api.GetComponentImages(RIL.TEXTLINE, True)
            
            for i, (im, box, _, _) in enumerate(boxes):
                # im is a PIL image object
                # box is a dict with x, y, w and h keys
                api.SetRectangle(box['x'], box['y'], box['w'], box['h'])

                #this tracks all the places that the texture needs to be laid
                self.bounding_boxes.append(box)
                self.ocr_text.append(api.GetUTF8Text())

        if self.translate:
            self.translateText()

        self.generateExpandedPatches() # strip and expand line spaces
        self.cropImageBlocks() # slice original image into lines
        self.generateFullCompositeImage() # merge everything together

    def expandStrip(self, img_strip):
        """ Expand an image strip using pixel randomization and quilting """
        img_comp = [img_strip]
        for x in range(1, self.spread):
            img_block = self.randomizeStrip(img_strip)
            img_expand = self.mergeImageList(img_block, "horizontal")
            img_comp.append(img_expand)
        
        return self.mergeImageList(img_comp, "vertical")

    def translateText(self):
        """ Translate text that has been OCR'd from this image """
        for text in self.ocr_text:
            trans_text = g_translate(text)
            self.ocr_translated.append(trans_text)

    def generateFullCompositeImage(self):
        """ Merge image blocks with patches to generate complete composite image """
        # merge everything back together to a composite image
        for i in range(0, len(self.img_blocks)):
            if i == 0:
                self.img_comp = self.mergeImages(self.img_blocks[i], self.img_patches[i], "vertical")

            else:
                self.img_comp = self.mergeImages(self.img_comp,self.img_blocks[i],"vertical")
                
                if i != len(self.img_blocks):
                    self.img_comp = self.mergeImages(self.img_comp,self.img_patches[i],"vertical")

        self.img_comp.save(open('./image_processing/img_comp.jpg', 'w')) # testing

    def generateExpandedPatches(self):
        """ Crop space between lines using starting and ending co-ordinates 
        and then expand the strip based on spread """
        tmp = Image.new('RGBA', (self.img_width, self.img_height), (0,0,0,0))
        img = self.img_file.convert("RGBA")
        space_height = 5 # default max space height
        # Find minimum space height - use this for symmetry
        for idx, box in enumerate(self.bounding_boxes):
            if idx+1 == len(self.bounding_boxes):
                break
            new_space_height = (self.bounding_boxes[idx+1]['y']-1) - (box['y']+box['h']+1)
            if new_space_height < space_height and new_space_height > 0:
                space_height = new_space_height

        # Create the expanded patches
        for idx, box in enumerate(self.bounding_boxes):
            # Cut textures for expansion in paper backgrounds
            # Cut between current box and next box +/- a pixel for slack
            y_start = box['y']+box['h']+1
            y_end = y_start + space_height

            textureCrop = img.crop((0, y_start, self.img_width, y_end))
            img_strip = self.randomizeStrip(textureCrop)
            img_patch = self.mergeImageList(img_strip)
            # don't need to expand the last patch
            if idx != len(self.bounding_boxes)-1:
                img_patch = self.expandStrip(img_patch)

            self.img_patches.append(img_patch)

    def cropImageBlocks(self, pad_bottom=True):
        """ Crop blocks of image entities for recomposition with bottom padding """
        tmp = Image.new('RGBA', (self.img_width, self.img_height), (0,0,0,0))
        # This creates a composite image with the original image and the transparent overlay
        img = Image.alpha_composite(self.img_file.convert("RGBA"), tmp)
        width, height = img.size
        # iterate through the bounding boxes and crop them out accounting for the first and the last chop
        # to keep headers and footers
        for i, box in enumerate(self.bounding_boxes):
            y_end = box['y']+box['h']+1
            if i == 0:
                tmpImageCrop = img.crop((0, 0, width, y_end))
            elif i == len(self.bounding_boxes)-1:
                tmpImageCrop = img.crop((0, box['y']-1, width, height))
            else:
                if pad_bottom:
                    # use space between bounding boxes as padding
                    y_end = self.bounding_boxes[i+1]['y']-1
                tmpImageCrop = img.crop((0, box['y']-1, width, y_end))
            self.img_blocks.append(tmpImageCrop)

    #This merges two image files using PIL
    def mergeImages(self, image1, image2, orientation):
        """Merge two images into one, displayed above and below
        :param image1: PIL object
        :param image2: PIL object
        :return: the merged Image object
        """
        (width1, height1) = image1.size
        (width2, height2) = image2.size
        
        mask1 = image1.convert("RGBA")
        mask2 = image2.convert("RGBA")

        if orientation == "vertical":

            result_width = max(width1, width2)
            result_height = height1 + height2

            result = Image.new('RGB', (result_width, result_height))
            result.paste(image1, (0, 0), mask1)        
            result.paste(image2, (0, height1), mask2)

        elif orientation == "horizontal":     

            result_width = width1 + width2
            result_height = max(height1, height2)

            result = Image.new('RGB', (result_width, result_height))
            result.paste(image1, (0, 0), mask1)        
            result.paste(image2, (width1, 0), mask2)
        
        return result

    def mergeImageList(self, img_block, orientation="horizontal"):
        """ Iteratively merge a list of PIL image objects """
        compImage = None
        for i in range(0, len(img_block)):
            if len(img_block) > 1:
                if i == 0:
                    compImage = self.mergeImages(img_block[0],img_block[1],orientation)
                elif i > 1:
                    compImage = self.mergeImages(compImage, img_block[i],orientation)
            else:
                # nothing to merge
                compImage = img_block[i]

        return compImage

    def randomizeStrip(self, im):
        """ Return blocks of randomized pixels in a single strip """
        rgb_im = im.convert('RGB')
        imWidth, imHeight = im.size
        noise = True
        img_block = []
        cut_width = 0        
        for i in range(0,imWidth,self.pixel_cut_width):
            for t in self.line_list:
                if abs(t-i) <= self.noise_threshold:
                    noise = False

            z = []
            pixelList = []
            for y in range(imHeight):
                cut_width = 0                
                for x in range(self.pixel_cut_width):
                    if i+x == imWidth:
                        break
                    cut_width += 1
                    r, g, b = rgb_im.getpixel((i+x, y))
                    pixelList.append(tuple([r,g,b]))

            if cut_width == 0:
                continue

            #Create a new image from random pixel choices
            im2 = Image.new('RGB', (cut_width, imHeight))

            if noise:
                random.shuffle(pixelList)
                
            im2.putdata(pixelList)
            img_block.append(im2)

        return img_block

    def detectLines(self, fname):
        """ Use CV2 to estimate vertical line threshold for randomization """
        gray = cv2.imread(fname)
        edges = cv2.Canny(gray,50,150,apertureSize = 3)
        
        minLineLength=100
        lines = cv2.HoughLinesP(image=edges,rho=1,theta=np.pi/180, threshold=200,lines=np.array([]), minLineLength=minLineLength,maxLineGap=100)

        a,b,c = lines.shape
        lineLst =[]
        for i in range(a):

            if abs(lines[i][0][0] - lines[i][0][2]) == 0:
                lineLst.append(lines[i][0][0])

            cv2.line(gray, (lines[i][0][0], lines[i][0][1]), (lines[i][0][2], lines[i][0][3]), (0, 0, 255), 3, cv2.LINE_AA)

        return lineLst